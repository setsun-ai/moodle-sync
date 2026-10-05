"""Secrets must never reach logs, step output (which is also sent in error alerts) or printed exceptions."""

import requests

from moodle_sync import runner

SECRETS = {
    "MOODLE_TOKEN": "moodletoken0123456789abcdef",
    "MOODLE_PRIVATE_TOKEN": "privatetoken9876543210",
    "TELEGRAM_BOT_TOKEN": "123456:ABCdefGhIJKlmnOPQ",
    "DISCORD_WEBHOOK_URL": "https://discord.com/api/webhooks/1/secretwebhookpart",
    "SMTP_PASSWORD": "abcd efgh ijkl mnop",
    "HEALTHCHECK_URL": "https://hc-ping.com/5f1c0e6a-secret-uuid",
}


def _set_secrets(monkeypatch):
    for key, value in SECRETS.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setenv("MOODLE_BASE_URL", "https://moodle.example.edu")


def _leaks(text: str) -> list[str]:
    return [key for key, value in SECRETS.items() if value in text]


def test_failing_step_output_contains_no_secret(monkeypatch, capsys):
    _set_secrets(monkeypatch)

    def step():
        # what requests/urllib3 put into exception messages: the full URL, token included
        raise requests.ConnectionError(
            f"HTTPSConnectionPool: /webservice/rest/server.php?wstoken={SECRETS['MOODLE_TOKEN']} | "
            f"https://api.telegram.org/bot{SECRETS['TELEGRAM_BOT_TOKEN']}/sendMessage | "
            f"{SECRETS['DISCORD_WEBHOOK_URL']} | smtp auth {SECRETS['SMTP_PASSWORD']} | "
            f"privatetoken={SECRETS['MOODLE_PRIVATE_TOKEN']}"
        )

    code, output = runner.run_step(step)
    printed = capsys.readouterr().out
    assert code == 1
    assert "Traceback" in output  # the error itself is still reported
    assert _leaks(output) == [] and _leaks(printed) == []
    assert "***" in output


def test_healthcheck_failure_does_not_print_ping_url(monkeypatch, capsys):
    _set_secrets(monkeypatch)

    def failing_post(url, **kwargs):
        raise requests.ConnectionError(f"Max retries exceeded with url: {url}")

    monkeypatch.setattr(runner.requests, "post", failing_post)
    runner.ping_healthcheck("/fail", "body")
    printed = capsys.readouterr().out
    assert "[healthchecks]" in printed
    assert _leaks(printed) == []


def test_log_file_contains_no_secret(monkeypatch, tmp_path):
    _set_secrets(monkeypatch)

    def step():
        raise RuntimeError(f"GET https://moodle.example.edu/?token={SECRETS['MOODLE_TOKEN']} failed")

    log = tmp_path / "sync.log"
    with runner._open_log(log) as fh, runner.redirect_stdout(fh):
        runner.run_step(step)
    assert _leaks(log.read_text(encoding="utf-8")) == []
