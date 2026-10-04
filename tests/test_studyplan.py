from datetime import datetime
from pathlib import Path

import pytest
from conftest import make_file

from moodle_sync import config, files, state, studyplan

PLAN_URL = "https://ects.example.edu/en/courses/100"


def row(name: str, card: int | None, secondary: bool = False) -> str:
    cls = "data-table__row secondary-row" if secondary else "data-table__row"
    link = f'<a href="https://ects.example.edu/en/subjects/{card}/card.pdf">Download</a>' if card else ""
    # the catalogue repeats the card link in a mobile-only block of the same row
    return (f'<div class="{cls}"><div class="cell"><span class="cell__inner">{name}</span></div>'
            f'<div class="cell">6</div><div class="cell">{link}</div><div class="cell-mobile">{link}</div></div>')


def plan_page() -> str:
    return (
        '<div class="data-table__header"><h3><strong>Semester: 1</strong>&nbsp;(2025/2026 - winter)</h3></div>'
        + row("Mathematics I", 11) + row("Programming", 12)
        + row("Elective humanities", None) + row("History of science", 13, secondary=True)
        + row("Ethics &amp; society", 14, secondary=True)
        + '<div class="data-table__header"><h3><strong>Semestr: 2</strong>&nbsp;(2025/2026 - letni)</h3></div>'
        + row("Mathematics II", 21) + row("Databases", 22)
    )


PLAN = studyplan.parse_plan(plan_page())


def ts(year, month, day=1):
    return datetime(year, month, day).timestamp()


class TestParsing:
    def test_semesters_subjects_cards_and_electives(self):
        assert [(s["number"], s["year"], s["season"]) for s in PLAN] == [(1, 2025, "winter"), (2, 2025, "summer")]
        first = PLAN[0]["subjects"]
        assert [(s["name"], s["card"], s["elective"]) for s in first] == [
            ("Mathematics I", 11, False), ("Programming", 12, False),
            ("History of science", 13, True), ("Ethics & society", 14, True)]  # module header without card skipped

    def test_programs_listing(self):
        page = ('<a class="cell__inner collapsed" href="#course_1">\n  Automation\n</a>'
                '<div class="cell__inner">FACULTY</div>'
                '<a href="#course_1_1">full-time - second cycle</a>'
                '<a class="x" href="https://ects.example.edu/pl/courses/501">rok rozpoczęcia 2025/2026\n'
                '  (obecnie semestr 2)</a>'
                '<a href="https://ects.example.edu/pl/courses/502">rok rozpoczęcia 2026/2027</a>')
        assert studyplan.parse_programs(page) == [
            {"field": "Automation", "mode": "full-time - second cycle", "start": "2025/2026", "current": 2,
             "url": "https://ects.example.edu/pl/courses/501"},
            {"field": "Automation", "mode": "full-time - second cycle", "start": "2026/2027", "current": None,
             "url": "https://ects.example.edu/pl/courses/502"}]

    def test_specialisations(self):
        page = ('<a href="https://ects.example.edu/pl/courses/7/subcourses/8/subjects">Specjalność: Robotics</a>'
                '<a href="/pl/courses/7/subcourses/9/subjects">\n Specialisation: Control </a>')
        assert studyplan.parse_specializations(page, "https://ects.example.edu") == [
            ("Robotics", "https://ects.example.edu/pl/courses/7/subcourses/8/subjects"),
            ("Control", "https://ects.example.edu/pl/courses/7/subcourses/9/subjects")]

    def test_any_program_link_becomes_its_subject_list(self):
        assert studyplan.normalize_plan_url(PLAN_URL) == PLAN_URL + "/subjects"
        url = "https://ects.example.edu/pl/courses/7/subcourses/8/subjects"
        assert studyplan.normalize_plan_url(url) == url
        assert studyplan.normalize_plan_url(PLAN_URL + "/plan.xls") == PLAN_URL + "/subjects"


class TestTermsAndMatching:
    def test_terms(self):
        assert studyplan.term_of(ts(2025, 10, 1)) == (2025, "winter")
        assert studyplan.term_of(ts(2026, 1, 15)) == (2025, "winter")
        assert studyplan.term_of(ts(2026, 2, 20)) == (2025, "summer")
        assert studyplan.term_of(0) is None

    def test_semester_from_plan_or_start(self):
        assert studyplan.semester_by_term((2025, "summer"), PLAN, None) == 2
        assert studyplan.semester_by_term((2026, "winter"), None, (2025, "winter")) == 3
        assert studyplan.semester_by_term((2024, "summer"), None, (2025, "winter")) is None

    def test_most_specific_subject_wins(self):
        sem, subject = studyplan.match_subject("Mathematics II 2025/2026 (group 3)", PLAN)
        assert (sem["number"], subject["name"]) == (2, "Mathematics II")
        assert studyplan.match_subject("Mathematics I - lecture", PLAN)[1]["name"] == "Mathematics I"
        assert studyplan.match_subject("Library training", PLAN) is None

    def test_overrides_from_courses_json(self):
        courses = [{"id": 1, "fullname": "Maths for engineers", "startdate": ts(2025, 10, 1)},
                   {"id": 2, "fullname": "English B2", "startdate": ts(2026, 2, 20)},
                   {"id": 3, "fullname": "Sandbox", "startdate": 0}]
        cfg = {"plan": {"for engineers": "Mathematics II"}, "semester": {"sandbox": 1}}
        got = studyplan.assign_courses(courses, PLAN, cfg)
        assert got[1] == {"semester": 2, "subject": "Mathematics II", "card": 21, "key": "2|Mathematics II"}
        assert got[2] == {"semester": 2, "subject": None, "card": None, "key": None}  # by its start date
        assert got[3] == {"semester": 1, "subject": None, "card": None, "key": None}


@pytest.fixture
def with_plan(monkeypatch):
    monkeypatch.setenv("STUDY_PLAN_URL", PLAN_URL)
    monkeypatch.setattr(studyplan, "_get", lambda url, timeout=30: FakeResponse(plan_page()))
    return monkeypatch


class FakeResponse:
    def __init__(self, text: str = "", content: bytes = b""):
        self.text, self.content = text, content


class TestFileLayout:
    def test_semester_folder_and_subject_name(self, with_plan):
        courses = [{"id": 10, "fullname": "Mathematics II [2025/26]", "startdate": ts(2026, 2, 20)}]
        f = make_file(course_name=courses[0]["fullname"], section_name="Lectures")
        files.apply_layout([f], courses, {}, {})
        assert files.relative_path(f, {}) == Path("Semester 2", "Mathematics II", "Lectures", "a.pdf")
        assert files.relative_path(f, {"names": {"mathematics": "Maths"}}).parts[:2] == ("Semester 2", "Maths")

    def test_polish_folder_and_switch_off(self, with_plan):
        with_plan.setenv("LANGUAGE", "pl")
        courses = [{"id": 10, "fullname": "Programming", "startdate": ts(2025, 10, 1)}]
        f = make_file(course_name="Programming")
        files.apply_layout([f], courses, {}, {})
        assert files.relative_path(f, {}).parts[0] == "Semestr 1"
        with_plan.setenv("SEMESTER_FOLDERS", "0")
        files.apply_layout([f], courses, {}, {})
        assert files.relative_path(f, {}).parts[0] == "Programming"

    def test_plan_cached_and_offline(self, with_plan):
        st = {}
        assert studyplan.load_plan(st) == PLAN
        with_plan.setattr(studyplan, "_get", lambda url, timeout=30: (_ for _ in ()).throw(
            studyplan.requests.ConnectionError("offline")))
        assert studyplan.load_plan(st, force=True) == PLAN  # catalogue down -> saved copy
        with pytest.raises(RuntimeError):
            studyplan.load_plan({}, force=True)  # nothing saved -> refuse instead of changing the layout

    def test_no_plan_no_change(self):
        f = make_file()
        files.apply_layout([f], [{"id": 10, "fullname": "Algorithms"}], {}, {})
        assert files.relative_path(f, {}) == Path("Algorithms", "Lectures", "a.pdf")


class TestCards:
    def setup_cards(self, with_plan, pdf=b"%PDF-1.7 card"):
        sent = []
        with_plan.setattr(studyplan, "notify", lambda kind, title, message="", urgent=False: sent.append(title))
        with_plan.setattr(studyplan.time, "sleep", lambda s: None)
        pages = {"pdf": pdf}

        def fake_get(url, timeout=30):
            return FakeResponse(content=pages["pdf"]) if url.endswith(".pdf") else FakeResponse(plan_page())

        with_plan.setattr(studyplan, "_get", fake_get)
        from moodle_sync import moodle
        with_plan.setattr(moodle, "my_courses", lambda: [
            {"id": 10, "fullname": "History of science", "startdate": ts(2025, 10, 1)}])
        return sent, pages

    def test_downloads_compulsory_and_matched_elective_cards(self, with_plan):
        sent, _ = self.setup_cards(with_plan)
        assert studyplan.run() == 0
        root = config.download_dir()
        got = sorted(p.relative_to(root).as_posix() for p in root.rglob("*.pdf"))
        assert got == ["Semester 1/History of science/Subject card.pdf", "Semester 1/Mathematics I/Subject card.pdf",
                       "Semester 1/Programming/Subject card.pdf", "Semester 2/Databases/Subject card.pdf",
                       "Semester 2/Mathematics II/Subject card.pdf"]  # "Ethics" (elective, no course) skipped
        assert sent == ["Subject cards (5)"]

    def test_recheck_spots_changes_and_moves_renamed(self, with_plan):
        sent, pages = self.setup_cards(with_plan)
        studyplan.run()
        sent.clear()
        assert studyplan.run() == 0 and sent == []  # checked less than 30 days ago
        pages["pdf"] = b"%PDF-1.7 new syllabus"
        studyplan.run(force=True)
        assert sent.count("Subject card changed: Programming") == 1
        with_plan.setenv("SEMESTER_FOLDERS", "0")
        studyplan.run()
        assert (config.download_dir() / "Programming" / "Subject card.pdf").exists()
        moves = state.load()["remote_moves"]
        assert {"from": "Semester 1/Programming/Subject card.pdf", "to": "Programming/Subject card.pdf"} in moves

    def test_rejects_non_pdf(self, with_plan):
        self.setup_cards(with_plan, pdf=b"<html>error</html>")
        assert studyplan.run() == 1
        assert not list(config.download_dir().rglob("*.pdf"))

    def test_off_without_plan(self):
        assert studyplan.run() == 2


class TestCatalogAddress:
    def test_from_setting_or_plan_url(self, monkeypatch):
        assert studyplan.catalog_url("https://ects.example.edu") == "https://ects.example.edu/pl"
        assert studyplan.catalog_url("https://ects.example.edu/en/courses/7") == "https://ects.example.edu/en"
        assert studyplan.catalog_url() == ""
        monkeypatch.setenv("STUDY_PLAN_URL", "https://ects.example.edu/pl/courses/7/subjects")
        assert studyplan.catalog_url() == "https://ects.example.edu/pl"
        monkeypatch.setenv("STUDY_CATALOG", "https://other.example.edu/en/")
        assert studyplan.catalog_url() == "https://other.example.edu/en"

    def test_search_needs_a_catalogue(self, capsys):
        assert studyplan.search("anything") == 2
        assert "STUDY_CATALOG" in capsys.readouterr().out


class TestShoutingCatalogue:
    def test_readable_names(self):
        assert studyplan.readable("MACHINE LEARNING I SIECI NEURONOWE") == "Machine learning i sieci neuronowe"
        assert studyplan.readable("Mathematics II") == "Mathematics II"
        assert studyplan.folder_subject("CHEMOINFORMATYKA") is None and studyplan.folder_subject("Databases") == "Databases"

    def test_moodle_name_wins_over_capitals(self, monkeypatch):
        page = ('<div><h3><strong>Semestr: 1</strong>&nbsp;(2025/2026 - zimowy)</h3></div>'
                + row("CHEMOINFORMATYKA", 31) + row("OTWARTE BAZY DANYCH", 32))
        plan = studyplan.parse_plan(page)
        monkeypatch.setenv("STUDY_PLAN_URL", PLAN_URL)
        courses = [{"id": 5, "fullname": "Chemoinformatyka [2025/26]", "startdate": ts(2025, 10, 1)}]
        layout = studyplan.course_layout(courses, {}, plan)
        assert layout[5] == ("Semester 1", None)  # files keep the Moodle course name
        cards = {path.as_posix() for path, _ in studyplan.planned_cards(courses, plan, {}).values()}
        assert cards == {"Semester 1/Chemoinformatyka [2025_26]/Subject card.pdf",
                         "Semester 1/Otwarte bazy danych/Subject card.pdf"}



ELECTIVE_PAGE = ('<div><h3><strong>Semestr: 2</strong>&nbsp;(2025/2026 - letni)</h3></div>'
                 + row("Proteomics", 41) + row("Safety training", None)
                 + row("Elective module A", None) + row("Option one", 42, secondary=True)
                 + row("Option two", 43, secondary=True) + row("Option three", None, secondary=True))
ELECTIVE_PLAN = studyplan.parse_plan(ELECTIVE_PAGE)


class TestElectivesAndMissingCards:
    def test_modules_and_subjects_without_card(self):
        subjects = ELECTIVE_PLAN[0]["subjects"]
        assert [(x["name"], x["card"], x["elective"], x["module"]) for x in subjects] == [
            ("Proteomics", 41, False, None), ("Safety training", None, False, None),
            ("Option one", 42, True, "Elective module A"), ("Option two", 43, True, "Elective module A"),
            ("Option three", None, True, "Elective module A")]

    def test_pending_choice_then_cards_of_the_pick(self, monkeypatch):
        monkeypatch.setenv("STUDY_PLAN_URL", PLAN_URL)
        st = {}
        pending = studyplan.pending_modules(ELECTIVE_PLAN, [], {}, st)
        assert [(m["module"], m["options"]) for m in pending] == [
            ("Elective module A", ["Option one", "Option two", "Option three"])]
        missing = []
        cards = studyplan.planned_cards([], ELECTIVE_PLAN, {}, studyplan.chosen_keys(ELECTIVE_PLAN, st), missing)
        assert set(cards) == {41} and missing == ["Semester 2: Safety training"]

        st["electives"] = {"2|Elective module A": ["Option two", "Option three"]}
        assert studyplan.pending_modules(ELECTIVE_PLAN, [], {}, st) == []
        missing = []
        cards = studyplan.planned_cards([], ELECTIVE_PLAN, {}, studyplan.chosen_keys(ELECTIVE_PLAN, st), missing)
        assert set(cards) == {41, 43}
        assert missing == ["Semester 2: Safety training", "Semester 2: Option three"]

    def test_a_moodle_course_counts_as_the_choice(self, monkeypatch):
        monkeypatch.setenv("STUDY_PLAN_URL", PLAN_URL)
        courses = [{"id": 1, "fullname": "Option one 2025/26", "startdate": ts(2026, 2, 20)}]
        assert studyplan.pending_modules(ELECTIVE_PLAN, courses, {}, {}) == []
        assert 42 in studyplan.planned_cards(courses, ELECTIVE_PLAN, {})

    def test_missing_list_notified_once(self, monkeypatch):
        sent = []
        monkeypatch.setattr(studyplan, "notify", lambda kind, title, message="", urgent=False: sent.append(title))
        st = {}
        studyplan.notify_once(st, "syllabi_missing", ["A"], "plan_cards_missing")
        studyplan.notify_once(st, "syllabi_missing", ["A"], "plan_cards_missing")
        studyplan.notify_once(st, "syllabi_missing", ["A", "B"], "plan_cards_missing")
        assert sent == ["Subjects without a card in the catalogue (1)", "Subjects without a card in the catalogue (2)"]
