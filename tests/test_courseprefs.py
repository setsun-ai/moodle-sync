"""Per-course settings (courseprefs.py): what each course may send you and put into your calendar."""
import json

from moodle_sync import config, courseprefs
from moodle_sync.courseprefs import KINDS

ALGORITHMS = {"id": 1, "fullname": "Algorithms 2026/2027"}
LIBRARY = {"id": 2, "fullname": "Library training"}
SANDBOX = {"id": 3, "fullname": "Sandbox"}


def test_everything_but_autosend_is_on_by_default(monkeypatch):
    assert courseprefs.muted([ALGORITHMS, LIBRARY], {}) == {1: {"autosend"}, 2: {"autosend"}}
    assert courseprefs.allows({}, 1, "grades") and courseprefs.allows({}, None, "calendar")
    monkeypatch.setenv("AUTOSEND_FILES", "1")  # every course's new files into the chat
    assert courseprefs.muted([ALGORITHMS, LIBRARY], {}) == {}


def test_courses_json_mutes_by_a_fragment_of_the_name():
    cfg = {"mute": {"sandbox": "all", "Library": ["announcements", "calendar", "no-such-kind"]}}
    assert courseprefs.muted([ALGORITHMS, LIBRARY, SANDBOX], cfg) == {1: {"autosend"},
                                                                       2: {"announcements", "calendar", "autosend"},
                                                                       3: set(KINDS)}


def test_the_bots_choice_wins_and_only_differences_are_kept():
    cfg = {"mute": {"Library": ["announcements"]}}
    courseprefs.switch(LIBRARY, ["announcements"], True, cfg)  # on, although courses.json mutes it
    courseprefs.switch(LIBRARY, ["grades"], False, cfg)
    assert courseprefs.load() == {"2": {"announcements": True, "grades": False}}
    assert courseprefs.muted([LIBRARY], cfg) == {2: {"grades", "autosend"}}
    courseprefs.switch(LIBRARY, ["announcements"], False, cfg)  # back to what courses.json says
    courseprefs.switch(LIBRARY, ["grades", "EVIL_KEY"], True, cfg)
    assert courseprefs.load() == {} and courseprefs.muted([LIBRARY], cfg) == {2: {"announcements", "autosend"}}
    assert not list(config.DATA_DIR.glob("*.tmp"))


def test_a_damaged_file_means_everything_on(capsys):
    courseprefs.path().write_text("{half a file", encoding="utf-8")
    assert courseprefs.muted([ALGORITHMS], {}) == {1: {"autosend"}}
    assert "course_settings.json" in capsys.readouterr().out
    courseprefs.switch(ALGORITHMS, ["files"], False, {})  # and the next change repairs it
    assert json.loads(courseprefs.path().read_text()) == {"1": {"files": False}}


def test_globally_off(monkeypatch):
    monkeypatch.setenv("NOTIFY_GRADES", "0")
    # no Google calendar, no Telegram yet
    assert courseprefs.globally_off() == {"grades", "calendar", "classes", "deadlines", "autosend"}
    config.GOOGLE_TOKEN_FILE.write_text("{}", encoding="utf-8")
    monkeypatch.setenv("SYNC_CLASSES", "0")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "1:a")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "1")
    assert courseprefs.globally_off() == {"grades", "classes"}


def test_mute_button_names_the_course_and_the_site(monkeypatch):
    [[(text, data)]] = courseprefs.mute_buttons(1234567, "announcements")
    assert text == "🔕 Mute this for this course"
    assert data == f"cpq:1234567:{courseprefs.site_key()}:announcements" and len(data.encode()) <= 64
    assert courseprefs.site_key(config.DATA_DIR) == courseprefs.site_key()
    assert courseprefs.mute_buttons(0, "grades") is None  # a site event: no course to mute
    monkeypatch.setenv("TELEGRAM_FILE_BUTTONS", "0")
    assert courseprefs.mute_buttons(1, "grades") is None


def test_hidden_on_moodle_or_in_the_bot():
    old = {"id": 4, "fullname": "Physics 2024", "hidden": True}  # hidden on Moodle's dashboard
    assert courseprefs.is_hidden(old) and not courseprefs.is_hidden(ALGORITHMS)
    assert courseprefs.active([ALGORITHMS, old]) == [ALGORITHMS]
    assert courseprefs.muted([old], {}) == {4: set(KINDS)}  # nothing comes from a hidden course

    courseprefs.set_hidden(old, False)  # shown in the bot, although Moodle hides it
    courseprefs.set_hidden(ALGORITHMS, True)
    assert courseprefs.active([ALGORITHMS, old]) == [old]
    assert courseprefs.load() == {"1": {"hidden": True}, "4": {"hidden": False}}
    courseprefs.switch(ALGORITHMS, ["grades"], False, {})  # other settings live next to it
    courseprefs.set_hidden(ALGORITHMS, False)
    courseprefs.set_hidden({**old, "hidden": False}, False)  # Moodle shows it now too: nothing to remember
    assert courseprefs.load() == {"1": {"grades": False}}
