"""
Other Moodle sites synced by a second copy (see "A second Moodle site" in docs/*/configuration.md).

Only the first copy runs the Telegram bot. OTHER_SITES (data folders, comma-separated) lets it
pause those sites (pause.py) and show them in /courses, /today, /deadlines, /new and /grades: for
that moment use() switches .env and the data files (state.json, courses.json) to the other site's folder.
"""

import html
import os
from contextlib import contextmanager
from pathlib import Path

from dotenv import dotenv_values

from . import config, moodle, notify
from .i18n import t

# The bot's own settings: it keeps talking to you in the same chat and language.
KEEP = ("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID", "LANGUAGE")


class SiteError(Exception):
    """Something failed on another site - the message names the site and has no secrets."""


def sites() -> list[Path]:
    """This site's data folder first, then OTHER_SITES."""
    others = [Path(p.strip()).expanduser().resolve() for p in config.env("OTHER_SITES").split(",") if p.strip()]
    return [config.DATA_DIR] + [p for p in others if p != config.DATA_DIR]


def label(site: Path) -> str:
    """SITE_LABEL of the site (from its own .env), else its folder name."""
    if site == config.DATA_DIR:
        return config.site_label()
    return (dotenv_values(site / ".env").get("SITE_LABEL") or "").strip() or site.name


def each(collect) -> tuple[list, list[str]]:
    """
    collect(index, prefix) on every site, results joined; prefix is "" here and "UG · " on another site.
    Another site that fails becomes a note (HTML) instead of an error, so this site's answer still comes.
    """
    found, notes = [], []
    for i, site in enumerate(sites()):
        if i and not site.is_dir():
            continue  # /pause tells about a wrong OTHER_SITES
        prefix = f"{label(site)} · " if i else ""
        try:
            with use(site):
                found += collect(i, prefix)
        except SiteError as e:
            notes.append(t("ui_site_unavailable", error=html.escape(str(e)[:300])))
    return found, notes


@contextmanager
def use(site: Path):
    """Run code against another site: its .env and data folder. This site: nothing changes."""
    if site == config.DATA_DIR:
        yield
        return
    name = label(site)
    saved_env = dict(os.environ)
    saved_paths = {key: getattr(config, key) for key in config.DATA_PATHS}
    saved_retries = moodle.RETRIES
    try:
        for key in set(dotenv_values(config.ENV_FILE)) - set(KEEP):  # this site's settings must not leak over
            os.environ.pop(key, None)
        os.environ.update({key: value for key, value in dotenv_values(site / ".env").items()
                           if value is not None and key not in KEEP})
        config.use_data_dir(site)
        moodle.RETRIES = 0  # you're waiting for the answer: a site that's down mustn't hold the bot for minutes
        try:
            yield
        except Exception as e:  # masked while the other site's token is still known
            raise SiteError(f"{name}: {moodle.redact(notify._redact(str(e)))}") from None
    finally:
        os.environ.clear()
        os.environ.update(saved_env)
        for key, value in saved_paths.items():
            setattr(config, key, value)
        moodle.RETRIES = saved_retries
