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



class TestMeetingLinks:
    def test_link_from_description_goes_to_location(self):
        e = {"id": 1, "name": "Lecture 5", "eventtype": "attendance", "courseid": 0, "timestart": 1_700_000_000,
             "timeduration": 5400,
             "description": '<p>Online: <a href="https://teams.microsoft.com/l/meetup-join/19%3ameeting_X">join</a></p>'}
        _, body = calendar_sync.build_event(e, {}, cfg={})
        assert body["location"] == "https://teams.microsoft.com/l/meetup-join/19%3ameeting_X"
        assert "https://teams.microsoft.com/l/meetup-join/19%3ameeting_X" in body["description"]

    def test_meeting_activity_links_to_its_page(self):
        e = {"id": 2, "name": "Seminar", "eventtype": "meeting_start", "courseid": 0, "timestart": 1_700_000_000,
             "modulename": "bigbluebuttonbn", "instance": 44, "description": ""}
        urls = {"bigbluebuttonbn:44": "https://m.example/mod/bigbluebuttonbn/view.php?id=9"}
        _, body = calendar_sync.build_event(e, {}, cfg={}, module_urls=urls)
        assert body["location"] == "https://m.example/mod/bigbluebuttonbn/view.php?id=9"

    def test_no_link_no_location(self):
        e = {"id": 3, "name": "Essay", "eventtype": "due", "courseid": 0, "timestart": 1_700_000_000,
             "description": "<p>Upload a PDF</p>"}
        _, body = calendar_sync.build_event(e, {}, cfg={})
        assert "location" not in body


class TestPerCourseSettings:
    """courseprefs: a muted course is still synced, it just doesn't push (or leaves the calendar)."""

    def test_muted_course_announcements_are_remembered_but_not_sent(self, monkeypatch):
        from moodle_sync import courseprefs

        forums = [{"id": 1, "type": "news", "name": "Announcements", "course": 10},
                  {"id": 2, "type": "news", "name": "Announcements", "course": 11}]
        discussions = {1: [], 2: []}
        monkeypatch.setattr(moodle, "call", lambda fn, **kw: forums if fn == "mod_forum_get_forums_by_courses"
                            else {"discussions": discussions[kw["forumid"]]})
        sent = []
        monkeypatch.setattr(watch, "notify", lambda kind, title, message="", **k: sent.append((title, k)))
        courses = [{"id": 10, "fullname": "Algorithms"}, {"id": 11, "fullname": "Sandbox"}]
        section: dict = {}
        watch.check_forums(courses, {}, section, {}, dry_run=False)  # baseline
        courseprefs.switch(courses[1], ["announcements"], False, {})
        discussions[1].append({"discussion": 5, "created": 1, "subject": "Exam", "message": "Monday"})
        discussions[2].append({"discussion": 6, "created": 1, "subject": "Test post", "message": "spam"})
        assert watch.check_forums(courses, {}, section, {}, dry_run=False) == 2
        [(title, extra)] = sent
        assert "Exam" in title and extra["buttons"] == courseprefs.mute_buttons(10, "announcements")
        assert "6" in section["seen"]  # switched on later, it is not "new" again

    def test_muted_course_grades_are_kept_but_not_sent(self, monkeypatch):
        from moodle_sync import courseprefs

        grades = {1: "", 2: ""}

        def fake_call(fn, **kw):
            if fn == "mod_assign_get_assignments":
                return {"courses": [{"id": 10, "assignments": [{"id": 1, "name": "Report"}]},
                                    {"id": 11, "assignments": [{"id": 2, "name": "Quiz-like"}]}]}
            if fn == "mod_quiz_get_quizzes_by_courses":
                return {"quizzes": []}
            return {"feedback": {"gradefordisplay": grades[kw["assignid"]]}}

        monkeypatch.setattr(moodle, "call", fake_call)
        sent = []
        monkeypatch.setattr(watch, "notify", lambda kind, title, message="", **k: sent.append(title))
        courses = [{"id": 10, "fullname": "Algorithms"}, {"id": 11, "fullname": "Sandbox"}]
        section: dict = {}
        watch.check_grades(courses, {}, section, {}, force=True, dry_run=False)  # baseline
        courseprefs.switch(courses[1], ["grades"], False, {})
        grades.update({1: "5", 2: "3"})
        assert watch.check_grades(courses, {}, section, {}, force=True, dry_run=False) == 2
        assert sent == ["Grade: 5 — Report"]
        assert section["items"]["assign:2"]["grade"] == "3"  # /grades still knows it

    def test_reminders_leave_out_muted_courses(self, monkeypatch):
        from moodle_sync import courseprefs

        courses = [{"id": 10, "fullname": "Algorithms"}, {"id": 11, "fullname": "Sandbox"}]
        events = [{"id": 1, "name": "Report", "eventtype": "due", "courseid": 10, "timestart": 4_000_000_000},
                  {"id": 2, "name": "Test", "eventtype": "due", "courseid": 11, "timestart": 4_000_000_000}]
        monkeypatch.setattr(moodle, "my_courses", lambda: courses)
        monkeypatch.setattr(calendar_sync, "fetch_events", lambda courses, past_days, future_days: events)
        monkeypatch.setattr(calendar_sync, "fetch_open_action_ids", lambda past_days: {1, 2})
        courseprefs.switch(courses[1], ["reminders"], False, {})
        assert len(calendar_sync.upcoming_deadlines()) == 2  # /deadlines shows everything
        assert [text for _, text, _ in calendar_sync.upcoming_deadlines(kind="reminders")] == ["[Algorithms] Report"]

    def test_calendar_off_removes_the_course_and_on_brings_it_back_quietly(self, monkeypatch):
        from moodle_sync import courseprefs, state as state_mod

        courses = [{"id": 10, "fullname": "Algorithms"}, {"id": 11, "fullname": "Sandbox"}]
        events = [{**TestCalendar.event, "id": 1, "courseid": 10, "timestart": 4_000_000_000},
                  {**TestCalendar.event, "id": 2, "courseid": 11, "timestart": 4_000_000_000},
                  {**TestCalendar.event, "id": 3, "courseid": 11, "eventtype": "attendance", "timestart": 4_000_000_000}]
        monkeypatch.setattr(calendar_sync, "status", lambda: (True, ""))
        monkeypatch.setattr(moodle, "my_courses", lambda: courses)
        monkeypatch.setattr(calendar_sync, "fetch_events", lambda courses: list(events))
        monkeypatch.setattr(calendar_sync, "fetch_open_action_ids", lambda: {e["id"] for e in events})  # none done
        sent = []
        monkeypatch.setattr(calendar_sync, "notify", lambda kind, title, message="", **k: sent.append(message))
        google = FakeGoogle()
        monkeypatch.setattr(calendar_sync, "google_session", lambda: google)

        assert calendar_sync.run() == 0
        assert set(state_mod.load()["calendar"]["events"]) == {"1", "2", "3"} and len(sent) == 1
        courseprefs.switch(courses[1], ["calendar"], False, {})  # Sandbox deadlines out, its classes stay
        google.calls.clear()
        assert calendar_sync.run() == 0
        assert google.calls[-1] == ("DELETE", "https://www.googleapis.com/calendar/v3/calendars/new1/events/pgmoodle2")
        assert set(state_mod.load()["calendar"]["events"]) == {"1", "3"}

        events.append({**TestCalendar.event, "id": 4, "courseid": 11, "timestart": 4_000_000_000})  # new while off
        assert calendar_sync.run() == 0 and len(sent) == 1
        courseprefs.switch(courses[1], ["calendar"], True, {})
        assert calendar_sync.run() == 0
        assert set(state_mod.load()["calendar"]["events"]) == {"1", "2", "3", "4"}
        assert len(sent) == 1 and state_mod.load()["calendar"]["hidden"] == []  # back without "new deadlines"

        courseprefs.switch(courses[0], ["deadlines"], False, {})  # in the calendar, but no notification
        events.append({**TestCalendar.event, "id": 5, "courseid": 10, "timestart": 4_000_000_000})
        events.append({**TestCalendar.event, "id": 6, "courseid": 11, "timestart": 4_000_000_000})
        assert calendar_sync.run() == 0
        assert "5" in state_mod.load()["calendar"]["events"] and len(sent) == 2
        assert "Sandbox" in sent[-1] and "Algorithms" not in sent[-1]


class TestHiddenCourses:
    def test_forums_of_a_hidden_course_are_forgotten_and_come_back_quietly(self, monkeypatch):
        forums = [{"id": 1, "type": "news", "name": "Announcements", "course": 10},
                  {"id": 2, "type": "news", "name": "Announcements", "course": 11}]
        discussions = {1: [], 2: [{"discussion": 21, "created": 1}]}

        def fake_call(fn, **kw):
            if fn == "mod_forum_get_forums_by_courses":  # only the courses asked about
                return [f for f in forums if f["course"] in kw.values()]
            return {"discussions": discussions[kw["forumid"]]}

        monkeypatch.setattr(moodle, "call", fake_call)
        sent = []
        monkeypatch.setattr(watch, "notify", lambda *a, **k: sent.append(a))
        section: dict = {}
        watch.check_forums([{"id": 10}, {"id": 11}], {}, section, {}, dry_run=False)
        watch.check_forums([{"id": 10}], {}, section, {}, dry_run=False)  # course 11 hidden
        assert section["forums_known"] == [1]
        discussions[2].append({"discussion": 22, "created": 2, "subject": "While hidden", "message": "x"})
        assert watch.check_forums([{"id": 10}, {"id": 11}], {}, section, {}, dry_run=False) == 0  # shown again
        assert sent == []

    def test_deadlines_leave_out_hidden_courses(self, monkeypatch):
        courses = [{"id": 10, "fullname": "Algorithms"}, {"id": 11, "fullname": "Old", "hidden": True}]
        events = [{"id": 1, "name": "Report", "eventtype": "due", "courseid": 10, "timestart": 4_000_000_000},
                  {"id": 2, "name": "Test", "eventtype": "due", "courseid": 11, "timestart": 4_000_000_000},
                  {"id": 3, "name": "Holiday", "eventtype": "site", "courseid": 1, "timestart": 4_000_000_000}]
        monkeypatch.setattr(moodle, "my_courses", lambda: courses)
        monkeypatch.setattr(calendar_sync, "fetch_events", lambda courses, past_days, future_days: events)
        monkeypatch.setattr(calendar_sync, "fetch_open_action_ids", lambda past_days: set())
        assert [text for _, text, _ in calendar_sync.upcoming_deadlines()] == ["[Algorithms] Report", "[Moodle] Holiday"]
