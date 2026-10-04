"""Course preview, assignment submission, forum posts and attendance - no network, no real Moodle/Telegram."""
import time
from datetime import datetime

import pytest

from moodle_sync import assignments, attendance, coursebrowse, interactive, moodle

# --- attendance pages (made-up HTML in the shape of mod_attendance) --------------------------------

FORM_LABEL_FOR = """
<div class="alert alert-info">Enter the password</div>
<form autocomplete="off" action="https://m.example/mod/attendance/attendance.php" method="post" id="mform1">
  <input name="sessid" type="hidden" value="77" />
  <input name="sesskey" type="hidden" value="abc" />
  <input name="_qf__mod_attendance_form_studentattendance" type="hidden" value="1" />
  <input type="password" name="studentpassword" id="id_studentpassword" />
  <input type="radio" name="status" id="id_status_5" value="5"><label for="id_status_5">Present</label>
  <input type="radio" name="status" id="id_status_6" value="6"><label for="id_status_6">Late</label>
  <input type="submit" name="submitbutton" id="id_submitbutton" value="Save changes" />
</form>"""

FORM_WRAPPED = """
<form action="attendance.php" method="post">
  <input type="hidden" name="sessid" value="88">
  <label class="form-check-label"><input type="radio" class="form-check-input" name="status" value="9">
    Spóźniony</label>
  <label class="form-check-label"><input type="radio" class="form-check-input" name="status" value="8"> Obecny
  </label>
  <input type="submit" name="submitbutton" value="Zapisz">
</form>"""

VIEW_PAGE = """
<table><tr><td>Mon 13.10.2025 10:15 - 12:00</td><td>Lecture 3</td>
<td><a href="https://m.example/mod/attendance/attendance.php?sessid=77&amp;sesskey=abc">Submit attendance</a></td></tr>
<tr><td>Mon 20.10.2025</td><td>Lecture 4</td><td>?</td></tr></table>"""


class TestAttendanceParsing:
    def test_links(self):
        assert attendance.parse_link("https://m.example/mod/attendance/attendance.php?qrpass=XYZ&sessid=77") == {
            "url": "https://m.example/mod/attendance/attendance.php?qrpass=XYZ&sessid=77", "sessid": "77",
            "qrpass": "XYZ"}
        assert attendance.parse_link("https://example.com/something") is None

    def test_sessions_on_the_activity_page(self):
        links = attendance.session_links(VIEW_PAGE, "https://m.example/mod/attendance/view.php?id=5")
        assert [(s["sessid"], s["url"]) for s in links] == [
            ("77", "https://m.example/mod/attendance/attendance.php?sessid=77&sesskey=abc")]
        assert "Lecture 3" in links[0]["label"]

    def test_form_with_label_for_and_password(self):
        form = attendance.parse_form(FORM_LABEL_FOR, "https://m.example/mod/attendance/attendance.php?sessid=77")
        assert form["statuses"] == [("5", "Present"), ("6", "Late")]
        assert form["password"] == "studentpassword"
        assert form["hidden"]["sesskey"] == "abc" and form["submit"] == ("submitbutton", "Save changes")
        assert attendance.page_message(FORM_LABEL_FOR) == "Enter the password"

    def test_form_with_wrapping_labels_relative_action(self):
        form = attendance.parse_form(FORM_WRAPPED, "https://m.example/mod/attendance/attendance.php?sessid=88")
        assert form["action"] == "https://m.example/mod/attendance/attendance.php"
        assert form["statuses"] == [("9", "Spóźniony"), ("8", "Obecny")] and form["password"] is None
        assert attendance.default_status(form["statuses"]) == "8"
        assert attendance.parse_form("<p>no form</p>", "https://m.example/") is None

    def test_submit_success_when_form_is_gone(self, monkeypatch):
        posted = []

        class Resp:
            def __init__(self, text):
                self.text, self.url = text, "https://m.example/mod/attendance/view.php?id=5"

        monkeypatch.setattr(attendance.WEB, "post", lambda url, data: posted.append((url, data)) or Resp(
            '<div class="alert alert-success">Your attendance in this session has been recorded.</div>'))
        form = attendance.parse_form(FORM_LABEL_FOR, "https://m.example/")
        ok, message = attendance.submit(form, "5", "secret")
        assert ok and "recorded" in message
        assert posted[0][1] == {"sessid": "77", "sesskey": "abc", "_qf__mod_attendance_form_studentattendance": "1",
                                "status": "5", "studentpassword": "secret", "submitbutton": "Save changes"}

    def test_autologin_needs_private_token_and_waits(self, monkeypatch):
        web = attendance.Web()
        with pytest.raises(attendance.NotAvailable, match="no_private_token"):
            web.get("https://m.example/mod/attendance/view.php?id=5")
        monkeypatch.setenv("MOODLE_PRIVATE_TOKEN", "priv")
        web.last_key = time.time()
        with pytest.raises(attendance.NotAvailable, match="autologin_wait"):
            web.get("https://m.example/mod/attendance/view.php?id=5")


# --- assignments -------------------------------------------------------------------------------------

def assign(**configs):
    base = {"enabled": "1", "filetypeslist": ".pdf", "maxsubmissionsizebytes": str(5 * 1024 * 1024),
            "maxfilesubmissions": "1"}
    base.update(configs)
    return {"id": 3, "cmid": 30, "name": "Sprawozdanie", "duedate": 0, "submissiondrafts": 1,
            "configs": [{"plugin": "file", "subtype": "assignsubmission", "name": k, "value": v} for k, v in base.items()]}


class TestAssignments:
    def test_requirements_and_checks(self):
        a = assign(filetypeslist=".pdf, document")
        req = assignments.requirements(a)
        assert ".pdf" in req["types"] and ".docx" in req["types"] and req["max_bytes"] == 5 * 1024 * 1024
        assert assignments.check_file(a, "report.PDF", 1000) == []
        assert assignments.check_file(assign(), "report.docx", 1000) == ["type"]
        assert assignments.check_file(assign(), "report.pdf", 6 * 1024 * 1024) == ["size"]
        assert assignments.check_file(assign(enabled="0"), "report.pdf", 1) == ["nofiles"]
        assert assignments.check_file(assign(filetypeslist=""), "anything.xyz", 1) == []

    def test_name_from_template(self, monkeypatch):
        monkeypatch.setenv("STUDENT_ID", "123456")
        assert assignments.target_name(assign(), "LCMS", "scan_final (2).PDF") == "Sprawozdanie LCMS 123456.pdf"
        monkeypatch.setenv("SUBMISSION_NAME", "{student_id}_{course}_{assignment}")
        assert assignments.target_name(assign(), "LCMS", "x.pdf") == "123456_LCMS_Sprawozdanie.pdf"
        monkeypatch.delenv("STUDENT_ID")
        monkeypatch.delenv("SUBMISSION_NAME")
        assert assignments.target_name(assign(), "LCMS", "x.pdf") == "Sprawozdanie LCMS.pdf"

    def test_open_assignments_filters_and_sorts(self, monkeypatch):
        now = time.time()
        later, sooner, closed, future = assign(), assign(), assign(), assign()
        later.update(id=1, duedate=now + 7200)
        sooner.update(id=2, duedate=now + 3600)
        closed.update(id=3, cutoffdate=now - 10)
        future.update(id=4, allowsubmissionsfromdate=now + 100)
        monkeypatch.setattr(moodle, "call", lambda fn, **kw: {"courses": [
            {"id": 10, "fullname": "LCMS", "assignments": [later, sooner, closed, future]}]})
        got = assignments.open_assignments([{"id": 10, "fullname": "LCMS"}])
        assert [a["id"] for a in got] == [2, 1] and got[0]["course"] == "LCMS"

    def test_save_uploads_then_saves(self, monkeypatch):
        calls = []
        monkeypatch.setattr(moodle, "upload_draft", lambda name, data: calls.append(("upload", name)) or 555)
        monkeypatch.setattr(moodle, "call", lambda fn, **kw: calls.append((fn, kw)) or [])
        assignments.save(assign(), "Sprawozdanie LCMS.pdf", b"%PDF")
        assert calls == [("upload", "Sprawozdanie LCMS.pdf"),
                         ("mod_assign_save_submission", {"assignmentid": 3, "plugindata[files_filemanager]": 555})]


# --- course preview ------------------------------------------------------------------------------------

def file_content(name, ts):
    return {"type": "file", "filename": name, "fileurl": f"https://m.example/pluginfile.php/1/{name}",
            "filesize": 10, "timemodified": ts}


SECTION = {"name": "Week 3", "summary": "", "modules": [
    {"modname": "resource", "name": "Slides 3", "url": "https://m.example/mod/resource/view.php?id=1",
     "contents": [file_content("w3.pdf", 1000)]},
    {"modname": "url", "name": "Recording", "url": "https://m.example/mod/url/view.php?id=2",
     "contents": [{"type": "url", "fileurl": "https://video.example/abc", "timemodified": 1000}]},
    {"modname": "label", "name": "x", "description": '<p>Read <a href="https://docs.example/a">this</a></p>'},
    {"modname": "assign", "name": "Report", "url": "https://m.example/mod/assign/view.php?id=4"},
    {"modname": "page", "name": "Hidden", "url": "u", "uservisible": False},
]}


class TestCourseBrowse:
    def test_section_links(self):
        from moodle_sync.files import stable_id

        paths = {stable_id(SECTION["modules"][0]["contents"][0]): "Algo/Lectures/w3.pdf"}
        links = {"algo/lectures/w3.pdf": "https://drive.google.com/file/d/ID1/view"}
        text = coursebrowse.render_section("Algo", SECTION, paths, links)
        assert '📄 <a href="https://drive.google.com/file/d/ID1/view">Slides 3</a> ☁️' in text
        assert '🔗 <a href="https://video.example/abc">Recording</a>' in text
        assert 'href="https://docs.example/a"' in text and "Report" in text and "Hidden" not in text

    def test_without_cloud_copy_link_goes_to_moodle(self):
        text = coursebrowse.render_section("Algo", SECTION, {}, {})
        assert 'href="https://m.example/mod/resource/view.php?id=1">Slides 3</a>' in text

    def test_day_view(self):
        blocks = coursebrowse.render_day([("Algo", [SECTION]), ("Other", [{"name": "S", "modules": []}])],
                                         900, 1100, {}, {})
        assert len(blocks) == 1 and "Slides 3" in blocks[0] and "Recording" in blocks[0] and "Report" not in blocks[0]

    def test_parse_day(self):
        assert interactive.parse_day([]) == 0 and interactive.parse_day(["wczoraj"]) == 1
        assert interactive.parse_day(["3"]) == 3
        today = datetime.now()
        assert interactive.parse_day([today.strftime("%d.%m")]) == 0


# --- the bot conversations ---------------------------------------------------------------------------------

@pytest.fixture
def bot(monkeypatch):
    out = {"sent": [], "edits": [], "calls": []}

    def fake_send(chat, text, rows=None):
        out["sent"].append((text, rows))
        return len(out["sent"])

    monkeypatch.setattr(interactive, "send", fake_send)
    monkeypatch.setattr(interactive, "edit", lambda chat, mid, text, rows=None: out["edits"].append((text, rows)))
    monkeypatch.setattr(interactive, "api", lambda method, **p: out["calls"].append((method, p)) or {})
    monkeypatch.setattr(interactive, "download", lambda file_id: b"%PDF-1.7")
    monkeypatch.setattr(moodle, "my_courses", lambda: [{"id": 10, "fullname": "LCMS"}])
    interactive.STATE.clear()
    return out


def click(data):
    interactive.on_callback({"id": "q", "data": data, "message": {"message_id": 1}}, "1")


def test_write_actions_are_off_by_default(bot):
    interactive.on_document({"document": {"file_id": "f", "file_name": "a.pdf", "file_size": 10}}, "1")
    assert "MOODLE_ACTIONS" in bot["sent"][-1][0]


def test_submit_flow(bot, monkeypatch):
    monkeypatch.setenv("MOODLE_ACTIONS", "1")
    monkeypatch.setenv("STUDENT_ID", "123456")
    a = assign()
    a["course"] = "LCMS"
    saved = []
    monkeypatch.setattr(assignments, "open_assignments", lambda courses: [a])
    monkeypatch.setattr(assignments, "submission_status",
                        lambda aid: {"status": "draft", "files": ["old.pdf"], "can_edit": True, "can_submit": True})
    monkeypatch.setattr(assignments, "save", lambda assign_, name, data: saved.append((name, data)))
    monkeypatch.setattr(assignments, "submit_for_grading", lambda assign_: saved.append("graded"))

    interactive.on_document({"document": {"file_id": "f", "file_name": "photo.docx", "file_size": 10}}, "1")
    click("sa:0")
    assert "Allowed types: .pdf" in bot["sent"][-1][0] and saved == []  # wrong type: asks for another file
    interactive.on_document({"document": {"file_id": "g", "file_name": "scan.pdf", "file_size": 10}}, "1")
    confirm = bot["sent"][-1][0]
    assert "Sprawozdanie LCMS 123456.pdf" in confirm and "old.pdf" in confirm and saved == []
    click("sok")
    assert saved == [("Sprawozdanie LCMS 123456.pdf", b"%PDF-1.7")]
    assert "Submit for grading" in str(bot["edits"][-1][1])
    click("sg")
    assert saved[-1] == "graded"


def test_forum_flow(bot, monkeypatch):
    monkeypatch.setenv("MOODLE_ACTIONS", "1")
    calls = []

    def fake_call(fn, **kw):
        calls.append((fn, kw))
        if fn == "mod_forum_get_forums_by_courses":
            return [{"id": 7, "name": "Questions"}]
        if fn == "mod_forum_can_add_discussion":
            return {"status": True}
        return {"discussionid": 1}

    monkeypatch.setattr(moodle, "call", fake_call)
    interactive.handle_command("forum", [], "1")
    click("fc:10")
    click("ff:7")
    interactive.on_text({"text": "Lab 3 question", "message_id": 5}, "1")
    interactive.on_text({"text": "Is <b> allowed?\nThanks", "message_id": 6}, "1")
    assert not any(fn == "mod_forum_add_discussion" for fn, _ in calls)  # only after ✅
    click("fp")
    post = next(kw for fn, kw in calls if fn == "mod_forum_add_discussion")
    assert post == {"forumid": 7, "subject": "Lab 3 question", "message": "<p>Is &lt;b&gt; allowed?<br>Thanks</p>"}


def test_attendance_from_qr_link(bot, monkeypatch):
    monkeypatch.setenv("MOODLE_ACTIONS", "1")
    monkeypatch.setenv("MOODLE_PRIVATE_TOKEN", "priv")
    form = attendance.parse_form(FORM_LABEL_FOR, "https://m.example/")
    submitted = []
    monkeypatch.setattr(attendance, "open_session", lambda url: (form, "", url))
    monkeypatch.setattr(attendance, "submit", lambda f, status, password: submitted.append((status, password))
                        or (True, "Recorded"))
    assert interactive.on_text({"text": "https://m.example/mod/attendance/attendance.php?qrpass=QQ&sessid=77",
                                "message_id": 3}, "1")
    buttons = [b["text"] for row in interactive.kb(bot["sent"][-1][1])["inline_keyboard"] for b in row]
    assert buttons[0] == "✅ Present"
    click("as:5")
    assert submitted == []  # needs the ✅ confirmation
    click("ao")
    assert submitted == [("5", "QQ")] and "Recorded" in bot["edits"][-1][0]


def test_attendance_password_is_asked_and_deleted(bot, monkeypatch):
    monkeypatch.setenv("MOODLE_ACTIONS", "1")
    monkeypatch.setenv("MOODLE_PRIVATE_TOKEN", "priv")
    form = attendance.parse_form(FORM_LABEL_FOR, "https://m.example/")
    submitted = []
    monkeypatch.setattr(attendance, "open_session", lambda url: (form, "", url))
    monkeypatch.setattr(attendance, "submit", lambda f, status, password: submitted.append(password) or (True, ""))
    interactive.open_attendance("1", "https://m.example/mod/attendance/attendance.php?sessid=77")
    click("as:5")
    interactive.on_text({"text": "letmein", "message_id": 9}, "1")
    assert ("deleteMessage", {"chat_id": "1", "message_id": 9}) in bot["calls"]
    click("ao")
    assert submitted == ["letmein"]


def test_attendance_links_without_private_token(bot, monkeypatch):
    monkeypatch.setenv("MOODLE_ACTIONS", "1")  # no MOODLE_PRIVATE_TOKEN: the university doesn't hand it out
    link = "https://m.example/mod/attendance/attendance.php?qrpass=QQ&sessid=77"
    interactive.on_text({"text": link, "message_id": 3}, "1")
    button = interactive.kb(bot["sent"][-1][1])["inline_keyboard"][0][0]
    assert button == {"text": "✋ Open attendance", "url": link}

    monkeypatch.setattr(moodle, "course_contents", lambda cid: [{"modules": [
        {"modname": "attendance", "name": "Obecność", "url": "https://m.example/mod/attendance/view.php?id=5"},
        {"modname": "resource", "name": "x", "url": "u"}]}])
    interactive.handle_command("obecnosc", [], "1")
    button = interactive.kb(bot["sent"][-1][1])["inline_keyboard"][0][0]
    assert button == {"text": "✋ LCMS: Obecność", "url": "https://m.example/mod/attendance/view.php?id=5"}



def test_stale_copies_only_same_name_and_size():
    from moodle_sync import storage

    listing = [("Semestr 1/Algo/Lectures/w1.pdf", 100), ("Algo/Lectures/w1.pdf", 100),  # left behind
               ("Algo/Lectures/w1-notes.pdf", 100), ("Algo/Lectures/w2.pdf", 999),  # not copies
               ("Semestr 1/Algo/Lectures/w2.pdf", 200), ("My own/w1.pdf", 5)]
    tracked = {"semestr 1/algo/lectures/w1.pdf", "semestr 1/algo/lectures/w2.pdf"}
    assert storage.stale_copies(listing, tracked) == ["Algo/Lectures/w1.pdf"]


def test_only_filter_for_a_second_site(monkeypatch, tmp_path):
    import json

    from moodle_sync import config

    (tmp_path / "courses.json").write_text(json.dumps({"only": ["inter-university"]}), encoding="utf-8")
    monkeypatch.setattr(moodle, "site_info", lambda **kw: {"userid": 1})
    monkeypatch.setattr(moodle, "call", lambda fn, **kw: [{"id": 1, "fullname": "Chemistry"},
                                                          {"id": 2, "fullname": "Inter-University Seminar"}])
    assert config.courses_file() == tmp_path / "courses.json"
    assert [c["id"] for c in moodle.my_courses()] == [2]


def test_electives_in_the_bot(bot, monkeypatch):
    from moodle_sync import state as state_mod, studyplan

    plan = studyplan.parse_plan(
        '<div><h3><strong>Semestr: 2</strong>&nbsp;(2025/2026 - letni)</h3></div>'
        '<div class="data-table__row"><div class="cell"><span class="cell__inner">MODULE X</span></div></div>'
        '<div class="data-table__row secondary-row"><div class="cell"><div class="cell__inner">ALPHA</div></div>'
        '<a href="/pl/subjects/1/card.pdf">x</a></div>'
        '<div class="data-table__row secondary-row"><div class="cell"><div class="cell__inner">BETA</div></div>'
        '<a href="/pl/subjects/2/card.pdf">x</a></div>')
    monkeypatch.setenv("STUDY_PLAN_URL", "https://ects.example.edu/pl/courses/1")
    monkeypatch.setattr(studyplan, "load_plan", lambda state=None, force=False: plan)
    interactive.handle_command("obieralne", [], "1")
    assert len(bot["sent"]) == 1 and bot["sent"][-1][1] == [[("❓ S2: Module X", "elm:0")]]  # one short message
    click("elm:0")
    text, rows = bot["edits"][-1]
    assert "MODULE X" not in text and "Module X" in text and "/subjects/2/card.pdf" in text
    assert [r[0][0] for r in rows[:3]] == ["⬜ 1. Alpha", "⬜ 2. Beta", "⬜ 🌐 Not in the catalogue (another university)"]
    click("elt:0:1")
    assert any(r[0][0] == "☑️ 2. Beta" for r in bot["edits"][-1][1])
    click("els:0")
    assert state_mod.load()["electives"] == {"2|MODULE X": ["2"]}
    assert bot["edits"][-1][1] == [[("✅ S2: Module X – 2. Beta", "elm:0")]]  # back to the list, updated


def test_cleanup_in_the_bot(bot, monkeypatch):
    from moodle_sync import storage

    removed = []
    monkeypatch.setattr(storage, "find_stale", lambda: {"local": ["a/x.pdf"], "remote": ["a/x.pdf", "b/y.pdf"]})
    monkeypatch.setattr(storage, "remove_stale", lambda found: removed.append(found) or 3)
    interactive.handle_command("porzadki", [], "1")
    assert "local 1, cloud 2" in bot["sent"][-1][0] and removed == []
    click("cu!")
    assert removed and "3" in bot["edits"][-1][0]



def test_assign_a_course_in_the_bot(bot, monkeypatch):
    from moodle_sync import state as state_mod, studyplan

    plan = studyplan.parse_plan(
        '<div><h3><strong>Semestr: 1</strong>&nbsp;(2025/2026 - zimowy)</h3></div>'
        '<div class="data-table__row"><div class="cell"><span class="cell__inner">JEZYK ANGIELSKI I</span></div>'
        '<a href="/pl/subjects/9/card.pdf">x</a></div>')
    monkeypatch.setenv("STUDY_PLAN_URL", "https://ects.example.edu/pl/courses/1")
    monkeypatch.setattr(studyplan, "load_plan", lambda state=None, force=False: plan)
    monkeypatch.setattr(moodle, "my_courses", lambda: [{"id": 10, "fullname": "English B2 group 4", "startdate": 0}])
    interactive.handle_command("przypisz", [], "1")
    text = bot["sent"][-1][0]
    assert "❓ <b>English B2 group 4</b>" in text and "→ —" in text
    click("mc:10")
    click("ms:10:1")
    labels = [r[0][0] for r in bot["edits"][-1][1]]
    assert labels[0] == "Jezyk angielski I"
    click("mk:10:0")
    assert state_mod.load()["course_map"] == {"10": "1|JEZYK ANGIELSKI I|9"}
    assert "✋ <b>English B2 group 4</b>" in bot["edits"][-1][0]
    assert "Semester 1/Jezyk angielski I" in bot["edits"][-1][0]
    click("mr:10")
    assert state_mod.load()["course_map"] == {}



PLAN_2SEM = ('<div><h3><strong>Semestr: 1</strong>&nbsp;(2025/2026 - letni)</h3></div>'
             '<div class="data-table__row"><div class="cell"><span class="cell__inner">PROJECT I</span></div>'
             '<a href="/pl/subjects/11/card.pdf">x</a></div>'
             '<div><h3><strong>Semestr: 2</strong>&nbsp;(2026/2027 - zimowy)</h3></div>'
             '<div class="data-table__row"><div class="cell"><span class="cell__inner">PROJECT II</span></div>'
             '<a href="/pl/subjects/12/card.pdf">x</a></div>'
             '<div class="data-table__row"><div class="cell"><span class="cell__inner">SEMINAR</span></div></div>')


def test_one_course_for_two_semesters_and_folder_names(bot, monkeypatch):
    from moodle_sync import state as state_mod, studyplan

    plan = studyplan.parse_plan(PLAN_2SEM)
    monkeypatch.setenv("STUDY_PLAN_URL", "https://ects.example.edu/pl/courses/1")
    monkeypatch.setattr(studyplan, "load_plan", lambda state=None, force=False: plan)
    monkeypatch.setattr(moodle, "my_courses", lambda: [{"id": 7, "fullname": "Team project", "startdate": 0}])
    interactive.handle_command("przypisz", [], "1")
    click("mc:7")
    click("ms:7:1")
    click("mk:7:0")
    click("ma:7")
    click("mas:7:2")
    click("mka:7:0")
    assert state_mod.load()["course_map"] == {"7": ["1|PROJECT I|11", "2|PROJECT II|12"]}
    assert "Semester 1/Project I + Semester 2/Project II" in bot["edits"][-1][0]

    from datetime import datetime
    splits = studyplan.course_splits(moodle.my_courses(), plan, state_mod.load())
    old = datetime(2026, 4, 1).timestamp()
    new = datetime(2026, 11, 5).timestamp()
    assert studyplan.pick_by_date(splits[7], old, plan)[1:] == ("Semester 1", "Project I")
    assert studyplan.pick_by_date(splits[7], new, plan)[1:] == ("Semester 2", "Project II")

    click("mc:7")
    click("mf:7")
    interactive.on_text({"text": "ZPB – nasz projekt", "message_id": 4}, "1")
    assert state_mod.load()["folder_names"] == {"1|PROJECT I|11": "ZPB – nasz projekt"}
    assert studyplan.course_layout(moodle.my_courses(), {}, plan, state_mod.load())[7][1] == "ZPB – nasz projekt"


def test_own_card_link(bot, monkeypatch):
    from moodle_sync import state as state_mod, studyplan

    plan = studyplan.parse_plan(PLAN_2SEM)
    monkeypatch.setenv("STUDY_PLAN_URL", "https://ects.example.edu/pl/courses/1")
    monkeypatch.setattr(studyplan, "load_plan", lambda state=None, force=False: plan)

    class Resp:
        content, headers = b"%PDF-1.4 card", {"Content-Type": "application/pdf"}

        def raise_for_status(self):
            pass

    monkeypatch.setattr(interactive.requests, "get", lambda url, **kw: Resp())
    interactive.handle_command("karta", [], "1")
    assert "Semester 2: Seminar" in str(bot["sent"][-1][1])
    click("ck:0")
    interactive.on_text({"text": "https://uni.example/syllabus.pdf", "message_id": 5}, "1")
    st = state_mod.load()
    assert st["custom_cards"] == {"2|SEMINAR|": {"url": "https://uni.example/syllabus.pdf", "ext": ".pdf"}}
    missing = []
    cards = studyplan.planned_cards([], plan, {}, set(), missing, st)
    assert cards["custom:2|SEMINAR|"][0].as_posix() == "Semester 2/Seminar/Subject card.pdf"
    assert missing == []
    assert studyplan.card_url("custom:2|SEMINAR|", st) == "https://uni.example/syllabus.pdf"


def test_errors_command_shows_the_full_output(bot):
    from moodle_sync import state as state_mod

    state_mod.save({"last_run": {"end": 1_700_000_000, "steps": [["Upload to cloud", "ERROR (code 1)", 1]]},
                    "last_errors": {"Upload to cloud": "$ rclone moveto a b\n  ERROR : a: directory not found"}})
    interactive.handle_command("bledy", [], "1")
    text = bot["sent"][-1][0]
    assert "❌ Upload to cloud" in text and "directory not found" in text


def test_folders_are_created_before_parallel_moves(monkeypatch):
    from moodle_sync import state as state_mod, storage

    calls = []
    monkeypatch.setattr(storage, "remote_files", lambda: {"Old/a.pdf", "Old/b.pdf", "Old/c.pdf"})
    monkeypatch.setattr(storage, "rclone", lambda *args, quiet=False: calls.append(args) or 0)
    state_mod.save({"remote_moves": [{"from": f"Old/{n}.pdf", "to": f"Sem 2/New/{n}.pdf"} for n in "abc"]})
    storage.apply_remote_moves(dry_run=False)
    mkdirs = [c for c in calls if c[0] == "mkdir"]
    first_move = next(i for i, c in enumerate(calls) if c[0] == "moveto")
    assert len(mkdirs) == 1 and calls.index(mkdirs[0]) < first_move  # one folder, created once, before moving


def test_duplicate_folders_are_found():
    from moodle_sync import storage

    items = [{"Path": "Sem 1/English", "IsDir": True}, {"Path": "Sem 1/English", "IsDir": True},
             {"Path": "Sem 1/English/a.pdf", "Size": 1}, {"Path": "Sem 1/Bio", "IsDir": True}]
    assert storage.duplicate_paths(items) == ["Sem 1/English"]



def test_rename_a_whole_module(bot, monkeypatch):
    from moodle_sync import state as state_mod, studyplan

    plan = studyplan.parse_plan(
        '<div><h3><strong>Semestr: 2</strong>&nbsp;(2025/2026 - letni)</h3></div>'
        '<div class="data-table__row"><div class="cell"><span class="cell__inner">HUMANITIES</span></div></div>'
        '<div class="data-table__row secondary-row"><div class="cell"><div class="cell__inner">ART</div></div>'
        '<a href="/pl/subjects/1/card.pdf">x</a></div>')
    monkeypatch.setenv("STUDY_PLAN_URL", "https://ects.example.edu/pl/courses/1")
    monkeypatch.setattr(studyplan, "load_plan", lambda state=None, force=False: plan)
    interactive.handle_command("obieralne", [], "1")
    click("elr:0")
    interactive.on_text({"text": "Automation and GenAI", "message_id": 3}, "1")
    st = state_mod.load()
    assert st["folder_names"] == {"2|HUMANITIES|": "Automation and GenAI"}
    st["custom_cards"] = {"2|HUMANITIES|": {"url": "https://uni.example/card.pdf", "ext": ".pdf"}}
    cards = studyplan.planned_cards([], plan, {}, set(), None, st)
    assert cards["custom:2|HUMANITIES|"][0].as_posix() == "Semester 2/Automation and GenAI/Subject card.pdf"



def test_long_module_has_pages(bot, monkeypatch):
    from moodle_sync import studyplan

    options = "".join(f'<div class="data-table__row secondary-row"><div class="cell"><div class="cell__inner">'
                      f'Option {n}</div></div><a href="/pl/subjects/{n}/card.pdf">x</a></div>' for n in range(1, 36))
    plan = studyplan.parse_plan('<div><h3><strong>Semestr: 2</strong>&nbsp;(2025/2026 - letni)</h3></div>'
                                '<div class="data-table__row"><div class="cell"><span class="cell__inner">'
                                'Humanities</span></div></div>' + options)
    monkeypatch.setenv("STUDY_PLAN_URL", "https://ects.example.edu/pl/courses/1")
    monkeypatch.setattr(studyplan, "load_plan", lambda state=None, force=False: plan)
    interactive.handle_command("obieralne", [], "1")
    click("elm:0")
    labels = [b[0] for row in bot["edits"][-1][1] for b in row]
    assert "⬜ 20. Option 20" in labels and "⬜ 21. Option 21" not in labels and "▶" in labels
    click("elp:0:1")
    labels = [b[0] for row in bot["edits"][-1][1] for b in row]
    assert "⬜ 35. Option 35" in labels and "◀" in labels
    click("elt:0:34")
    assert "☑️ 35. Option 35" in [b[0] for row in bot["edits"][-1][1] for b in row]  # stays on page 2
