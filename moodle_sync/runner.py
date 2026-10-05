"""
One full run: what the scheduler (systemd / Task Scheduler / launchd) starts.

    1. files      new files from Moodle -> DOWNLOAD_DIR
       syllabus   subject cards from the study plan (STUDY_PLAN_URL) -> DOWNLOAD_DIR
    2. storage    DOWNLOAD_DIR -> cloud (rclone) + backup of state.json
    3. calendar   deadlines -> Google Calendar (✅ = done)
    4. watch      new announcements and grades -> notifications

Steps are independent: a download error doesn't block uploading what's
already there, and a cloud problem doesn't block the calendar. A step that
isn't configured (no rclone, no Google token) is skipped - exit code 2 - so
the tool works from day one with whatever you've set up.

"Am I alive?":
  - on Sunday evening a weekly summary (what came in + deadlines for the
    coming week) - no summary on Sunday = something is wrong,
  - optionally healthchecks.io (HEALTHCHECK_URL): the service alerts YOU when
    the pings stop, e.g. when the Raspberry Pi dies.

Errors are notified, but the same error at most every ALERT_REPEAT_HOURS -
running every 15 minutes, an expired token must not flood your phone.
"""

import hashlib
import io
import os
import sys
import time
import traceback
from collections import deque
from contextlib import redirect_stdout
from datetime import datetime
from pathlib import Path

import requests

from . import calendar_sync, config, files, moodle, state as state_mod, storage, studyplan, watch
from .i18n import t, weekday
from .notify import _redact as notify_redact, bullet_list, notify

ALERT_REPEAT_HOURS = 6
WEEKLY_DAY, WEEKLY_HOUR = 6, 18  # Sunday, from 18:00
LOCK_BUSY = 3
LOG_MAX_BYTES = 1_000_000

# (i18n key of the step name, function) - each returns 0 ok / 1 error / 2 skipped
STEPS = [
    ("step_files", lambda: files.run()),
    ("step_syllabus", lambda: studyplan.run()),
    ("step_storage", lambda: storage.run()),
    ("step_calendar", lambda: calendar_sync.run()),
    ("step_watch", lambda: watch.run()),
]

# Recognisable causes -> what to do (notification text)
KNOWN_PROBLEMS = [
    ("--reorganize", "hint_mass_move"),
    ("invalidtoken", "hint_moodle_token"),
    ("MOODLE_TOKEN is not set", "hint_moodle_token"),
    ("invalid_grant", "hint_google_token"),
    ("couldn't fetch token", "hint_rclone_token"),
    ("Name or service not known", "hint_network"),
    ("Failed to resolve", "hint_network"),
    ("getaddrinfo failed", "hint_network"),
]


class SingleInstance:
    """Lock, so a manual run can't overlap with a scheduled one."""

    def __enter__(self):
        self.fh = open(config.LOCK_FILE, "a+")
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(self.fh.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self.fh.close()
            self.fh = None
        return self

    @property
    def acquired(self) -> bool:
        return self.fh is not None

    def __exit__(self, *exc):
        if self.fh:
            self.fh.close()  # closing the file releases the lock


class Tee(io.TextIOBase):
    """Print to the real stdout AND keep the last lines (for error notifications)."""

    def __init__(self, target):
        self.target = target
        self.tail = deque(maxlen=60)
        self._partial = ""

    def write(self, s):
        if self.target:
            self.target.write(s)
            self.target.flush()
        lines = (self._partial + s).split("\n")
        self._partial = lines.pop()
        self.tail.extend(line for line in lines if line.strip())
        return len(s)

    def text(self) -> str:
        return "\n".join([*self.tail, self._partial]).strip()


def redact(text: str) -> str:
    """Mask every configured secret: Moodle tokens and notification/healthcheck credentials.

    Step output ends up in logs/ and, through alert(), in error notifications, so tracebacks
    must not carry tokens (HTTP libraries put full URLs into exception messages).
    """
    return notify_redact(moodle.redact(text))


def run_step(func) -> tuple[int, str]:
    tee = Tee(sys.stdout)
    with redirect_stdout(tee):
        try:
            code = func()
        except moodle.NotConfigured as e:
            print(e)
            code = 1
        except Exception:
            print(redact(traceback.format_exc()))
            code = 1
    return code, tee.text()


def alert(state: dict, step: str, output: str) -> None:
    hint_key = next((key for needle, key in KNOWN_PROBLEMS if needle in output), None)
    # Error signature without digits (counters, times), so "the same" error stays the same.
    signature = hashlib.sha1((hint_key or "".join(c for c in output if not c.isdigit())).encode()).hexdigest()
    alerts = state.setdefault("alerts", {})
    previous = alerts.get(step)
    if previous and previous["sig"] == signature and time.time() - previous["ts"] < ALERT_REPEAT_HOURS * 3600:
        return
    alerts[step] = {"sig": signature, "ts": time.time()}
    # rclone / Moodle error lines first: the last lines alone are often just commands
    lines = output.splitlines()
    errors = [line for line in lines if "ERROR" in line or "BŁĄD" in line or "Traceback" in line][-4:]
    last_lines = "\n".join(errors + [line for line in lines[-4:] if line not in errors])
    message = f"{t(hint_key)}\n\n{last_lines}" if hint_key else last_lines
    notify("errors", t("notify_error_title", step=step), message, urgent=True)


def ping_healthcheck(suffix: str = "", body: str = "") -> None:
    url = config.env("HEALTHCHECK_URL").rstrip("/")
    if not url:
        return
    try:
        requests.post(url + suffix, data=body.encode("utf-8")[:10000], timeout=10)
    except requests.RequestException as e:
        print(f"[healthchecks] {redact(str(e))}")


def weekly_summary(state: dict, force: bool = False) -> None:
    """Once a week (Sunday evening): what came in + deadlines for the coming week."""
    now = datetime.now()
    last = state.get("weekly", {}).get("last", 0)
    if not force and (now.weekday() != WEEKLY_DAY or now.hour < WEEKLY_HOUR or time.time() - last < 3 * 86400):
        return
    week_ago = time.time() - 7 * 86400
    w = state.get("watch", {})
    n_files = sum(1 for e in state.get("downloaded", {}).values() if e.get("ts", 0) >= week_ago)
    n_posts = sum(1 for ts in w.get("forums", {}).get("seen", {}).values() if ts >= week_ago)
    n_grades = sum(1 for v in w.get("grades", {}).get("items", {}).values()
                   if v.get("grade") and v.get("ts", 0) >= week_ago)
    lines = [t("weekly_counts", files=n_files, posts=n_posts, grades=n_grades)]
    try:
        upcoming = [f"{'✅' if done else '⏰'} {weekday(datetime.fromtimestamp(ts).weekday())} "
                    f"{datetime.fromtimestamp(ts):%d.%m %H:%M}  {text}"
                    for ts, text, done in calendar_sync.upcoming_deadlines(days=7)]
        lines.append("\n" + t("weekly_deadlines") + "\n" + (bullet_list(upcoming, 15) if upcoming else t("weekly_none")))
    except Exception as e:  # the summary must arrive even when Moodle is down
        lines.append("\n" + t("weekly_deadlines_failed", error=e))
    notify("summary", t("weekly_title"), "\n".join(lines))
    state.setdefault("weekly", {})["last"] = time.time()


def _open_log(path: Path):
    """Append to a log file, keeping one old copy when it grows past 1 MB."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.stat().st_size > LOG_MAX_BYTES:
        os.replace(path, path.with_suffix(path.suffix + ".1"))
    return open(path, "a", encoding="utf-8")


def run(log_file: str | None = None) -> int:
    log = _open_log(Path(log_file)) if log_file else None
    # pythonw.exe (Windows, hidden window) has no console: sys.stdout is None.
    out = log or sys.stdout
    if out is None:
        out = _open_log(config.LOG_DIR / "sync.log")
    try:
        with redirect_stdout(out):
            return _run()
    finally:
        if log:
            log.close()


def _run() -> int:
    with SingleInstance() as lock:
        if not lock.acquired:
            print(t("run_busy"))
            return LOCK_BUSY
        print(f"=== {datetime.now():%Y-%m-%d %H:%M:%S} start ===", flush=True)
        started = time.time()
        ping_healthcheck("/start")

        results = []
        for key, func in STEPS:
            name = t(key)
            print(f"\n--- {name} ---", flush=True)
            code, output = run_step(func)
            results.append((name, code, output))

        state = state_mod.load()  # steps saved their own changes - read them back
        steps = []
        for name, code, output in results:
            if code == 0:
                state.get("alerts", {}).pop(name, None)  # fixed -> the next error notifies again
                steps.append([name, "OK", 0])
            elif code == 2:
                steps.append([name, t("result_skipped"), 2])
            else:
                steps.append([name, t("result_error", code=code), code])
                alert(state, name, output)
        state["last_run"] = {"start": started, "end": time.time(), "steps": steps}
        # the last 40 lines of each failed step - the bot's /errors shows them
        state["last_errors"] = {name: "\n".join(output.splitlines()[-40:])
                                for name, code, output in results if code not in (0, 2)}
        try:
            weekly_summary(state)
        except Exception as e:
            print(f"[weekly] {e}")
        state_mod.save(state)

        summary = "\n".join(f"{name}: {result}" for name, result, _ in steps)
        print(f"\n=== {t('summary')} ===\n{summary}", flush=True)
        failed = any(code not in (0, 2) for _, code, _ in results)
        ping_healthcheck("/fail" if failed else "", summary)
        return 1 if failed else 0
