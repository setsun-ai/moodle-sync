"""
Shared test setup. Every test runs in isolation from the real configuration:
- data files (state.json, .env, courses.json, downloads/) point to a temp dir,
- all secrets and notification channels are removed from the environment,
  so a test can NEVER send a real Telegram/Discord/e-mail message,
- the language is English unless a test changes it.
"""

import pytest

from moodle_sync import config

SENSITIVE_OR_STATEFUL = [
    "MOODLE_BASE_URL", "MOODLE_TOKEN", "LANGUAGE", "SITE_LABEL", "MOODLE_LANG", "TIMEZONE",
    "DOWNLOAD_DIR", "MAX_FILE_MB", "RCLONE_REMOTE", "DRIVE_DEST", "KEEP_LOCAL", "STATE_BACKUP_DEST",
    "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID", "DISCORD_WEBHOOK_URL", "NTFY_TOPIC", "NTFY_SERVER",
    "SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASSWORD", "EMAIL_TO", "EMAIL_FROM",
    "HEALTHCHECK_URL", "WATCH_ALL_FORUMS", "SYNC_CLASSES",
    "STUDY_PLAN_URL", "STUDY_START", "SEMESTER_FOLDERS", "SYLLABUS",
    "NOTIFY_FILES", "NOTIFY_DEADLINES", "NOTIFY_ANNOUNCEMENTS", "NOTIFY_GRADES", "NOTIFY_ERRORS", "NOTIFY_SUMMARY",
]


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    for key in SENSITIVE_OR_STATEFUL:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("LANGUAGE", "en")
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "ENV_FILE", tmp_path / ".env")
    monkeypatch.setattr(config, "STATE_FILE", tmp_path / "state.json")
    monkeypatch.setattr(config, "LOCK_FILE", tmp_path / ".lock")
    monkeypatch.setattr(config, "GOOGLE_TOKEN_FILE", tmp_path / "google_token.json")
    monkeypatch.setattr(config, "CLIENT_SECRET_FILE", tmp_path / "client_secret.json")
    monkeypatch.setattr(config, "COURSES_FILES", [tmp_path / "courses.json", tmp_path / "przedmioty.json"])
    return tmp_path


def make_file(**overrides) -> dict:
    """A file record as produced by files.iter_course_files."""
    record = {
        "id": "url:https://m.example/webservice/pluginfile.php/1/mod_resource/content/1/a.pdf",
        "course_id": 10, "course_name": "Algorithms", "section_name": "General",
        "module_id": 100, "modname": "resource", "module_name": "Slides",
        "filepath": "/", "filename": "a.pdf",
        "fileurl": "https://m.example/webservice/pluginfile.php/1/mod_resource/content/1/a.pdf",
        "filesize": 1000, "timemodified": 1_700_000_000,
    }
    record.update(overrides)
    return record
