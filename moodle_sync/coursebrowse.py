"""
Course preview for the Telegram bot: a course's sections and what's in them,
and "what appeared on a given day" across all courses - without opening Moodle.

Every item gets the most useful link:
    📄 file      -> your copy in Google Drive when it's there (rclone with the drive
                    backend gives file ids; the link opens only for you), else Moodle
    🔗 URL       -> the shared link itself
    🏷 label     -> its text, with the links it contains
    other        -> the activity in Moodle

Rendering is pure (render_module, render_section, render_day) - see
tests/test_coursebrowse.py.
"""

import html
import json
import re
import subprocess
import time
from datetime import datetime, timedelta

from . import config, moodle, state as state_mod
from .textutil import clean_text, shorten

DRIVE_LINKS_TTL = 30 * 60
ICONS = {"resource": "📄", "folder": "📁", "url": "🔗", "assign": "📎", "forum": "💬", "quiz": "❓",
         "page": "📝", "attendance": "✋", "label": "🏷", "lesson": "📚", "choice": "🗳", "feedback": "🗳"}
_drive_cache = {"ts": 0.0, "links": {}}


def esc(text) -> str:
    return html.escape(str(text))


# --- links to the cloud copy ------------------------------------------------------------------

def drive_links(force: bool = False) -> dict:
    """Path under DRIVE_DEST (casefolded) -> Google Drive link; {} when there's no drive remote."""
    if not config.rclone_remote():
        return {}
    if not force and time.time() - _drive_cache["ts"] < DRIVE_LINKS_TTL:
        return _drive_cache["links"]
    from . import storage

    links = {}
    try:
        out = subprocess.run([config.rclone_bin(), "lsjson", "-R", "--files-only", "--no-mimetype", "--no-modtime",
                              storage.target()], capture_output=True, text=True, timeout=120)
        for item in json.loads(out.stdout or "[]"):
            if item.get("ID"):
                links[item["Path"].casefold()] = f"https://drive.google.com/file/d/{item['ID']}/view"
    except (OSError, subprocess.SubprocessError, ValueError):
        pass
    _drive_cache.update(ts=time.time(), links=links)
    return links


def downloaded_paths() -> dict:
    """Stable file id -> path relative to DOWNLOAD_DIR (what the sync step saved)."""
    return {fid: e["path"] for fid, e in state_mod.load().get("downloaded", {}).items() if e.get("path")}


# --- rendering (pure) -------------------------------------------------------------------------

def _links_in(html_text: str) -> list[tuple[str, str]]:
    found = []
    for href, label in re.findall(r'<a[^>]+href="(https?://[^"]+)"[^>]*>(.*?)</a>', html_text or "", re.S | re.I):
        text = clean_text(label) or href
        if (href, text) not in found:
            found.append((html.unescape(href), text))
    return found


def module_time(module: dict) -> int:
    """When the module's content last changed (newest file/link), 0 if Moodle doesn't say."""
    times = [c.get("timemodified") or c.get("timecreated") or 0 for c in module.get("contents", [])]
    return max(times or [0])


def render_module(module: dict, paths: dict, links: dict) -> list[str]:
    """Lines (HTML) for one activity or resource."""
    from .files import stable_id

    lang = config.moodle_content_language()
    if not module.get("uservisible", True) or module.get("visible") == 0:
        return []
    kind = module.get("modname", "")
    name = clean_text(module.get("name", ""), lang)
    icon = ICONS.get(kind, "▫️")
    moodle_url = module.get("url", "")
    if kind == "url":
        target = next((c.get("fileurl") for c in module.get("contents", []) if c.get("type") == "url"), moodle_url)
        return [f'{icon} <a href="{esc(target)}">{esc(name)}</a>']
    if kind == "label":
        text = shorten(clean_text(module.get("description", ""), lang).replace("\n", " "), 160)
        lines = [f"{icon} {esc(text)}"] if text else []
        lines += [f'   🔗 <a href="{esc(href)}">{esc(shorten(label, 60))}</a>'
                  for href, label in _links_in(module.get("description", ""))]
        return lines
    if kind in ("resource", "folder"):
        lines = []
        for content in module.get("contents", []):
            if content.get("type") != "file":
                continue
            path = paths.get(stable_id(content))
            drive = links.get(path.casefold()) if path else None
            label = content.get("filename") if kind == "folder" else name
            where = drive or moodle_url
            lines.append(f'{icon} <a href="{esc(where)}">{esc(label)}</a>' + (" ☁️" if drive else ""))
        return lines or [f'{icon} <a href="{esc(moodle_url)}">{esc(name)}</a>']
    return [f'{icon} <a href="{esc(moodle_url)}">{esc(name)}</a>' if moodle_url else f"{icon} {esc(name)}"]


def render_section(course_name: str, section: dict, paths: dict, links: dict) -> str:
    lang = config.moodle_content_language()
    title = clean_text(section.get("name", ""), lang) or "—"
    lines = [f"📘 <b>{esc(course_name)}</b>", f"<b>{esc(title)}</b>", ""]
    summary = shorten(clean_text(section.get("summary", ""), lang).replace("\n", " "), 300)
    if summary:
        lines += [esc(summary), ""]
    for module in section.get("modules", []):
        lines += render_module(module, paths, links)
    return "\n".join(lines).strip()


def day_bounds(offset_days: int = 0) -> tuple[float, float, datetime]:
    day = (datetime.now() - timedelta(days=offset_days)).replace(hour=0, minute=0, second=0, microsecond=0)
    return day.timestamp(), (day + timedelta(days=1)).timestamp(), day


def render_day(courses_contents: list[tuple[str, list]], start: float, end: float, paths: dict,
               links: dict) -> list[str]:
    """Per course: sections with something changed between start and end."""
    lang = config.moodle_content_language()
    blocks = []
    for course_name, sections in courses_contents:
        lines = []
        for section in sections:
            changed = [m for m in section.get("modules", []) if start <= module_time(m) < end]
            if changed:
                lines.append(f"<i>{esc(clean_text(section.get('name', ''), lang))}</i>")
                for module in changed:
                    lines += render_module(module, paths, links)
        if lines:
            blocks.append(f"📘 <b>{esc(course_name)}</b>\n" + "\n".join(lines))
    return blocks


# --- data ----------------------------------------------------------------------------------------

def course_sections(course_id: int) -> list[dict]:
    """Sections that have something visible in them (Moodle's empty placeholders are skipped)."""
    return [s for s in moodle.course_contents(course_id)
            if s.get("modules") or clean_text(s.get("summary", ""))]
