import json
import os
from pathlib import Path

import pytest
from conftest import make_file

from moodle_sync import config, files, state


class TestCategorize:
    def test_section_name_wins(self):
        f = make_file(section_name="Lab sessions", module_name="Lecture slides")
        assert files.categorize(f, {}) == "Labs"

    def test_falls_back_to_module_then_file_name(self):
        assert files.categorize(make_file(module_name="Project brief"), {}) == "Projects"
        assert files.categorize(make_file(module_name="Stuff", filename="lecture3.pdf"), {}) == "Lectures"

    def test_polish_keywords_and_folder_names(self, monkeypatch):
        monkeypatch.setenv("LANGUAGE", "pl")
        f = make_file(section_name="WYKŁADY I MATERIAŁY", module_name="x")
        assert files.categorize(f, {}) == "Wyklady"
        assert files.categorize(make_file(section_name="Ćwiczenia audytoryjne"), {}) == "Cwiczenia"

    def test_syllabus_is_not_a_lab(self):
        assert files.categorize(make_file(module_name="Syllabus", filename="syllabus.pdf"), {}) == "Other materials"

    def test_default_category_from_courses_json(self):
        cfg = {"default_category": {"algo": "exercises"}}
        assert files.categorize(make_file(module_name="Stuff"), cfg) == "Exercises"

    def test_custom_rules_go_first(self):
        cfg = {"category_rules": [{"folder": "Exams", "pattern": "egzamin|exam"}]}
        f = make_file(section_name="Exam and lab info")
        assert files.categorize(f, cfg) == "Exams"


class TestPaths:
    def test_folder_module_keeps_structure(self):
        f = make_file(modname="folder", module_name="Materials", filepath="/Demos/", filename="w2.c",
                      section_name="Lecture")
        assert files.relative_path(f, {}) == Path("Algorithms", "Lectures", "Materials", "Demos", "w2.c")

    def test_course_name_override(self):
        cfg = {"names": {"algo": "Algo & DS"}}
        assert files.relative_path(make_file(), cfg).parts[0] == "Algo & DS"

    def test_collision_is_case_insensitive(self):
        owners = {"a/x.pdf": "key1"}
        assert files.resolve_collision(Path("a/X.pdf"), "key2", owners) == Path("a/X (2).pdf")
        assert files.resolve_collision(Path("a/x.pdf"), "key1", owners) == Path("a/x.pdf")

    def test_new_revision_keeps_the_same_path(self):
        old = make_file(id="url:rev1")
        new = make_file(id="url:rev2")  # same module/name -> same logical key
        plan = files.plan_paths([old, new], downloaded={"url:rev1": {}}, cfg={})
        assert plan["url:rev1"] == plan["url:rev2"]

    def test_existing_file_keeps_its_name_when_new_one_clashes(self):
        existing = make_file(id="url:b", module_id=200, module_name="Z")
        newcomer = make_file(id="url:a", module_id=100, module_name="A")  # would sort first
        plan = files.plan_paths([existing, newcomer], downloaded={"url:b": {}}, cfg={})
        assert plan["url:b"].name == "a.pdf"
        assert plan["url:a"].name == "a (2).pdf"


def test_stable_id_prefers_contenthash_then_url():
    assert files.stable_id({"contenthash": "abc", "fileurl": "u"}) == "hash:abc"
    assert files.stable_id({"fileurl": "u"}) == "url:u"
    assert files.stable_id({"filename": "f", "filesize": 1, "timemodified": 2}) == "meta:f:1:2"


def test_relocate_moves_file_and_queues_cloud_move(isolated):
    root = config.download_dir()
    old = root / "Algorithms" / "Other materials" / "a.pdf"
    old.parent.mkdir(parents=True)
    old.write_text("x")
    os.utime(old, (1_700_000_000, 1_700_000_000))
    f = make_file(section_name="Lectures")
    downloaded = {f["id"]: {"path": "Algorithms/Other materials/a.pdf", "key": files.logical_key(f)}}
    st = {"downloaded": downloaded}

    plan = files.plan_paths([f], downloaded, {})
    moves = files.planned_moves([f], plan, downloaded)
    assert files.relocate(moves, downloaded, st, dry_run=False) == 1

    new = root / "Algorithms" / "Lectures" / "a.pdf"
    assert new.read_text() == "x" and not old.exists()
    assert int(new.stat().st_mtime) == 1_700_000_000  # mtime kept (rclone compares it)
    assert not (root / "Algorithms" / "Other materials").exists()  # empty dir removed
    saved = json.loads(config.STATE_FILE.read_text(encoding="utf-8"))
    assert saved["remote_moves"] == [{"from": "Algorithms/Other materials/a.pdf", "to": "Algorithms/Lectures/a.pdf"}]
    assert state.load()["downloaded"][f["id"]]["path"] == "Algorithms/Lectures/a.pdf"


def test_mass_move_is_blocked_until_confirmed(monkeypatch):
    """Regression: LANGUAGE lost in a broken .env must not rename the whole archive."""
    from moodle_sync import moodle

    course_files = [make_file(id=f"url:{i}", module_id=i, filename=f"w{i}.pdf", section_name="Wykłady")
                    for i in range(30)]
    monkeypatch.setattr(moodle, "my_courses", lambda: [])
    monkeypatch.setattr(files, "collect_files", lambda courses: course_files)
    monkeypatch.setattr(files, "download_file", lambda f, dest: pytest.fail("must not download"))
    monkeypatch.setenv("LANGUAGE", "pl")
    st = {"downloaded": {f["id"]: {"path": files.relative_path(f, {}).as_posix(), "key": files.logical_key(f)}
                         for f in course_files}}
    st["layout_sig"] = files.layout_signature({}, st)  # a steady state: no deliberate layout change
    state.save(st)

    monkeypatch.setenv("LANGUAGE", "en")  # the accident: every folder would become English
    assert files.run() == 1
    assert "Wyklady" in state.load()["downloaded"]["url:0"]["path"]  # nothing moved
    assert "remote_moves" not in state.load()

    assert files.run(reorganize=True) == 0  # explicitly confirmed
    assert "Lectures" in state.load()["downloaded"]["url:0"]["path"]
    assert len(state.load()["remote_moves"]) == 30


def test_deliberate_layout_change_moves_without_the_fuse(monkeypatch):
    """/assign, /electives, courses.json or a new layout version: moved at once, with a notification."""
    from moodle_sync import moodle

    sent = []
    course_files = [make_file(id=f"url:{i}", module_id=i, filename=f"w{i}.pdf") for i in range(30)]
    monkeypatch.setattr(moodle, "my_courses", lambda: [])
    monkeypatch.setattr(files, "collect_files", lambda courses: course_files)
    monkeypatch.setattr(files, "notify", lambda kind, title, message="", urgent=False: sent.append(title))
    st = {"downloaded": {f["id"]: {"path": files.relative_path(f, {}).as_posix(), "key": files.logical_key(f)}
                         for f in course_files}}
    st["layout_sig"] = files.layout_signature({}, st)
    state.save(st)
    (config.DATA_DIR / "courses.json").write_text(json.dumps({"names": {"algo": "Algorithms 2"}}), encoding="utf-8")
    assert files.run() == 0
    assert state.load()["downloaded"]["url:0"]["path"].startswith("Algorithms 2/")
    assert sent == ["Files moved into the new folders (30)"]
    assert files.run() == 0 and len(sent) == 1  # steady again


class TestNetMoves:
    """Regression: an interrupted PL->EN re-organisation followed by EN->PL."""

    def net(self, queue, existing):
        from moodle_sync.storage import net_moves
        return net_moves([{"from": a, "to": b} for a, b in queue], set(existing))

    def test_already_done_move_is_dropped(self):
        assert self.net([("pl/a", "en/a"), ("en/a", "pl/a")], {"pl/a"}) == []       # never executed -> round trip

    def test_executed_move_is_reverted_once(self):
        assert self.net([("pl/a", "en/a"), ("en/a", "pl/a")], {"en/a"}) == [{"from": "en/a", "to": "pl/a"}]

    def test_chain_collapses(self):
        assert self.net([("a", "b"), ("b", "c")], {"a"}) == [{"from": "a", "to": "c"}]

    def test_missing_source_costs_nothing(self):
        assert self.net([("gone", "x")], {"other"}) == []


def test_apply_remote_moves_only_runs_net_moves(monkeypatch):
    from moodle_sync import storage

    state.save({"remote_moves": [{"from": "pl/a", "to": "en/a"}, {"from": "pl/b", "to": "en/b"},
                                 {"from": "en/a", "to": "pl/a"}, {"from": "en/b", "to": "pl/b"},
                                 {"from": "pl/c", "to": "en/c"}]})
    monkeypatch.setattr(storage, "remote_files", lambda: {"en/a", "pl/b", "pl/c"})  # a moved, b/c not yet
    calls = []
    monkeypatch.setattr(storage, "_move_one", lambda m: calls.append((m["from"], m["to"])) or m["from"] != "pl/c")
    monkeypatch.setattr(storage, "rclone", lambda *a, **k: 0)

    assert storage.apply_remote_moves(dry_run=False) == 1           # pl/c failed once
    assert sorted(calls) == [("en/a", "pl/a"), ("pl/c", "en/c")]    # b's round trip needs no call
    assert state.load()["remote_moves"] == [{"from": "pl/c", "to": "en/c", "attempts": 1}]


def test_too_large_is_retried_after_raising_the_limit(monkeypatch):
    f = make_file(filesize=50 * 1024 * 1024)
    downloaded = {f["id"]: {"skipped": "too_large"}}
    monkeypatch.setenv("MAX_FILE_MB", "10")
    assert files.too_large(f) and not files.is_pending(f, downloaded)
    monkeypatch.setenv("MAX_FILE_MB", "100")
    assert files.is_pending(f, downloaded)


def test_new_course_is_announced_once(monkeypatch):
    from moodle_sync import moodle

    sent = []
    courses = [{"id": 1, "fullname": "Algorithms", "startdate": 0}]
    monkeypatch.setenv("SUBMITTED_FILES", "0")
    monkeypatch.setattr(moodle, "my_courses", lambda: courses)
    monkeypatch.setattr(files, "collect_files", lambda courses: [])
    monkeypatch.setattr(files, "notify", lambda kind, title, message="", urgent=False: sent.append((title, message)))
    assert files.run() == 0 and sent == []  # the first run only remembers what's there
    courses.append({"id": 2, "fullname": "Databases [2026/27]", "startdate": 0})
    assert files.run() == 0
    assert sent == [("New Moodle courses (1)", "• Databases [2026/27] → Databases [2026/27]")]
    assert files.run() == 0 and len(sent) == 1


def test_new_course_outside_the_plan_asks_for_assign(monkeypatch):
    from moodle_sync import studyplan

    plan = studyplan.parse_plan('<div><h3><strong>Semestr: 1</strong>&nbsp;(2025/2026 - zimowy)</h3></div>'
                                '<div class="data-table__row"><div class="cell"><span class="cell__inner">'
                                'CHEMOINFORMATYKA</span></div><a href="/pl/subjects/31/card.pdf">x</a></div>')
    monkeypatch.setenv("STUDY_PLAN_URL", "https://ects.example.edu/pl/courses/1")
    monkeypatch.setattr(studyplan, "load_plan", lambda state=None, force=False: plan)
    st = {"known_courses": []}
    lines = files.new_courses([{"id": 7, "fullname": "Chemoinformatyka 2025/2026", "startdate": 0},
                               {"id": 8, "fullname": "Kompetencje informacyjne", "startdate": 0}], {}, st)
    assert lines[0].endswith("→ Semester 1/Chemoinformatyka")
    assert "/assign" in lines[1] and "/assign" not in lines[0]
    assert st["known_courses"] == [7, 8]


def test_submitted_files_land_in_their_own_folder(monkeypatch):
    from moodle_sync import moodle

    calls = []

    def fake_call(fn, **kw):
        calls.append(fn)
        if fn == "mod_assign_get_assignments":
            return {"courses": [{"id": 1, "assignments": [{"id": 9, "cmid": 90, "name": "Report 1"}]}]}
        return {"lastattempt": {"submission": {"plugins": [{"type": "file", "fileareas": [{"files": [
            {"filename": "report.pdf", "filepath": "/", "fileurl": "https://m.example/pluginfile.php/1/report.pdf",
             "filesize": 3, "timemodified": 1}]}]}]}}}

    monkeypatch.setattr(moodle, "call", fake_call)
    courses = [{"id": 1, "fullname": "Algorithms"}]
    st = {}
    [f] = files.submitted_files(courses, st)
    assert files.relative_path(f, {}).as_posix() == "Algorithms/Submitted work/Report 1/report.pdf"
    assert files.submitted_files(courses, st) == [f] and calls.count("mod_assign_get_submission_status") == 1  # cached

    sent = []
    monkeypatch.setattr(moodle, "my_courses", lambda: courses)
    monkeypatch.setattr(files, "collect_files", lambda courses: [])
    monkeypatch.setattr(files, "download_file", lambda f, dest: (dest.parent.mkdir(parents=True, exist_ok=True),
                                                                 dest.write_bytes(b"pdf")))
    monkeypatch.setattr(files, "notify", lambda kind, title, message="", urgent=False: sent.append(title))
    assert files.run() == 0
    assert state.load()["downloaded"][f["id"]]["path"] == "Algorithms/Submitted work/Report 1/report.pdf"
    assert sent == []  # your own files are not news


def test_submitted_files_can_be_turned_off(monkeypatch):
    monkeypatch.setenv("SUBMITTED_FILES", "0")
    assert files.submitted_files([{"id": 1, "fullname": "A"}], {}) == []


def test_one_course_only(monkeypatch):
    from moodle_sync import moodle

    seen = []
    monkeypatch.setenv("SUBMITTED_FILES", "0")
    monkeypatch.setattr(moodle, "my_courses", lambda: [{"id": 1, "fullname": "A"}, {"id": 2, "fullname": "B"}])
    monkeypatch.setattr(files, "collect_files", lambda courses: seen.append([c["id"] for c in courses]) or [])
    assert files.run(course_ids=[2]) == 0
    assert seen == [[2]]
    assert state.load()["known_courses"] == [1, 2]  # new-course notices still see every course


def test_course_of_path_skips_the_semester_folder():
    assert files.course_of_path("Semester 2/Biochemistry/Lectures/a.pdf") == "Biochemistry"
    assert files.course_of_path("Semestr 1/Język angielski I/Inne materialy/a.pdf") == "Język angielski I"
    assert files.course_of_path("Algorithms/Lectures/a.pdf") == "Algorithms"
    assert files.course_of_path("Semester 2/Lectures/a.pdf") == "Semester 2"  # a course really named like that


def test_new_files_are_grouped_by_course():
    message = files.new_files_message(["Semester 1/Algorithms/Lectures/a.pdf", "Semester 1/Algorithms/Labs/b.pdf",
                                       "Semester 1/Databases/Lectures/c.pdf"])
    assert message == "📘 Algorithms\n• a.pdf\n• b.pdf\n\n📘 Databases\n• c.pdf"


class TestDownloadButtons:
    def test_one_file_one_button(self):
        st = {}
        assert files.download_buttons(["id-a"], ["A/Lectures/a.pdf"], st) == [
            [("⬇️ Download", f"dl:{files.file_token('id-a')}")]]
        assert "file_batches" not in st

    def test_many_files_first_few_and_all(self):
        st = {}
        ids = [f"url:https://m.example/pluginfile.php/{i}/long/name.pdf" for i in range(9)]
        rows = files.download_buttons(ids, [f"A/Lectures/{i}.pdf" for i in range(9)], st)
        assert [r[0][0] for r in rows] == [f"⬇️ {i}.pdf" for i in range(files.FILE_BUTTONS)] + ["⬇️ Download all (9)"]
        assert all(len(r[0][1].encode()) <= 64 for r in rows)
        batch = rows[-1][0][1].removeprefix("dla:")
        assert st["file_batches"] == {batch: ids}
        assert files.find_by_token(rows[2][0][1].removeprefix("dl:"), {i: {} for i in ids}) == ids[2]

    def test_old_batches_are_forgotten(self):
        st = {}
        for i in range(files.BATCHES_KEPT + 5):
            files.download_buttons([f"{i}-a", f"{i}-b"], ["A/a", "A/b"], st)
        assert len(st["file_batches"]) == files.BATCHES_KEPT
        assert list(st["file_batches"].values())[-1] == [f"{files.BATCHES_KEPT + 4}-a", f"{files.BATCHES_KEPT + 4}-b"]

    def test_can_be_turned_off(self, monkeypatch):
        monkeypatch.setenv("TELEGRAM_FILE_BUTTONS", "0")
        assert files.download_buttons(["id-a"], ["A/a.pdf"], {}) is None


def test_new_files_notification_names_the_course_and_offers_downloads(monkeypatch):
    from moodle_sync import moodle

    a = make_file()
    b = make_file(id="url:b", fileurl="https://m.example/b.pdf", filename="b.pdf", course_id=11,
                  course_name="Databases", module_id=101)
    sent = []
    monkeypatch.setenv("SUBMITTED_FILES", "0")
    monkeypatch.setattr(moodle, "my_courses", lambda: [{"id": 10, "fullname": "Algorithms", "startdate": 0},
                                                       {"id": 11, "fullname": "Databases", "startdate": 0}])
    monkeypatch.setattr(files, "collect_files", lambda courses: [a, b])
    monkeypatch.setattr(files, "download_file", lambda f, dest: (dest.parent.mkdir(parents=True, exist_ok=True),
                                                                 dest.write_bytes(b"x")))
    monkeypatch.setattr(files, "notify", lambda kind, title, message="", urgent=False, buttons=None:
                        sent.append((title, message, buttons)))
    assert files.run() == 0
    title, message, buttons = sent[-1]
    assert title == "New course materials (2)"
    assert message == "📘 Algorithms\n• a.pdf\n\n📘 Databases\n• b.pdf"
    assert [row[0] for row in buttons[:2]] == [("⬇️ a.pdf", f"dl:{files.file_token(a['id'])}"),
                                               ("⬇️ b.pdf", f"dl:{files.file_token('url:b')}")]
    assert state.load()["file_batches"][buttons[-1][0][1].removeprefix("dla:")] == [a["id"], "url:b"]
