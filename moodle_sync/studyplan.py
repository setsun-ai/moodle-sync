"""
Study plan: semester folders and subject cards (syllabi) from the university's
ECTS catalogue.

    STUDY_CATALOG     your university's ECTS catalogue, e.g. https://ects.example.edu/pl
                      (only needed to search; taken from STUDY_PLAN_URL otherwise)
    STUDY_PLAN_URL    your field of study in the catalogue, e.g.
                      https://ects.example.edu/pl/courses/123 (or a specialisation:
                      .../courses/123/subcourses/456/subjects).
                      Find it with: python -m moodle_sync plan --search "name"
    STUDY_START       without a catalogue: your first semester, e.g. 2025/2026-winter;
                      semester numbers are then counted from the course start dates
    SEMESTER_FOLDERS  1 = put courses into "Semester N" folders (default: on when
                      STUDY_PLAN_URL or STUDY_START is set)
    SYLLABUS          1 = download subject cards into the subject folders
                      (default: on with STUDY_PLAN_URL)

Supported catalogues show the plan as semesters ("Semestr 1 (2025/2026 -
zimowy)") with a PDF card per subject (".../subjects/<id>/card.pdf"). The
parsing functions are pure - see tests/test_studyplan.py - so a catalogue in
another format only needs its own parse_* functions.

How a Moodle course finds its subject: the subject whose every word appears in
the course name (most words wins: "Mathematics II" beats "Mathematics"), else a
close fuzzy match. The plan's semesters carry their academic term
("2025/2026 - winter"), so a course without a match still gets its semester
from its start date. courses.json can override both:
    "plan":     {"fragment of the Moodle name": "subject name in the plan"}
    "semester": {"fragment of the Moodle name": 2}
"""

import hashlib
import html
import os
import re
import time
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path
from urllib.parse import urlsplit

import requests

from . import config, state as state_mod
from .i18n import t
from .notify import bullet_list, notify
from .textutil import normalize_for_matching, pick_language, sanitize_component

PLAN_TTL = 24 * 3600            # the plan is fetched at most once a day
CARD_RECHECK_DAYS = 30           # cards are re-downloaded to spot changes
MATCH_THRESHOLD = 0.82
SEARCH_MAX_PAGES = 20
SEASONS = ("winter", "summer")
HEADERS = {"User-Agent": "moodle-sync (+https://github.com/setsun-ai/moodle-sync)"}


# --- settings --------------------------------------------------------------------------------

def plan_url() -> str:
    return normalize_plan_url(config.env("STUDY_PLAN_URL"))


def catalog_url(url: str = "") -> str:
    """Base of the ECTS catalogue with its language part: https://ects.example.edu/pl"""
    url = (url or config.env("STUDY_CATALOG") or config.env("STUDY_PLAN_URL")).strip()
    m = re.match(r"(https?://[^/]+)(?:/([a-z]{2})(?=/|$))?", url)
    return f"{m.group(1)}/{m.group(2) or 'pl'}" if m else ""


def study_start() -> tuple[int, str] | None:
    """STUDY_START=2025/2026-winter -> (2025, 'winter')."""
    m = re.fullmatch(r"(\d{4})(?:/\d{2,4})?[-_ ]*(winter|summer|zima|zimowy|lato|letni)",
                     config.env("STUDY_START").lower())
    if not m:
        return None
    return int(m.group(1)), "winter" if m.group(2) in ("winter", "zima", "zimowy") else "summer"


def semester_folders_enabled() -> bool:
    return config.env_bool("SEMESTER_FOLDERS", bool(plan_url() or study_start()))


def syllabus_enabled() -> bool:
    return bool(plan_url()) and config.env_bool("SYLLABUS", True)


def semester_folder(number: int) -> str:
    return t("plan_semester_folder", n=number)


def card_filename() -> str:
    return t("plan_card_file")


# --- parsing the catalogue (pure functions) -----------------------------------------------------

_SEMESTER = re.compile(r"Semest(?:r|er):?\s*(\d+)\s*</strong>\s*(?:&nbsp;|\s)*\(\s*(\d{4})\s*/\s*(\d{4})\s*-\s*"
                       r"(zimowy|letni|winter|summer)\s*\)", re.I)
_ROW = re.compile(r'<div class="data-table__row( secondary-row)?">')
_FIRST_CELL = re.compile(r'<div class="cell">(.*?)</div>', re.S)
_CARD = re.compile(r"/subjects/(\d+)/card\.pdf")
_TAG = re.compile(r"<[^>]+>")


def _text(fragment: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(_TAG.sub(" ", fragment))).strip()


def normalize_plan_url(url: str) -> str:
    """Any page of a field of study -> its subject list (.../courses/ID[/subcourses/ID]/subjects)."""
    url = (url or "").strip()
    m = re.match(r"(https?://[^/]+/\w+/courses/\d+(?:/subcourses/\d+)?)", url)
    return f"{m.group(1)}/subjects" if m else url


def parse_plan(page: str) -> list[dict]:
    """
    Subject list page -> [{"number": 1, "year": 2025, "season": "winter",
    "subjects": [{"name", "card", "elective"}]}]. Rows without a card are
    module headers ("Elective subjects ..."); their alternatives come as
    secondary rows and are marked elective.
    """
    semesters = []
    heads = list(_SEMESTER.finditer(page))
    for i, head in enumerate(heads):
        chunk = page[head.end(): heads[i + 1].start() if i + 1 < len(heads) else len(page)]
        rows = list(_ROW.finditer(chunk))
        subjects, seen = [], set()
        for j, row in enumerate(rows):
            body = chunk[row.end(): rows[j + 1].start() if j + 1 < len(rows) else len(chunk)]
            cell = _FIRST_CELL.search(body)
            card = _CARD.search(body)
            name = _text(cell.group(1)) if cell else ""
            if not name or not card or (name, card.group(1)) in seen:
                continue
            seen.add((name, card.group(1)))
            subjects.append({"name": name, "card": int(card.group(1)), "elective": bool(row.group(1))})
        season = "winter" if head.group(4).lower() in ("zimowy", "winter") else "summer"
        semesters.append({"number": int(head.group(1)), "year": int(head.group(2)), "season": season,
                          "subjects": subjects})
    return semesters


def parse_specializations(page: str, base: str) -> list[tuple[str, str]]:
    """Specialisations offered on a subject list page: [(name, url of its subject list)]."""
    out = []
    for path, label in re.findall(r'href="(?:https?://[^/"]+)?(/\w+/courses/\d+/subcourses/\d+/subjects)"[^>]*>(.*?)</a>',
                                  page, re.S):
        name = re.sub(r"^\s*(Specjalno\w*|Specialisation|Specialization)\s*:\s*", "", _text(label), flags=re.I)
        url = base + path
        if (name, url) not in out:
            out.append((name, url))
    return out


_LISTING = re.compile(
    r'href="#course_\d+"[^>]*>(?P<field>[^<]+)</a>'
    r'|href="#course_\d+_\d+"[^>]*>(?P<mode>[^<]+)</a>'
    r'|href="(?P<url>https?://[^"]+/courses/\d+)"[^>]*>(?P<label>[^<]+)</a>')


def parse_programs(page: str) -> list[dict]:
    """Catalogue listing -> [{"field", "mode", "start", "current", "url"}]."""
    out, field, mode = [], "", ""
    for m in _LISTING.finditer(page):
        if m.group("field"):
            field, mode = _text(m.group("field")), ""
        elif m.group("mode"):
            mode = _text(m.group("mode"))
        else:
            label = _text(m.group("label"))
            start = re.search(r"(\d{4}/\d{4})", label)
            current = re.search(r"(\d+)\s*\)", label)
            out.append({"field": field, "mode": mode, "start": start.group(1) if start else "",
                        "current": int(current.group(1)) if current else None, "url": m.group("url")})
    return out


# --- terms and semesters --------------------------------------------------------------------------

def term_of(timestamp: float) -> tuple[int, str] | None:
    """Course start date -> academic term: October-January = winter, February-August = summer."""
    if not timestamp:
        return None
    d = datetime.fromtimestamp(timestamp)
    if d.month >= 9:
        return d.year, "winter"
    return (d.year - 1, "winter") if d.month == 1 else (d.year - 1, "summer")


def semester_by_term(term: tuple[int, str] | None, plan: list[dict] | None,
                     start: tuple[int, str] | None) -> int | None:
    if term is None:
        return None
    for sem in plan or []:
        if (sem["year"], sem["season"]) == term:
            return sem["number"]
    if start:
        n = (term[0] - start[0]) * 2 + SEASONS.index(term[1]) - SEASONS.index(start[1]) + 1
        return n if n >= 1 else None
    return None


# --- matching Moodle courses to subjects ------------------------------------------------------------

def _words(text: str) -> list[str]:
    lang = config.moodle_content_language()
    words = re.findall(r"[a-z0-9]+", normalize_for_matching(pick_language(text, lang), lang))
    return [w for w in words if not (w.isdigit() and len(w) >= 2)]  # years, group numbers


def match_subject(course_name: str, plan: list[dict], term: tuple[int, str] | None = None) -> tuple[dict, dict] | None:
    """Best (semester, subject) for a Moodle course name, or None."""
    course = _words(course_name)
    course_set, course_text = set(course), " ".join(course)
    best, best_score = None, 0.0
    for sem in plan:
        same_term = term == (sem["year"], sem["season"])
        for subject in sem["subjects"]:
            words = _words(subject["name"])
            if not words:
                continue
            if set(words) <= course_set:
                score = 1.0 + len(words) / 100
            else:
                score = SequenceMatcher(None, " ".join(words), course_text).ratio()
            score += 0.05 if same_term else 0
            if score > best_score:
                best, best_score = (sem, subject), score
    return best if best_score >= MATCH_THRESHOLD else None


def _find_subject(plan: list[dict], name: str) -> tuple[dict, dict] | None:
    wanted = " ".join(_words(name))
    for sem in plan:
        for subject in sem["subjects"]:
            if " ".join(_words(subject["name"])) == wanted:
                return sem, subject
    return None


def _override(cfg: dict, section: str, course_name: str):
    name = pick_language(course_name, config.moodle_content_language()).casefold()
    for fragment, value in cfg.get(section, {}).items():
        if fragment.casefold() in name:
            return value
    return None


def assign_courses(courses: list[dict], plan: list[dict] | None, cfg: dict) -> dict:
    """
    Moodle course id -> {"semester": N or None, "subject": name from the plan or None,
    "card": card id or None}. Pure, given the plan.
    """
    start = study_start()
    out = {}
    for course in courses:
        name = course.get("fullname", "")
        term = term_of(course.get("startdate") or 0)
        found = None
        if plan:
            forced = _override(cfg, "plan", name)
            found = _find_subject(plan, forced) if forced else match_subject(name, plan, term)
        semester = _override(cfg, "semester", name)
        if semester is None and found:
            semester = found[0]["number"]
        if semester is None:
            semester = semester_by_term(term, plan, start)
        out[course["id"]] = {"semester": int(semester) if semester else None,
                             "subject": found[1]["name"] if found else None,
                             "card": found[1]["card"] if found else None}
    return out


def shouting(name: str) -> bool:
    """Catalogues sometimes write every subject in CAPITALS - not a folder name anyone wants."""
    letters = [c for c in name if c.isalpha()]
    return len(letters) > 3 and all(c.isupper() for c in letters)


def readable(name: str) -> str:
    """'MACHINE LEARNING I SIECI NEURONOWE' -> 'Machine learning i sieci neuronowe'; other names unchanged."""
    if not shouting(name):
        return name
    lower = name.lower()
    return lower[:1].upper() + lower[1:]


def folder_subject(subject: str | None) -> str | None:
    """The plan's name for a course folder, or None to keep Moodle's own name (when the plan only SHOUTS)."""
    return None if not subject or shouting(subject) else subject


def course_layout(courses: list[dict], cfg: dict, plan: list[dict] | None) -> dict:
    """Moodle course id -> (semester folder or None, course folder name or None) for files.relative_path."""
    folders = semester_folders_enabled()
    layout = {}
    for cid, a in assign_courses(courses, plan, cfg).items():
        layout[cid] = (semester_folder(a["semester"]) if folders and a["semester"] else None,
                       folder_subject(a["subject"]))
    return layout


# --- fetching ---------------------------------------------------------------------------------------

def _get(url: str, timeout: int = 30) -> requests.Response:
    resp = requests.get(url, headers=HEADERS, timeout=timeout)
    resp.raise_for_status()
    return resp


def load_plan(state: dict | None = None, force: bool = False) -> list[dict] | None:
    """
    The plan of STUDY_PLAN_URL, cached in state.json for a day. When the
    catalogue is down, the cached copy is used - folders must not jump back
    to the old layout just because a website is offline.
    """
    url = plan_url()
    if not url:
        return None
    own_state = state is None
    state = state_mod.load() if own_state else state
    cache = state.get("study_plan") or {}
    fresh = cache.get("url") == url and time.time() - cache.get("fetched", 0) < PLAN_TTL
    if fresh and not force:
        return cache["semesters"]
    try:
        semesters = parse_plan(_get(url).text)
        if not semesters:
            raise ValueError(t("plan_empty", url=url))
    except (requests.RequestException, ValueError) as e:
        if cache.get("url") == url and cache.get("semesters"):
            print(t("plan_cached", error=e))
            return cache["semesters"]
        raise RuntimeError(t("plan_unavailable", url=url, error=e)) from e
    state["study_plan"] = {"url": url, "fetched": time.time(), "semesters": semesters}
    if own_state:
        state_mod.save(state)
    return semesters


def search_programs(query: str, catalog: str = "") -> list[dict]:
    """Fields of study in the catalogue whose name contains all words of the query."""
    base = catalog_url(catalog)
    if not base:
        raise ValueError(t("plan_no_catalog"))
    wanted = _words(query)
    found = []
    for page in range(1, SEARCH_MAX_PAGES + 1):
        programs = parse_programs(_get(f"{base}/courses?p={page}").text)
        if not programs:
            break
        found += [p for p in programs if set(wanted) <= set(_words(p["field"]))]
    return found


# --- subject cards -------------------------------------------------------------------------------

def planned_cards(courses: list[dict], plan: list[dict], cfg: dict) -> dict:
    """
    Card id -> relative path of its PDF. Compulsory subjects of every semester,
    plus elective ones only when you have a matching Moodle course (nobody
    wants all fifteen alternatives). The folder is the same as for the
    course's Moodle files, so the card lands next to its materials.
    """
    from .files import course_display_name  # files imports this module

    lang = config.moodle_content_language()
    folders = semester_folders_enabled()
    assigned = assign_courses(courses, plan, cfg)
    by_card = {}  # card -> folder name of the matching Moodle course (courses.json "names" wins)
    for course in courses:
        a = assigned[course["id"]]
        if a["card"]:
            # the same folder as the course's Moodle files (files.course_folder)
            by_card[a["card"]] = (_override(cfg, "names", course.get("fullname", "")) or folder_subject(a["subject"])
                                  or course_display_name(course.get("fullname", ""), cfg))
    cards = {}
    for sem in plan:
        for subject in sem["subjects"]:
            if subject["elective"] and subject["card"] not in by_card:
                continue
            parts = [semester_folder(sem["number"])] if folders else []
            parts += [sanitize_component(by_card.get(subject["card"]) or readable(subject["name"]), "Course", lang),
                      card_filename()]
            cards[subject["card"]] = (Path(*parts), subject["name"])
    return cards


def card_url(card: int) -> str:
    parts = urlsplit(plan_url())
    lang = parts.path.strip("/").split("/")[0] or "pl"
    return f"{parts.scheme}://{parts.netloc}/{lang}/subjects/{card}/card.pdf"


def run(dry_run: bool = False, force: bool = False) -> int:
    """Download new and changed subject cards. 2 = not configured."""
    if not syllabus_enabled():
        print(t("plan_off"))
        return 2
    from . import moodle

    state = state_mod.load()
    plan = load_plan(state)
    cfg = config.load_courses_config()
    cards = planned_cards(moodle.my_courses(), plan, cfg)
    known = state.setdefault("syllabi", {})
    root = config.download_dir()
    new, changed, failed = [], [], 0
    now = time.time()

    for card, (rel, name) in sorted(cards.items(), key=lambda x: x[1][0].as_posix()):
        entry = known.get(str(card))
        if entry and entry["path"] != rel.as_posix():  # subject renamed / semester folders switched on
            old = root / entry["path"]
            if not dry_run:
                if old.exists():
                    (root / rel).parent.mkdir(parents=True, exist_ok=True)
                    os.replace(old, root / rel)
                state.setdefault("remote_moves", []).append({"from": entry["path"], "to": rel.as_posix()})
            print(f"    {entry['path']}\n -> {rel.as_posix()}")
            entry["path"] = rel.as_posix()
        if entry and not force and now - entry.get("checked", 0) < CARD_RECHECK_DAYS * 86400:
            continue
        if dry_run:
            print(f"[?] {rel.as_posix()}")
            continue
        try:
            data = _get(card_url(card)).content
            if not data.startswith(b"%PDF"):
                raise ValueError(t("plan_not_pdf"))
        except (requests.RequestException, ValueError) as e:
            failed += 1
            print(f"{rel.as_posix()}: " + t("error", error=e))
            continue
        digest = hashlib.sha1(data).hexdigest()
        if not entry or entry.get("sha") != digest:
            dest = root / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            tmp = dest.with_name(dest.name + ".part")
            tmp.write_bytes(data)
            os.replace(tmp, dest)
            (changed if entry else new).append(name)
            print(("[~] " if entry else "[+] ") + rel.as_posix())
        known[str(card)] = {"path": rel.as_posix(), "sha": digest, "checked": now}
        state_mod.save(state)
        time.sleep(0.3)  # a public university website - no hurry

    if not dry_run:
        state_mod.save(state)
        if new:
            notify("files", t("plan_cards_new", n=len(new)), bullet_list(new))
        for subject in changed:
            notify("files", t("plan_card_changed", subject=subject))
    print(t("plan_cards_summary", new=len(new), changed=len(changed), failed=failed))
    return 1 if failed else 0


# --- python -m moodle_sync plan ----------------------------------------------------------------------

def preview() -> int:
    """Semesters, subjects and which Moodle course feeds each folder."""
    from . import moodle
    from .files import course_display_name

    cfg = config.load_courses_config()
    courses = moodle.my_courses()
    plan = load_plan(force=True) if plan_url() else None
    assigned = assign_courses(courses, plan, cfg)
    now_term = term_of(time.time())
    current = semester_by_term(now_term, plan, study_start())

    if plan:
        print(t("plan_header", url=plan_url()) + "\n")
        for sem in plan:
            mark = "  ← " + t("plan_now") if sem["number"] == current else ""
            season = t("plan_winter") if sem["season"] == "winter" else t("plan_summer")
            print(f"■ {semester_folder(sem['number'])}  ({sem['year']}/{sem['year'] + 1} {season}){mark}")
            for subject in sem["subjects"]:
                moodle_names = [course_display_name(c["fullname"], cfg) for c in courses
                                if assigned[c["id"]]["card"] == subject["card"]]
                if subject["elective"] and not moodle_names:
                    continue
                tick = "✓ " + ", ".join(moodle_names) if moodle_names else "– " + t("plan_no_moodle")
                print(f"    {subject['name']}  [{tick}]")
            print()
    elif study_start():
        print(t("plan_by_dates", start=config.env("STUDY_START")) + "\n")
    else:
        print(t("plan_none"))
        return 2

    loose = [c for c in courses if not assigned[c["id"]]["subject"]]
    if loose:
        print(t("plan_unmatched"))
        for c in loose:
            n = assigned[c["id"]]["semester"]
            where = semester_folder(n) if n else t("plan_no_semester")
            print(f"    {course_display_name(c['fullname'], cfg)}  -> {where}")
    return 0


def search(query: str, catalog: str = "") -> int:
    """python -m moodle_sync plan --search "name" [--catalog URL]: find the STUDY_PLAN_URL."""
    try:
        programs = search_programs(query, catalog)
    except ValueError as e:
        print(e)
        return 2
    if not programs:
        print(t("plan_search_none", query=query))
        return 1
    for p in programs:
        now = f", {t('plan_now')}: {p['current']}" if p["current"] else ""
        print(f"■ {p['field']} – {p['mode']}, {p['start']}{now}\n    {p['url']}")
    if len(programs) <= 6:
        base = "{0.scheme}://{0.netloc}".format(urlsplit(programs[0]["url"]))
        for p in programs:
            specs = parse_specializations(_get(normalize_plan_url(p["url"])).text, base)
            for name, url in specs:
                print(f"      {t('plan_specialisation')}: {name}\n        {url}")
    print("\n" + t("plan_search_hint"))
    return 0
