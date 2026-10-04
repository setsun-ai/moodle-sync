"""
The interactive part of the Telegram bot: buttons, files and short conversations.

    /courses /kursy        a course -> its sections -> what's in them (links to Drive / Moodle)
    /today   /dzis [N]     what appeared in your courses today (N days ago, "wczoraj", "12.10")
    a file                 submit it to an assignment (MOODLE_ACTIONS=1)
    /forum                 start a discussion in a forum (MOODLE_ACTIONS=1)
    /attendance /obecnosc  mark attendance; or send the link / a photo of the QR code (MOODLE_ACTIONS=1)

Nothing that changes Moodle happens without a "✅" tap on a summary of exactly
what will be sent. Only TELEGRAM_CHAT_ID is served (telegram_bot.py checks it).
"""

import html
import re
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path

import requests

from . import assignments, attendance, config, coursebrowse, moodle, notify
from .i18n import t
from .textutil import clean_text

LIMIT = 3900
STATE: dict = {}  # the bot serves one chat, so one conversation state


def esc(text) -> str:
    return html.escape(str(text))


def trim(text: str) -> str:
    return text if len(text) <= LIMIT else text[:LIMIT].rsplit("\n", 1)[0] + "\n…"


# --- Telegram ------------------------------------------------------------------------------

def api(method: str, **params) -> dict:
    resp = requests.post(f"{notify.telegram_api()}/{method}", json=params, timeout=60)
    data = resp.json()
    if not data.get("ok"):
        print(f"[telegram] {method}: {data.get('description', resp.status_code)}")
        return {}
    return data.get("result") or {}


def kb(rows: list) -> dict:
    """Rows of (text, callback data) - or (text, https://...) for a button that opens a page."""
    return {"inline_keyboard": [[{"text": text[:60], "url": data} if data.startswith("http")
                                 else {"text": text[:60], "callback_data": data[:64]} for text, data in row]
                                for row in rows if row]}


def send(chat: str, text: str, rows: list | None = None) -> int | None:
    params = {"chat_id": chat, "text": trim(text), "parse_mode": "HTML", "disable_web_page_preview": True}
    if rows:
        params["reply_markup"] = kb(rows)
    return api("sendMessage", **params).get("message_id")


def edit(chat: str, message_id: int, text: str, rows: list | None = None) -> None:
    params = {"chat_id": chat, "message_id": message_id, "text": trim(text), "parse_mode": "HTML",
              "disable_web_page_preview": True, "reply_markup": kb(rows or [])}
    api("editMessageText", **params)


def download(file_id: str) -> bytes:
    info = api("getFile", file_id=file_id)
    url = f"{notify.telegram_api().replace('/bot', '/file/bot', 1)}/{info['file_path']}"
    resp = requests.get(url, timeout=120)
    resp.raise_for_status()
    return resp.content


def actions_enabled() -> bool:
    return config.env_bool("MOODLE_ACTIONS", False)


def fail(chat: str, error: Exception) -> None:
    text = moodle.redact(notify._redact(str(error)))
    private = config.env("MOODLE_PRIVATE_TOKEN")
    if private:
        text = text.replace(private, "***")
    send(chat, "❌ " + esc(text[:500]))


# --- commands ------------------------------------------------------------------------------

COMMANDS = {"courses": "courses", "kursy": "courses", "today": "today", "dzis": "today", "dziś": "today",
            "forum": "forum", "attendance": "attendance", "obecnosc": "attendance", "obecność": "attendance",
            "submit": "submit", "oddaj": "submit"}


def handle_command(command: str, args: list[str], chat: str) -> bool:
    """True when the command is ours (the caller then sends nothing itself)."""
    kind = COMMANDS.get(command)
    if kind is None:
        return False
    STATE.clear()
    try:
        {"courses": show_courses, "today": lambda c: show_day(c, parse_day(args)),
         "forum": start_forum, "attendance": start_attendance, "submit": explain_submit}[kind](chat)
    except Exception as e:  # a command must never crash the bot
        fail(chat, e)
    return True


def parse_day(args: list[str]) -> int:
    """"" -> 0, "wczoraj"/"yesterday" -> 1, "3" -> 3 days ago, "12.10" -> that date."""
    if not args:
        return 0
    arg = args[0].lower()
    if arg in ("wczoraj", "yesterday"):
        return 1
    if arg.isdigit():
        return min(int(arg), 365)
    m = re.fullmatch(r"(\d{1,2})\.(\d{1,2})(?:\.(\d{4}))?", arg)
    if m:
        today = datetime.now()
        day = datetime(int(m.group(3) or today.year), int(m.group(2)), int(m.group(1)))
        return max(0, (today.date() - day.date()).days)
    return 0


# --- course preview ------------------------------------------------------------------------

def course_rows(courses: list[dict]) -> list:
    from .files import course_display_name

    cfg = config.load_courses_config()
    return [[(course_display_name(c["fullname"], cfg), f"c:{c['id']}")] for c in courses]


def show_courses(chat: str, message_id: int | None = None) -> None:
    rows = course_rows(moodle.my_courses())
    (edit(chat, message_id, t("ui_courses"), rows) if message_id else send(chat, t("ui_courses"), rows))


def course_name(course_id: int) -> str:
    from .files import course_display_name

    course = next((c for c in moodle.my_courses() if c["id"] == course_id), {"fullname": str(course_id)})
    return course_display_name(course["fullname"], config.load_courses_config())


def show_sections(chat: str, message_id: int, course_id: int) -> None:
    sections = coursebrowse.course_sections(course_id)
    lang = config.moodle_content_language()
    rows = [[(clean_text(s.get("name", ""), lang) or "—", f"s:{course_id}:{i}")]
            for i, s in enumerate(sections[:40])]
    rows.append([(t("ui_back"), "cl")])
    edit(chat, message_id, f"📘 <b>{esc(course_name(course_id))}</b>\n" + t("ui_sections"), rows)


def show_section(chat: str, message_id: int, course_id: int, index: int) -> None:
    sections = coursebrowse.course_sections(course_id)
    index = max(0, min(index, len(sections) - 1))
    text = coursebrowse.render_section(course_name(course_id), sections[index], coursebrowse.downloaded_paths(),
                                       coursebrowse.drive_links())
    nav = []
    if index > 0:
        nav.append(("◀", f"s:{course_id}:{index - 1}"))
    nav.append((t("ui_back"), f"c:{course_id}"))
    if index < len(sections) - 1:
        nav.append(("▶", f"s:{course_id}:{index + 1}"))
    edit(chat, message_id, text, [nav])


def show_day(chat: str, offset: int, message_id: int | None = None) -> None:
    from .files import course_display_name

    start, end, day = coursebrowse.day_bounds(offset)
    cfg = config.load_courses_config()
    contents = [(course_display_name(c["fullname"], cfg), moodle.course_contents(c["id"])) for c in moodle.my_courses()]
    blocks = coursebrowse.render_day(contents, start, end, coursebrowse.downloaded_paths(), coursebrowse.drive_links())
    title = t("ui_day", day=day.strftime("%d.%m.%Y"))
    text = title + "\n\n" + ("\n\n".join(blocks) if blocks else t("ui_day_empty"))
    nav = [("◀", f"d:{offset + 1}")] + ([("▶", f"d:{offset - 1}")] if offset > 0 else [])
    (edit(chat, message_id, text, [nav]) if message_id else send(chat, text, [nav]))


# --- submitting assignments -------------------------------------------------------------------

def explain_submit(chat: str) -> None:
    send(chat, t("ui_submit_help") if actions_enabled() else t("ui_actions_off"))


def on_document(msg: dict, chat: str) -> None:
    doc = msg["document"]
    if not actions_enabled():
        send(chat, t("ui_actions_off"))
        return
    STATE["file"] = {"id": doc["file_id"], "name": doc.get("file_name") or "file", "size": doc.get("file_size", 0)}
    if STATE.get("await") == "submit_file" and STATE.get("assign"):  # a corrected file for the chosen assignment
        check_and_confirm(chat, STATE["assign"])
        return
    assigns = assignments.open_assignments(moodle.my_courses())
    STATE["assigns"] = assigns
    if not assigns:
        send(chat, t("ui_no_assignments"))
        return
    rows = [[(f"{a['course']}: {clean_text(a['name'])}"
              + (f" ({datetime.fromtimestamp(a['duedate']):%d.%m})" if a.get("duedate") else ""), f"sa:{i}")]
            for i, a in enumerate(assigns[:15])]
    rows.append([(t("ui_cancel"), "x")])
    send(chat, t("ui_pick_assignment", file=esc(STATE["file"]["name"])), rows)


def check_and_confirm(chat: str, assign: dict) -> None:
    STATE["assign"] = assign
    f = STATE["file"]
    problems = assignments.check_file(assign, f["name"], f["size"])
    req = assignments.requirements(assign)
    if problems:
        parts = []
        if "nofiles" in problems:
            send(chat, t("ui_assign_nofiles"))
            return
        if "type" in problems:
            parts.append(t("ui_need_types", types=esc(assignments.types_text(assign))))
        if "size" in problems:
            parts.append(t("ui_need_size", size=assignments.human_size(req["max_bytes"])))
        STATE["await"] = "submit_file"
        send(chat, "⚠️ " + "\n".join(parts) + "\n" + t("ui_send_again"), [[(t("ui_cancel"), "x")]])
        return
    status = assignments.submission_status(assign["id"])
    if not status["can_edit"]:
        send(chat, t("ui_assign_locked"))
        return
    name = assignments.target_name(assign, assign["course"], f["name"])
    STATE["target"] = name
    lines = [t("ui_submit_confirm"), "",
             f"📎 <b>{esc(clean_text(assign['name']))}</b> – {esc(assign['course'])}"]
    if assign.get("duedate"):
        lines.append(t("ui_due", when=datetime.fromtimestamp(assign["duedate"]).strftime("%d.%m %H:%M")))
    lines.append(f"📄 {esc(name)} ({assignments.human_size(f['size'])})")
    if status["files"]:
        lines.append(t("ui_replaces", files=esc(", ".join(status["files"]))))
    STATE["await"] = None
    send(chat, "\n".join(lines), [[(t("ui_send"), "sok"), (t("ui_cancel"), "x")]])


def do_submit(chat: str, message_id: int) -> None:
    assign, f = STATE.get("assign"), STATE.get("file")
    if not assign or not f:
        edit(chat, message_id, t("ui_expired"))
        return
    edit(chat, message_id, t("ui_sending"))
    assignments.save(assign, STATE["target"], download(f["id"]))
    lines = [t("ui_submitted", name=esc(STATE["target"]))]
    rows = []
    if assign.get("submissiondrafts"):  # the teacher wants an explicit "submit for grading"
        lines.append(t("ui_draft_note"))
        rows = [[(t("ui_submit_grading"), "sg"), (t("ui_later"), "x")]]
    edit(chat, message_id, "\n".join(lines), rows)


def do_submit_grading(chat: str, message_id: int) -> None:
    assign = STATE.get("assign")
    if not assign:
        edit(chat, message_id, t("ui_expired"))
        return
    assignments.submit_for_grading(assign)
    edit(chat, message_id, t("ui_graded_sent"))
    STATE.clear()


# --- forum posts ---------------------------------------------------------------------------------

def start_forum(chat: str) -> None:
    if not actions_enabled():
        send(chat, t("ui_actions_off"))
        return
    rows = [[(text, data.replace("c:", "fc:"))] for [(text, data)] in course_rows(moodle.my_courses())]
    send(chat, t("ui_forum_course"), rows)


def show_forums(chat: str, message_id: int, course_id: int) -> None:
    forums = moodle.call("mod_forum_get_forums_by_courses", **{"courseids[0]": course_id}) or []
    STATE["forums"] = {f["id"]: f for f in forums}
    rows = [[(clean_text(f["name"]), f"ff:{f['id']}")] for f in forums]
    edit(chat, message_id, t("ui_forum_pick") if forums else t("ui_forum_none"), rows + [[(t("ui_cancel"), "x")]])


def pick_forum(chat: str, message_id: int, forum_id: int) -> None:
    allowed = moodle.call("mod_forum_can_add_discussion", forumid=forum_id)
    if not (allowed or {}).get("status"):
        edit(chat, message_id, t("ui_forum_denied"))
        return
    STATE["forum"], STATE["await"] = forum_id, "forum_subject"
    edit(chat, message_id, t("ui_forum_subject"), [[(t("ui_cancel"), "x")]])


def post_forum(chat: str, message_id: int) -> None:
    if not STATE.get("forum") or not STATE.get("subject") or not STATE.get("message"):
        edit(chat, message_id, t("ui_expired"))
        return
    body = "<p>" + esc(STATE["message"]).replace("\n", "<br>") + "</p>"
    moodle.call("mod_forum_add_discussion", forumid=STATE["forum"], subject=STATE["subject"], message=body)
    edit(chat, message_id, t("ui_forum_posted"))
    STATE.clear()


# --- attendance ------------------------------------------------------------------------------------

def links_only() -> bool:
    """Without MOODLE_ACTIONS or the private token the bot only opens attendance pages for you."""
    return not (actions_enabled() and config.env("MOODLE_PRIVATE_TOKEN"))


def start_attendance(chat: str) -> None:
    if links_only():  # the activities of your courses, one tap from Telegram
        modules = attendance.attendance_modules(moodle.my_courses())
        rows = [[(f"✋ {m['course']}: {m['name']}", m["url"])] for m in modules[:20]]
        send(chat, t("ui_att_open_pick") if rows else t("ui_att_no_modules"), rows)
        return
    send(chat, t("ui_att_searching"))
    sessions = attendance.today_sessions(moodle.my_courses())
    STATE["sessions"] = sessions
    if not sessions:
        send(chat, t("ui_att_none"))
        return
    rows = [[(f"{s['course']}: {s['label']}"[:60], f"at:{i}")] for i, s in enumerate(sessions[:15])]
    send(chat, t("ui_att_pick"), rows + [[(t("ui_cancel"), "x")]])


def open_attendance(chat: str, url: str, qrpass: str = "") -> None:
    if links_only():  # a page you open yourself: logged in as usual, the QR password already in the link
        send(chat, t("ui_att_open_link"), [[(t("ui_att_open"), url)]])
        return
    try:
        form, message, _final = attendance.open_session(url)
    except attendance.NotAvailable as e:
        send(chat, not_available(e))
        return
    if form is None:  # e.g. a QR link that marked attendance on its own, or an error page
        send(chat, "✋ " + esc(message or t("ui_att_no_form")))
        return
    STATE.clear()
    STATE.update(form=form, qrpass=qrpass)
    default = attendance.default_status(form["statuses"])
    ordered = sorted(form["statuses"], key=lambda s: s[0] != default)
    rows = [[(("✅ " if v == default else "") + label, f"as:{v}")] for v, label in ordered]
    send(chat, t("ui_att_status") + (f"\n<i>{esc(message)}</i>" if message else ""), rows + [[(t("ui_cancel"), "x")]])


def choose_status(chat: str, message_id: int, value: str) -> None:
    form = STATE.get("form")
    if not form:
        edit(chat, message_id, t("ui_expired"))
        return
    STATE["status"] = value
    if form["password"] and not STATE.get("qrpass"):
        STATE["await"] = "att_password"
        edit(chat, message_id, t("ui_att_password"), [[(t("ui_cancel"), "x")]])
        return
    confirm_attendance(chat, message_id)


def confirm_attendance(chat: str, message_id: int | None) -> None:
    form = STATE["form"]
    label = dict(form["statuses"]).get(STATE["status"], STATE["status"])
    text = t("ui_att_confirm", status=esc(label))
    rows = [[(t("ui_send"), "ao"), (t("ui_cancel"), "x")]]
    (edit(chat, message_id, text, rows) if message_id else send(chat, text, rows))


def do_attendance(chat: str, message_id: int) -> None:
    form = STATE.get("form")
    if not form or "status" not in STATE:
        edit(chat, message_id, t("ui_expired"))
        return
    ok, message = attendance.submit(form, STATE["status"], STATE.get("qrpass") or STATE.get("password", ""))
    edit(chat, message_id, ("✅ " if ok else "❌ ") + esc(message or t("ui_att_done" if ok else "ui_att_failed")))
    STATE.clear()


def decode_qr(data: bytes) -> str | None:
    """Text of a QR code in a photo (zbarimg from zbar-tools); None if none was found."""
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "qr.jpg"
        path.write_bytes(data)
        out = subprocess.run(["zbarimg", "--raw", "-q", str(path)], capture_output=True, text=True, timeout=30)
    return out.stdout.strip().splitlines()[0] if out.stdout.strip() else None


def on_photo(msg: dict, chat: str) -> None:
    photo = max(msg["photo"], key=lambda p: p.get("file_size", 0))
    try:
        text = decode_qr(download(photo["file_id"]))
    except FileNotFoundError:
        send(chat, t("ui_qr_no_tool"))
        return
    link = attendance.parse_link(text or "")
    if not link:
        send(chat, t("ui_qr_none"))
        return
    open_attendance(chat, link["url"], link["qrpass"])


# --- text replies and buttons ------------------------------------------------------------------

def on_text(msg: dict, chat: str) -> bool:
    """Free text: an attendance link, or the answer the bot is waiting for. True if handled."""
    text = msg["text"].strip()
    link = attendance.parse_link(text)
    if link:
        open_attendance(chat, link["url"], link["qrpass"])
        return True
    waiting = STATE.get("await")
    if waiting == "forum_subject":
        STATE["subject"], STATE["await"] = text[:200], "forum_message"
        send(chat, t("ui_forum_message"), [[(t("ui_cancel"), "x")]])
    elif waiting == "forum_message":
        STATE["message"], STATE["await"] = text, None
        preview = f"<b>{esc(STATE['subject'])}</b>\n{esc(text)}"
        send(chat, t("ui_forum_preview") + "\n\n" + preview, [[(t("ui_send"), "fp"), (t("ui_cancel"), "x")]])
    elif waiting == "att_password":
        try:  # the password doesn't stay in the chat
            api("deleteMessage", chat_id=chat, message_id=msg["message_id"])
        except requests.RequestException:
            pass
        STATE["password"], STATE["await"] = text, None
        confirm_attendance(chat, None)
    else:
        return False
    return True


def on_callback(cq: dict, chat: str) -> None:
    data = cq.get("data", "")
    message_id = cq.get("message", {}).get("message_id")
    try:
        api("answerCallbackQuery", callback_query_id=cq["id"])
    except requests.RequestException:
        pass
    kind, _, rest = data.partition(":")
    try:
        if data == "x":
            STATE.clear()
            edit(chat, message_id, t("ui_cancelled"))
        elif data == "cl":
            show_courses(chat, message_id)
        elif kind == "c":
            show_sections(chat, message_id, int(rest))
        elif kind == "s":
            course, index = rest.split(":")
            show_section(chat, message_id, int(course), int(index))
        elif kind == "d":
            show_day(chat, max(0, int(rest)), message_id)
        elif kind == "sa" and STATE.get("assigns") and STATE.get("file"):
            check_and_confirm(chat, STATE["assigns"][int(rest)])
        elif data == "sok":
            do_submit(chat, message_id)
        elif data == "sg":
            do_submit_grading(chat, message_id)
        elif kind == "fc":
            show_forums(chat, message_id, int(rest))
        elif kind == "ff":
            pick_forum(chat, message_id, int(rest))
        elif data == "fp":
            post_forum(chat, message_id)
        elif kind == "at" and STATE.get("sessions"):
            session = STATE["sessions"][int(rest)]
            open_attendance(chat, session["url"])
        elif kind == "as":
            choose_status(chat, message_id, rest)
        elif data == "ao":
            do_attendance(chat, message_id)
        else:
            edit(chat, message_id, t("ui_expired"))
    except attendance.NotAvailable as e:
        send(chat, not_available(e))
    except Exception as e:  # a button must never crash the bot
        fail(chat, e)


def not_available(e: Exception) -> str:
    return t("ui_att_autologin_wait") if str(e) == "autologin_wait" else t("ui_att_no_private")
