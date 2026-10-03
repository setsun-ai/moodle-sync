"""
Configuration: paths and settings read from the .env file.

Every setting is read through a function at call time (not a module-level
constant), so the setup wizard can write .env and immediately use the new
values after reload(). All settings are optional except MOODLE_BASE_URL and
MOODLE_TOKEN - see .env.example and docs/*/configuration.md.
"""

import json
import os
import re
from pathlib import Path

from dotenv import load_dotenv

PROJECT_DIR = Path(__file__).resolve().parent.parent
# Where user data lives (.env, state.json, tokens, downloads). Defaults to the
# project folder; set MOODLE_SYNC_DATA_DIR to keep code and data separate.
DATA_DIR = Path(os.environ.get("MOODLE_SYNC_DATA_DIR", PROJECT_DIR)).resolve()

ENV_FILE = DATA_DIR / ".env"
STATE_FILE = DATA_DIR / "state.json"
LOCK_FILE = DATA_DIR / ".moodle_sync.lock"
LOG_DIR = DATA_DIR / "logs"
CLIENT_SECRET_FILE = DATA_DIR / "client_secret.json"
GOOGLE_TOKEN_FILE = DATA_DIR / "google_token.json"
# courses.json (przedmioty.json is the legacy name from the first version)
COURSES_FILES = [DATA_DIR / "courses.json", DATA_DIR / "przedmioty.json"]


def reload() -> None:
    """(Re)load .env into os.environ, overriding values loaded earlier."""
    load_dotenv(ENV_FILE, override=True)


reload()


def env(key: str, default: str = "") -> str:
    return os.environ.get(key, default).strip()


def env_int(key: str, default: int) -> int:
    try:
        return int(float(env(key) or default))
    except ValueError:
        return default


def env_bool(key: str, default: bool) -> bool:
    value = env(key).lower()
    if not value:
        return default
    return value in ("1", "true", "yes", "tak", "on")


# --- core ---------------------------------------------------------------------

def moodle_base_url() -> str:
    return env("MOODLE_BASE_URL").rstrip("/")


def moodle_token() -> str:
    return env("MOODLE_TOKEN")


def language() -> str:
    """UI language of messages, bot and notifications: 'pl' or 'en'."""
    lang = env("LANGUAGE", "en").lower()[:2]
    return lang if lang in ("pl", "en") else "en"


def site_label() -> str:
    """Short name of the school, used in calendar names (e.g. 'UNI')."""
    return env("SITE_LABEL", "Moodle")


def moodle_content_language() -> str:
    """Which variant to keep from multi-language names ({mlang pl}...{mlang en}...)."""
    return env("MOODLE_LANG", language()).lower()


def timezone_name() -> str:
    return env("TIMEZONE", "Europe/Warsaw" if language() == "pl" else "UTC")


# --- files --------------------------------------------------------------------

def download_dir() -> Path:
    return (DATA_DIR / env("DOWNLOAD_DIR", "downloads")).resolve()


def max_file_mb() -> float:
    try:
        return float(env("MAX_FILE_MB", "0") or 0)
    except ValueError:
        return 0.0


# --- cloud storage (rclone) -----------------------------------------------------

def rclone_remote() -> str:
    """Empty = upload disabled (files stay in DOWNLOAD_DIR only)."""
    return env("RCLONE_REMOTE").rstrip(":")


def remote_dest() -> str:
    return env("DRIVE_DEST", "Moodle").strip("/")


def rclone_bin() -> str:
    return env("RCLONE_BIN", "rclone")


def keep_local() -> bool:
    return env_bool("KEEP_LOCAL", True)


def state_backup_dest() -> str:
    parent = os.path.dirname(remote_dest())
    default = f"{parent}/_moodle_sync" if parent else "_moodle_sync"
    return env("STATE_BACKUP_DEST", default).strip("/")


# --- courses.json ---------------------------------------------------------------

def courses_file() -> Path:
    """The courses config file in use (existing one, or courses.json for new setups)."""
    return next((p for p in COURSES_FILES if p.exists()), COURSES_FILES[0])


def load_courses_config() -> dict:
    path = courses_file()
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    # Accept the legacy Polish keys from the first version.
    data.setdefault("names", data.get("nazwy", {}))
    data.setdefault("default_category", data.get("kategoria_domyslna", {}))
    data.setdefault("skip", [])
    data.setdefault("category_rules", [])
    return data


# --- checking and writing .env ---------------------------------------------------------

def env_file_problems() -> list[tuple[int, str, str]]:
    """
    Lines of .env that silently don't work: [(line number, problem, key)].
    'no_equals' - neither a comment nor KEY=value, ignored by the parser;
    'glued'     - a value containing another KEY=..., i.e. two settings in one
                  line (appending with `echo >>` to a file without a final
                  newline does this, and the second setting silently vanishes).
    """
    problems = []
    if not ENV_FILE.exists():
        return problems
    for number, line in enumerate(ENV_FILE.read_text(encoding="utf-8").splitlines(), 1):
        text = line.strip()
        if not text or text.startswith("#"):
            continue
        key, sep, value = text.partition("=")
        if not sep:
            problems.append((number, "no_equals", ""))
        elif re.search(r"[A-Z][A-Z0-9_]{2,}=", value):
            problems.append((number, "glued", key.strip()))
    return problems


def set_env_var(key: str, value: str) -> None:
    """
    Set KEY=value in .env: replaces an existing (also commented-out) line in
    place, otherwise appends. Keeps the rest of the file - including the
    user's comments - untouched.
    """
    lines = ENV_FILE.read_text(encoding="utf-8").splitlines() if ENV_FILE.exists() else []
    new_line = f"{key}={value}"
    for i, line in enumerate(lines):
        stripped = line.lstrip("# ").strip()
        if stripped.startswith(f"{key}="):
            lines[i] = new_line
            break
    else:
        lines.append(new_line)
    # newline="\n": the same LF file on Windows and Linux (it's often copied to a Raspberry Pi)
    ENV_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    os.environ[key] = value
