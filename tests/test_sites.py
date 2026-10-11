"""Other sites (OTHER_SITES): switching the bot to a second copy's .env and data for a moment."""
import os

import pytest

from moodle_sync import config, coursebrowse, moodle, sites, telegram_bot


@pytest.fixture
def two_sites(tmp_path, monkeypatch):
    config.ENV_FILE.write_text("MOODLE_BASE_URL=https://moodle.example.edu\nMOODLE_TOKEN=token-one\n"
                               "STUDY_PLAN_URL=https://ects.example.edu/1\n", encoding="utf-8")
    monkeypatch.setenv("MOODLE_BASE_URL", "https://moodle.example.edu")
    monkeypatch.setenv("MOODLE_TOKEN", "token-one")
    monkeypatch.setenv("STUDY_PLAN_URL", "https://ects.example.edu/1")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:abc")
    other = tmp_path / "site-2"
    other.mkdir()
    (other / ".env").write_text("MOODLE_BASE_URL=https://other.example.edu\nMOODLE_TOKEN=token-two\n"
                                "SITE_LABEL=UNI2\nLANGUAGE=pl\n", encoding="utf-8")
    monkeypatch.setenv("OTHER_SITES", str(other))
    return other.resolve()


def test_use_switches_settings_and_files_then_restores_them(two_sites):
    own_state = config.STATE_FILE
    with sites.use(two_sites):
        assert config.moodle_base_url() == "https://other.example.edu" and config.moodle_token() == "token-two"
        assert config.STATE_FILE == two_sites / "state.json" and config.DATA_DIR == two_sites
        assert config.env("STUDY_PLAN_URL") == ""  # this site's settings don't leak into the other one
        assert config.env("TELEGRAM_BOT_TOKEN") == "123:abc" and config.language() == "en"  # the bot's own stay
        assert moodle.RETRIES == 0
    assert config.moodle_token() == "token-one" and config.STATE_FILE == own_state
    assert config.env("STUDY_PLAN_URL") == "https://ects.example.edu/1" and moodle.RETRIES > 0


def test_errors_on_another_site_name_it_and_hide_its_token(two_sites):
    with pytest.raises(sites.SiteError, match=r"^UNI2: .*token=\*\*\*") as error:
        with sites.use(two_sites):
            raise RuntimeError("https://other.example.edu/webservice?token=token-two timed out")
    assert "token-two" not in str(error.value)
    assert os.environ["MOODLE_TOKEN"] == "token-one"


def test_this_site_is_used_as_it_is(two_sites):
    with pytest.raises(RuntimeError):  # not wrapped: the bot reports it as always
        with sites.use(config.DATA_DIR):
            assert config.moodle_token() == "token-one"
            raise RuntimeError("x")


def test_use_data_dir_points_every_file_at_the_folder(tmp_path):
    config.use_data_dir(tmp_path / "x")
    assert {key: getattr(config, key) for key in ("ENV_FILE", "STATE_FILE", "GOOGLE_TOKEN_FILE")} == {
        "ENV_FILE": tmp_path / "x" / ".env", "STATE_FILE": tmp_path / "x" / "state.json",
        "GOOGLE_TOKEN_FILE": tmp_path / "x" / "google_token.json"}
    assert config.COURSES_FILES == [tmp_path / "x" / "courses.json", tmp_path / "x" / "przedmioty.json"]


def test_drive_links_are_cached_per_cloud_folder(monkeypatch):
    from types import SimpleNamespace

    listed = []
    monkeypatch.setattr(coursebrowse, "_drive_cache", {})
    monkeypatch.setattr(coursebrowse.subprocess, "run", lambda cmd, **kw: listed.append(cmd[-1]) or SimpleNamespace(
        stdout=f'[{{"Path": "{cmd[-1]}.pdf", "ID": "x"}}]'))
    monkeypatch.setenv("RCLONE_REMOTE", "gdrive")
    monkeypatch.setenv("DRIVE_DEST", "One")
    one = coursebrowse.drive_links()
    monkeypatch.setenv("DRIVE_DEST", "Two")
    two = coursebrowse.drive_links()
    assert coursebrowse.drive_links() is two and listed == ["gdrive:One", "gdrive:Two"]
    assert list(one) == ["gdrive:one.pdf"] and list(two) == ["gdrive:two.pdf"]


def test_menu_failure_is_logged(monkeypatch, capsys):
    from types import SimpleNamespace

    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:abc")
    monkeypatch.setattr(telegram_bot.requests, "post", lambda *a, **k: SimpleNamespace(
        status_code=400, text="Bad Request: command description is too long"))
    telegram_bot.register_menu()
    assert "setMyCommands: HTTP 400 Bad Request" in capsys.readouterr().out


def test_deadlines_of_every_site_in_one_list(two_sites, monkeypatch):
    import time

    from moodle_sync import calendar_sync

    now = time.time()
    by_site = {"https://moodle.example.edu": [(now + 7200, "[Algorithms] Report", False)],
               "https://other.example.edu": [(now + 3600, "[Shared] Essay", None)]}
    monkeypatch.setattr(calendar_sync, "upcoming_deadlines", lambda days=14: by_site[config.moodle_base_url()])
    lines = telegram_bot.cmd_deadlines("1").splitlines()
    assert lines[1].endswith("UNI2 · [Shared] Essay") and lines[2].endswith("[Algorithms] Report")  # by time

    def down(days=14):
        if config.moodle_base_url() == "https://other.example.edu":
            raise ConnectionError("timed out")
        return []

    monkeypatch.setattr(calendar_sync, "upcoming_deadlines", down)
    reply = telegram_bot.cmd_deadlines("1")
    assert reply.startswith("📅 No deadlines in the next 14 days.")
    assert "UNI2: timed out" in reply


def test_new_files_and_grades_of_every_site(two_sites):
    import json
    import time

    now = time.time()
    config.STATE_FILE.write_text(json.dumps({
        "downloaded": {"a": {"path": "Semester 1/Algorithms/Lectures/a.pdf", "ts": now - 60}},
        "watch": {"grades": {"items": {"g": {"grade": "5", "name": "Lab 1", "course": "Algorithms", "ts": now - 60}}}},
    }), encoding="utf-8")
    (two_sites / "state.json").write_text(json.dumps({
        "downloaded": {"b": {"path": "Semester 1/Shared/Lectures/b.pdf", "ts": now}},
        "watch": {"grades": {"items": {"h": {"grade": "4.5", "name": "Essay", "course": "Shared", "ts": now}}}},
    }), encoding="utf-8")
    new = telegram_bot.cmd_new("1").splitlines()
    assert "<b>UNI2 · Shared</b>: b.pdf" in new[1] and "<b>Algorithms</b>: a.pdf" in new[2]
    grades = telegram_bot.cmd_grades("1").splitlines()
    assert "Essay <i>(UNI2 · Shared)</i>" in grades[1] and "Lab 1 <i>(Algorithms)</i>" in grades[2]


def test_one_weekly_summary_for_every_site(two_sites, monkeypatch):
    import json
    import time

    from moodle_sync import calendar_sync, runner

    now = time.time()
    (two_sites / "state.json").write_text(json.dumps({"downloaded": {"b": {"path": "x/y/b.pdf", "ts": now}}}),
                                          encoding="utf-8")
    by_site = {"https://moodle.example.edu": [(now + 7200, "[Algorithms] Report", False)],
               "https://other.example.edu": [(now + 3600, "[Shared] Essay", True)]}
    monkeypatch.setattr(calendar_sync, "upcoming_deadlines", lambda days=7: by_site[config.moodle_base_url()])
    sent = []
    monkeypatch.setattr(runner, "notify", lambda kind, title, message="", **k: sent.append(message))
    runner.weekly_summary({}, force=True)
    lines = sent[0].splitlines()
    assert lines[0].startswith("This week: 0 new files") and lines[1].startswith("UNI2 · This week: 1 new files")
    assert lines[-2].endswith("UNI2 · [Shared] Essay") and lines[-1].endswith("[Algorithms] Report")

    def down(days=7):
        raise ConnectionError(f"{config.moodle_base_url()} timed out")

    monkeypatch.setattr(calendar_sync, "upcoming_deadlines", down)
    runner.weekly_summary({}, force=True)
    assert "none 🎉" not in sent[1] and "Couldn't get deadlines" in sent[1]
    assert "UNI2: https://other.example.edu timed out" in sent[1]


def test_status_and_errors_show_every_site(two_sites, monkeypatch):
    import json
    import time

    from moodle_sync import interactive

    run = {"start": time.time() - 30, "end": time.time() - 20, "steps": [["Downloading files", "error (1)", 1]]}
    (two_sites / "state.json").write_text(json.dumps({"last_run": run, "last_errors": {"Downloading files": "boom"}}),
                                          encoding="utf-8")
    status = telegram_bot.cmd_status("1")
    assert status.index("run yet") < status.index("<b>UNI2</b>") < status.index("❌ Downloading files")
    sent = []
    monkeypatch.setattr(interactive, "send", lambda chat, text, rows=None: sent.append(text))
    interactive.handle_command("bledy", [], "1")
    assert "<b>UNI2</b> · " in sent[0] and "<pre>boom</pre>" in sent[0]
