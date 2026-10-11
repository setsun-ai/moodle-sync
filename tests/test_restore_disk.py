"""restore (state from the cloud backup) and the low disk space alarm."""
import json
from collections import namedtuple
from pathlib import Path

import pytest

from moodle_sync import config, runner, storage


@pytest.fixture
def backup(monkeypatch):
    """A cloud backup as rclone would serve it: name -> content (None = missing)."""
    files = {"state.json": json.dumps({"downloaded": {"a": {"path": "A/x.pdf"}, "b": {"path": None}}}),
             "courses.json": "{}", "przedmioty.json": None}
    calls = []
    monkeypatch.setenv("RCLONE_REMOTE", "gdrive")
    monkeypatch.setenv("DRIVE_DEST", "Studies/Moodle")
    monkeypatch.setattr(storage, "status", lambda: (True, "ok"))

    def fake_rclone(*args, quiet=False):
        calls.append(args[:3])
        content = files.get(args[1].rsplit("/", 1)[-1])
        if content is None:
            return 3
        Path(args[2]).write_text(content, encoding="utf-8")
        return 0

    monkeypatch.setattr(storage, "rclone", fake_rclone)
    return files, calls


def test_restore_brings_back_state_and_keeps_existing_files(backup, capsys):
    files, calls = backup
    (config.DATA_DIR / "courses.json").write_text('{"mine": 1}', encoding="utf-8")
    assert storage.restore() == 0
    assert calls[0][:2] == ("copyto", "gdrive:Studies/_moodle_sync/state.json")
    assert json.loads(config.STATE_FILE.read_text())["downloaded"]["a"]["path"] == "A/x.pdf"
    assert json.loads((config.DATA_DIR / "courses.json").read_text()) == {"mine": 1}  # kept
    out = capsys.readouterr().out
    assert "courses.json: already there" in out and "przedmioty.json: not in the backup" in out
    assert "knows 1 downloaded files" in out
    assert storage.restore(force=True) == 0
    assert json.loads((config.DATA_DIR / "courses.json").read_text()) == {}
    assert not list(config.DATA_DIR.glob("*.restoring"))


def test_damaged_backup_is_not_put_in_place(backup):
    files, _ = backup
    files.update({"state.json": "{half a file", "courses.json": None})
    config.STATE_FILE.write_text('{"downloaded": {}}', encoding="utf-8")
    assert storage.restore(force=True) == 1
    assert config.STATE_FILE.read_text() == '{"downloaded": {}}'


def test_restore_needs_the_cloud(monkeypatch):
    monkeypatch.setattr(storage, "status", lambda: (False, "no remote"))
    assert storage.restore() == 1


Usage = namedtuple("Usage", "total used free")


def test_low_disk_is_notified_once_a_day(monkeypatch):
    sent = []
    monkeypatch.setenv("LOW_DISK_GB", "1")
    monkeypatch.setenv("RCLONE_REMOTE", "gdrive")
    monkeypatch.setattr(runner, "notify", lambda kind, title, message="", **k: sent.append((kind, title, message)))
    monkeypatch.setattr(runner.shutil, "disk_usage", lambda path: Usage(32e9, 31.5e9, 0.5e9))
    state: dict = {}
    runner.check_disk(state)
    runner.check_disk(state)
    [(kind, title, message)] = sent
    assert kind == "errors" and "0.5 GB of 32 GB" in message and "KEEP_LOCAL 0" in message
    monkeypatch.setattr(runner.shutil, "disk_usage", lambda path: Usage(32e9, 20e9, 12e9))
    runner.check_disk(state)
    assert "disk_alert" not in state  # enough space again: the next shortage is notified at once


def test_low_disk_alarm_can_be_turned_off(monkeypatch):
    monkeypatch.setattr(runner.shutil, "disk_usage", lambda path: Usage(32e9, 32e9, 0))
    monkeypatch.setattr(runner, "notify", lambda *a, **k: pytest.fail("off"))
    runner.check_disk({})  # conftest: LOW_DISK_GB=0
