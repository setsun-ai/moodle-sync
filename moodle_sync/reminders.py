"""
Reminders of what you haven't handed in yet: REMIND_HOURS=24,3 hours before the deadline
(empty or 0 = off, NOTIFY_REMINDERS=0 mutes them like any other kind).

Only assignments and quizzes that Moodle reports as not done (calendar_sync.is_done is False)
are reminded about - never what you've already submitted, never plain calendar events.
A course with reminders switched off in the bot (courseprefs) is left out.
Every reminder goes out once: state.json -> "reminders" remembers which ones were sent.
A deadline first seen when it's already close gets only the nearest reminder, not all of them.
"""

import time
from datetime import datetime

from . import calendar_sync, config, notify, state as state_mod
from .i18n import t, weekday

SKIPPED = 2


def hours() -> list[float]:
    """REMIND_HOURS as a list of hours, largest first (default 24 and 3)."""
    out = []
    for part in config.env("REMIND_HOURS", "24,3").replace(";", ",").split(","):
        try:
            value = float(part.strip().replace("h", ""))
        except ValueError:
            continue
        if value > 0:
            out.append(value)
    return sorted(set(out), reverse=True)


def due(items: list, sent: dict, marks: list[float], now: float) -> list[tuple[int, str]]:
    """
    (deadline, text) to remind about now; `sent` (key -> hours already reminded) is updated.
    Pure, so tests can move the clock.
    """
    out = []
    for ts, text, done in items:
        left = ts - now
        if done is not False or left <= 0:
            continue
        crossed = [h for h in marks if left <= h * 3600]
        key = f"{int(ts)}:{text}"
        already = set(sent.get(key, []))
        if not crossed or min(crossed) in already:
            continue
        out.append((int(ts), text))
        sent[key] = sorted(already | set(crossed), reverse=True)  # the bigger ones are past: never send them late
    return out


def left_text(seconds: float) -> str:
    return f"{seconds / 3600:.0f} h" if seconds >= 5400 else f"{max(1, round(seconds / 60))} min"


def run() -> int:
    marks = hours()
    if not marks or not notify.channels() or not config.env_bool("NOTIFY_REMINDERS", True):
        print(t("remind_off"))
        return SKIPPED
    items = calendar_sync.upcoming_deadlines(days=int(max(marks) // 24) + 1, kind="reminders")
    state = state_mod.load()
    sent = state.setdefault("reminders", {})
    now = time.time()
    found = due(items, sent, marks, now)
    for ts, text in found:
        when = datetime.fromtimestamp(ts)
        notify.notify("reminders", t("remind_title", left=left_text(ts - now)),
                      f"{text}\n{weekday(when.weekday())} {when:%d.%m %H:%M}")
    for key in [k for k in sent if int(k.split(":", 1)[0]) < now - 86400]:  # deadlines long gone
        del sent[key]
    state_mod.save(state)
    print(t("remind_sent", n=len(found)))
    return 0
