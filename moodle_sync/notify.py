"""
Notifications - sent to EVERY configured channel (all optional, combine freely):

    Telegram   TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID   (also supports commands - see telegram_bot.py)
    Discord    DISCORD_WEBHOOK_URL                     (channel webhook, notifications only)
    ntfy       NTFY_TOPIC [+ NTFY_SERVER]              (push app, no account needed)
    e-mail     SMTP_HOST, SMTP_USER, SMTP_PASSWORD [+ SMTP_PORT, EMAIL_TO, EMAIL_FROM]

Each kind can be switched off: NOTIFY_FILES, NOTIFY_DEADLINES,
NOTIFY_ANNOUNCEMENTS, NOTIFY_GRADES, NOTIFY_ERRORS, NOTIFY_SUMMARY (=0).

A notification failure must never break the sync - errors are only printed.
Setup guide: docs/*/notifications.md
"""

import html
import re
import smtplib
import ssl
from email.message import EmailMessage

import requests

from . import config

KIND_EMOJI = {
    "files": "📚", "deadlines": "📅", "announcements": "📢", "grades": "🎓",
    "errors": "🚨", "summary": "✅", "test": "🔔",
}
KIND_TAGS = {  # ntfy shows these as emoji
    "files": "books", "deadlines": "date", "announcements": "loudspeaker", "grades": "mortar_board",
    "errors": "rotating_light", "summary": "white_check_mark", "test": "bell",
}
TELEGRAM_LIMIT = 4096
DISCORD_LIMIT = 2000


def telegram_api() -> str:
    return f"https://api.telegram.org/bot{config.env('TELEGRAM_BOT_TOKEN')}"


def _redact(text: str) -> str:
    for key in ("TELEGRAM_BOT_TOKEN", "DISCORD_WEBHOOK_URL", "SMTP_PASSWORD", "HEALTHCHECK_URL"):
        secret = config.env(key)
        if secret:
            text = text.replace(secret, "***")
    return text


def channels() -> list[str]:
    """Names of the configured channels."""
    out = []
    if config.env("TELEGRAM_BOT_TOKEN") and config.env("TELEGRAM_CHAT_ID"):
        out.append("telegram")
    if config.env("DISCORD_WEBHOOK_URL"):
        out.append("discord")
    if config.env("NTFY_TOPIC"):
        out.append("ntfy")
    if config.env("SMTP_HOST") and config.env("SMTP_USER"):
        out.append("email")
    return out


# --- channels ------------------------------------------------------------------------------

def send_telegram_html(text: str, chat_id: str | None = None) -> bool:
    """Send ready HTML (parse_mode=HTML). Returns True on success."""
    chat_id = chat_id or config.env("TELEGRAM_CHAT_ID")
    if not (config.env("TELEGRAM_BOT_TOKEN") and chat_id):
        return False
    if len(text) > TELEGRAM_LIMIT:
        text = text[: TELEGRAM_LIMIT - 20] + "\n…"
    try:
        resp = requests.post(f"{telegram_api()}/sendMessage", timeout=15, json={
            "chat_id": chat_id, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True,
        })
        if resp.status_code == 400 and "parse" in resp.text:
            # HTML broken (e.g. cut inside a tag or &entity;): deliver it as plain text rather than not at all
            plain = html.unescape(re.sub(r"<[^>]*>?", "", text))
            resp = requests.post(f"{telegram_api()}/sendMessage", timeout=15, json={
                "chat_id": chat_id, "text": plain, "disable_web_page_preview": True,
            })
        if resp.status_code != 200:
            print(f"[telegram] HTTP {resp.status_code} {resp.text[:200]}")
            return False
        return True
    except requests.RequestException as e:
        print(f"[telegram] {_redact(str(e))}")
        return False


def _send_discord(title: str, message: str, emoji: str) -> bool:
    text = f"{emoji} **{title}**\n{message}".strip()
    if len(text) > DISCORD_LIMIT:
        text = text[: DISCORD_LIMIT - 2] + "\n…"
    try:
        # allowed_mentions: forum posts may contain @everyone - never ping anyone.
        resp = requests.post(config.env("DISCORD_WEBHOOK_URL"), timeout=15,
                             json={"content": text, "allowed_mentions": {"parse": []}})
        if resp.status_code >= 300:
            print(f"[discord] HTTP {resp.status_code} {resp.text[:200]}")
            return False
        return True
    except requests.RequestException as e:
        print(f"[discord] {_redact(str(e))}")
        return False


def _send_ntfy(title: str, message: str, kind: str, urgent: bool) -> bool:
    # JSON publishing, because HTTP headers (Title:) don't like non-ASCII letters.
    payload = {
        "topic": config.env("NTFY_TOPIC"), "title": title, "message": message[:3900] or title,
        "tags": [KIND_TAGS.get(kind, "bell")], "priority": 4 if urgent else 3,
    }
    try:
        requests.post(config.env("NTFY_SERVER", "https://ntfy.sh").rstrip("/"), json=payload,
                      timeout=10).raise_for_status()
        return True
    except requests.RequestException as e:
        print(f"[ntfy] {e}")
        return False


def _send_email(title: str, message: str) -> bool:
    user = config.env("SMTP_USER")
    msg = EmailMessage()
    msg["Subject"] = f"[moodle-sync] {title}"
    msg["From"] = config.env("EMAIL_FROM", user)
    msg["To"] = config.env("EMAIL_TO", user)
    msg.set_content(message or title)
    host, port = config.env("SMTP_HOST"), config.env_int("SMTP_PORT", 587)
    try:
        if port == 465:
            server = smtplib.SMTP_SSL(host, port, context=ssl.create_default_context(), timeout=20)
        else:
            server = smtplib.SMTP(host, port, timeout=20)
            server.starttls(context=ssl.create_default_context())
        with server:
            server.login(user, config.env("SMTP_PASSWORD"))
            server.send_message(msg)
        return True
    except (smtplib.SMTPException, OSError) as e:
        print(f"[email] {_redact(str(e))}")
        return False


# --- public API ------------------------------------------------------------------------------

def notify(kind: str, title: str, message: str = "", urgent: bool = False) -> None:
    """Send a notification of the given kind to all configured channels."""
    if kind != "test" and not config.env_bool(f"NOTIFY_{kind.upper()}", True):
        return
    emoji = KIND_EMOJI.get(kind, "🔔")
    for channel in channels():
        if channel == "telegram":
            text = f"{emoji} <b>{html.escape(title)}</b>"
            if message:
                text += "\n" + html.escape(message)
            send_telegram_html(text)
        elif channel == "discord":
            _send_discord(title, message, emoji)
        elif channel == "ntfy":
            _send_ntfy(title, message, kind, urgent)
        elif channel == "email":
            _send_email(title, message)


def bullet_list(lines: list[str], limit: int = 12) -> str:
    shown = [f"• {line}" for line in lines[:limit]]
    if len(lines) > limit:
        shown.append(f"… (+{len(lines) - limit})")
    return "\n".join(shown)
