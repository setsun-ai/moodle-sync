"""/update and /rollback: unpacking a release, the folder swap, the Telegram commands. No network, no pip."""

import io
import tarfile

import pytest

from moodle_sync import __version__, notify, runner, telegram_bot, updater

RELEASE = {"moodle_sync/__init__.py": '__version__ = "1.9.0"\n', "moodle_sync/runner.py": "# new\n",
           "requirements.txt": "requests>=9\n", ".env.example": "MOODLE_TOKEN=\n", "tests/test_x.py": ""}


def archive(files: dict, top="moodle-sync-1.9.0") -> bytes:
    data = io.BytesIO()
    with tarfile.open(fileobj=data, mode="w:gz") as tar:
        for name, text in files.items():
            body = text.encode()
            info = tarfile.TarInfo(f"{top}/{name}")
            info.size = len(body)
            tar.addfile(info, io.BytesIO(body))
    return data.getvalue()


@pytest.fixture
def project(tmp_path, monkeypatch):
    root = tmp_path / "project"
    package = root / "moodle_sync"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text('__version__ = "1.0.3"\n')
    (root / "requirements.txt").write_text("requests>=2.28\n")
    (root / ".env").write_text("MOODLE_TOKEN=secret\n")
    monkeypatch.setattr(updater, "PACKAGE_DIR", package)
    monkeypatch.setattr(updater, "PROJECT_DIR", root)
    monkeypatch.setattr(updater, "WORK_DIR", root / ".update")
    monkeypatch.setattr(updater, "PREVIOUS_DIR", root / ".update" / "previous")
    monkeypatch.setattr(updater, "_get", lambda url, timeout=30: archive(RELEASE))
    return root


def test_versions_compare_as_numbers():
    assert updater.newer("v1.10.0", "1.9.3")
    assert not updater.newer("v1.0.3", "1.0.3")


def test_unpack_takes_only_the_package_and_requirements(tmp_path):
    updater.unpack(archive(RELEASE), tmp_path / "out")
    assert (tmp_path / "out" / "moodle_sync" / "runner.py").is_file()
    assert (tmp_path / "out" / "requirements.txt").is_file()
    assert not (tmp_path / "out" / ".env.example").exists()
    assert not (tmp_path / "out" / "tests").exists()


def test_unpack_refuses_paths_leaving_the_folder(tmp_path):
    with pytest.raises(updater.UpdateError):
        updater.unpack(archive({"moodle_sync/../../evil.py": "x"}), tmp_path / "out")
    assert not (tmp_path / "evil.py").exists()


def test_install_swaps_code_keeps_private_files_and_rollback_undoes_it(project, monkeypatch):
    runs = []
    monkeypatch.setattr(updater, "_run", lambda args, timeout: runs.append(args[1:3]) or (True, "OK 1.9.0"))
    updater.install("v1.9.0")
    assert "1.9.0" in (project / "moodle_sync" / "__init__.py").read_text()
    assert (project / "requirements.txt").read_text() == "requests>=9\n"
    assert (project / ".env").read_text() == "MOODLE_TOKEN=secret\n"
    assert runs[0] == ["-m", "pip"]  # requirements changed -> pip before the selftest
    assert updater.rollback() == "1.0.3"
    assert "1.0.3" in (project / "moodle_sync" / "__init__.py").read_text()
    assert (project / "requirements.txt").read_text() == "requests>=2.28\n"
    assert updater.rollback() == "1.9.0"  # a second rollback goes forward again


def test_failed_selftest_changes_nothing(project, monkeypatch):
    results = iter([(True, ""), (False, "ImportError: boom")])
    monkeypatch.setattr(updater, "_run", lambda args, timeout: next(results))
    with pytest.raises(updater.UpdateError, match="boom"):
        updater.install("v1.9.0")
    assert "1.0.3" in (project / "moodle_sync" / "__init__.py").read_text()
    assert updater.previous_version() is None
    assert updater.rollback() is None


@pytest.fixture
def sent(monkeypatch):
    messages = []
    monkeypatch.setattr(notify, "send_telegram_html", lambda text, chat_id=None: messages.append(text))
    monkeypatch.setattr(updater, "request_restart", lambda: messages.append("RESTART"))
    return messages


def test_update_command_installs_and_asks_for_a_restart(sent, monkeypatch):
    monkeypatch.setattr(updater, "latest_release", lambda: "v99.0.0")
    monkeypatch.setattr(updater, "install", lambda tag: "OK 99.0.0")
    reply = telegram_bot.handle("/update", "1")
    assert "v99.0.0 installed" in reply and sent[-1] == "RESTART"


def test_update_command_when_already_newest(sent, monkeypatch):
    monkeypatch.setattr(updater, "latest_release", lambda: f"v{__version__}")
    assert "newest version" in telegram_bot.handle("/update", "1")
    assert "RESTART" not in sent


def test_update_waits_for_a_running_sync(sent, monkeypatch):
    monkeypatch.setattr(updater, "latest_release", lambda: "v99.0.0")
    monkeypatch.setattr(updater, "install", lambda tag: pytest.fail("installed during a sync"))
    with runner.SingleInstance():
        assert "sync is running" in telegram_bot.handle("/update", "1")
    assert "RESTART" not in sent


def test_failed_update_is_reported(sent, monkeypatch):
    monkeypatch.setattr(updater, "latest_release", lambda: "v99.0.0")

    def fail(tag):
        raise updater.UpdateError("selftest:\nboom")

    monkeypatch.setattr(updater, "install", fail)
    reply = telegram_bot.handle("/update", "1")
    assert "still running" in reply and "boom" in reply
    assert "RESTART" not in sent
