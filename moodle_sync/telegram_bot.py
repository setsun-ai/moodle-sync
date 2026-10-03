"""
Telegram bot: notifications are sent by notify.py; this module answers commands.

Commands (Polish and English aliases; only YOUR chat - TELEGRAM_CHAT_ID - is
answered, anything else is ignored without a reply):
    /deadlines  /terminy   upcoming deadlines (14 days) straight from Moodle, ✅ = done
    /new        /nowe      recently downloaded materials
    /grades     /oceny     latest grades
    /status                last run, free disk space, uptime
    /sync                  run the sync now
    /update                install the newest GitHub release (updater.py), then restart
    /rollback              back to the version before the last /update
    /help       /pomoc     list of commands

Uses long polling (getUpdates) - no public address or open router ports needed.
Setup: python -m moodle_sync bot --setup   (docs/*/notifications.md)
"""

import html
import json
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import requests

from . import __version__, config, notify, state as state_mod, updater
from .i18n import t, weekday

RUN_INTERVAL_MIN = 15  # only for display ("next run at ...")
STARTED = time.time()


def esc(text) -> str:
    return html.escape(str(text))


def fmt_when(ts: float) -> str:
    dt = datetime.fromtimestamp(ts)
    return f"{weekday(dt.weekday())} {dt:%d.%m %H:%M}"


# --- commands ---------------------------------------------------------------------------

def cmd_deadlines(chat_id: str) -> str:
    from .calendar_sync import upcoming_deadlines

    items = upcoming_deadlines(days=14)
    if not items:
        return "📅 " + esc(t("bot_no_deadlines"))
    lines = ["📅 <b>" + esc(t("bot_deadlines_header")) + "</b>"]
    for ts, text, done in items:
        lines.append(f"{'✅' if done else '⏰'} <b>{esc(fmt_when(ts))}</b>  {esc(text)}")
    return "\n".join(lines)


def cmd_new(chat_id: str) -> str:
    downloaded = state_mod.load().get("downloaded", {})
    recent = sorted((e for e in downloaded.values() if e.get("ts") and e.get("path")),
                    key=lambda e: e["ts"], reverse=True)[:12]
    if not recent:
        return "📚 " + esc(t("bot_no_new"))
    lines = ["📚 <b>" + esc(t("bot_new_header")) + "</b>"]
    for e in recent:
        parts = e["path"].split("/")
        lines.append(f"• {esc(fmt_when(e['ts']))} — <b>{esc(parts[0])}</b>: {esc(parts[-1])}")
    return "\n".join(lines)


def cmd_grades(chat_id: str) -> str:
    items = state_mod.load().get("watch", {}).get("grades", {}).get("items", {})
    graded = sorted((v for v in items.values() if v.get("grade")), key=lambda v: v.get("ts", 0), reverse=True)[:12]
    if not graded:
        return "🎓 " + esc(t("bot_no_grades"))
    lines = ["🎓 <b>" + esc(t("bot_grades_header")) + "</b>"]
    for v in graded:
        lines.append(f"• <b>{esc(v['grade'])}</b> — {esc(v.get('name', '?'))} <i>({esc(v.get('course', ''))})</i>")
    return "\n".join(lines)


def cmd_status(chat_id: str) -> str:
    state = state_mod.load()
    last = state.get("last_run")
    lines = ["🤖 <b>" + esc(t("bot_status_header")) + "</b>"]
    if last:
        lines.append(esc(t("bot_last_run", when=fmt_when(last["end"]), secs=int(last["end"] - last["start"]))))
        for step in last["steps"]:
            name, result = step[0], step[1]
            # version 1 stored [name, result] without the exit code
            code = step[2] if len(step) > 2 else (0 if result == "OK" else 2 if "pomini" in result else 1)
            icon = {0: "✅", 2: "⏭"}.get(code, "❌")
            lines.append(f"  {icon} {esc(name)}: {esc(result)}")
        next_run = last["end"] + RUN_INTERVAL_MIN * 60
        if next_run > time.time():
            lines.append(esc(t("bot_next_run", time=datetime.fromtimestamp(next_run).strftime("%H:%M"))))
    else:
        lines.append(esc(t("bot_never_ran")))
    files = sum(1 for e in state.get("downloaded", {}).values() if e.get("path"))
    lines.append(esc(t("bot_files_count", n=files)))
    usage = shutil.disk_usage(config.DATA_DIR)
    lines.append(esc(t("bot_disk", free=usage.free / 1e9, total=usage.total / 1e9)))
    try:
        up = float(Path("/proc/uptime").read_text().split()[0])
        lines.append(esc(t("bot_uptime", d=int(up // 86400), h=int(up % 86400 // 3600))))
    except OSError:
        pass  # not Linux
    return "\n".join(lines)


def cmd_sync(chat_id: str) -> str:
    notify.send_telegram_html("⏳ " + esc(t("bot_sync_started")), chat_id)
    proc = subprocess.run(
        [sys.executable, "-m", "moodle_sync", "run"], cwd=config.PROJECT_DIR,
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    if proc.returncode == 3:  # another run in progress (lock)
        return "⏳ " + esc(t("bot_sync_busy"))
    summary = proc.stdout.split("=== ")[-1].split("===", 1)[-1].strip() or proc.stdout[-1500:]
    icon = "✅" if proc.returncode == 0 else "❌"
    return f"{icon} <b>{esc(t('bot_sync_done'))}</b>\n{esc(summary)}"


def cmd_update(chat_id: str) -> str:
    from .runner import SingleInstance

    notify.send_telegram_html("🔎 " + esc(t("bot_update_checking")), chat_id)
    tag = updater.latest_release()
    if not updater.newer(tag):
        return "✅ " + esc(t("bot_update_latest", version=__version__))
    with SingleInstance() as lock:  # no sync may start while the code is being swapped
        if not lock.acquired:
            return "⏳ " + esc(t("bot_sync_busy"))
        notify.send_telegram_html("⬇️ " + esc(t("bot_update_installing", tag=tag, version=__version__)), chat_id)
        try:
            notes = updater.install(tag)
        except updater.UpdateError as e:
            return "❌ " + esc(t("bot_update_failed", version=__version__)) + f"\n<pre>{esc(e)}</pre>"
    updater.request_restart()
    return "🔄 " + esc(t("bot_update_restart", tag=tag)) + f"\n<pre>{esc(notes)}</pre>"


def cmd_rollback(chat_id: str) -> str:
    from .runner import SingleInstance

    with SingleInstance() as lock:
        if not lock.acquired:
            return "⏳ " + esc(t("bot_sync_busy"))
        version = updater.rollback()
    if version is None:
        return esc(t("bot_rollback_none"))
    updater.request_restart()
    return "↩️ " + esc(t("bot_rollback_restart", version=version))


def cmd_help(chat_id: str) -> str:
    return esc(t("bot_help"))


COMMANDS = {  # name -> (handler, i18n key of the description shown in Telegram's menu)
    "deadlines": (cmd_deadlines, "bot_cmd_deadlines"), "terminy": (cmd_deadlines, None),
    "new": (cmd_new, "bot_cmd_new"), "nowe": (cmd_new, None),
    "grades": (cmd_grades, "bot_cmd_grades"), "oceny": (cmd_grades, None),
    "status": (cmd_status, "bot_cmd_status"),
    "sync": (cmd_sync, "bot_cmd_sync"),
    "update": (cmd_update, "bot_cmd_update"), "rollback": (cmd_rollback, "bot_cmd_rollback"),
    "help": (cmd_help, "bot_cmd_help"), "pomoc": (cmd_help, None), "start": (cmd_help, None),
}
# Menu in Telegram: Polish names for Polish users, English otherwise.
MENU_NAMES = {"pl": ["terminy", "nowe", "oceny", "status", "sync", "update", "rollback", "pomoc"],
              "en": ["deadlines", "new", "grades", "status", "sync", "update", "rollback", "help"]}
MENU_DESCRIPTIONS = {"terminy": "bot_cmd_deadlines", "nowe": "bot_cmd_new", "oceny": "bot_cmd_grades",
                     "pomoc": "bot_cmd_help"}


def command_of(text: str) -> str:
    match = re.match(r"/(\w+)", text.strip())
    return match.group(1).lower() if match else ""


def handle(text: str, chat_id: str) -> str:
    command = command_of(text)
    handler = COMMANDS.get(command, (cmd_help, None))[0]
    try:
        return handler(chat_id)
    except Exception as e:  # a command must never crash the bot
        return "❌ " + esc(notify._redact(str(e)))[:500]


# --- loop and setup ------------------------------------------------------------------------

def get_updates(offset: int | None, timeout: int = 50) -> list:
    params = {"timeout": timeout, "allowed_updates": json.dumps(["message"])}
    if offset is not None:
        params["offset"] = offset
    resp = requests.get(f"{notify.telegram_api()}/getUpdates", params=params, timeout=timeout + 15)
    resp.raise_for_status()
    return resp.json().get("result", [])


def run() -> int:
    chat = config.env("TELEGRAM_CHAT_ID")
    if not (config.env("TELEGRAM_BOT_TOKEN") and chat):
        print(t("bot_not_configured"))
        return 2
    print(t("bot_running"), flush=True)
    try:
        register_menu()  # new commands appear in the menu after an update
    except requests.RequestException:
        pass
    offset = None
    while True:
        try:
            for update in get_updates(offset):
                offset = update["update_id"] + 1
                msg = update.get("message") or {}
                if str(msg.get("chat", {}).get("id", "")) != chat or not msg.get("text"):
                    continue  # someone else's chat or not text: ignore silently
                if time.time() - msg.get("date", 0) > 600:
                    continue  # command older than 10 min (bot was off) - don't execute it now
                if command_of(msg["text"]) in {"update", "rollback"} and msg.get("date", 0) < STARTED - 1:
                    continue  # sent before this process started: it already ran before the restart
                print(f"> {msg['text'][:40]}", flush=True)
                notify.send_telegram_html(handle(msg["text"], chat), chat)
                if updater.restart_requested():
                    try:
                        get_updates(offset, timeout=0)  # confirm, so Telegram doesn't deliver /update again
                    except (requests.RequestException, ValueError):
                        pass
                    updater.restart()
        except (requests.RequestException, ValueError) as e:  # ValueError: not JSON (e.g. a proxy error page)
            print(f"[telegram] {notify._redact(str(e))} - retry in 15 s", flush=True)
            time.sleep(15)


def register_menu() -> None:
    lang = config.language()
    commands = [{"command": name, "description": t(MENU_DESCRIPTIONS.get(name) or COMMANDS[name][1])[:256]}
                for name in MENU_NAMES[lang]]
    requests.post(f"{notify.telegram_api()}/setMyCommands", json={"commands": commands}, timeout=15)


def setup(wait_seconds: int = 180) -> int:
    """Find the user's chat id: they send any message to the bot, we save TELEGRAM_CHAT_ID."""
    if not config.env("TELEGRAM_BOT_TOKEN"):
        print(t("bot_need_token"))
        return 2
    me = requests.get(f"{notify.telegram_api()}/getMe", timeout=15)
    if me.status_code != 200:
        print(t("bot_bad_token"))
        return 1
    username = me.json()["result"]["username"]
    print(t("bot_send_message", username=username), flush=True)
    offset, deadline = None, time.time() + wait_seconds
    while time.time() < deadline:
        for update in get_updates(offset, timeout=20):
            offset = update["update_id"] + 1
            chat = (update.get("message") or {}).get("chat") or {}
            if chat.get("type") == "private":
                chat_id = str(chat["id"])
                config.set_env_var("TELEGRAM_CHAT_ID", chat_id)
                get_updates(offset, timeout=0)  # acknowledge received messages
                register_menu()
                notify.send_telegram_html(f"✅ <b>{esc(t('bot_connected'))}</b>\n\n{esc(t('bot_help'))}", chat_id)
                print(t("bot_setup_done", chat_id=chat_id))
                return 0
    print(t("bot_setup_timeout"))
    return 1
