import json

import pytest

from moodle_sync import config, webarchive


def test_cookie_forms():
    assert webarchive.parse_cookie("abc123") == {"MoodleSession": "abc123"}
    assert webarchive.parse_cookie("MoodleSessionold=x") == {"MoodleSessionold": "x"}
    assert webarchive.parse_cookie("Cookie: a=1; MoodleSession=2") == {"a": "1", "MoodleSession": "2"}


MOODLE3_COURSE = """
<li id="section-0" class="section main" aria-label="Ogólne">
  <a href="https://old.example/mod/forum/view.php?id=1"><span class="instancename">Ogłoszenia</span></a>
</li>
<li id="section-1" class="section main" aria-label="Wykłady">
  <a class="aalink" href="https://old.example/mod/resource/view.php?id=7"><img src="icon.png"></a>
  <a class="aalink" href="https://old.example/mod/resource/view.php?id=7"><span class="instancename">Wykład 1
    <span class="accesshide "> Plik</span></span></a>
  <div class="contentafterlink"><a href="https://old.example/pluginfile.php/5/mod_label/intro/extra.pdf">x</a></div>
</li>
<li id="section-2" class="section main" aria-label="Laboratoria">
  <a href="https://old.example/mod/folder/view.php?id=8"><span class="instancename">Instrukcje</span></a>
</li>"""


def test_course_page_of_an_old_moodle():
    mods = webarchive.parse_course_page(MOODLE3_COURSE)
    assert [(m["section"], m["modname"], m["name"]) for m in mods] == [
        ("Ogólne", "forum", "Ogłoszenia"), ("Wykłady", "resource", "Wykład 1"), ("Laboratoria", "folder", "Instrukcje")]
    assert webarchive.pluginfile_links(MOODLE3_COURSE) == ["https://old.example/pluginfile.php/5/mod_label/intro/extra.pdf"]


def test_state_of_moodle_4():
    state = {"section": [{"id": 11, "title": "Lectures"}],
             "cm": [{"id": 3, "sectionid": 11, "module": "resource", "name": "Slides", "url": "https://x/mod/resource/view.php?id=3"},
                    {"id": 4, "sectionid": 11, "module": "label", "name": "Note"}]}
    assert webarchive.parse_state(state) == [
        {"section": "Lectures", "modname": "resource", "name": "Slides", "url": "https://x/mod/resource/view.php?id=3"}]


def test_link_details():
    assert webarchive.link_details("https://x/pluginfile.php/9/mod_folder/content/0/Lab%201/a.pdf?forcedownload=1") == (
        "/Lab 1/", None)
    assert webarchive.link_details("https://x/pluginfile.php/9/assignsubmission_file/submission_files/4/r.pdf") == (
        "/", "submitted")


class FakeResponse:
    def __init__(self, url, body=b"", ctype="application/pdf", headers=None):
        self.url, self.content = url, body
        self.headers = {"Content-Type": ctype, **(headers or {})}
        self.text = body.decode("utf-8") if isinstance(body, bytes) else body

    def raise_for_status(self):
        pass

    def iter_content(self, size):
        yield self.content

    def json(self):
        return json.loads(self.text)

    def close(self):
        pass


class FakeHttp:
    def __init__(self, pages, ajax):
        self.pages, self.ajax, self.headers, self.got = pages, ajax, {}, []
        import requests
        self.cookies = requests.cookies.RequestsCookieJar()

    def get(self, url, **kw):
        self.got.append(url)
        page = self.pages[url]
        return page if isinstance(page, FakeResponse) else FakeResponse(url, page.encode(), "text/html")

    def post(self, url, params=None, json=None, **kw):
        method = params["info"]
        data = self.ajax.get(method)
        reply = [{"error": True, "exception": {"errorcode": "nope"}}] if data is None else [{"error": False, "data": data}]
        import json as j
        return FakeResponse(url, j.dumps(reply).encode(), "application/json")


def test_archive_a_course(monkeypatch, capsys):
    base = "https://old.example/moodle"
    pages = {
        f"{base}/my/": '<script>M.cfg = {"sesskey":"S1"}</script>',
        f"{base}/course/view.php?id=5": MOODLE3_COURSE,
        "https://old.example/mod/resource/view.php?id=7&redirect=1": FakeResponse(
            "https://old.example/pluginfile.php/1/mod_resource/content/1/W1.pdf", b"%PDF-1"),
        "https://old.example/mod/folder/view.php?id=8": '<a href="https://old.example/pluginfile.php/2/mod_folder/'
                                                       'content/0/Lab%201/i.pdf?forcedownload=1">i</a>',
        "https://old.example/pluginfile.php/2/mod_folder/content/0/Lab%201/i.pdf?forcedownload=1": FakeResponse(
            "https://old.example/pluginfile.php/2/mod_folder/content/0/Lab%201/i.pdf", b"%PDF-2",
            headers={"Content-Disposition": "attachment; filename*=UTF-8''Instrukcja%201.pdf"}),
        "https://old.example/pluginfile.php/5/mod_label/intro/extra.pdf": FakeResponse(
            "https://old.example/pluginfile.php/5/mod_label/intro/extra.pdf", b"%PDF-3"),
    }
    http = FakeHttp(pages, {"core_course_get_enrolled_courses_by_timeline_classification":
                            {"courses": [{"id": 5, "fullname": "Biochemia &amp; co"}]}})
    monkeypatch.setattr(webarchive.requests, "Session", lambda: http)
    monkeypatch.setattr(webarchive.getpass, "getpass", lambda prompt: "cookie")
    monkeypatch.setattr(webarchive, "PAUSE", 0)
    monkeypatch.setenv("LANGUAGE", "pl")
    assert webarchive.run(base + "/my/") == 0
    root = config.DATA_DIR / "archive" / "old_example_moodle"
    got = sorted(p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file())
    assert got == ["Biochemia & co/Inne materialy/extra.pdf", "Biochemia & co/Laboratoria/Instrukcje/Lab 1/Instrukcja 1.pdf",
                   "Biochemia & co/Wyklady/W1.pdf"]
    assert http.cookies.get("MoodleSession") == "cookie"

    http.got.clear()
    assert webarchive.run(base) == 0  # again: nothing downloaded twice
    assert not [u for u in http.got if "pluginfile" in u or "redirect=1" in u]


def test_expired_session(monkeypatch, capsys):
    base = "https://old.example/moodle"
    http = FakeHttp({f"{base}/my/": FakeResponse(f"{base}/login/index.php", b"", "text/html")}, {})
    monkeypatch.setattr(webarchive.requests, "Session", lambda: http)
    monkeypatch.setattr(webarchive.getpass, "getpass", lambda prompt: "old")
    assert webarchive.run(base) == 1
    assert "expired" in capsys.readouterr().out


@pytest.mark.parametrize("disposition,url,name", [
    ('attachment; filename="a b.pdf"', "https://x/y", "a b.pdf"),
    ("", "https://x/pluginfile.php/1/c/W%C5%82.pdf", "Wł.pdf"),
])
def test_filename(disposition, url, name):
    resp = FakeResponse(url, headers={"Content-Disposition": disposition} if disposition else {})
    assert webarchive.filename_of(resp) == name
