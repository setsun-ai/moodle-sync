import re
import string
from pathlib import Path

import pytest

from moodle_sync import config, notify, runner, setup_wizard
from moodle_sync.i18n import MESSAGES, t

PACKAGE = Path(__file__).resolve().parent.parent / "moodle_sync"


class TestI18n:
    def test_every_key_used_in_code_exists(self):
        source = "\n".join(p.read_text(encoding="utf-8") for p in PACKAGE.glob("*.py"))
        used = set(re.findall(r"\bt\(\s*[\"']([a-z0-9_]+)[\"']", source))
        used |= set(re.findall(r"[\"']((?:step|hint|doc_fn|bot_cmd|wiz_done)_[a-z_]+)[\"']", source))
        missing = sorted(key for key in used if key not in MESSAGES)
        assert not missing, f"missing translations: {missing}"

    @pytest.mark.parametrize("key", sorted(MESSAGES))
    def test_all_languages_have_same_placeholders(self, key):
        fields = {lang: {f[1] for f in string.Formatter().parse(text) if f[1]} for lang, text in MESSAGES[key].items()}
        assert set(MESSAGES[key]) == {"pl", "en"}
        assert fields["pl"] == fields["en"], key

    def test_language_switch(self, monkeypatch):
        monkeypatch.setenv("LANGUAGE", "pl")
        assert t("files_none") == "Brak plików do pobrania."
        monkeypatch.setenv("LANGUAGE", "xx")  # unknown -> English
        assert t("files_none") == "No files to download."


class TestNotify:
    def test_no_channels_means_nothing_is_sent(self, monkeypatch):
        monkeypatch.setattr(notify.requests, "post", lambda *a, **k: pytest.fail("must not send"))
        notify.notify("files", "title", "msg")

    def test_telegram_message_is_html_escaped(self, monkeypatch):
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:abc")
        monkeypatch.setenv("TELEGRAM_CHAT_ID", "42")
        sent = []

        class Ok:
            status_code = 200
            text = ""

        monkeypatch.setattr(notify.requests, "post", lambda url, json=None, **k: sent.append(json) or Ok())
        notify.notify("announcements", "Test <moved> & room", "<b>not bold</b>")
        assert sent[0]["text"] == "📢 <b>Test &lt;moved&gt; &amp; room</b>\n&lt;b&gt;not bold&lt;/b&gt;"
        assert sent[0]["parse_mode"] == "HTML"

    def test_discord_never_pings_anyone(self, monkeypatch):
        monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://discord.test/hook")
        sent = []

        class Ok:
            status_code = 204
            text = ""

        monkeypatch.setattr(notify.requests, "post", lambda url, json=None, **k: sent.append(json) or Ok())
        notify.notify("announcements", "@everyone exam moved", "")
        assert sent[0]["allowed_mentions"] == {"parse": []}

    def test_kind_can_be_muted(self, monkeypatch):
        monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://discord.test/hook")
        monkeypatch.setenv("NOTIFY_FILES", "0")
        monkeypatch.setattr(notify.requests, "post", lambda *a, **k: pytest.fail("muted kind was sent"))
        notify.notify("files", "New materials", "")

    def test_secrets_are_redacted(self, monkeypatch):
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:secret")
        assert notify._redact("https://api.telegram.org/bot123:secret/x") == "https://api.telegram.org/bot***/x"


class TestConfig:
    def test_set_env_var_replaces_commented_and_appends(self):
        config.ENV_FILE.write_text("# comment\n# KEEP_LOCAL=1  # hint\nA=1\n", encoding="utf-8")
        config.set_env_var("KEEP_LOCAL", "0")
        config.set_env_var("A", "2")
        config.set_env_var("NEW", "x")
        assert config.ENV_FILE.read_text(encoding="utf-8") == "# comment\nKEEP_LOCAL=0\nA=2\nNEW=x\n"

    def test_glued_lines_are_detected(self):
        """Regression: `printf 'LANGUAGE=pl' >> .env` onto a file without a final newline."""
        config.ENV_FILE.write_bytes(b"A=1\r\nrclone / Google Drive:\r\nSTATE_BACKUP_DEST=Studia/_syncLANGUAGE=pl\nSITE_LABEL=UNI\n")
        assert config.env_file_problems() == [(2, "no_equals", ""), (3, "glued", "STATE_BACKUP_DEST")]

    def test_set_command_repairs_a_glued_file(self):
        from moodle_sync.__main__ import main
        config.ENV_FILE.write_bytes(b"MOODLE_TOKEN=x\r\nSTATE_BACKUP_DEST=Studia/_syncLANGUAGE=pl")  # no final newline
        assert main(["set", "STATE_BACKUP_DEST", "Studia/_sync"]) == 0
        assert main(["set", "language", "pl"]) == 0
        assert config.ENV_FILE.read_text(encoding="utf-8") == "MOODLE_TOKEN=x\nSTATE_BACKUP_DEST=Studia/_sync\nLANGUAGE=pl\n"
        assert config.env_file_problems() == [] and config.language() == "pl"

    def test_legacy_polish_courses_file(self):
        (config.DATA_DIR / "przedmioty.json").write_text(
            '{"nazwy": {"a": "B"}, "kategoria_domyslna": {"a": "labs"}}', encoding="utf-8")
        cfg = config.load_courses_config()
        assert cfg["names"] == {"a": "B"} and cfg["default_category"] == {"a": "labs"}


class TestRunner:
    def test_same_error_alerts_once(self, monkeypatch):
        sent = []
        monkeypatch.setattr(runner, "notify", lambda *a, **k: sent.append(a))
        state: dict = {}
        runner.alert(state, "Files", "MoodleError [invalidtoken] at 12:01")
        runner.alert(state, "Files", "MoodleError [invalidtoken] at 12:16")  # same error, other digits
        runner.alert(state, "Files", "something else broke")
        assert len(sent) == 2
        assert "python -m moodle_sync token" in sent[0][2]  # the hint tells what to do

    def test_tee_keeps_tail_and_partial_line(self):
        tee = runner.Tee(None)
        tee.write("a\nb\n")
        tee.write("c")
        assert tee.text() == "a\nb\nc"


@pytest.mark.parametrize("raw, expected", [
    ("moodle.example.edu.pl/2025/my/", "https://moodle.example.edu.pl/2025"),
    ("https://moodle.example.edu/course/view.php?id=5", "https://moodle.example.edu"),
    ("https://moodle.example.edu/", "https://moodle.example.edu"),
    ("http://localhost/moodle/login/index.php", "http://localhost/moodle"),
])
def test_wizard_normalizes_urls(raw, expected):
    assert setup_wizard.normalize_url(raw) == expected


def test_broken_telegram_html_falls_back_to_plain_text(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:abc")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "42")
    sent = []

    class Resp:
        def __init__(self, status):
            self.status_code, self.text = status, "Bad Request: can't parse entities" if status == 400 else ""

    def post(url, json=None, **k):
        sent.append(json)
        return Resp(400 if json.get("parse_mode") else 200)

    monkeypatch.setattr(notify.requests, "post", post)
    assert notify.send_telegram_html("<b>Room &amp; time</b> changed &am")
    assert sent[1] == {"chat_id": "42", "text": "Room & time changed &am", "disable_web_page_preview": True}
