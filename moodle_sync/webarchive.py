"""
One-off archive of an old Moodle site you can only open in the browser - e.g. when the
university's single sign-on hands out tokens for the new site only, and the old one has
no password login. Instead of a token it uses your browser session (the MoodleSession
cookie, asked for hidden and never saved):

- courses: the dashboard's AJAX service (core_course_get_enrolled_courses_by_timeline_classification),
  else the course links on the dashboard;
- sections and activities: core_courseformat_get_state (Moodle 4), else the course page;
- files: resources (view.php?redirect=1), and the file links on folder, assignment, page and
  book pages and on the course page itself (labels, section summaries).

Files land in <DATA_DIR>/archive/<site>/ in the usual layout (<course>/<category>/<file>,
your own submissions in "Submitted work/<assignment>/"), then the folder is copied to the
cloud. Progress is kept next to it, so an expired session just means: run it again.
"""

import getpass
import html
import json
import os
import re
import time
from pathlib import Path
from urllib.parse import unquote, urlsplit

import requests

from . import config, files
from .i18n import t

# activities whose pages hold files worth keeping (forums, quizzes, links... are skipped)
FILE_MODULES = {"resource", "folder", "assign", "page", "book"}
PAUSE = 0.2  # seconds between requests - an old server, no hurry


class SessionExpired(Exception):
    pass


def parse_cookie(text: str) -> dict:
    """'MoodleSession=abc', 'a=b; c=d' (a whole Cookie header) or just 'abc' -> cookies."""
    text = text.strip().removeprefix("Cookie:").strip()
    if "=" not in text:
        return {"MoodleSession": text}
    pairs = (part.split("=", 1) for part in text.split(";") if "=" in part)
    return {name.strip(): value.strip() for name, value in pairs}


_PLUGINFILE = re.compile(r'href="([^"]*?/pluginfile\.php/[^"]+)"')


def pluginfile_links(page: str) -> list[str]:
    """File links on a page, in order, without duplicates (images in the text are not files to keep)."""
    out = []
    for link in _PLUGINFILE.findall(page):
        link = html.unescape(link)
        if link not in out:
            out.append(link)
    return out


def link_details(link: str) -> tuple[str, str | None]:
    """(subfolder inside a folder activity, category) of a file link."""
    path = unquote(urlsplit(link).path)
    m = re.search(r"/mod_folder/content/\d+(/.*/)[^/]+$", path)
    category = "submitted" if "/assignsubmission_file/" in path else None
    return (m.group(1) if m else "/"), category


_SECTION = re.compile(r'<li[^>]*\bid="section-(\d+)"[^>]*>', re.S)
_ATTR = re.compile(r'(?:data-sectionname|aria-label)="([^"]*)"')
_HEADING = re.compile(r'<h3[^>]*class="[^"]*sectionname[^"]*"[^>]*>(.*?)</h3>', re.S)
_MODULE = re.compile(r'href="([^"]*/mod/(\w+)/view\.php\?id=(\d+))"[^>]*>(.*?)</a>', re.S)


def _text(fragment: str) -> str:
    fragment = re.sub(r'<span class="accesshide[^"]*">.*?</span>', "", fragment, flags=re.S)
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", fragment))).strip()


def parse_course_page(page: str) -> list[dict]:
    """Course page (any Moodle) -> [{"section", "modname", "name", "url"}] of its activities."""
    heads = list(_SECTION.finditer(page))
    chunks = [(page[h.start():heads[i + 1].start() if i + 1 < len(heads) else len(page)], h.group(0))
              for i, h in enumerate(heads)] or [(page, "")]
    mods = {}
    for chunk, tag in chunks:
        attr = _ATTR.search(tag)
        heading = _HEADING.search(chunk)
        section = html.unescape(attr.group(1)) if attr else _text(heading.group(1)) if heading else ""
        for url, modname, cmid, label in _MODULE.findall(chunk):
            mod = mods.setdefault(cmid, {"section": section, "modname": modname, "name": "", "url": html.unescape(url)})
            mod["name"] = mod["name"] or _text(label)  # the icon's link comes first, without text
    return [dict(m, name=m["name"] or m["modname"]) for m in mods.values()]


def parse_state(state: dict) -> list[dict]:
    """core_courseformat_get_state (Moodle 4) -> the same list as parse_course_page."""
    titles = {str(s["id"]): s.get("title", "") for s in state.get("section", [])}
    return [{"section": titles.get(str(cm.get("sectionid")), ""), "modname": cm.get("module", ""),
             "name": cm.get("name", ""), "url": cm.get("url", "")}
            for cm in state.get("cm", []) if cm.get("url") and cm.get("uservisible", True)]


def filename_of(resp: requests.Response) -> str:
    disposition = resp.headers.get("Content-Disposition", "")
    m = re.search(r"filename\*=(?:UTF-8|utf-8)''([^;]+)", disposition) or re.search(r'filename="?([^";]+)"?',
                                                                                   disposition)
    if m:
        return unquote(m.group(1)).strip()
    return unquote(urlsplit(resp.url).path.rsplit("/", 1)[-1])


class WebMoodle:
    def __init__(self, base: str, cookies: dict, http: requests.Session | None = None):
        self.base = base.rstrip("/")
        self.http = http or requests.Session()
        self.http.headers["User-Agent"] = "Mozilla/5.0 (moodle-sync archive)"
        for name, value in cookies.items():
            self.http.cookies.set(name, value)
        self.sesskey = ""

    def get(self, url: str, **kw) -> requests.Response:
        resp = self.http.get(url, timeout=(10, 120), **kw)
        resp.raise_for_status()
        if "/login/" in urlsplit(resp.url).path:
            raise SessionExpired()
        return resp

    def start(self) -> None:
        page = self.get(f"{self.base}/my/").text
        m = re.search(r'"sesskey":"([^"]+)"', page)
        if not m:
            raise SessionExpired()
        self.sesskey = m.group(1)
        self.dashboard = page

    def ajax(self, method: str, **args):
        resp = self.http.post(f"{self.base}/lib/ajax/service.php", params={"sesskey": self.sesskey, "info": method},
                              json=[{"index": 0, "methodname": method, "args": args}], timeout=(10, 120))
        resp.raise_for_status()
        reply = resp.json()
        if isinstance(reply, dict) or reply[0].get("error"):
            error = reply if isinstance(reply, dict) else reply[0].get("exception") or {}
            if error.get("errorcode") in ("servicerequireslogin", "invalidsesskey"):
                raise SessionExpired()
            raise RuntimeError(error.get("message") or error.get("errorcode") or "ajax error")
        return reply[0]["data"]

    def courses(self) -> list[dict]:
        found = {}
        for kind in ("all", "hidden"):
            try:
                data = self.ajax("core_course_get_enrolled_courses_by_timeline_classification",
                                 classification=kind, limit=0, offset=0, sort="fullname")
            except (RuntimeError, requests.RequestException, ValueError):
                continue
            for c in data.get("courses", []):
                found[c["id"]] = {"id": c["id"], "fullname": html.unescape(c.get("fullname", ""))}
        if not found:  # old Moodle: the course links on the dashboard and "My courses"
            pages = [self.dashboard]
            try:
                pages.append(self.get(f"{self.base}/my/courses.php").text)
            except requests.RequestException:
                pass
            for page in pages:
                for cid, label in re.findall(r'href="[^"]*/course/view\.php\?id=(\d+)"[^>]*>(.*?)</a>', page, re.S):
                    name = _text(label)
                    if name and int(cid) not in found and int(cid) != 1:
                        found[int(cid)] = {"id": int(cid), "fullname": name}
        return sorted(found.values(), key=lambda c: c["fullname"].casefold())

    def modules(self, course_id: int) -> tuple[list[dict], str]:
        """(activities, course page HTML)."""
        page = self.get(f"{self.base}/course/view.php?id={course_id}").text
        try:
            mods = parse_state(json.loads(self.ajax("core_courseformat_get_state", courseid=course_id)))
        except (RuntimeError, requests.RequestException, ValueError, TypeError):
            mods = parse_course_page(page)
        return mods, page


def _record(course: dict, section: str, mod: dict | None, filename: str, filepath: str, category: str | None) -> dict:
    f = {"course_id": course["id"], "course_name": course["fullname"], "section_name": section,
         "module_id": None, "modname": (mod or {}).get("modname", ""), "module_name": (mod or {}).get("name", ""),
         "filepath": filepath, "filename": filename}
    if category:
        f["category"] = category
    return f


def save(resp: requests.Response, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.name + ".part")
    with open(tmp, "wb") as fh:
        for chunk in resp.iter_content(files.CHUNK_SIZE):
            fh.write(chunk)
    os.replace(tmp, dest)


def free_path(rel: Path, used: set) -> Path:
    candidate, n = rel, 2
    while candidate.as_posix().casefold() in used:
        candidate = rel.with_name(f"{rel.stem} ({n}){rel.suffix}")
        n += 1
    return candidate


def fetch(web: WebMoodle, url: str, course: dict, section: str, mod: dict | None, filepath: str,
          category: str | None, root: Path, used: set) -> list[str]:
    """Download one link; a resource shown inside a page yields that page's files. Returns relative paths."""
    resp = web.get(url, stream=True)
    if "text/html" in resp.headers.get("Content-Type", ""):
        page = resp.text
        out = []
        if (mod or {}).get("modname") == "resource":  # "embed" / "in a frame" display: the file is linked inside
            for link in pluginfile_links(page):
                out += fetch(web, link, course, section, mod, "/", None, root, used)
        return out
    filename = filename_of(resp)
    if Path(filename).suffix.lower() in files.EXCLUDED_EXTENSIONS:
        resp.close()
        return []
    rel = free_path(files.relative_path(_record(course, section, mod, filename, filepath, category), {}), used)
    used.add(rel.as_posix().casefold())
    save(resp, root / rel)
    print(f"    [+] {rel.as_posix()}")
    return [rel.as_posix()]


def run(site: str, dest: str = "", list_only: bool = False) -> int:
    from . import storage
    from .setup_wizard import normalize_url

    base = normalize_url(site)
    parts = urlsplit(base)
    print(t("arch_cookie_help", host=parts.netloc, path=parts.path or "/"))
    web = WebMoodle(base, parse_cookie(getpass.getpass(t("arch_cookie_prompt"))))
    try:
        web.start()
        courses = web.courses()
    except (SessionExpired, requests.RequestException):
        print(t("arch_session_expired"))
        return 1
    print(t("arch_courses", n=len(courses)))

    root = config.DATA_DIR / "archive" / re.sub(r"\W+", "_", parts.netloc + parts.path).strip("_")
    progress_file = root.with_name(root.name + ".json")
    done = json.loads(progress_file.read_text(encoding="utf-8")) if progress_file.exists() else {}
    used = {p.casefold() for paths in done.values() for p in paths}
    saved, failed = 0, 0
    for course in courses:
        print(f"\n== {course['fullname']}")
        try:
            mods, page = web.modules(course["id"])
        except SessionExpired:
            print(t("arch_session_expired"))
            return 1
        except requests.RequestException as e:
            print("   " + t("error", error=e))
            failed += 1
            continue
        if list_only:
            for mod in mods:
                print(f"   {mod['section'] or '-'} | {mod['modname']} | {mod['name']}")
            continue
        targets = [(link, "", None) for link in pluginfile_links(page)]  # labels, section summaries
        for mod in mods:
            if mod["modname"] == "resource":
                targets.append((mod["url"] + "&redirect=1", mod["section"], mod))
            elif mod["modname"] in FILE_MODULES:
                try:
                    links = pluginfile_links(web.get(mod["url"]).text)
                except SessionExpired:
                    print(t("arch_session_expired"))
                    return 1
                except requests.RequestException as e:
                    print(f"   {mod['name']}: " + t("error", error=e))
                    failed += 1
                    continue
                targets += [(link, mod["section"], mod) for link in links]
                time.sleep(PAUSE)
        for url, section, mod in targets:
            key = url.split("?")[0] if "pluginfile.php" in url else url
            if key in done:
                continue
            filepath, category = link_details(url) if "pluginfile.php" in url else ("/", None)
            try:
                paths = fetch(web, url, course, section, mod, filepath, category, root, used)
            except SessionExpired:
                print(t("arch_session_expired"))
                return 1
            except (requests.RequestException, OSError) as e:
                print(f"    {url.split('?')[0].rsplit('/', 1)[-1]}: " + t("error", error=e))
                failed += 1
                continue
            done[key] = paths
            saved += len(paths)
            progress_file.parent.mkdir(parents=True, exist_ok=True)
            progress_file.write_text(json.dumps(done, ensure_ascii=False, indent=1), encoding="utf-8")
            time.sleep(PAUSE)

    if list_only:
        return 0
    print("\n" + t("arch_summary", ok=saved, failed=failed, dir=root))
    if dest and config.rclone_remote() and root.exists():
        print(t("arch_uploading", dest=f"{config.rclone_remote()}:{dest}"))
        if storage.rclone("copy", str(root), f"{config.rclone_remote()}:{dest.strip('/')}") != 0:
            return 1
    return 1 if failed else 0
