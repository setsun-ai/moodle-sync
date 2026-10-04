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
    "subjects": [{"name", "card", "elective", "module"}]}]. A row without a card
    followed by secondary rows is a module ("Elective subjects ..."): its
    alternatives are marked elective, with the module's name. A row without a
    card and without alternatives is a subject whose card isn't published
    (card None) - reported, not silently skipped.
    """
    semesters = []
    heads = list(_SEMESTER.finditer(page))
    for i, head in enumerate(heads):
        chunk = page[head.end(): heads[i + 1].start() if i + 1 < len(heads) else len(page)]
        rows = list(_ROW.finditer(chunk))
        subjects, seen, module = [], set(), None
        for j, row in enumerate(rows):
            body = chunk[row.end(): rows[j + 1].start() if j + 1 < len(rows) else len(chunk)]
            cell = _FIRST_CELL.search(body)
            card = _CARD.search(body)
            name = _text(cell.group(1)) if cell else ""
            secondary = bool(row.group(1))
            if not secondary:
                module = None
                if not card and j + 1 < len(rows) and rows[j + 1].group(1):
                    module = name  # a module header: its alternatives follow
                    continue
            card_id = int(card.group(1)) if card else None
            if not name or (name, card_id) in seen:
                continue
            seen.add((name, card_id))
            subjects.append({"name": name, "card": card_id, "elective": secondary,
                             "module": module if secondary else None})
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


_NUMERALS = {"i", "ii", "iii", "iv", "v", "vi", "1", "2", "3", "4", "5", "6"}


def base_words(words: list[str]) -> list[str]:
    """Without the trailing part number: "Language II" and "Language I" are one series."""
    return words[:-1] if len(words) > 1 and words[-1] in _NUMERALS else words


def match_subject(course_name: str, plan: list[dict], term: tuple[int, str] | None = None,
                  taken: set | None = None) -> tuple[dict, dict] | None:
    """
    Best (semester, subject) for a Moodle course name, or None. Moodle often leaves out the
    part number ("English" for "English I" and "English II"): then the semester the course
    started in decides. Electives you picked (/electives) beat the alternatives you didn't.
    """
    course = _words(course_name)
    course_set, course_text = set(course), " ".join(course)
    course_numeral = {w for w in course if w in _NUMERALS}
    best, best_score = None, 0.0
    for sem in plan:
        same_term = term == (sem["year"], sem["season"])
        for subject in sem["subjects"]:
            words = _words(subject["name"])
            if not words:
                continue
            base = base_words(words)
            if set(words) <= course_set:
                score = 1.0 + len(words) / 100
            elif base != words and set(base) <= course_set and not course_numeral:
                score = 0.92 + len(base) / 100  # the series without its number
            else:
                score = SequenceMatcher(None, " ".join(words), course_text).ratio()
            score += 0.05 if same_term else 0
            if taken is not None and subject["elective"]:
                score += 0.03 if subject_key(sem, subject) in taken else -0.03
            if score > best_score:
                best, best_score = (sem, subject), score
    return best if best_score >= MATCH_THRESHOLD else None


def module_entry(subject: dict) -> dict:
    """A whole elective module as an assignable 'subject' (e.g. a course from another university)."""
    return {"name": subject["module"], "card": None, "elective": False, "module": None, "is_module": True}


def _find_subject(plan: list[dict], name: str) -> tuple[dict, dict] | None:
    """A subject - or an elective module - by name (courses.json "plan")."""
    wanted = " ".join(_words(name))
    for sem in plan:
        for subject in sem["subjects"]:
            if " ".join(_words(subject["name"])) == wanted:
                return sem, subject
    for sem in plan:
        for subject in sem["subjects"]:
            if subject.get("module") and " ".join(_words(subject["module"])) == wanted:
                return sem, module_entry(subject)
    return None


def narrow_module(found: tuple[dict, dict] | None, taken: set | None) -> tuple[dict, dict] | None:
    """
    A course assigned to a whole module that has one option ("Language I" -> "English I"),
    or one option you picked, goes to that option - the same folder as its card.
    """
    if not found or not found[1].get("is_module"):
        return found
    sem, module = found
    options = [s for s in sem["subjects"] if s.get("module") == module["name"]]
    picked = [s for s in options if subject_key(sem, s) in (taken or set())]
    if len(picked) == 1:
        return sem, picked[0]
    if len(options) == 1 and not picked:
        return sem, options[0]
    return found


def find_by_key(plan: list[dict], key: str) -> tuple[dict, dict] | None:
    """The subject (or module) behind a subject_key, e.g. from /assign in the bot."""
    number, name, card = (key.split("|") + ["", ""])[:3]
    for sem in plan:
        if str(sem["number"]) != number:
            continue
        for subject in sem["subjects"]:
            if subject["name"] == name and str(subject["card"] or "") == card:
                return sem, subject
        for subject in sem["subjects"]:
            if subject.get("module") == name and not card:
                return sem, module_entry(subject)
    return None


def _override(cfg: dict, section: str, course_name: str):
    name = pick_language(course_name, config.moodle_content_language()).casefold()
    for fragment, value in cfg.get(section, {}).items():
        if fragment.casefold() in name:
            return value
    return None


def assign_courses(courses: list[dict], plan: list[dict] | None, cfg: dict, state: dict | None = None) -> dict:
    """
    Moodle course id -> {"semester": N or None, "subject": name from the plan or None,
    "card": card id or None, "key": subject key or None, "manual": bool}. Pure, given the
    plan. Order: your choice in the bot (/assign, state "course_map"), courses.json "plan",
    then automatic matching.
    """
    start = study_start()
    manual = (state or {}).get("course_map", {})
    taken = chosen_keys(plan, state) if plan and state else None
    out = {}
    for course in courses:
        name = course.get("fullname", "")
        term = term_of(course.get("startdate") or 0)
        found = None
        chosen = manual.get(str(course["id"]))
        if plan and chosen and chosen != "none":
            found = narrow_module(find_by_key(plan, chosen[0] if isinstance(chosen, list) else chosen), taken)
        elif plan and not chosen:
            forced = _override(cfg, "plan", name)
            found = _find_subject(plan, forced) if forced else match_subject(name, plan, term, taken)
        semester = _override(cfg, "semester", name)
        if semester is None and found:
            semester = found[0]["number"]
        if semester is None:
            semester = semester_by_term(term, plan, start)
        out[course["id"]] = {"semester": int(semester) if semester else None,
                             "subject": found[1]["name"] if found else None,
                             "card": found[1]["card"] if found else None,
                             "key": subject_key(*found) if found else None,
                             "manual": bool(chosen)}
    return out


def subject_key(sem: dict, subject: dict) -> str:
    """Semester + name + card: elective options can share a name ("Team project I" x10)."""
    return f"{sem['number']}|{subject['name']}|{subject['card'] or ''}"


def option_id(subject: dict) -> str:
    return str(subject["card"]) if subject["card"] else "name:" + subject["name"]


EXTERNAL = "__external__"  # an elective taken at another university


def module_key(sem: dict, subject: dict) -> str:
    return f"{sem['number']}|{subject['module']}"


def chosen_keys(plan: list[dict], state: dict) -> set:
    """Subjects picked in elective modules (bot: /electives), as subject keys."""
    picks = state.get("electives", {})
    return {subject_key(sem, subj) for sem in plan for subj in sem["subjects"]
            if subj["elective"] and (option_id(subj) in picks.get(module_key(sem, subj), [])
                                     or subj["name"] in picks.get(module_key(sem, subj), []))}


def elective_modules(plan: list[dict], courses: list[dict], cfg: dict, state: dict) -> list[dict]:
    """
    Elective modules: [{"key", "semester", "module", "options": [{"id", "name", "card"}], "chosen": [ids],
    "matched": [ids]}]. "matched" = alternatives you already have a Moodle course for (they count as
    chosen); a course assigned to the whole module (another university) counts too.
    """
    assigned = assign_courses(courses, plan, cfg, state).values()
    matched = {a["key"] for a in assigned if a["key"]}
    picks = state.get("electives", {})
    modules = {}
    for sem in plan:
        for subj in sem["subjects"]:
            if not subj["elective"]:
                continue
            key = module_key(sem, subj)
            m = modules.setdefault(key, {"key": key, "semester": sem["number"], "module": subj["module"] or "?",
                                         "options": [], "chosen": list(picks.get(key, [])), "matched": []})
            m["options"].append({"id": option_id(subj), "name": subj["name"], "card": subj["card"]})
            if subject_key(sem, subj) in matched:
                m["matched"].append(option_id(subj))
            if subject_key(sem, module_entry(subj)) in matched and EXTERNAL not in m["matched"]:
                m["matched"].append(EXTERNAL)
    return list(modules.values())


def cards_needed(plan: list[dict], courses: list[dict], cfg: dict, state: dict) -> list[tuple[str, str, str]]:
    """
    What you take but has no card in the catalogue - a subject without a published card, or
    an elective module you take at another university: [(key, label, current custom url or "")].
    """
    taken = chosen_keys(plan, state) | {a["key"] for a in assign_courses(courses, plan, cfg, state).values() if a["key"]}
    custom = state.get("custom_cards") or {}
    out = []
    for sem in plan:
        for subject in sem["subjects"]:
            key = subject_key(sem, subject)
            if subject["card"] is None and (not subject["elective"] or key in taken):
                out.append((key, f"{semester_folder(sem['number'])}: {readable(subject['name'])}",
                            custom.get(key, {}).get("url", "")))
    for m in elective_modules(plan, courses, cfg, state):
        if EXTERNAL in m["chosen"] or EXTERNAL in m["matched"]:
            key = f"{m['semester']}|{m['module']}|"
            out.append((key, f"{semester_folder(m['semester'])}: 🎓 {readable(m['module'])}",
                        custom.get(key, {}).get("url", "")))
    return out


def pending_modules(plan, courses, cfg, state) -> list[dict]:
    """Elective modules with nothing chosen yet - the bot asks about them."""
    return [m for m in elective_modules(plan, courses, cfg, state) if not m["chosen"] and not m["matched"]]


def shouting(name: str) -> bool:
    """Catalogues sometimes write subjects in CAPITALS - not a folder name anyone wants."""
    letters = [c for c in name if c.isalpha()]
    return len(letters) > 3 and sum(c.isupper() for c in letters) >= 0.8 * len(letters)


_ROMAN = re.compile(r"^(?:I|II|III|IV|V|VI|VII|VIII|IX|X)$")
_VOWELS = set("AEIOUYĄĘÓ")
# short words that look like acronyms in capitals but aren't
_PLAIN = {"i", "w", "z", "na", "do", "od", "po", "dla", "bez", "nad", "pod", "przy", "oraz", "ich", "jak", "big",
          "new", "the", "and", "for", "with", "of", "in", "on", "at", "to", "by", "kurs", "plan", "rok", "typ",
          "styl", "film", "test", "tryb", "las", "krew", "dziś", "dzis", "cel", "cele", "rola"}


# words the catalogue writes in capitals that aren't lower-case words either
_PROPER = {"python": "Python", "java": "Java", "javascript": "JavaScript", "linux": "Linux", "windows": "Windows",
           "excel": "Excel", "matlab": "MATLAB", "mathematica": "Mathematica", "github": "GitHub", "polska": "Polska",
           "europa": "Europa", "europejska": "Europejska", "gdańsk": "Gdańsk", "pomorze": "Pomorze"}


def readable(name: str) -> str:
    """
    'MACHINE LEARNING I SIECI NEURONOWE' -> 'Machine learning i sieci neuronowe',
    'LABORATORIUM DYPLOMOWE I' -> 'Laboratorium dyplomowe I', 'MODELOWANIE QSAR, QSPR' ->
    'Modelowanie QSAR, QSPR'. Names that aren't in capitals stay as they are.
    """
    if not shouting(name):
        return name
    words = name.split()
    out = []
    for i, word in enumerate(words):
        core = re.sub(r"[^\w]", "", word)
        roman = _ROMAN.match(core) and (i == len(words) - 1 or words[i + 1].startswith("("))
        acronym = (2 <= len(core) <= 4 and core.isupper() and core.lower() not in _PLAIN
                   and sum(c in _VOWELS for c in core) <= 1)
        mixed = any(c.islower() for c in core)  # "WCh" was written that way on purpose
        proper = _PROPER.get(core.lower())
        out.append(word if roman or acronym or mixed else word.lower().replace(core.lower(), proper)
                   if proper else word.lower())
    text = " ".join(out)
    return text[:1].upper() + text[1:]


def subject_folder(key: str | None, name: str, state: dict | None = None) -> str:
    """Folder of a subject: your own name for it (bot: /assign → ✏️) or the plan's name, readable."""
    return ((state or {}).get("folder_names") or {}).get(key or "") or readable(name)


def course_layout(courses: list[dict], cfg: dict, plan: list[dict] | None, state: dict | None = None) -> dict:
    """Moodle course id -> (semester folder or None, folder named after the plan's subject or None)."""
    folders = semester_folders_enabled()
    layout = {}
    for cid, a in assign_courses(courses, plan, cfg, state).items():
        layout[cid] = (semester_folder(a["semester"]) if folders and a["semester"] else None,
                       subject_folder(a["key"], a["subject"], state) if a["subject"] else None)
    return layout


def series_keys(plan: list[dict], sem: dict, subject: dict, taken: set) -> list[str]:
    """
    The other parts of a numbered series from the course's semester on ("Project I" in
    semester 1 -> "Project II" in semester 2): the part you picked in each semester, else
    the first one of that name.
    """
    base = base_words(_words(subject["name"]))
    if base == _words(subject["name"]):
        return []
    keys = []
    for other in plan:
        if other["number"] <= sem["number"]:
            continue
        parts = [s for s in other["subjects"] if base_words(_words(s["name"])) == base and s["name"] != subject["name"]]
        if parts:
            picked = [s for s in parts if subject_key(other, s) in taken]
            keys.append(subject_key(other, (picked or parts)[0]))
    return keys


def course_splits(courses: list[dict], plan: list[dict] | None, state: dict | None = None,
                  cfg: dict | None = None) -> dict:
    """
    Moodle courses used for several semesters: course id -> [(semester number, semester
    folder, subject folder)]; each file goes to the semester its date falls into. Either
    you assigned them so (/assign ➕), or the course matched part I of a numbered series
    ("Team project" -> "Team project I") that continues later ("Team project II").
    """
    folders = semester_folders_enabled()
    taken = chosen_keys(plan, state or {}) if plan else set()
    assigned = assign_courses(courses, plan, cfg or {}, state) if plan else {}
    splits = {}
    for course in courses:
        chosen = ((state or {}).get("course_map") or {}).get(str(course["id"]))
        if not plan:
            continue
        if isinstance(chosen, list):
            keys = chosen
        elif chosen is None and assigned[course["id"]]["key"] and not _override(cfg or {}, "plan", course["fullname"]):
            first = find_by_key(plan, assigned[course["id"]]["key"])
            keys = [assigned[course["id"]]["key"]] + series_keys(plan, *first, taken) if first else []
        else:
            continue
        if len(keys) < 2:
            continue
        options = []
        for key in keys:
            found = narrow_module(find_by_key(plan, key), taken)
            if found:
                sem, subject = found
                options.append((sem["number"], semester_folder(sem["number"]) if folders else None,
                                subject_folder(subject_key(sem, subject), subject["name"], state)))
        if len(options) > 1:
            splits[course["id"]] = sorted(options)
    return splits


def pick_by_date(options: list[tuple], timestamp: float, plan: list[dict]) -> tuple:
    """The (number, semester folder, folder) whose semester the date falls into; before the first -> the first."""
    number = semester_by_term(term_of(timestamp), plan, None)
    if number is not None:
        for option in options:
            if option[0] == number:
                return option
        if number > options[-1][0]:
            return options[-1]
    return options[0]


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

def planned_cards(courses: list[dict], plan: list[dict], cfg: dict, chosen: set | None = None,
                  missing: list | None = None, state: dict | None = None) -> dict:
    """
    Card id -> relative path of its PDF. Compulsory subjects of every semester,
    plus electives you have a Moodle course for or picked in /electives (nobody
    wants all fifteen alternatives). The folder is the same as for the
    course's Moodle files, so the card lands next to its materials. Subjects
    you take whose card isn't published are appended to `missing`.
    """
    lang = config.moodle_content_language()
    folders = semester_folders_enabled()
    assigned = assign_courses(courses, plan, cfg, state)
    by_card = {}  # card -> folder name of the matching Moodle course (courses.json "names" wins)
    taken = set(chosen or ()) | {a["key"] for a in assigned.values() if a["key"]}
    custom = (state or {}).get("custom_cards") or {}
    for course in courses:
        a = assigned[course["id"]]
        if a["card"]:
            # the same folder as the course's Moodle files (files.course_folder)
            by_card[a["card"]] = (_override(cfg, "names", course.get("fullname", ""))
                                  or subject_folder(a["key"], a["subject"], state))
    cards = {}
    for sem in plan:
        for subject in sem["subjects"]:
            if subject["elective"] and subject_key(sem, subject) not in taken:
                continue
            if subject["card"] is None:
                if missing is not None and subject_key(sem, subject) not in custom:
                    missing.append(f"{semester_folder(sem['number'])}: {readable(subject['name'])}")
                continue
            parts = [semester_folder(sem["number"])] if folders else []
            folder = by_card.get(subject["card"]) or subject_folder(subject_key(sem, subject), subject["name"], state)
            parts += [sanitize_component(folder, "Course", lang), card_filename()]
            cards[subject["card"]] = (Path(*parts), subject["name"])
    # your own links (bot: /card) - a subject without a published card, or one from another university
    for key, link in custom.items():
        found = find_by_key(plan, key)
        if not found:
            continue
        sem, subject = found
        parts = [semester_folder(sem["number"])] if folders else []
        name = Path(card_filename()).stem + link.get("ext", ".pdf")
        parts += [sanitize_component(subject_folder(key, subject["name"], state), "Course", lang), name]
        cards["custom:" + key] = (Path(*parts), subject["name"])
    return cards


def notify_once(state: dict, key: str, items: list, title_key: str) -> None:
    """A message about this exact list only once (e.g. cards still missing), again when the list changes."""
    if items and state.get(key) != items:
        notify("files", t(title_key, n=len(items)), bullet_list(items))
    state[key] = items


def card_url(card, state: dict | None = None) -> str:
    if isinstance(card, str) and card.startswith("custom:"):
        return ((state or {}).get("custom_cards") or {}).get(card[len("custom:"):], {}).get("url", "")
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
    courses = moodle.my_courses()
    missing = []
    cards = planned_cards(courses, plan, cfg, chosen_keys(plan, state), missing, state)
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
            data = _get(card_url(card, state)).content
            if not data.startswith(b"%PDF") and not str(card).startswith("custom:"):
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
        notify_once(state, "syllabi_missing", sorted(missing), "plan_cards_missing")
        pending = [f"{semester_folder(m['semester'])}: {readable(m['module'])}"
                   for m in pending_modules(plan, courses, cfg, state)]
        notify_once(state, "electives_pending", pending, "plan_electives_pending")
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
    st = state_mod.load()
    assigned = assign_courses(courses, plan, cfg, st)
    chosen = chosen_keys(plan, st) if plan else set()
    now_term = term_of(time.time())
    current = semester_by_term(now_term, plan, study_start())

    if plan:
        print(t("plan_header", url=plan_url()) + "\n")
        for sem in plan:
            mark = "  ← " + t("plan_now") if sem["number"] == current else ""
            season = t("plan_winter") if sem["season"] == "winter" else t("plan_summer")
            print(f"■ {semester_folder(sem['number'])}  ({sem['year']}/{sem['year'] + 1} {season}){mark}")
            for subject in sem["subjects"]:
                moodle_names = [course_display_name(c["fullname"], cfg) + (" ✋" if assigned[c["id"]]["manual"] else "")
                                for c in courses if assigned[c["id"]]["key"] == subject_key(sem, subject)]
                picked = subject_key(sem, subject) in chosen
                if subject["elective"] and not moodle_names and not picked:
                    continue
                tick = "✓ " + ", ".join(moodle_names) if moodle_names else "– " + t("plan_no_moodle")
                card = "" if subject["card"] else "  📄✗ " + t("plan_no_card")
                print(f"    {subject_folder(subject_key(sem, subject), subject['name'], st)}  [{tick}]{card}")
            for module in sorted({x["module"] for x in sem["subjects"] if x.get("module")}):
                key = f"{sem['number']}|{module}|"
                names = [course_display_name(c["fullname"], cfg) for c in courses if assigned[c["id"]]["key"] == key]
                if names:
                    print(f"    🎓 {subject_folder(key, module, st)}  [✓ {', '.join(names)}]")
            print()
    elif study_start():
        print(t("plan_by_dates", start=config.env("STUDY_START")) + "\n")
    else:
        print(t("plan_none"))
        return 2

    if plan:
        pending = pending_modules(plan, courses, cfg, st)
        if pending:
            print(t("plan_electives_pending", n=len(pending)) + ":")
            for m in pending:
                names = list(dict.fromkeys(readable(o["name"]) for o in m["options"]))
                print(f"    {semester_folder(m['semester'])}: {readable(m['module'])} – "
                      + ", ".join(names[:6]) + ("…" if len(names) > 6 else "") + f" ({len(m['options'])})")
            print("    " + t("plan_electives_hint") + "\n")
    loose = [c for c in courses if not assigned[c["id"]]["subject"]]
    if loose:
        print(t("plan_unmatched"))
        for c in loose:
            n = assigned[c["id"]]["semester"]
            where = semester_folder(n) if n else t("plan_no_semester")
            print(f"    {course_display_name(c['fullname'], cfg)}  -> {where}")
        print("    " + t("plan_assign_hint"))
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
