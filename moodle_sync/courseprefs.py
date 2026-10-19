"""
Per-course settings: what each course may send you and put into your calendar.

    files          🔔 "new materials" notification (the files are downloaded either way)
    announcements  🔔 new announcements
    grades         🔔 new grades
    deadlines      🔔 new and moved deadlines (noticed by the calendar sync, so they need "calendar" on)
    reminders      🔔 reminders of what you haven't handed in
    calendar       📅 its deadlines in the "<SITE_LABEL> – deadlines" Google calendar
    classes        📅 its classes (attendance sessions) in the "<SITE_LABEL> – classes" calendar

Everything is on by default. Two places switch things off, the bot's choice wins:
  course_settings.json   written by the bot (/settings -> 📘 or /courses -> a course -> ⚙️), by course id
  courses.json "mute"    by a fragment of the course name, for setups without the bot:
                         {"mute": {"Sandbox": "all", "Library": ["announcements", "calendar"]}}

The global switches (NOTIFY_*, SYNC_CLASSES in /settings) still apply on top: a kind muted there is muted
for every course. Settings decide what is PUSHED to you; what you ask for (/deadlines, /today, /courses,
the weekly summary) still shows every course.

A file of its own, not state.json: the bot writes it at any moment, also while a sync runs (the sync saves
state.json at the end and would undo the change); the sync only reads it.
"""

import hashlib
import json
import os
from pathlib import Path

from . import config
from .i18n import t

KINDS = ["files", "announcements", "grades", "deadlines", "reminders", "calendar", "classes"]
FILE = "course_settings.json"
GLOBAL_SWITCHES = {"files": "NOTIFY_FILES", "announcements": "NOTIFY_ANNOUNCEMENTS", "grades": "NOTIFY_GRADES",
                   "deadlines": "NOTIFY_DEADLINES", "reminders": "NOTIFY_REMINDERS", "classes": "SYNC_CLASSES"}


def path() -> Path:
    return config.DATA_DIR / FILE


def load() -> dict:
    """course id (str) -> {kind: on?} - only what was switched in the bot."""
    try:
        data = json.loads(path().read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except (ValueError, OSError) as e:  # a damaged file: defaults (all on) - nothing is lost, only too loud
        print(f"[{FILE}] {e}")
        return {}
    return data if isinstance(data, dict) else {}


def defaults(course: dict, cfg: dict) -> set[str]:
    """Kinds that courses.json -> "mute" switches off for this course."""
    name = course.get("fullname", "").casefold()
    off = set()
    for fragment, kinds in (cfg.get("mute") or {}).items():
        if fragment.casefold() in name:
            kinds = [kinds] if isinstance(kinds, str) else kinds
            off |= set(KINDS) if "all" in kinds else set(kinds) & set(KINDS)
    return off


def muted(courses: list, cfg: dict | None = None) -> dict[int, set[str]]:
    """Course id -> kinds switched off. Courses with everything on are left out."""
    cfg = config.load_courses_config() if cfg is None else cfg
    saved = load()
    out = {}
    for c in courses:
        off = defaults(c, cfg)
        for kind, on in (saved.get(str(c["id"])) or {}).items():
            if kind in KINDS:
                (off.discard if on else off.add)(kind)
        if off:
            out[c["id"]] = off
    return out


def allows(off: dict, course_id, kind: str) -> bool:
    """May this course do `kind`? (off = muted(...); a site event without a course is always allowed)"""
    return kind not in off.get(course_id, ())


def switch(course: dict, kinds: list[str], on: bool, cfg: dict | None = None) -> None:
    """Switch kinds on or off for a course. Only what differs from courses.json is kept in the file."""
    cfg = config.load_courses_config() if cfg is None else cfg
    default_off = defaults(course, cfg)
    data = load()
    key = str(course["id"])
    entry = data.get(key) or {}
    for kind in kinds:
        if kind not in KINDS:
            continue  # only known settings are ever written
        if on == (kind not in default_off):
            entry.pop(kind, None)
        else:
            entry[kind] = on
    if entry:
        data[key] = entry
    else:
        data.pop(key, None)
    tmp = path().with_name(FILE + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
    os.replace(tmp, path())  # the sync may read it at any moment: never half a file


def globally_off() -> set[str]:
    """Kinds no course can do right now: muted in /settings, or the Google calendar isn't connected."""
    off = {kind for kind, key in GLOBAL_SWITCHES.items() if not config.env_bool(key, True)}
    if not config.GOOGLE_TOKEN_FILE.exists():
        off |= {"calendar", "classes", "deadlines"}
    return off


def site_key(site: Path | None = None) -> str:
    """A short name of a data folder, so a button under a notification finds its site in the bot (sites.py)."""
    return hashlib.sha1(str(site or config.DATA_DIR).encode()).hexdigest()[:8]


def mute_buttons(course_id: int, kind: str) -> list | None:
    """🔕 under a notification: mute this kind for this course with one tap (TELEGRAM_FILE_BUTTONS=0 hides it)."""
    if not course_id or not config.env_bool("TELEGRAM_FILE_BUTTONS", True):
        return None
    return [[(t("notify_mute_course"), f"cpq:{course_id}:{site_key()}:{kind}")]]
