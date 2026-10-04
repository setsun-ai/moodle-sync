"""
Step 3: deadlines from Moodle -> Google Calendar.

Where events come from: Moodle creates calendar events for activities with
dates - assignment due ('due'), quiz open/close ('open'/'close'), attendance
sessions ('attendance') - plus events added by teachers ('course', 'group').
Dates mentioned only in text (a forum post, a PDF) are NOT events - the
"watch" step forwards announcements for that.

Where they go: two separate Google calendars, created on the first run:
  "<SITE_LABEL> – deadlines"  everything except attendance, with reminders
  "<SITE_LABEL> – classes"    attendance sessions (your timetable, no
                              reminders) - hide it with one click
Only calendars created by this app are accessible (scope
calendar.app.created) - it can't see your main calendar.

Sync: every Moodle event gets a fixed Google id ("pgmoodle<id>") and a
fingerprint of its content in state.json, so unchanged events cost no API
calls, a moved deadline is updated in place, and an event deleted in Moodle
is deleted in Google. Submitted assignments / finished quizzes get a ✅ and
lose their reminders.

Other calendars (Outlook, Apple): use the subscription URL printed by
`python -m moodle_sync ics` - no Google needed (updates are slower).
"""

import hashlib
import html
import json
import re
import time
from datetime import datetime, timezone

from . import config, moodle, state as state_mod
from .files import course_display_name
from .i18n import t
from .notify import bullet_list, notify
from .textutil import clean_text

SKIPPED = 2
SCOPES = ["https://www.googleapis.com/auth/calendar.app.created"]
API = "https://www.googleapis.com/calendar/v3"

# Sync window. A bit of the past, so a deadline moved backwards is updated too.
PAST_DAYS = 30
FUTURE_DAYS = 365

# Reminders in minutes before the event, per Moodle eventtype.
REMINDERS = {"open": [60], "attendance": []}
DEFAULT_REMINDERS = [24 * 60, 120]  # deadlines: a day before and 2 h before
TYPE_ICONS = {"due": "⏰", "close": "⏰", "open": "▶"}

# "To do" events: we can tell whether you've already dealt with them.
DONE_CHECK_TYPES = {"due", "close"}
DONE_CHECK_MODULES = {"assign", "quiz"}


# Online classes: links to these are put into the event's location (clickable in Google Calendar).
MEETING_LINK = re.compile(r"https?://[^\s\"'<>]*(?:teams\.microsoft\.com|teams\.live\.com|zoom\.us|meet\.google\.com|"
                          r"webex\.com|meet\.jit\.si|clickmeeting|whereby\.com|bigbluebutton|/mod/bigbluebuttonbn/|"
                          r"/mod/zoom/|/mod/teams/|/mod/googlemeet/|/mod/jitsi/)[^\s\"'<>]*", re.I)
MEETING_MODULES = {"bigbluebuttonbn", "zoom", "teams", "googlemeet", "jitsi", "webex", "msteams"}


def meeting_link(e: dict, module_urls: dict | None = None) -> str | None:
    """A link to join an online class: from the event's description, or the meeting activity itself."""
    m = MEETING_LINK.search(html.unescape(e.get("description") or ""))
    if m:
        return m.group(0).rstrip(".,);")
    if e.get("modulename") in MEETING_MODULES:
        return (module_urls or {}).get(f"{e['modulename']}:{e.get('instance')}")
    return None


def calendar_names() -> dict:
    return {
        "deadlines": f"{config.site_label()} – {t('cal_deadlines')}",
        "classes": f"{config.site_label()} – {t('cal_classes')}",
    }


# --- Moodle side ------------------------------------------------------------------------

def fetch_events(courses: list, past_days: int = PAST_DAYS, future_days: int = FUTURE_DAYS) -> list:
    now = int(time.time())
    params = {
        "options[userevents]": 1,
        "options[siteevents]": 1,
        "options[timestart]": now - past_days * 86400,
        "options[timeend]": now + future_days * 86400,
    }
    for i, c in enumerate(courses):
        params[f"events[courseids][{i}]"] = c["id"]
    events = moodle.call("core_calendar_get_calendar_events", **params).get("events", [])
    events = [e for e in events if e.get("visible", 1)]
    if not config.env_bool("SYNC_CLASSES", True):
        events = [e for e in events if e.get("eventtype") != "attendance"]
    return events


def fetch_open_action_ids(past_days: int = PAST_DAYS) -> set | None:
    """
    Ids of events still waiting for your action - what Moodle's "Timeline"
    block shows. A submitted assignment / finished quiz disappears from this
    list, so a due/close event that is NOT here is considered done.
    None = couldn't fetch (then nothing is marked as done).
    """
    ids, after = set(), None
    try:
        while True:
            params = {"timesortfrom": int(time.time()) - past_days * 86400, "limitnum": 50}
            if after:
                params["aftereventid"] = after
            events = moodle.call("core_calendar_get_action_events_by_timesort", **params).get("events", [])
            ids.update(e["id"] for e in events)
            if len(events) < 50:
                return ids
            after = events[-1]["id"]
    except Exception as e:
        print(t("cal_timeline_failed", error=e))
        return None


def is_done(e: dict, open_ids: set | None) -> bool | None:
    """True/False for assignments and quizzes, None when not applicable or unknown."""
    if e.get("eventtype") not in DONE_CHECK_TYPES or e.get("modulename") not in DONE_CHECK_MODULES:
        return None
    if open_ids is None:
        return None
    return e["id"] not in open_ids


def course_label(course: dict | None, cfg: dict | None = None) -> str:
    if not course:
        return config.site_label()
    name = course_display_name(course["fullname"], cfg)
    return name if len(name) <= 40 else name[:39].rstrip() + "…"


def upcoming_deadlines(days: int = 14) -> list[tuple[int, str, bool | None]]:
    """Upcoming deadlines straight from Moodle (no Google): [(timestamp, text, done?), ...]."""
    courses = moodle.my_courses()
    by_id = {c["id"]: c for c in courses}
    cfg = config.load_courses_config()
    open_ids = fetch_open_action_ids(past_days=0)
    lang = config.moodle_content_language()
    now = time.time()
    out = []
    for e in fetch_events(courses, past_days=0, future_days=days):
        if e.get("eventtype") == "attendance" or e["timestart"] < now:
            continue
        label = course_label(by_id.get(e.get("courseid")), cfg)
        out.append((e["timestart"], f"[{label}] {clean_text(e['name'], lang)}", is_done(e, open_ids)))
    return sorted(out)


# --- event building ------------------------------------------------------------------------

def rfc3339(ts: int) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat().replace("+00:00", "Z")


def build_event(e: dict, courses_by_id: dict, done: bool | None = None, cfg: dict | None = None,
                module_urls: dict | None = None) -> tuple[str, dict]:
    """(calendar key, Google event body) for a Moodle event."""
    etype = e.get("eventtype", "")
    course = courses_by_id.get(e.get("courseid"))
    calendar = "classes" if etype == "attendance" else "deadlines"
    lang = config.moodle_content_language()
    base = config.moodle_base_url()

    icon = "✅" if done else TYPE_ICONS.get(etype, "")  # done: nothing left to remind about
    summary = f"{icon} [{course_label(course, cfg)}] {clean_text(e['name'], lang)}".strip()

    start = e["timestart"]
    # A deadline is a point in time (timeduration = 0) -> a zero-length event
    # shown exactly at the deadline.
    end = start + (e.get("timeduration") or 0)

    course_url = f"{base}/course/view.php?id={course['id']}" if course else base
    join = meeting_link(e, module_urls)
    description = "\n\n".join(part for part in [
        f"🔗 {t('cal_join')}: {join}" if join else "",
        clean_text(e.get("description", ""), lang),
        f"{t('cal_course')}: {clean_text(course['fullname'], lang)}" if course else "",
        f"Moodle: {base}/calendar/view.php?view=day&time={start}",
    ] if part)

    minutes = [] if done else REMINDERS.get(etype, DEFAULT_REMINDERS)
    body = {
        "summary": summary,
        "description": description,
        "start": {"dateTime": rfc3339(start), "timeZone": config.timezone_name()},
        "end": {"dateTime": rfc3339(end), "timeZone": config.timezone_name()},
        "reminders": {"useDefault": False, "overrides": [{"method": "popup", "minutes": m} for m in minutes]},
        # A deadline doesn't take time - don't block the slot in free/busy.
        "transparency": "opaque" if calendar == "classes" else "transparent",
        "source": {"title": "Moodle", "url": course_url},
        "status": "confirmed",
    }
    if join:
        body["location"] = join  # Google Calendar shows it as a link at the top of the event
    return calendar, body


def fingerprint(calendar: str, body: dict) -> str:
    return hashlib.sha1(json.dumps([calendar, body], sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def google_event_id(moodle_id) -> str:
    # Google requires base32hex characters (a-v, 0-9), 5-1024 chars.
    # The "pgmoodle" prefix is kept for compatibility with version 1.
    return f"pgmoodle{moodle_id}"


# --- Google side --------------------------------------------------------------------------

def authorize() -> int:
    """One-time Google login in the browser -> google_token.json."""
    from google_auth_oauthlib.flow import InstalledAppFlow

    if not config.CLIENT_SECRET_FILE.exists():
        print(t("cal_no_client_secret", file=config.CLIENT_SECRET_FILE))
        return 1
    flow = InstalledAppFlow.from_client_secrets_file(str(config.CLIENT_SECRET_FILE), SCOPES)
    creds = flow.run_local_server(port=0, prompt="consent")
    config.GOOGLE_TOKEN_FILE.write_text(creds.to_json(), encoding="utf-8")
    print(t("cal_authorized", file=config.GOOGLE_TOKEN_FILE.name))
    return 0


def google_session():
    from google.auth.transport.requests import AuthorizedSession
    from google.oauth2.credentials import Credentials

    creds = Credentials.from_authorized_user_file(str(config.GOOGLE_TOKEN_FILE), SCOPES)
    return AuthorizedSession(creds)


def ensure_calendars(session, cal_state: dict) -> tuple[dict, set]:
    """
    Our two calendars: (ids, keys of calendars created just now). A calendar is
    (re)created only when Google says it's gone (404/410, e.g. deleted by hand) -
    any other error (expired login, Google hiccup) is raised, never answered with
    a duplicate "<SITE_LABEL> – deadlines" calendar.
    """
    ids = cal_state.setdefault("calendars", {})
    created = set()
    for key, name in calendar_names().items():
        cal_id = ids.get(key)
        if cal_id:
            resp = session.get(f"{API}/calendars/{cal_id}")
            if resp.status_code == 200:
                continue
            if resp.status_code not in (404, 410):
                resp.raise_for_status()
        resp = session.post(f"{API}/calendars", json={"summary": name, "timeZone": config.timezone_name()})
        resp.raise_for_status()
        ids[key] = resp.json()["id"]
        created.add(key)
        print(t("cal_created", name=name))
    return ids, created


def upsert_event(session, cal_id: str, event_id: str, body: dict) -> None:
    resp = session.post(f"{API}/calendars/{cal_id}/events", json={"id": event_id, **body})
    if resp.status_code == 409:
        # Already exists (or was deleted by hand and is 'cancelled') -
        # PUT overwrites it and restores status 'confirmed'.
        resp = session.put(f"{API}/calendars/{cal_id}/events/{event_id}", json=body)
    resp.raise_for_status()


def delete_event(session, cal_id: str, event_id: str) -> None:
    resp = session.delete(f"{API}/calendars/{cal_id}/events/{event_id}")
    if resp.status_code not in (200, 204, 404, 410):
        resp.raise_for_status()


def status() -> tuple[bool, str]:
    if not config.GOOGLE_TOKEN_FILE.exists():
        return False, t("cal_not_configured")
    try:
        import google.auth  # noqa: F401
    except ImportError:
        return False, t("cal_no_libs")
    return True, ", ".join(calendar_names().values())


# --- main -------------------------------------------------------------------------------

def run(dry_run: bool = False) -> int:
    if not dry_run:
        ok, reason = status()
        if not ok:
            print(reason)
            return SKIPPED

    courses = moodle.my_courses()
    courses_by_id = {c["id"]: c for c in courses}
    cfg = config.load_courses_config()
    events = fetch_events(courses)
    open_ids = fetch_open_action_ids()

    state = state_mod.load()
    cal_state = state.setdefault("calendar", {})
    known = cal_state.setdefault("events", {})  # moodle id -> {fp, cal, start, done, added}

    session = cal_ids = None
    if not dry_run:
        # Checked every run (2 cheap requests): a calendar deleted by hand in Google
        # is recreated and refilled right away, not only when something changes in Moodle.
        session = google_session()
        cal_ids, created = ensure_calendars(session, cal_state)
        for entry in known.values():
            if entry["cal"] in created:
                entry["fp"] = ""  # upload again; same start -> no "new deadline" notification

    to_upsert, fetched_ids = [], set()
    for e in events:
        mid = str(e["id"])
        fetched_ids.add(mid)
        prev = known.get(mid)
        done = is_done(e, open_ids)
        if done is None and open_ids is None and prev:
            done = prev.get("done")  # timeline unavailable - keep the previous state
        cal, body = build_event(e, courses_by_id, done, cfg, state.get("module_urls"))
        fp = fingerprint(cal, body)
        if prev is None or prev["fp"] != fp:
            to_upsert.append((mid, cal, body, fp, prev, done))

    # Gone from Moodle but inside the window we just fetched -> deleted there.
    # Older entries are just forgotten (they stay in Google as history).
    window_start = time.time() - PAST_DAYS * 86400
    to_delete = [mid for mid, en in known.items() if mid not in fetched_ids and en["start"] >= window_start]
    for mid in [mid for mid, en in known.items() if mid not in fetched_ids and en["start"] < window_start]:
        del known[mid]

    print(t("cal_summary", events=len(events), upsert=len(to_upsert), delete=len(to_delete)))
    names = calendar_names()

    if dry_run:
        for _mid, cal, body, _fp, prev, _done in to_upsert:
            start = datetime.fromisoformat(body["start"]["dateTime"].replace("Z", "+00:00")).astimezone()
            print(f"  {'+' if prev is None else '~'} {names[cal]:<22} {start:%Y-%m-%d %H:%M}  {body['summary']}")
        print("\n" + t("dry_run_note"))
        return 0

    if not to_upsert and not to_delete:
        state_mod.save(state)
        return 0

    failed, new_deadlines, moved_deadlines = 0, [], []
    for mid, cal, body, fp, prev, done in to_upsert:
        try:
            if prev and prev["cal"] != cal:  # the event changed calendars
                delete_event(session, cal_ids[prev["cal"]], google_event_id(mid))
            upsert_event(session, cal_ids[cal], google_event_id(mid), body)
        except Exception as ex:  # one bad event must not stop the rest
            failed += 1
            print("  " + t("error", error=f"{body['summary']}: {ex}"))
            continue
        start_ts = datetime.fromisoformat(body["start"]["dateTime"].replace("Z", "+00:00")).timestamp()
        known[mid] = {"fp": fp, "cal": cal, "start": start_ts, "done": done,
                      "added": prev.get("added") if prev else int(time.time())}
        print(f"  {'+' if prev is None else '~'} {body['summary']}")
        # Notify only about future, not-yet-done deadlines: new, or with a changed time.
        if cal == "deadlines" and start_ts > time.time() and not done:
            when = datetime.fromtimestamp(start_ts).strftime("%d.%m %H:%M")
            if prev is None:
                new_deadlines.append(f"{when}  {body['summary']}")
            elif prev["start"] != start_ts:
                moved_deadlines.append(f"{when}  {body['summary']}")

    for mid in to_delete:
        try:
            delete_event(session, cal_ids[known[mid]["cal"]], google_event_id(mid))
        except Exception as ex:
            failed += 1
            print("  " + t("error", error=ex))
            continue
        del known[mid]

    state_mod.save(state)
    if new_deadlines:
        notify("deadlines", t("notify_new_deadlines", n=len(new_deadlines)), bullet_list(new_deadlines))
    if moved_deadlines:
        notify("deadlines", t("notify_moved_deadlines", n=len(moved_deadlines)), bullet_list(moved_deadlines),
               urgent=True)
    return 1 if failed else 0


def ics_url() -> int:
    """
    Print the personal calendar subscription URL (for Outlook, Apple Calendar,
    Thunderbird...). It contains a secret key - treat it like a password.
    """
    info = moodle.site_info()
    data = moodle.call("core_calendar_get_calendar_export_token")
    token = data.get("token")
    if not token:
        print(t("ics_unavailable"))
        return 1
    url = (f"{config.moodle_base_url()}/calendar/export_execute.php?userid={info['userid']}"
           f"&authtoken={token}&preset_what=all&preset_time=recentupcoming")
    print(t("ics_intro") + "\n\n" + url + "\n")
    return 0
