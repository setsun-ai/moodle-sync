"""Reminders of what isn't handed in yet, quiet hours and the site label in notifications."""
from datetime import datetime

import pytest

from moodle_sync import calendar_sync, notify, reminders, runner, state

HOUR = 3600


class TestDue:
    def test_24h_then_3h_once_each(self):
        sent, items = {}, [(100 * HOUR, "[Algorithms] Report", False)]
        assert reminders.due(items, sent, [24, 3], now=70 * HOUR) == []  # 30 h left
        assert reminders.due(items, sent, [24, 3], now=77 * HOUR) == [(100 * HOUR, "[Algorithms] Report")]
        assert reminders.due(items, sent, [24, 3], now=78 * HOUR) == []  # already reminded
        assert reminders.due(items, sent, [24, 3], now=97.5 * HOUR) == [(100 * HOUR, "[Algorithms] Report")]
        assert reminders.due(items, sent, [24, 3], now=99 * HOUR) == []

    def test_first_seen_close_gets_only_the_nearest(self):
        sent = {}
        assert len(reminders.due([(100 * HOUR, "x", False)], sent, [24, 3], now=98 * HOUR)) == 1
        assert reminders.due([(100 * HOUR, "x", False)], sent, [24, 3], now=98.5 * HOUR) == []

    def test_done_unknown_or_past_are_skipped(self):
        items = [(100 * HOUR, "done", True), (100 * HOUR, "event", None), (90 * HOUR, "past", False)]
        assert reminders.due(items, {}, [24, 3], now=95 * HOUR) == []

    @pytest.mark.parametrize("value, expected", [("", [24, 3]), ("48, 2h;1", [48, 2, 1]), ("0", []), ("x", [])])
    def test_hours(self, monkeypatch, value, expected):
        if value:
            monkeypatch.setenv("REMIND_HOURS", value)
        assert reminders.hours() == expected


def test_run_sends_reminders_and_forgets_old_ones(monkeypatch):
    import time

    monkeypatch.setenv("NTFY_TOPIC", "t")
    now = time.time()
    asked = []
    monkeypatch.setattr(calendar_sync, "upcoming_deadlines",
                        lambda days=14, kind="": asked.append(kind) or [(now + 2 * HOUR, "[Algorithms] Report", False)])
    sent = []
    monkeypatch.setattr(notify, "notify", lambda kind, title, message="", **k: sent.append((kind, title, message)))
    state.save({"reminders": {f"{int(now - 3 * 86400)}:old": [24]}})
    assert reminders.run() == 0
    [(kind, title, message)] = sent
    assert kind == "reminders" and title == "Due in 2 h – not handed in yet" and message.startswith("[Algorithms] Report\n")
    assert list(state.load()["reminders"]) == [f"{int(now + 2 * HOUR)}:[Algorithms] Report"]
    assert reminders.run() == 0 and len(sent) == 1
    assert asked == ["reminders", "reminders"]  # courses with reminders muted are left out


def test_run_is_skipped_without_a_channel_or_when_off(monkeypatch):
    monkeypatch.setattr(calendar_sync, "upcoming_deadlines", lambda days=14: pytest.fail("must not ask Moodle"))
    assert reminders.run() == 2
    monkeypatch.setenv("NTFY_TOPIC", "t")
    monkeypatch.setenv("REMIND_HOURS", "0")
    assert reminders.run() == 2


def test_reminders_are_a_step_of_the_run():
    assert "step_reminders" in [key for key, _ in runner.STEPS]


class TestQuietHoursAndLabel:
    @pytest.mark.parametrize("spec, hour, minute, quiet", [
        ("23-7", 23, 0, True), ("23-7", 3, 0, True), ("23-7", 7, 0, False), ("23-7", 12, 0, False),
        ("22:30-6:45", 22, 29, False), ("22:30-6:45", 6, 44, True), ("13-15", 14, 0, True), ("13-15", 16, 0, False),
        ("", 3, 0, False), ("nonsense", 3, 0, False),
    ])
    def test_quiet_now(self, monkeypatch, spec, hour, minute, quiet):
        monkeypatch.setenv("QUIET_HOURS", spec)
        assert notify.quiet_now(datetime(2026, 10, 12, hour, minute)) is quiet

    def test_quiet_messages_are_silent_and_labelled(self, monkeypatch):
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:abc")
        monkeypatch.setenv("TELEGRAM_CHAT_ID", "42")
        monkeypatch.setenv("NTFY_TOPIC", "t")
        monkeypatch.setenv("NOTIFY_LABEL", "1")
        monkeypatch.setenv("SITE_LABEL", "UNI2")
        sent = []

        class Ok:
            status_code = 200
            text = ""

            def raise_for_status(self):
                pass

        monkeypatch.setattr(notify.requests, "post", lambda url, json=None, **k: sent.append(json) or Ok())
        monkeypatch.setattr(notify, "quiet_now", lambda: True)
        notify.notify("grades", "New grade", "5")
        telegram, ntfy = sent
        assert telegram["text"].startswith("🎓 <b>[UNI2] New grade</b>") and telegram["disable_notification"] is True
        assert ntfy["title"] == "[UNI2] New grade" and ntfy["priority"] == 2

        sent.clear()
        monkeypatch.setattr(notify, "quiet_now", lambda: False)
        monkeypatch.delenv("NOTIFY_LABEL")
        notify.notify("grades", "New grade", "5")
        assert "disable_notification" not in sent[0] and sent[0]["text"].startswith("🎓 <b>New grade</b>")
