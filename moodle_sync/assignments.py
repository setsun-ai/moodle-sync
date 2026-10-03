"""
Submitting assignments from the Telegram bot.

You send the bot a file, pick the assignment, the bot checks what the
assignment accepts (file types, size, number of files), renames the file
after the assignment and the course, and - only after you confirm - uploads
it the way the Moodle app does: webservice/upload.php into your draft area,
then mod_assign_save_submission. "Submit for grading" is a separate tap.

    STUDENT_ID        your student number, used in the file name
    SUBMISSION_NAME   file name template, default "{assignment} {course} {student_id}";
                      fields: {assignment} {course} {student_id} {original}

Pure helpers (requirements, check_file, target_name) are tested in
tests/test_assignments.py.
"""

import re
import time
from pathlib import Path

from . import config, moodle
from .textutil import clean_text, sanitize_component

# Moodle's file type groups (core_filetypes) -> extensions, for the groups students meet most
TYPE_GROUPS = {
    "document": {".doc", ".docx", ".odt", ".pdf", ".rtf", ".txt", ".md", ".tex", ".epub"},
    "spreadsheet": {".xls", ".xlsx", ".ods", ".csv"},
    "presentation": {".ppt", ".pptx", ".odp", ".key"},
    "image": {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".svg", ".webp", ".tif", ".tiff", ".heic"},
    "archive": {".zip", ".7z", ".rar", ".tar", ".gz", ".tgz", ".bz2", ".xz"},
    "web_file": {".html", ".htm", ".css", ".js", ".json", ".xml"},
    "audio": {".mp3", ".wav", ".ogg", ".m4a", ".flac"},
    "video": {".mp4", ".mov", ".avi", ".mkv", ".webm"},
}


def _config(assign: dict, plugin: str, name: str, default: str = "") -> str:
    for c in assign.get("configs", []):
        if c.get("subtype") == "assignsubmission" and c.get("plugin") == plugin and c.get("name") == name:
            return str(c.get("value", default))
    return default


def requirements(assign: dict) -> dict:
    """{"files": file submissions on?, "types": set of extensions or None (anything), "unknown": groups we
    can't resolve, "max_bytes": int or 0, "max_files": int}."""
    types, unknown = set(), []
    for item in re.split(r"[\s,;]+", _config(assign, "file", "filetypeslist")):
        item = item.strip().lower()
        if not item or item == "*":
            continue
        if item.startswith("."):
            types.add(item)
        elif item in TYPE_GROUPS:
            types |= TYPE_GROUPS[item]
        elif "/" not in item:
            unknown.append(item)
    return {"files": _config(assign, "file", "enabled") == "1",
            "types": types or None,
            "unknown": unknown,
            "max_bytes": int(_config(assign, "file", "maxsubmissionsizebytes", "0") or 0),
            "max_files": int(_config(assign, "file", "maxfilesubmissions", "1") or 1)}


def check_file(assign: dict, filename: str, size: int) -> list[str]:
    """Problems with this file for this assignment: [] = fine; otherwise "type" / "size" / "nofiles"."""
    req = requirements(assign)
    if not req["files"]:
        return ["nofiles"]
    problems = []
    if req["types"] and not req["unknown"] and Path(filename).suffix.lower() not in req["types"]:
        problems.append("type")
    if req["max_bytes"] and size > req["max_bytes"]:
        problems.append("size")
    return problems


def target_name(assign: dict, course_name: str, original: str) -> str:
    """File name from SUBMISSION_NAME, e.g. "Sprawozdanie LCMS 123456.pdf"."""
    template = config.env("SUBMISSION_NAME") or "{assignment} {course} {student_id}"
    lang = config.moodle_content_language()
    stem = template.format(assignment=clean_text(assign.get("name", ""), lang), course=course_name,
                           student_id=config.env("STUDENT_ID"), original=Path(original).stem)
    stem = re.sub(r"\s+", " ", stem).strip(" _-") or Path(original).stem
    return sanitize_component(stem + Path(original).suffix.lower(), "file", lang)


def open_assignments(courses: list[dict]) -> list[dict]:
    """Assignments accepting files now, soonest deadline first; each with "course" (display name) added."""
    from .files import course_display_name

    if not courses:
        return []
    cfg = config.load_courses_config()
    names = {c["id"]: course_display_name(c["fullname"], cfg) for c in courses}
    data = moodle.call("mod_assign_get_assignments", **{f"courseids[{i}]": c["id"] for i, c in enumerate(courses)})
    now = time.time()
    found = []
    for course in data.get("courses", []):
        for a in course.get("assignments", []):
            opens, cutoff = a.get("allowsubmissionsfromdate") or 0, a.get("cutoffdate") or 0
            if opens > now or (cutoff and now > cutoff) or not requirements(a)["files"]:
                continue
            a["course"] = names.get(course["id"], course.get("fullname", ""))
            found.append(a)
    return sorted(found, key=lambda a: (not a.get("duedate"), a.get("duedate") or 0))


def submission_status(assign_id: int) -> dict:
    """{"status": new/draft/submitted, "files": [names], "can_edit": bool, "can_submit": bool}."""
    data = moodle.call("mod_assign_get_submission_status", assignid=assign_id)
    attempt = data.get("lastattempt") or {}
    submission = attempt.get("submission") or {}
    files = [f.get("filename") for p in submission.get("plugins", []) if p.get("type") == "file"
             for area in p.get("fileareas", []) for f in area.get("files", [])]
    return {"status": submission.get("status", "new"), "files": [f for f in files if f],
            "can_edit": attempt.get("canedit", True), "can_submit": bool(attempt.get("cansubmit"))}


def save(assign: dict, filename: str, data: bytes) -> None:
    """Upload and save as the assignment's submission (replaces the files already there)."""
    itemid = moodle.upload_draft(filename, data)
    result = moodle.call("mod_assign_save_submission", assignmentid=assign["id"],
                         **{"plugindata[files_filemanager]": itemid})
    warnings = result if isinstance(result, list) else (result or {}).get("warnings", [])
    if warnings:
        raise moodle.MoodleError(warnings[0].get("warningcode", "?"), warnings[0].get("item", "") + " " +
                                 warnings[0].get("message", ""))


def submit_for_grading(assign: dict) -> None:
    result = moodle.call("mod_assign_submit_for_grading", assignmentid=assign["id"], acceptsubmissionstatement=1)
    if result:
        warning = result[0] if isinstance(result, list) else result
        raise moodle.MoodleError(str(warning.get("warningcode", "?")), warning.get("message", ""))


def human_size(n: int) -> str:
    return f"{n / 1024 / 1024:.1f} MB" if n >= 1024 * 1024 else f"{max(1, n // 1024)} KB"


def types_text(assign: dict) -> str:
    req = requirements(assign)
    return ", ".join(sorted(req["types"])) if req["types"] else ""

