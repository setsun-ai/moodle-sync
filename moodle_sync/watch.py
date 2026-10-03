"""
Step 4: new forum ANNOUNCEMENTS and new GRADES -> notification.

Announcements: teachers post things that are not calendar events there -
test dates, room changes, cancelled classes. We watch forums of type "news"
(the course "Announcements" forum) plus general forums whose name looks like
announcements; student discussion forums are skipped (WATCH_ALL_FORUMS=1
changes that).

Grades: many sites hide the gradebook report from
students (gradereport_* -> nopermissiontoviewgrades), but an assignment's
grade and teacher feedback are visible in its submission status, and a
quiz's result in mod_quiz_get_user_best_grade.

The first run only remembers the current state (no flood of notifications
about old posts/grades). Checks are less frequent than for files - forums
every 30 min, grades every hour (already graded ones once a day, in case of a
correction) - to keep the load on the university server low.
"""

import html
import re
import time

import requests

from . import config, moodle, state as state_mod
from .files import course_display_name
from .i18n import t
from .notify import notify
from .textutil import clean_text, shorten

FORUM_INTERVAL = 30 * 60
GRADES_INTERVAL = 60 * 60
GRADED_RECHECK = 24 * 3600
DISCUSSIONS_PER_FORUM = 10
ANNOUNCEMENT_NAME = re.compile(r"og[łl]osz|announc|komunikat|informacj|news", re.I)
SORT_CREATED_DESC = 3  # mod_forum: newest discussions first
NETWORK_ERRORS = (moodle.MoodleError, requests.RequestException)


def plain_grade(text: str) -> str:
    """'90,00&nbsp;/&nbsp;100,00' -> '90 / 100'"""
    text = html.unescape(re.sub(r"<[^>]+>", "", text or "")).replace("\xa0", " ")
    return re.sub(r"[,.]00\b", "", text).strip()


def _course_name(courses_by_id: dict, course_id: int, cfg: dict) -> str:
    c = courses_by_id.get(course_id)
    return course_display_name(c["fullname"], cfg) if c else config.site_label()


# --- announcements ---------------------------------------------------------------------

def check_forums(courses: list, courses_by_id: dict, section: dict, cfg: dict, dry_run: bool) -> int:
    seen = section.setdefault("seen", {})
    first_run = not section.get("initialized")
    lang = config.moodle_content_language()
    watch_all = config.env_bool("WATCH_ALL_FORUMS", False)
    forums = moodle.call("mod_forum_get_forums_by_courses",
                         **{f"courseids[{i}]": c["id"] for i, c in enumerate(courses)})
    watched = [f for f in forums if watch_all or f["type"] == "news" or ANNOUNCEMENT_NAME.search(f["name"])]

    # Forums whose existing discussions are already remembered. A forum seen for
    # the first time (first run, a new course, or WATCH_ALL_FORUMS switched on)
    # is remembered silently - otherwise all its old posts would look "new".
    known_forums = set(section.setdefault("forums_known", []))
    new = []
    for forum in watched:
        try:
            data = moodle.call("mod_forum_get_forum_discussions", forumid=forum["id"],
                               sortorder=SORT_CREATED_DESC, page=0, perpage=DISCUSSIONS_PER_FORUM)
        except NETWORK_ERRORS as e:
            print(f"[forum] {forum['name']}: {e}")
            continue
        forum_is_new = first_run or forum["id"] not in known_forums
        for d in data.get("discussions", []):
            key = str(d["discussion"])
            if key in seen:
                continue
            seen[key] = 0 if forum_is_new else int(time.time())  # 0 = existed before we started watching
            if not forum_is_new:
                new.append((forum, d))
        known_forums.add(forum["id"])
    section["forums_known"] = sorted(known_forums)

    for forum, d in sorted(new, key=lambda x: x[1]["created"]):
        course = _course_name(courses_by_id, forum["course"], cfg)
        title = f"[{course}] {clean_text(d.get('subject') or d.get('name'), lang)}"
        attachments = [a.get("filename") for a in d.get("attachments") or []]
        parts = [
            f"{d.get('userfullname', '')}, {time.strftime('%d.%m %H:%M', time.localtime(d['created']))}",
            shorten(clean_text(d.get("message", ""), lang), 1500),
            f"{t('attachments')}: {', '.join(attachments)}" if attachments else "",
            f"{config.moodle_base_url()}/mod/forum/discuss.php?d={d['discussion']}",
        ]
        print("  " + t("watch_announcement", title=title))
        if not dry_run:
            notify("announcements", title, "\n\n".join(p for p in parts if p), urgent=True)

    section["initialized"] = True
    if first_run:
        print("  " + t("watch_forums_baseline", n=len(seen)))
    return len(new)


# --- grades ------------------------------------------------------------------------------

def assignment_grade(assign_id: int) -> tuple[str, str]:
    """(grade, teacher's feedback comment) - empty strings when none."""
    status = moodle.call("mod_assign_get_submission_status", assignid=assign_id)
    feedback = status.get("feedback") or {}
    grade = plain_grade(feedback.get("gradefordisplay", ""))
    comment = ""
    for plugin in feedback.get("plugins") or []:
        if plugin.get("type") == "comments":
            for field in plugin.get("editorfields") or []:
                comment = clean_text(field.get("text", ""), config.moodle_content_language())
    return grade, comment


def quiz_grade(quiz: dict) -> str:
    best = moodle.call("mod_quiz_get_user_best_grade", quizid=quiz["id"])
    if not best.get("hasgrade"):
        return ""
    return f"{best['grade']:g} / {float(quiz.get('grade') or 0):g}"


def check_grades(courses: list, courses_by_id: dict, section: dict, cfg: dict, force: bool, dry_run: bool) -> int:
    items = section.setdefault("items", {})
    first_run = not section.get("initialized")
    now = time.time()
    lang = config.moodle_content_language()
    course_params = {f"courseids[{i}]": c["id"] for i, c in enumerate(courses)}

    targets = []  # (key, name, course id, fetch() -> (grade, comment))
    for c in moodle.call("mod_assign_get_assignments", **course_params).get("courses", []):
        for a in c.get("assignments", []):
            targets.append((f"assign:{a['id']}", a["name"], c["id"], lambda a=a: assignment_grade(a["id"])))
    try:
        quizzes = moodle.call("mod_quiz_get_quizzes_by_courses", **course_params).get("quizzes", [])
    except NETWORK_ERRORS as e:
        print(f"[quiz] {e}")
        quizzes = []
    for q in quizzes:
        targets.append((f"quiz:{q['id']}", q["name"], q["course"], lambda q=q: (quiz_grade(q), "")))

    changes = []
    for key, name, course_id, fetch in targets:
        prev = items.get(key, {})
        interval = GRADED_RECHECK if prev.get("grade") else GRADES_INTERVAL
        if not force and now - prev.get("checked", 0) < interval:
            continue
        try:
            grade, comment = fetch()
        except NETWORK_ERRORS as e:
            print(f"[grade] {name}: {e}")
            continue
        unchanged = grade == prev.get("grade")
        items[key] = {
            "grade": grade, "checked": int(now), "name": clean_text(name, lang),
            "course": _course_name(courses_by_id, course_id, cfg),
            "ts": prev.get("ts", 0) if unchanged or first_run else int(now),
        }
        if grade and not unchanged and not first_run:
            changes.append((course_id, name, grade, comment, prev.get("grade")))

    for course_id, name, grade, comment, old in changes:
        title = t("notify_grade_title", grade=grade, name=clean_text(name, lang))
        message = _course_name(courses_by_id, course_id, cfg)
        if old:
            message += "\n" + t("grade_previous", old=old)
        if comment:
            message += f"\n\n{t('grade_feedback')}:\n{shorten(comment, 1200)}"
        print("  " + title)
        if not dry_run:
            notify("grades", title, message, urgent=True)

    section["initialized"] = True
    if first_run:
        print("  " + t("watch_grades_baseline", n=len(items)))
    return len(changes)


def run(force: bool = False, dry_run: bool = False) -> int:
    courses = moodle.my_courses()
    courses_by_id = {c["id"]: c for c in courses}
    cfg = config.load_courses_config()
    state = state_mod.load()
    watch = state.setdefault("watch", {})
    now = time.time()
    failed = 0

    forums = watch.setdefault("forums", {})
    if force or now - forums.get("last_check", 0) >= FORUM_INTERVAL:
        try:
            n = check_forums(courses, courses_by_id, forums, cfg, dry_run)
            forums["last_check"] = int(now)
            print(t("watch_forums_result", n=n))
        except NETWORK_ERRORS as e:
            failed += 1
            print(t("watch_forums_result", n="?") + " " + t("error", error=e))
    else:
        print(t("watch_forums_recent"))

    try:
        n = check_grades(courses, courses_by_id, watch.setdefault("grades", {}), cfg, force, dry_run)
        print(t("watch_grades_result", n=n))
    except NETWORK_ERRORS as e:
        failed += 1
        print(t("watch_grades_result", n="?") + " " + t("error", error=e))

    if dry_run:
        print(t("dry_run_note"))
    else:
        state_mod.save(state)
    return 1 if failed else 0
