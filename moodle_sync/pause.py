"""
Pausing a site: the scheduler keeps starting `run`, but it does nothing until resumed.

The pause is a file in the site's data folder (paused.json: {"since": ts, "until": ts}, until 0 =
until resumed), so the bot of the first copy can pause a second site (see "A second Moodle site"
in docs/*/configuration.md): OTHER_SITES lists their data folders, comma-separated.
A pause that has run out is removed by the next check, and the sync goes on as usual.
"""

import json
import time
from pathlib import Path

from dotenv import dotenv_values

from . import config

PAUSE_FILE = "paused.json"


def sites() -> list[Path]:
    """This site's data folder first, then OTHER_SITES."""
    others = [Path(p.strip()).expanduser().resolve() for p in config.env("OTHER_SITES").split(",") if p.strip()]
    return [config.DATA_DIR] + [p for p in others if p != config.DATA_DIR]


def label(site: Path) -> str:
    """SITE_LABEL of the site (from its own .env), else its folder name."""
    if site == config.DATA_DIR:
        return config.site_label()
    return (dotenv_values(site / ".env").get("SITE_LABEL") or "").strip() or site.name


def paused_until(site: Path | None = None) -> float | None:
    """None = running, 0 = paused until resumed, else the time the pause ends."""
    path = (site or config.DATA_DIR) / PAUSE_FILE
    try:
        until = float(json.loads(path.read_text(encoding="utf-8")).get("until") or 0)
    except FileNotFoundError:
        return None
    except (ValueError, AttributeError, OSError):
        return 0  # unreadable: better paused than syncing against your will
    if until and until <= time.time():
        path.unlink(missing_ok=True)
        return None
    return until


def pause(site: Path, days: float = 0) -> None:
    """Pause for `days` (0 = until resumed)."""
    if not site.is_dir():
        raise FileNotFoundError(site)
    now = time.time()
    data = {"since": int(now), "until": int(now + days * 86400) if days else 0}
    (site / PAUSE_FILE).write_text(json.dumps(data), encoding="utf-8")


def resume(site: Path) -> None:
    (site / PAUSE_FILE).unlink(missing_ok=True)
