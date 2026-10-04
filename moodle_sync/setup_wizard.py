"""
Interactive setup: python -m moodle_sync setup

Walks a first-time user through everything that can be done from the
terminal: Moodle address -> token -> download folder -> notifications ->
cloud storage -> Google Calendar -> first run. Each step can be skipped and
the wizard can be re-run any time (it keeps existing values as defaults).
Also used alone for renewing an expired token: python -m moodle_sync token
"""

import getpass
import re
import secrets
import shutil
import subprocess
import sys
import webbrowser

from . import config, moodle, notify
from .i18n import t

# --- input helpers ---------------------------------------------------------------------------

def ask(prompt: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    value = input(f"{prompt}{suffix}: ").strip()
    return value or default


def yes(prompt: str, default: bool = True) -> bool:
    hint = t("yes_no_default_yes") if default else t("yes_no_default_no")
    value = input(f"{prompt} {hint}: ").strip().lower()
    if not value:
        return default
    return value[0] in ("y", "t")  # yes / tak


def choose(prompt: str, options: list[tuple[str, str]], default: str) -> str:
    print(prompt)
    for i, (_key, label) in enumerate(options, 1):
        print(f"  {i}. {label}")
    keys = [k for k, _ in options]
    value = ask(t("choose_number"), str(keys.index(default) + 1))
    try:
        return keys[int(value) - 1]
    except (ValueError, IndexError):
        return default


def header(text: str) -> None:
    print(f"\n{'=' * 64}\n  {text}\n{'=' * 64}")


# --- Moodle address and token -------------------------------------------------------------------

MOODLE_PATH_MARKERS = ("/course/", "/my", "/login/", "/mod/", "/user/", "/admin/", "/index.php", "/calendar/")


def normalize_url(url: str) -> str:
    """'moodle.example.edu.pl/2025/course/view.php?id=1' -> 'https://moodle.example.edu.pl/2025'"""
    url = url.strip()
    if not re.match(r"https?://", url):
        url = "https://" + url
    url = url.split("?")[0].split("#")[0]
    for marker in MOODLE_PATH_MARKERS:
        idx = url.find(marker, len("https://"))
        if idx != -1:
            url = url[:idx]
    return url.rstrip("/")


def step_site() -> tuple[str, dict]:
    header(t("wiz_site_header"))
    print(t("wiz_site_help"))
    while True:
        url = normalize_url(ask(t("wiz_site_prompt"), config.moodle_base_url()))
        try:
            public = moodle.public_config(url)
            print("✅ " + t("wiz_site_ok", name=public.get("sitename", "?"), url=url))
            return url, public
        except Exception as e:
            print("❌ " + t("wiz_site_failed", url=url, error=e))


def token_via_sso(url: str, public: dict) -> str | None:
    launch, _passport = moodle.sso_launch_url(url)
    print(t("wiz_sso_steps", url=launch))
    try:
        webbrowser.open(launch)
    except Exception:
        pass
    while True:
        pasted = ask(t("wiz_sso_paste"))
        if not pasted:
            return None
        try:
            return moodle.decode_sso_token(pasted)
        except Exception:
            print("❌ " + t("wiz_sso_bad"))


def token_via_password(url: str) -> str | None:
    print(t("wiz_password_note"))
    username = ask(t("wiz_username"))
    password = getpass.getpass(t("wiz_password") + ": ")
    try:
        return moodle.token_from_password(url, username, password)
    except Exception as e:
        print("❌ " + t("wiz_password_failed", error=e))
        return None


def step_token(url: str, public: dict) -> dict:
    header(t("wiz_token_header"))
    existing = config.moodle_token()
    if existing and url == config.moodle_base_url():
        try:
            info = moodle.site_info(token=existing, base_url=url)
            if yes(t("wiz_token_keep", name=info.get("fullname", "?"))):
                return info
        except Exception:
            print(t("wiz_token_existing_invalid"))

    sso = public.get("typeoflogin", 1) != 1
    print(t("wiz_login_sso") if sso else t("wiz_login_password"))
    recommended = "sso" if sso else "password"
    methods = [(key, t(f"wiz_method_{key}") + (" ← " + t("wiz_recommended") if key == recommended else ""))
               for key in ("sso", "password", "paste")]
    while True:
        method = choose(t("wiz_method_prompt"), methods, "sso" if sso else "password")
        if method == "sso":
            token = token_via_sso(url, public)
        elif method == "password":
            token = token_via_password(url)
        else:
            token = ask(t("wiz_paste_token"))
        if not token:
            continue
        try:
            info = moodle.site_info(token=token, base_url=url)
        except Exception as e:
            print("❌ " + t("wiz_token_invalid", error=e))
            continue
        config.set_env_var("MOODLE_BASE_URL", url)
        config.set_env_var("MOODLE_TOKEN", token)
        if moodle.LAST_PRIVATE_TOKEN:  # needed only for attendance (web pages opened by the bot)
            config.set_env_var("MOODLE_PRIVATE_TOKEN", moodle.LAST_PRIVATE_TOKEN)
        print("✅ " + t("wiz_token_ok", name=info.get("fullname", "?")))
        return info


# --- other steps ----------------------------------------------------------------------------------

def step_basics(public: dict) -> None:
    header(t("wiz_basics_header"))
    name = public.get("sitename", "Moodle")
    default_label = config.env("SITE_LABEL") or (name if len(name) <= 12 else name.split()[-1])
    config.set_env_var("SITE_LABEL", ask(t("wiz_label_prompt"), default_label))
    print(t("wiz_folder_help"))
    config.set_env_var("DOWNLOAD_DIR", ask(t("wiz_folder_prompt"), config.env("DOWNLOAD_DIR", "downloads")))


def step_study_plan() -> None:
    """Optional: semester folders and subject cards from the university's ECTS catalogue."""
    from . import studyplan

    header(t("wiz_plan_header"))
    print(t("wiz_plan_help"))
    catalog = studyplan.catalog_url(ask(t("wiz_plan_catalog"), config.env("STUDY_CATALOG")))
    if not catalog:
        return
    query = ask(t("wiz_plan_prompt"))
    if not query:
        return
    config.set_env_var("STUDY_CATALOG", catalog)
    try:
        programs = studyplan.search_programs(query, catalog)
    except Exception as e:  # the catalogue is optional - never break the wizard
        print(t("error", error=e))
        return
    if not programs:
        print(t("plan_search_none", query=query))
        return
    options = [(p["url"], f"{p['field']} – {p['mode']}, {p['start']}"
                + (f" ({t('plan_now')}: {p['current']})" if p["current"] else "")) for p in programs[:30]]
    options.append(("", t("wiz_plan_skip")))
    url = choose(t("wiz_plan_choose"), options, options[0][0])
    if not url:
        return
    url = studyplan.normalize_plan_url(url)
    try:
        base = url.split("/", 3)[:3]
        specs = studyplan.parse_specializations(studyplan._get(url).text, "/".join(base))
    except Exception:
        specs = []
    if specs:
        url = choose(t("wiz_plan_specialisation"), [(u, name) for name, u in specs] + [(url, t("wiz_plan_common"))],
                     specs[0][1])
    config.set_env_var("STUDY_PLAN_URL", url)
    print(t("wiz_plan_done"))


def step_notifications() -> None:
    header(t("wiz_notify_header"))
    print(t("wiz_notify_help"))
    current = notify.channels()
    if current:
        print(t("wiz_notify_current", channels=", ".join(current)))

    if yes(t("wiz_telegram_q"), "telegram" in current or not current):
        if not config.env("TELEGRAM_BOT_TOKEN") or not yes(t("wiz_keep_existing"), True):
            print(t("wiz_telegram_steps"))
            token = ask(t("wiz_telegram_token"))
            if token:
                config.set_env_var("TELEGRAM_BOT_TOKEN", token)
        if config.env("TELEGRAM_BOT_TOKEN"):
            from . import telegram_bot
            telegram_bot.setup()

    if yes(t("wiz_discord_q"), "discord" in current):
        print(t("wiz_discord_steps"))
        hook = ask(t("wiz_discord_url"), config.env("DISCORD_WEBHOOK_URL"))
        if hook:
            config.set_env_var("DISCORD_WEBHOOK_URL", hook)

    if yes(t("wiz_ntfy_q"), "ntfy" in current):
        topic = ask(t("wiz_ntfy_topic"), config.env("NTFY_TOPIC") or f"moodle-{secrets.token_hex(6)}")
        config.set_env_var("NTFY_TOPIC", topic)
        print(t("wiz_ntfy_steps", topic=topic))

    if yes(t("wiz_email_q"), "email" in current):
        print(t("wiz_email_help"))
        config.set_env_var("SMTP_HOST", ask("SMTP host", config.env("SMTP_HOST", "smtp.gmail.com")))
        config.set_env_var("SMTP_PORT", ask("SMTP port", config.env("SMTP_PORT", "587")))
        config.set_env_var("SMTP_USER", ask(t("wiz_email_user"), config.env("SMTP_USER")))
        password = getpass.getpass(t("wiz_email_password") + ": ")
        if password:
            config.set_env_var("SMTP_PASSWORD", password)
        config.set_env_var("EMAIL_TO", ask(t("wiz_email_to"), config.env("EMAIL_TO") or config.env("SMTP_USER")))

    if notify.channels():
        notify.notify("test", t("wiz_test_title"), t("wiz_test_body"))
        print("🔔 " + t("wiz_test_sent", channels=", ".join(notify.channels())))


def step_storage() -> None:
    header(t("wiz_storage_header"))
    print(t("wiz_storage_help"))
    rclone = shutil.which(config.rclone_bin())
    if not rclone:
        print(t("wiz_storage_no_rclone"))
        return
    remotes = subprocess.run([rclone, "listremotes"], capture_output=True, text=True).stdout.split()
    if not remotes:
        print(t("wiz_storage_no_remotes"))
        return
    print(t("wiz_storage_remotes", remotes=", ".join(remotes)))
    remote = ask(t("wiz_storage_remote"), config.rclone_remote() or remotes[0].rstrip(":")).rstrip(":")
    if remote:
        config.set_env_var("RCLONE_REMOTE", remote)
        config.set_env_var("DRIVE_DEST", ask(t("wiz_storage_dest"), config.remote_dest()))


def step_calendar() -> None:
    header(t("wiz_calendar_header"))
    if config.GOOGLE_TOKEN_FILE.exists():
        print("✅ " + t("wiz_calendar_ok"))
        return
    print(t("wiz_calendar_help"))
    if config.CLIENT_SECRET_FILE.exists() and yes(t("wiz_calendar_login_q")):
        from . import calendar_sync
        calendar_sync.authorize()


def step_first_run() -> None:
    header(t("wiz_first_header"))
    from . import files
    all_files = files.collect_files(moodle.my_courses())
    size = sum(f.get("filesize") or 0 for f in all_files) / 1e6
    choice = choose(t("wiz_first_prompt", n=len(all_files), mb=size), [
        ("all", t("wiz_first_all")), ("baseline", t("wiz_first_baseline")), ("later", t("wiz_first_later")),
    ], "all")
    if choice == "baseline":
        files.run(baseline=True)
    elif choice == "all":
        from . import runner
        runner.run()


def step_finish() -> None:
    header(t("wiz_done_header"))
    key = {"win32": "wiz_done_windows", "darwin": "wiz_done_macos"}.get(sys.platform, "wiz_done_linux")
    print(t("wiz_done_common") + "\n\n" + t(key))


def run() -> int:
    try:
        header("moodle-sync")
        lang = choose("Language / Język:", [("en", "English"), ("pl", "Polski")], config.language())
        config.set_env_var("LANGUAGE", lang)
        header(t("wiz_rules_header"))
        print(t("wiz_rules_text"))
        input("\n" + t("wiz_rules_continue"))
        url, public = step_site()
        info = step_token(url, public)
        print(t("wiz_courses_found", n=len(moodle.call("core_enrol_get_users_courses", userid=info["userid"]))))
        step_basics(public)
        step_study_plan()
        step_notifications()
        step_storage()
        step_calendar()
        step_first_run()
        step_finish()
        return 0
    except (KeyboardInterrupt, EOFError):
        print("\n" + t("wiz_cancelled"))
        return 130


def run_token_only() -> int:
    """python -m moodle_sync token - just (re)new the Moodle token."""
    try:
        url, public = step_site()
        step_token(url, public)
        return 0
    except (KeyboardInterrupt, EOFError):
        print("\n" + t("wiz_cancelled"))
        return 130
