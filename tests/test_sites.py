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
