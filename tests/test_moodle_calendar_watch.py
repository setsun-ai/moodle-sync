import base64

from moodle_sync import calendar_sync, moodle, watch


class TestMoodle:
    def test_decode_sso_token_from_full_url(self):
        encoded = base64.b64encode(b"abc123signature:::THE_TOKEN:::private").decode().rstrip("=")
        assert moodle.decode_sso_token(f"moodlemobile://token={encoded}") == "THE_TOKEN"
        assert moodle.decode_sso_token(encoded) == "THE_TOKEN"

    def test_file_url_gets_token_and_webservice_path(self):
        url = moodle.file_url_with_token("https://m.example/pluginfile.php/5/a%20b.pdf?forcedownload=1&token=old", "T")
        assert url == "https://m.example/webservice/pluginfile.php/5/a%20b.pdf?forcedownload=1&token=T"

    def test_redact_hides_the_token(self, monkeypatch):
        monkeypatch.setenv("MOODLE_TOKEN", "secret123")
        assert moodle.redact("GET https://x/?token=secret123 failed") == "GET https://x/?token=*** failed"

    def test_skip_courses(self):
        assert moodle.course_skipped({"fullname": "Library Training 2025"}, {"skip": ["library training"]})
        assert not moodle.course_skipped({"fullname": "Algorithms"}, {"skip": ["library"]})


class TestCalendar:
    event = {"id": 7, "name": "Report 1 is due", "eventtype": "due", "modulename": "assign",
             "timestart": 1_800_000_000, "timeduration": 0, "courseid": None, "description": ""}

    def test_is_done_uses_open_action_events(self):
        assert calendar_sync.is_done(self.event, open_ids={7}) is False
        assert calendar_sync.is_done(self.event, open_ids=set()) is True
        assert calendar_sync.is_done(self.event, open_ids=None) is None
        assert calendar_sync.is_done({**self.event, "eventtype": "course"}, open_ids=set()) is None

    def test_done_event_has_check_mark_and_no_reminders(self):
        cal, body = calendar_sync.build_event(self.event, {}, done=True, cfg={})
        assert cal == "deadlines" and body["summary"].startswith("✅")
        assert body["reminders"]["overrides"] == []
        _, open_body = calendar_sync.build_event(self.event, {}, done=False, cfg={})
        assert open_body["summary"].startswith("⏰") and open_body["reminders"]["overrides"]
        assert calendar_sync.fingerprint(cal, body) != calendar_sync.fingerprint(cal, open_body)

    def test_attendance_goes_to_classes_calendar(self):
        cal, body = calendar_sync.build_event({**self.event, "eventtype": "attendance", "timeduration": 5400}, {},
                                              cfg={})
        assert cal == "classes" and body["transparency"] == "opaque"
        assert body["end"]["dateTime"] != body["start"]["dateTime"]

    def test_calendar_names_follow_language(self, monkeypatch):
        monkeypatch.setenv("SITE_LABEL", "UNI")
        monkeypatch.setenv("LANGUAGE", "pl")
        assert calendar_sync.calendar_names() == {"deadlines": "UNI – terminy", "classes": "UNI – zajęcia"}


class TestWatch:
    def test_plain_grade(self):
        assert watch.plain_grade("90,00&nbsp;/&nbsp;100,00") == "90 / 100"
        assert watch.plain_grade("<b>4.50</b> / 5.00") == "4.50 / 5"

    def test_newly_watched_forum_is_remembered_silently(self, monkeypatch):
        """Regression: enabling WATCH_ALL_FORUMS must not report old posts as new."""
        forums = [{"id": 1, "type": "news", "name": "Announcements", "course": 10},
                  {"id": 2, "type": "general", "name": "Group 4 discussion", "course": 10}]
        discussions = {1: [{"discussion": 11, "created": 1}], 2: [{"discussion": 21, "created": 1}]}

        def fake_call(fn, **kw):
            if fn == "mod_forum_get_forums_by_courses":
                return forums
            return {"discussions": discussions[kw["forumid"]]}

        monkeypatch.setattr(moodle, "call", fake_call)
        sent = []
        monkeypatch.setattr(watch, "notify", lambda *a, **k: sent.append(a))
        section: dict = {}
        watch.check_forums([{"id": 10}], {}, section, {}, dry_run=False)          # first run: baseline
        monkeypatch.setenv("WATCH_ALL_FORUMS", "1")
        assert watch.check_forums([{"id": 10}], {}, section, {}, dry_run=False) == 0  # forum 2 now watched
        discussions[2].append({"discussion": 22, "created": 2, "subject": "New post", "message": "hi"})
        assert watch.check_forums([{"id": 10}], {}, section, {}, dry_run=False) == 1  # a genuinely new post
        assert len(sent) == 1


class FakeGoogle:
    """Just enough of AuthorizedSession: records calls, answers with fixed status codes."""

    def __init__(self, calendar_status=200):
        self.calendar_status, self.calls, self.created = calendar_status, [], 0

    def _resp(self, status, data=None):
        class R:
            status_code = status

            def json(self):
                return data or {}

            def raise_for_status(self):
                if status >= 400:
                    raise RuntimeError(f"HTTP {status}")
        return R()

    def get(self, url):
        self.calls.append(("GET", url))
        return self._resp(self.calendar_status)

    def post(self, url, json=None):
        self.calls.append(("POST", url))
        if url.endswith("/calendars"):
            self.created += 1
            return self._resp(200, {"id": f"new{self.created}"})
        return self._resp(200)

    def put(self, url, json=None):
        self.calls.append(("PUT", url))
        return self._resp(200)

    def delete(self, url):
        self.calls.append(("DELETE", url))
        return self._resp(204)


class TestCalendarRecovery:
    def test_error_is_not_answered_with_a_duplicate_calendar(self):
        import pytest

        state = {"calendars": {"deadlines": "a", "classes": "b"}}
        with pytest.raises(RuntimeError):
            calendar_sync.ensure_calendars(FakeGoogle(calendar_status=401), state)
        assert state["calendars"] == {"deadlines": "a", "classes": "b"}
        ids, created = calendar_sync.ensure_calendars(FakeGoogle(calendar_status=200), state)
        assert created == set() and ids == {"deadlines": "a", "classes": "b"}

    def test_calendar_deleted_by_hand_is_recreated_and_refilled(self, monkeypatch):
        from moodle_sync import state as state_mod

        event = {**TestCalendar.event, "timestart": 4_000_000_000}
        monkeypatch.setattr(calendar_sync, "status", lambda: (True, ""))
        monkeypatch.setattr(moodle, "my_courses", lambda: [])
        monkeypatch.setattr(calendar_sync, "fetch_events", lambda courses: [event])
        monkeypatch.setattr(calendar_sync, "fetch_open_action_ids", lambda: {7})
        sent = []
        monkeypatch.setattr(calendar_sync, "notify", lambda *a, **k: sent.append(a))
        google = FakeGoogle()
        monkeypatch.setattr(calendar_sync, "google_session", lambda: google)

        assert calendar_sync.run() == 0                      # first sync: the event is created
        assert len(sent) == 1 and google.created == 2
        google.calls.clear()
        assert calendar_sync.run() == 0                      # nothing changed: no event upload
        assert not [c for c in google.calls if "/events" in c[1]]

        google.calendar_status = 404                         # both calendars deleted in Google
        assert calendar_sync.run() == 0
        assert google.created == 4
        assert any(c[0] == "POST" and "/calendars/new3/events" in c[1] for c in google.calls)
        assert len(sent) == 1                                # a refill is not a "new deadline"
        assert state_mod.load()["calendar"]["calendars"]["deadlines"] == "new3"
