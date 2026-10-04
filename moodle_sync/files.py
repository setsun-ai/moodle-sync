"""
Step 1: find files in your courses and download the ones you don't have yet.

Layout:  <DOWNLOAD_DIR>/[<Semester N>/]<Course>/<Category>/[<folder>/<subfolders>/]<file>
Category is one of Lectures / Exercises / Labs / Projects / Other materials
(Polish names with LANGUAGE=pl), guessed from section, module and file names.
With a study plan (STUDY_PLAN_URL, see studyplan.py) courses go into semester
folders and are named after the subject in the plan.

How "new" is detected: every file gets a stable id (see stable_id); the ids of
downloaded files are remembered in state.json -> "downloaded". Anything not
there is new. When a teacher replaces a file, Moodle changes the revision
number in its URL, so it gets a new id - and the same *logical* key (course +
module + path + name), so the new version overwrites the old one in place
instead of creating "file (2).pdf". "(2)", "(3)" are only used for genuinely
different files that would end up at the same path.

Changing category rules or course names (courses.json) re-plans all paths and
moves already downloaded files - locally right away, and on the cloud drive
through the "remote_moves" queue processed by the upload step.
"""

import json
import os
import re
import time
from pathlib import Path

import requests

from . import config, moodle, state as state_mod, studyplan
from .i18n import t
from .notify import bullet_list, notify
from .textutil import clean_text, normalize_for_matching, pick_language, sanitize_component

# Tracked: everything except Moodle-generated pages (.html) and extension-less
# artefacts. PDF, PPTX, DOCX, XLSX, ZIP, PY, IPYNB, CSV... all go through.
EXCLUDED_EXTENSIONS = {".html", ""}

CHUNK_SIZE = 64 * 1024

# Built-in category rules, checked in order - first match wins - on text
# without diacritics, lower case. Keywords in Polish and English.
# "(?<![a-z])lab" matches "laboratorium", "lab2", "_lab", but not "syllabus".
CATEGORY_RULES = [
    ("labs", r"(?<![a-z])lab"),
    ("projects", r"projekt|project"),
    ("lectures", r"wyklad|lecture|slajd|slides"),
    ("exercises", r"cwicz|exercise|tutorial|seminar|(?<![a-z])class(?![a-z])"),
]
FOLDER_NAMES = {
    "pl": {"labs": "Laboratoria", "projects": "Projekty", "lectures": "Wyklady",
           "exercises": "Cwiczenia", "other": "Inne materialy"},
    "en": {"labs": "Labs", "projects": "Projects", "lectures": "Lectures",
           "exercises": "Exercises", "other": "Other materials"},
}


# --- scanning -----------------------------------------------------------------------------

def stable_id(content: dict) -> str:
    """
    Dedup key of a file. contenthash (SHA1 of the content) is ideal, but many
    servers don't return it in core_course_get_contents; fileurl contains a
    unique file path incl. revision; the metadata combo is the last resort.
    """
    if content.get("contenthash"):
        return f"hash:{content['contenthash']}"
    if content.get("fileurl"):
        return f"url:{content['fileurl']}"
    return f"meta:{content.get('filename')}:{content.get('filesize')}:{content.get('timemodified')}"


def iter_course_files(course_contents: list, course: dict):
    """Flatten sections -> modules -> files into simple records."""
    for section in course_contents:
        for module in section.get("modules", []):
            for content in module.get("contents", []):
                if content.get("type") != "file":
                    continue
                filename = content.get("filename", "")
                if Path(filename).suffix.lower() in EXCLUDED_EXTENSIONS:
                    continue
                yield {
                    "id": stable_id(content),
                    "course_id": course["id"],
                    "course_name": course["fullname"],
                    "section_name": section.get("name", ""),
                    "module_id": module.get("id"),
                    "modname": module.get("modname", ""),
                    "module_name": module.get("name", ""),
                    "filepath": content.get("filepath", "/"),  # subfolder inside mod_folder
                    "filename": filename,
                    "fileurl": content.get("fileurl", ""),
                    "filesize": content.get("filesize", 0),
                    "timemodified": content.get("timemodified", 0),
                }


# "modname:instance" -> the activity's page; the calendar step uses it for "join" links
MODULE_URLS: dict = {}


def collect_files(courses: list) -> list:
    """All tracked files from all courses, without duplicates (by id)."""
    files = {}
    for course in courses:
        try:
            contents = moodle.course_contents(course["id"])
        except moodle.MoodleError as e:
            print(t("course_skipped", course=course["fullname"], error=e))
            continue
        for section in contents:
            for module in section.get("modules", []):
                if module.get("url") and module.get("instance"):
                    MODULE_URLS[f"{module.get('modname')}:{module['instance']}"] = module["url"]
        for f in iter_course_files(contents, course):
            files.setdefault(f["id"], f)
    return list(files.values())


# --- naming and categories -------------------------------------------------------------------

def _override(cfg: dict, section: str, course_name: str):
    name = pick_language(course_name, config.moodle_content_language()).casefold()
    for fragment, value in cfg.get(section, {}).items():
        if fragment.casefold() in name:
            return value
    return None


def course_display_name(course_name: str, cfg: dict | None = None) -> str:
    """Course folder / calendar label: from courses.json -> "names", or from Moodle."""
    cfg = config.load_courses_config() if cfg is None else cfg
    return _override(cfg, "names", course_name) or clean_text(course_name, config.moodle_content_language())


def folder_name(category: str) -> str:
    """Category key ('labs') -> folder name in the current language; other values pass through."""
    return FOLDER_NAMES[config.language()].get(category, category)


def categorize(f: dict, cfg: dict | None = None) -> str:
    """
    Folder name of the file's category. Sources are checked from the most
    reliable: teachers usually organise SECTIONS by type of class ("Lab
    sessions", "WYKŁADY"), so the section wins. Only if nothing matches there
    ("General", "New section") we look at the module name, then at the path
    and file name. Custom rules from courses.json go before the built-in ones.
    """
    cfg = config.load_courses_config() if cfg is None else cfg
    rules = [(r["folder"], r["pattern"]) for r in cfg.get("category_rules", [])] + CATEGORY_RULES
    lang = config.moodle_content_language()
    for text in (f["section_name"], f["module_name"], f"{f['filepath']} {f['filename']}"):
        normalized = normalize_for_matching(text, lang)
        for category, pattern in rules:
            if re.search(pattern, normalized):
                return folder_name(category)
    return folder_name(_override(cfg, "default_category", f["course_name"]) or "other")


def logical_key(f: dict) -> str:
    """File identity independent of revision - see the module docstring."""
    return f"{f['course_id']}:{f['module_id']}:{f['filepath']}{f['filename']}"


def course_folder(f: dict, cfg: dict) -> str:
    """Folder of a course: courses.json "names", else the subject name from the study plan, else Moodle's name."""
    return _override(cfg, "names", f["course_name"]) or f.get("plan_subject") or course_display_name(f["course_name"], cfg)


def apply_layout(files: list, courses: list, cfg: dict, state: dict) -> None:
    """Add the study plan's semester folder and subject name to every file record (no-op without a plan)."""
    if not (studyplan.plan_url() or studyplan.study_start()):
        return
    plan = studyplan.load_plan(state)
    layout = studyplan.course_layout(courses, cfg, plan, state)
    splits = studyplan.course_splits(courses, plan, state, cfg)
    for f in files:
        if f["course_id"] in splits:  # one course for several semesters: by the file's date
            _, f["semester_folder"], f["plan_subject"] = studyplan.pick_by_date(
                splits[f["course_id"]], f.get("timemodified") or 0, plan)
        else:
            f["semester_folder"], f["plan_subject"] = layout.get(f["course_id"], (None, None))


# Bump when the code changes where files go, so the next run moves them without the fuse.
LAYOUT_VERSION = 6


def layout_signature(cfg: dict, state: dict) -> str:
    """
    What you decide about the layout on purpose: courses.json, your assignments,
    electives and folder names in the bot, and this code's layout version. A change of
    THESE explains a mass move; a change of .env (e.g. LANGUAGE lost in a glued line)
    does not - that's what the fuse is for.
    """
    import hashlib

    picked = {k: state.get(k) for k in ("course_map", "electives", "folder_names")}
    return hashlib.sha1(json.dumps([LAYOUT_VERSION, cfg, picked], sort_keys=True, default=str).encode()).hexdigest()


def relative_path(f: dict, cfg: dict | None = None) -> Path:
    cfg = config.load_courses_config() if cfg is None else cfg
    lang = config.moodle_content_language()
    # Sections are flattened: the category already carries the main
    # information, and names like "New section" would only clutter the tree.
    parts = [sanitize_component(f["semester_folder"], lang=lang)] if f.get("semester_folder") else []
    parts += [
        sanitize_component(course_folder(f, cfg), "Course", lang),
        categorize(f, cfg),
    ]
    # Files of a "folder" module go into a subfolder named after the module,
    # keeping its internal structure (filepath, e.g. "/Demos/").
    if f["modname"] == "folder":
        parts.append(sanitize_component(f["module_name"], "Folder", lang))
        parts += [sanitize_component(p, lang=lang) for p in f["filepath"].split("/") if p]
    parts.append(sanitize_component(f["filename"], "file", lang))
    return Path(*parts)


def resolve_collision(rel: Path, key: str, owners: dict) -> Path:
    """
    If the path already belongs to a DIFFERENT logical file, add " (2)" etc.
    Compared case-insensitively, because NTFS/macOS don't distinguish
    "Lecture.pdf" from "lecture.pdf" - Linux does, but we want the same tree
    everywhere.
    """
    candidate, n = rel, 2
    while owners.get(candidate.as_posix().casefold(), key) != key:
        candidate = rel.with_name(f"{rel.stem} ({n}){rel.suffix}")
        n += 1
    return candidate


def plan_paths(files: list, downloaded: dict, cfg: dict | None = None) -> dict:
    """
    Target path of EVERY current file (id -> Path), computed from scratch on
    every run - so changing the rules just produces a different plan, and the
    difference against state.json is the list of moves. Already downloaded
    files go first, so a new file with a clashing name gets "(2)" instead of
    pushing an existing one to a different path.
    """
    cfg = config.load_courses_config() if cfg is None else cfg
    ordered = sorted(files, key=lambda f: (
        f["id"] not in downloaded,
        f["course_name"], f["section_name"], str(f["module_id"]),
        f["filepath"], f["filename"], f["id"],
    ))
    owners, plan = {}, {}
    for f in ordered:
        key = logical_key(f)
        rel = resolve_collision(relative_path(f, cfg), key, owners)
        owners[rel.as_posix().casefold()] = key
        plan[f["id"]] = rel
    return plan


# --- moving after re-categorisation ---------------------------------------------------------

def _remove_empty_dirs(root: Path) -> None:
    for d in sorted((p for p in root.rglob("*") if p.is_dir()), key=lambda p: len(p.parts), reverse=True):
        try:
            d.rmdir()  # only succeeds for empty directories
        except OSError:
            pass


def planned_moves(files: list, plan: dict, downloaded: dict) -> dict:
    """Downloaded files whose planned path differs from where they are: {old path: new path}."""
    moves = {}
    for f in files:
        entry = downloaded.get(f["id"])
        if entry and entry.get("path") and entry["path"] != plan[f["id"]].as_posix():
            moves[entry["path"]] = plan[f["id"]].as_posix()
    return moves


# Safety fuse: a handful of moves is a normal re-categorisation; moving a large
# part of the archive at once almost always means a configuration accident
# (e.g. LANGUAGE lost in a broken .env line -> every folder renamed to English).
# Then nothing is moved until the user confirms with --reorganize.
MASS_MOVE_MIN = 20
MASS_MOVE_SHARE = 0.10


def is_mass_move(n_moves: int, downloaded: dict) -> bool:
    tracked = sum(1 for e in downloaded.values() if e.get("path"))
    return n_moves > max(MASS_MOVE_MIN, int(tracked * MASS_MOVE_SHARE))


def relocate(moves: dict, downloaded: dict, state: dict, dry_run: bool) -> int:
    """
    Move downloaded files to their new planned paths. Two phases (everything
    to temporary names first, then to the targets), so swapping two files'
    places can't overwrite anything.
    """
    if not moves:
        return 0

    print(t("files_relocating", n=len(moves)))
    for old, new in moves.items():
        print(f"    {old}\n -> {new}")
    if dry_run:
        return len(moves)

    root = config.download_dir()
    staged = []
    for old, new in moves.items():
        src = root / old
        if src.exists():  # may be missing locally (e.g. KEEP_LOCAL=0)
            tmp = src.with_name(src.name + ".relocating")
            os.replace(src, tmp)
            staged.append((tmp, root / new))
    for tmp, dest in staged:
        dest.parent.mkdir(parents=True, exist_ok=True)
        os.replace(tmp, dest)  # os.replace keeps the modification time
    if root.exists():
        _remove_empty_dirs(root)

    for entry in downloaded.values():  # also older revisions pointing to the old path
        if entry.get("path") in moves:
            entry["path"] = moves[entry["path"]]
    state.setdefault("remote_moves", []).extend({"from": o, "to": n} for o, n in moves.items())
    state_mod.save(state)
    return len(moves)


# --- downloading ---------------------------------------------------------------------------------

def download_file(f: dict, dest: Path) -> int:
    """
    Stream into <file>.part and atomically rename on success - an interrupted
    transfer (Wi-Fi drop) never leaves a truncated file under the real name,
    which the upload step would then send to the cloud.
    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.name + ".part")
    try:
        with moodle.session().get(moodle.file_url_with_token(f["fileurl"]), stream=True,
                                  timeout=(10, 120)) as resp:
            resp.raise_for_status()
            # With a bad token Moodle may answer HTTP 200 with a JSON error
            # instead of the file. But .ipynb, .json, .geojson are JSON too -
            # so we recognise the error by its keys, not by Content-Type alone.
            chunks = resp.iter_content(CHUNK_SIZE)
            if "application/json" in resp.headers.get("Content-Type", ""):
                body = resp.content
                chunks = [body]
                try:
                    err = json.loads(body)
                except ValueError:
                    err = None
                if isinstance(err, dict) and ("errorcode" in err or "exception" in err):
                    raise moodle.MoodleError(err.get("errorcode", "?"), err.get("error") or err.get("message", ""))
            written = 0
            with open(tmp, "wb") as fh:
                for chunk in chunks:
                    fh.write(chunk)
                    written += len(chunk)
        expected = f.get("filesize") or 0
        if expected and written != expected:
            raise RuntimeError(t("files_incomplete", got=written, expected=expected))
        os.replace(tmp, dest)
    finally:
        tmp.unlink(missing_ok=True)

    # mtime = time modified in Moodle. rclone compares size + mtime, so a file
    # downloaded again (e.g. after deleting state.json) is not uploaded again.
    if f.get("timemodified"):
        os.utime(dest, (f["timemodified"], f["timemodified"]))
    return written


def too_large(f: dict) -> bool:
    limit = config.max_file_mb()
    return bool(limit) and (f.get("filesize") or 0) > limit * 1024 * 1024


def is_pending(f: dict, downloaded: dict) -> bool:
    entry = downloaded.get(f["id"])
    if entry is None:
        return True
    # Skipped as too large - retry if the limit has been raised since.
    return entry.get("skipped") == "too_large" and not too_large(f)


def run(dry_run: bool = False, limit: int = 0, baseline: bool = False, reorganize: bool = False) -> int:
    courses = moodle.my_courses()
    files = collect_files(courses)
    cfg = config.load_courses_config()

    state = state_mod.load()
    downloaded = state.setdefault("downloaded", {})
    try:
        apply_layout(files, courses, cfg, state)
    except RuntimeError as e:  # plan configured but unavailable: don't scatter files into the old layout
        print(t("error", error=e))
        return 1
    state_mod.save(state)  # keeps the cached study plan

    plan = plan_paths(files, downloaded, cfg)
    moves = planned_moves(files, plan, downloaded)
    signature = layout_signature(cfg, state)
    # a deliberate change (an update, /assign, /electives, courses.json) moves files without the fuse
    intended = state.get("layout_sig") != signature
    if is_mass_move(len(moves), downloaded) and not reorganize and not intended:
        print(t("files_mass_move", n=len(moves)))
        for old, new in list(moves.items())[:5]:
            print(f"    {old}\n -> {new}")
        if dry_run:
            print("\n" + t("dry_run_note"))
            return 0
        return 1  # nothing downloaded either - new files would land in the new layout
    relocate(moves, downloaded, state, dry_run)
    if not dry_run:
        if moves and intended:
            notify("files", t("files_relocated_title", n=len(moves)), t("files_relocated_body"))
        state["layout_sig"] = signature
        state["module_urls"] = MODULE_URLS
        state_mod.save(state)

    pending = sorted((f for f in files if is_pending(f, downloaded)), key=lambda f: plan[f["id"]].as_posix())

    if baseline:
        for f in pending:
            downloaded[f["id"]] = {"path": None, "key": logical_key(f), "skipped": "baseline"}
        state_mod.save(state)
        print(t("files_baseline", n=len(pending)))
        return 0

    if limit:
        pending = pending[:limit]
    if not pending:
        print(t("files_none"))
        return 0

    total_mb = sum(f.get("filesize") or 0 for f in pending) / 1024 / 1024
    print(t("files_to_download", n=len(pending), mb=total_mb, dir=config.download_dir()) + "\n")

    root = config.download_dir()
    failed, done = 0, []
    for i, f in enumerate(pending, 1):
        rel = plan[f["id"]]
        print(f"[{i}/{len(pending)}] {rel.as_posix()}  ({(f.get('filesize') or 0) / 1024:.0f} KB)")

        if too_large(f):
            print("    " + t("files_too_large", mb=config.max_file_mb()))
            if not dry_run:
                downloaded[f["id"]] = {"path": None, "key": logical_key(f), "skipped": "too_large"}
                state_mod.save(state)
            continue
        if dry_run:
            continue

        try:
            download_file(f, root / rel)
        except (requests.RequestException, RuntimeError, OSError) as e:
            failed += 1
            print("    " + t("error", error=moodle.redact(str(e))))
            continue

        downloaded[f["id"]] = {"path": rel.as_posix(), "key": logical_key(f), "ts": int(time.time())}
        done.append(rel)
        state_mod.save(state)  # after every file: an interrupted run won't start over

    if dry_run:
        print("\n" + t("dry_run_note"))
        return 0

    print("\n" + t("files_summary", ok=len(done), failed=failed))
    if done:
        notify("files", t("notify_files_title", n=len(done)),
               bullet_list([f"{rel.parts[0]}: {rel.name}" for rel in done]))
    return 1 if failed else 0


# --- preview (python -m moodle_sync courses) ---------------------------------------------------------

def preview() -> int:
    """Show how each course's files would be categorised - handy when editing courses.json."""
    courses = moodle.my_courses()
    cfg = config.load_courses_config()
    files = collect_files(courses)
    apply_layout(files, courses, cfg, state_mod.load())
    by_course: dict = {}
    for f in files:
        by_course.setdefault(f["course_name"], []).append(f)
    print(t("courses_header", n=len(courses), file=config.courses_file().name) + "\n")
    for course in courses:
        cf = by_course.get(course["fullname"], [])
        first = cf[0] if cf else {"course_name": course["fullname"]}
        where = f"{first['semester_folder']}/" if first.get("semester_folder") else ""
        print(f"■ {where}{course_folder(first, cfg)}")
        print(f"  Moodle: {clean_text(course['fullname'], config.moodle_content_language())}")
        counts: dict = {}
        for f in cf:
            counts[categorize(f, cfg)] = counts.get(categorize(f, cfg), 0) + 1
        summary = ", ".join(f"{name}: {n}" for name, n in sorted(counts.items())) or t("courses_no_files")
        print(f"  {summary}\n")
    return 0
