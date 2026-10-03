"""
Thin client for the Moodle Web Service (REST).

Moodle has ONE endpoint (webservice/rest/server.php); every API function is
called through the 'wsfunction' parameter. We use the token of the official
Moodle mobile app service ('moodle_mobile_app'), which every student can get
for their own account - see docs/*/token.md.
"""

import base64
import secrets
import time
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import requests

from . import PROJECT_URL, __version__, config

RETRIES = 3
RETRY_DELAYS = [2, 5, 15]
# Identify ourselves honestly to the server admins.
USER_AGENT = f"moodle-sync/{__version__} (+{PROJECT_URL})"

_session = requests.Session()  # keep-alive: one TLS connection for the whole run
_session.headers["User-Agent"] = USER_AGENT


class MoodleError(RuntimeError):
    """An error reported by Moodle itself (e.g. invalidtoken) - not retried."""

    def __init__(self, errorcode: str, message: str):
        super().__init__(f"Moodle [{errorcode}]: {message}")
        self.errorcode = errorcode


class NotConfigured(RuntimeError):
    pass


def _endpoint(base_url: str | None = None) -> str:
    base = (base_url or config.moodle_base_url()).rstrip("/")
    if not base:
        raise NotConfigured("MOODLE_BASE_URL is not set - run: python -m moodle_sync setup")
    return f"{base}/webservice/rest/server.php"


def _post_with_retries(url: str, **kwargs) -> requests.Response:
    """
    POST with retries on transient problems (connection reset, timeout, 5xx):
    university servers sometimes drop connections and Raspberry Pi Wi-Fi can
    blink. A Moodle-level error (HTTP 200 + error JSON) is NOT retried.
    """
    for attempt in range(RETRIES + 1):
        try:
            resp = _session.post(url, timeout=30, **kwargs)
            if resp.status_code < 500:
                return resp
        except (requests.ConnectionError, requests.Timeout):
            if attempt == RETRIES:
                raise
        if attempt < RETRIES:
            time.sleep(RETRY_DELAYS[attempt])
    return resp


def call(wsfunction: str, token: str | None = None, base_url: str | None = None, **params):
    """
    Call any Moodle Web Service function.

    On errors Moodle still answers HTTP 200 with a JSON containing
    'exception'/'errorcode'/'message' - so we check the content, not only
    the HTTP status.
    """
    token = token or config.moodle_token()
    if not token:
        raise NotConfigured("MOODLE_TOKEN is not set - run: python -m moodle_sync setup")
    payload = {"wstoken": token, "wsfunction": wsfunction, "moodlewsrestformat": "json", **params}
    resp = _post_with_retries(_endpoint(base_url), data=payload)
    resp.raise_for_status()
    data = resp.json()
    if isinstance(data, dict) and "exception" in data:
        raise MoodleError(data.get("errorcode", "?"), data.get("message", ""))
    return data


# --- common calls ------------------------------------------------------------------------

def site_info(**kw) -> dict:
    """The simplest token check; also returns userid and the allowed functions."""
    return call("core_webservice_get_site_info", **kw)


def course_skipped(course: dict, cfg: dict) -> bool:
    name = course.get("fullname", "").casefold()
    return any(fragment.casefold() in name for fragment in cfg.get("skip", []))


def my_courses() -> list:
    """Courses the user is enrolled in, minus those listed in courses.json -> "skip"."""
    courses = call("core_enrol_get_users_courses", userid=site_info()["userid"])
    cfg = config.load_courses_config()
    return [c for c in courses if not course_skipped(c, cfg)]


def course_contents(course_id: int) -> list:
    """Course structure: sections -> modules (incl. files)."""
    return call("core_course_get_contents", courseid=course_id)


def public_config(base_url: str) -> dict:
    """
    Public site info, no login needed. Tells us the site name and HOW users
    log in: typeoflogin 1 = in the app (username + password), 2/3 = via the
    browser (SSO: CAS, SAML, Microsoft, Google...).
    """
    resp = _post_with_retries(
        f"{base_url.rstrip('/')}/lib/ajax/service-nologin.php",
        params={"info": "tool_mobile_get_public_config"},
        json=[{"index": 0, "methodname": "tool_mobile_get_public_config", "args": {}}],
    )
    resp.raise_for_status()
    result = resp.json()[0]
    if result.get("error"):
        raise MoodleError("public_config", result.get("exception", {}).get("message", "?"))
    return result["data"]


# --- getting a token -------------------------------------------------------------------------

# The "private token" Moodle hands out together with a new token (HTTPS only). It
# lets the app open web pages logged in (tool_mobile_get_autologin_key) - we
# need it for attendance, which has no web service functions. The wizard saves
# it as MOODLE_PRIVATE_TOKEN; treat it like a password.
LAST_PRIVATE_TOKEN = ""

def token_from_password(base_url: str, username: str, password: str) -> str:
    """
    Sites with the normal login form (typeoflogin 1): Moodle's standard token
    endpoint. The password is sent only to your Moodle site, over HTTPS, and
    is never stored.
    """
    resp = _post_with_retries(
        f"{base_url.rstrip('/')}/login/token.php",
        data={"username": username, "password": password, "service": "moodle_mobile_app"},
    )
    resp.raise_for_status()
    data = resp.json()
    if "token" not in data:
        raise MoodleError(data.get("errorcode", "?"), data.get("error", ""))
    global LAST_PRIVATE_TOKEN
    LAST_PRIVATE_TOKEN = data.get("privatetoken") or ""
    return data["token"]


def sso_launch_url(base_url: str) -> tuple[str, str]:
    """
    Sites with browser login (SSO): the same URL the mobile app opens. After
    logging in, Moodle redirects to moodlemobile://token=<base64>, which the
    browser can't open - the user copies it from there. Returns (url, passport).
    """
    passport = secrets.token_hex(8)
    query = urlencode({"service": "moodle_mobile_app", "passport": passport, "urlscheme": "moodlemobile"})
    return f"{base_url.rstrip('/')}/admin/tool/mobile/launch.php?{query}", passport


def decode_sso_token(text: str) -> str:
    """
    moodlemobile://token=<base64> (or just the base64) -> web service token.
    Decoded format: <md5(site URL + passport)>:::<wstoken>[:::<privatetoken>].
    We don't verify the signature (the site URL in .env may differ cosmetically
    from the server's own, e.g. a trailing slash) - the setup wizard checks the
    token by actually calling the API, which is the real test.
    """
    raw = text.strip()
    if "token=" in raw:
        raw = raw.split("token=", 1)[1]
    raw = raw.strip().strip("'\"").split("&")[0].split('"')[0]
    raw += "=" * (-len(raw) % 4)
    decoded = base64.b64decode(raw).decode("utf-8")
    parts = decoded.split(":::")
    if len(parts) < 2 or not parts[1]:
        raise ValueError("unexpected token format")
    global LAST_PRIVATE_TOKEN
    LAST_PRIVATE_TOKEN = parts[2] if len(parts) > 2 else ""
    return parts[1]


def upload_draft(filename: str, data: bytes) -> int:
    """Upload a file to the user's draft area (like the app does before submitting); returns its itemid."""
    resp = _session.post(f"{config.moodle_base_url()}/webservice/upload.php", timeout=120,
                         data={"token": config.moodle_token(), "filearea": "draft", "itemid": 0},
                         files={"file_1": (filename, data)})
    resp.raise_for_status()
    body = resp.json()
    if isinstance(body, dict):
        raise MoodleError(body.get("errorcode", "?"), body.get("error") or body.get("message", ""))
    return int(body[0]["itemid"])


# --- files --------------------------------------------------------------------------------------

def file_url_with_token(fileurl: str, token: str | None = None) -> str:
    """
    File URLs from the API need the token in the query string (?token=...).
    The plain /pluginfile.php needs a browser session; the /webservice/ variant
    accepts the token - the official mobile app does the same rewrite.
    """
    token = token or config.moodle_token()
    parts = urlsplit(fileurl)
    path = parts.path
    if "/webservice/pluginfile.php" not in path:
        path = path.replace("/pluginfile.php", "/webservice/pluginfile.php", 1)
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if k != "token"]
    query.append(("token", token))
    return urlunsplit(parts._replace(path=path, query=urlencode(query)))


def redact(text: str) -> str:
    """requests puts the full URL (with the token!) into exception messages."""
    for secret in (config.moodle_token(), config.env("MOODLE_PRIVATE_TOKEN")):
        if secret:
            text = text.replace(secret, "***")
    return text


def session() -> requests.Session:
    return _session
