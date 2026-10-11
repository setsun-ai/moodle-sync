"""Pausing a site (paused.json) - the run, other sites' folders and the bot's /pause."""
import json
import time

import pytest

from moodle_sync import config, pause, runner


@pytest.fixture
def second_site(tmp_path, monkeypatch):
    site = tmp_path / "site-2"
    site.mkdir()
    (site / ".env").write_text("SITE_LABEL=UNI2\nMOODLE_TOKEN=not-read-here\n", encoding="utf-8")
    monkeypatch.setenv("OTHER_SITES", f" {site} , {config.DATA_DIR}")  # this site again is ignored
    return site


def test_pause_resume_and_expiry():
    assert pause.paused_until() is None
    pause.pause(config.DATA_DIR)
    assert pause.paused_until() == 0
    pause.resume(config.DATA_DIR)
    assert pause.paused_until() is None
    pause.pause(config.DATA_DIR, days=1)
    assert pause.paused_until() == pytest.approx(time.time() + 86400, abs=5)
    (config.DATA_DIR / pause.PAUSE_FILE).write_text(json.dumps({"until": time.time() - 1}), encoding="utf-8")
    assert pause.paused_until() is None and not (config.DATA_DIR / pause.PAUSE_FILE).exists()  # ran out


def test_unreadable_pause_file_keeps_it_paused():
    (config.DATA_DIR / pause.PAUSE_FILE).write_text("{broken", encoding="utf-8")
    assert pause.paused_until() == 0


def test_sites_and_labels(second_site, monkeypatch):
    monkeypatch.setenv("SITE_LABEL", "UNI1")
    assert pause.sites() == [config.DATA_DIR, second_site.resolve()]
    assert [pause.label(s) for s in pause.sites()] == ["UNI1", "UNI2"]
    (second_site / ".env").unlink()
    assert pause.label(second_site.resolve()) == "site-2"


def test_pausing_a_missing_folder_fails(tmp_path):
    with pytest.raises(FileNotFoundError):
        pause.pause(tmp_path / "nope")


def test_paused_run_does_nothing_but_tells_the_healthcheck(monkeypatch, capsys):
    pings = []
    monkeypatch.setattr(runner, "STEPS", [("step_files", lambda: pytest.fail("must not run while paused"))])
    monkeypatch.setattr(runner, "ping_healthcheck", lambda suffix="", body="": pings.append((suffix, body)))
    pause.pause(config.DATA_DIR)
    assert runner._run() == 0
    assert pings == [("", "paused")] and "until resumed" in capsys.readouterr().out
    assert not config.STATE_FILE.exists()  # no "last run", no weekly summary

    ran = []
    monkeypatch.setattr(runner, "STEPS", [("step_files", lambda: ran.append(1) or 0)])
    monkeypatch.setattr(runner, "weekly_summary", lambda state: None)
    pause.resume(config.DATA_DIR)
    assert runner._run() == 0 and ran == [1]
