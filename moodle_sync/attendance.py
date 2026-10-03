"""
Attendance (mod_attendance) through the Moodle web pages.

The attendance plugin has no web service functions for students, so we do
what the Moodle app does when it opens a page in its browser: ask for a
one-time autologin key (tool_mobile_get_autologin_key, needs the private
token saved by the setup wizard as MOODLE_PRIVATE_TOKEN), open the page
logged in and fill in the same form you would fill in by hand.

Nothing is marked on its own: the bot shows the session and the statuses your
teacher allows, and submits only the one you tap. Three cases are covered:
    - a QR link that already carries the password (qrpass) - one tap,
    - a session that asks for a password - you type it,
    - a session without a password - just pick the status.
Sessions restricted to the university network will refuse a bot at home.

The parsing functions are pure - see tests/test_attendance.py.
"""

import html
import re
import time
from html.parser import HTMLParser
from urllib.parse import parse_qs, urljoin, urlsplit

import requests

from . import config, moodle

AUTOLOGIN_MIN_INTERVAL = 6 * 60  # Moodle allows one autologin key per ~6 minutes


# --- parsing (pure) ------------------------------------------------------------------------

def parse_link(url: str) -> dict | None:
    """Attendance link (e.g. from a QR code) -> {"url", "sessid", "qrpass"}; None if it isn't one."""
    url = url.strip()
    if "/mod/attendance/" not in url:
        return None
    query = parse_qs(urlsplit(url).query)
    sessid = (query.get("sessid") or [""])[0]
    return {"url": url, "sessid": sessid, "qrpass": (query.get("qrpass") or [""])[0]}


def _text(fragment: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", fragment))).strip()


def session_links(page: str, base: str) -> list[dict]:
    """Links "Submit attendance" on an attendance activity page: [{"url", "sessid", "label"}]."""
    out, seen = [], set()
    rows = re.split(r"<tr\b", page, flags=re.I)
    for row in rows:
        for href in re.findall(r'href="([^"]*attendance\.php\?[^"]*sessid=\d+[^"]*)"', row):
            url = urljoin(base, html.unescape(href))
            sessid = re.search(r"sessid=(\d+)", url).group(1)
            if sessid in seen:
                continue
            seen.add(sessid)
            label = _text(row.split(">", 1)[-1])[:120]
            out.append({"url": url, "sessid": sessid, "label": label})
    return out


class _FormParser(HTMLParser):
    """Collects the attendance form: hidden fields, status radios, password field, labels."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.forms, self.current, self.labels = [], None, {}
        self.label_for, self.label_text, self.label_radio = None, None, None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "form":
            self.current = {"action": a.get("action", ""), "hidden": {}, "radios": [], "password": None,
                            "submit": None}
            self.forms.append(self.current)
        elif tag == "label":
            self.label_for, self.label_text, self.label_radio = a.get("for"), [], None
        elif tag == "input" and self.current is not None:
            kind, name = (a.get("type") or "text").lower(), a.get("name")
            if not name:
                return
            if kind == "hidden":
                self.current["hidden"][name] = a.get("value", "")
            elif kind == "radio" and name == "status":
                radio = {"value": a.get("value", ""), "id": a.get("id"), "label": ""}
                self.current["radios"].append(radio)
                if self.label_text is not None:  # <label><input type=radio> Present</label>
                    self.label_radio = radio
            elif kind in ("password", "text") and "pass" in name.lower():
                self.current["password"] = name
            elif kind == "submit" and self.current["submit"] is None:
                self.current["submit"] = (name, a.get("value", ""))

    def handle_data(self, data):
        if self.label_text is not None:
            self.label_text.append(data)

    def handle_endtag(self, tag):
        if tag == "label" and self.label_text is not None:
            text = " ".join("".join(self.label_text).split())
            if self.label_radio is not None:
                self.label_radio["label"] = text
            elif self.label_for:
                self.labels[self.label_for] = text
            self.label_for, self.label_text, self.label_radio = None, None, None
        elif tag == "form":
            self.current = None


def parse_form(page: str, base: str) -> dict | None:
    """
    The student's attendance form on a page -> {"action", "hidden", "statuses": [(value, label)],
    "password": field name or None, "submit": (name, value) or None}; None if the page has none.
    """
    parser = _FormParser()
    parser.feed(page)
    for form in parser.forms:
        if not form["radios"]:
            continue
        statuses = [(r["value"], r["label"] or parser.labels.get(r["id"], "") or r["value"]) for r in form["radios"]]
        return {"action": urljoin(base, form["action"] or "attendance.php"), "hidden": form["hidden"],
                "statuses": statuses, "password": form["password"], "submit": form["submit"]}
    return None


def page_message(page: str) -> str:
    """The notification Moodle shows on a page (success, error, "already recorded"...), as plain text."""
    m = re.search(r'<div[^>]*class="[^"]*\b(?:alert|notifysuccess|notifyproblem|notifymessage|errorbox)\b[^"]*"[^>]*>'
                  r"(.*?)</div>", page, re.S | re.I)
    if m:
        return _text(m.group(1))[:300]
    m = re.search(r'<div[^>]*role="main"[^>]*>(.*?)</div>', page, re.S | re.I)
    return _text(m.group(1))[:300] if m else ""


def default_status(statuses: list[tuple[str, str]]) -> str | None:
    """The status meaning 'present' (first one if none matches) - shown first on the buttons."""
    for value, label in statuses:
        if re.search(r"obecn|present|присут", label, re.I) and not re.search(r"nieobecn|absent", label, re.I):
            return value
    return statuses[0][0] if statuses else None


# --- web session -----------------------------------------------------------------------------

class NotAvailable(Exception):
    pass


class Web:
    """A logged-in web session, opened with an autologin key and reused while it lasts."""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers["User-Agent"] = moodle.USER_AGENT
        self.logged_in = False
        self.last_key = 0.0

    def _login(self, target: str) -> requests.Response:
        private = config.env("MOODLE_PRIVATE_TOKEN")
        if not private:
            raise NotAvailable("no_private_token")
        if time.time() - self.last_key < AUTOLOGIN_MIN_INTERVAL:
            raise NotAvailable("autologin_wait")
        self.last_key = time.time()
        key = moodle.call("tool_mobile_get_autologin_key", privatetoken=private)
        resp = self.session.get(key["autologinurl"], timeout=30, params={
            "userid": moodle.site_info()["userid"], "key": key["key"], "urltogo": target})
        resp.raise_for_status()
        self.logged_in = True
        return resp

    @staticmethod
    def _is_login_page(resp: requests.Response) -> bool:
        return "/login/" in resp.url and "attendance" not in resp.url

    def get(self, url: str) -> requests.Response:
        if not self.logged_in:
            return self._login(url)
        resp = self.session.get(url, timeout=30)
        if self._is_login_page(resp):  # the web session expired: log in again
            self.logged_in = False
            return self._login(url)
        return resp

    def post(self, url: str, data: dict) -> requests.Response:
        resp = self.session.post(url, data=data, timeout=30)
        resp.raise_for_status()
        return resp


WEB = Web()


def open_session(url: str) -> tuple[dict | None, str, str]:
    """Open an attendance page: (form or None, message on the page, final URL)."""
    resp = WEB.get(url)
    return parse_form(resp.text, resp.url), page_message(resp.text), resp.url


def submit(form: dict, status: str, password: str = "") -> tuple[bool, str]:
    """Send the chosen status; (True, Moodle's message) when the form is gone afterwards."""
    data = dict(form["hidden"])
    data["status"] = status
    if form["password"]:
        data[form["password"]] = password
    if form["submit"]:
        data[form["submit"][0]] = form["submit"][1]
    resp = WEB.post(form["action"], data)
    still_form = parse_form(resp.text, resp.url) is not None
    return not still_form, page_message(resp.text)


def today_sessions(courses: list[dict]) -> list[dict]:
    """Sessions you can mark now, from the attendance activities of your courses."""
    found = []
    for course in courses:
        try:
            contents = moodle.course_contents(course["id"])
        except moodle.MoodleError:
            continue
        for section in contents:
            for module in section.get("modules", []):
                if module.get("modname") != "attendance" or not module.get("uservisible", True):
                    continue
                resp = WEB.get(module["url"])
                for link in session_links(resp.text, resp.url):
                    link["course"] = course.get("fullname", "")
                    link["module"] = module.get("name", "")
                    found.append(link)
    return found
