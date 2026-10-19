"""
Per-course settings: what each course may send you and put into your calendar.

    files          🔔 "new materials" notification (the files are downloaded either way)
    announcements  🔔 new announcements
    grades         🔔 new grades
    deadlines      🔔 new and moved deadlines (noticed by the calendar sync, so they need "calendar" on)
    reminders      🔔 reminders of what you haven't handed in
    calendar       📅 its deadlines in the "<SITE_LABEL> – deadlines" Google calendar
    classes        📅 its classes (attendance sessions) in the "<SITE_LABEL> – classes" calendar
    autosend       📨 its new files sent to the Telegram chat as documents - OFF by default
                   (AUTOSEND_FILES=1 turns it on for every course)

Everything else is on by default. Two places switch things off, the bot's choice wins:
  course_settings.json   written by the bot (/settings -> 📘 or /courses -> a course -> ⚙️), by course id
  courses.json "mute"    by a fragment of the course name, for setups without the bot:
                         {"mute": {"Sandbox": "all", "Library": ["announcements", "calendar"]}}

The global switches (NOTIFY_*, SYNC_CLASSES in /settings) still apply on top: a kind muted there is muted
for every course. Settings decide what is PUSHED to you; what you ask for (/deadlines, /today, /courses,
the weekly summary) still shows every course that isn't hidden.

Hidden courses: like "Hide from the dashboard" in Moodle - and a course hidden there is hidden here too
(core_enrol_get_users_courses -> "hidden"), unless you showed it in the bot. A hidden course isn't synced
at all (files, calendar, announcements, grades, reminders) and leaves /courses, /today and /deadlines for
the 🙈 Hidden list; /sync can still fetch its files on request.

A file of its own, not state.json: the bot writes it at any moment, also while a sync runs (the sync saves
state.json at the end and would undo the change); the sync only reads it.
"""

import hashlib
import json
import os
from pathlib import Path

from . import config
from .i18n import t

KINDS = ["files", "announcements", "grades", "deadlines", "reminders", "calendar", "classes", "autosend"]
OFF_BY_DEFAULT = {"autosend"}  # pushes whole files: only when you ask for it
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
    """Kinds that are off for this course unless the bot says otherwise: courses.json -> "mute", autosend."""
    name = course.get("fullname", "").casefold()
    off = set() if config.env_bool("AUTOSEND_FILES", False) else set(OFF_BY_DEFAULT)
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
        if is_hidden(c, saved):
            out[c["id"]] = set(KINDS)  # nothing from a hidden course, whatever its settings say
            continue
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
    _store(data, key, entry)


def _store(data: dict, key: str, entry: dict) -> None:
    if entry:
        data[key] = entry
    else:
        data.pop(key, None)
    tmp = path().with_name(FILE + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
    os.replace(tmp, path())  # the sync may read it at any moment: never half a file


# --- hidden courses ------------------------------------------------------------------------------

def is_hidden(course: dict, saved: dict | None = None) -> bool:
    """Hidden in the bot, or - when the bot never said - hidden on Moodle's dashboard."""
    entry = ((load() if saved is None else saved).get(str(course["id"])) or {})
    return bool(entry.get("hidden", course.get("hidden", False)))


def active(courses: list) -> list:
    """The courses that are synced: everything that isn't hidden."""
    saved = load()
    return [c for c in courses if not is_hidden(c, saved)]


def set_hidden(course: dict, hidden: bool) -> None:
    """Hide or show a course. Kept only while it differs from Moodle's own "hidden" flag of `course`."""
    data = load()
    key = str(course["id"])
    entry = data.get(key) or {}
    if hidden == bool(course.get("hidden", False)):
        entry.pop("hidden", None)
    else:
        entry["hidden"] = hidden
    _store(data, key, entry)


def globally_off() -> set[str]:
    """Kinds no course can do right now: muted in /settings, no Google calendar or no Telegram."""
    off = {kind for kind, key in GLOBAL_SWITCHES.items() if not config.env_bool(key, True)}
    if not config.GOOGLE_TOKEN_FILE.exists():
        off |= {"calendar", "classes", "deadlines"}
    if not (config.env("TELEGRAM_BOT_TOKEN") and config.env("TELEGRAM_CHAT_ID")):
        off.add("autosend")
    return off


def site_key(site: Path | None = None) -> str:
    """A short name of a data folder, so a button under a notification finds its site in the bot (sites.py)."""
    return hashlib.sha1(str(site or config.DATA_DIR).encode()).hexdigest()[:8]


def mute_buttons(course_id: int, kind: str) -> list | None:
    """🔕 under a notification: mute this kind for this course with one tap (TELEGRAM_FILE_BUTTONS=0 hides it)."""
    if not course_id or not config.env_bool("TELEGRAM_FILE_BUTTONS", True):
        return None
    return [[(t("notify_mute_course"), f"cpq:{course_id}:{site_key()}:{kind}")]]
