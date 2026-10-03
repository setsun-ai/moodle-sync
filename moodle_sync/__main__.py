"""
Command line: python -m moodle_sync <command>

    setup       interactive setup wizard (start here)
    doctor      check the configuration and say what to fix
    run         one full sync: files -> cloud -> calendar -> announcements/grades
    token       get a new Moodle token (when the old one expired)
    download    only download new files         [--dry-run] [--limit N] [--baseline]
    upload      only upload to the cloud        [--dry-run] [--check]
    calendar    only sync the calendar          [--dry-run] [--auth]
    watch       only check announcements/grades [--dry-run] [--force]
    courses     preview how files are categorised (for editing courses.json)
    plan        study plan: semesters, subjects, cards  [--search NAME] [--cards [--force]]
    ics         print the calendar subscription URL (Outlook / Apple Calendar)
    bot         run the Telegram bot            [--setup]
    notify-test send a test notification to all configured channels
    set         change one setting in .env safely, e.g.: set LANGUAGE pl
"""

import argparse
import sys

from . import __version__

SECRET_WORDS = ("TOKEN", "PASSWORD", "SECRET", "WEBHOOK", "HEALTHCHECK")


def set_setting(key: str, value: str) -> int:
    """
    Change one .env setting in place. Safer than appending with `echo >>`:
    that glues the new line onto the last one when the file doesn't end
    with a newline (a real accident - see docs: troubleshooting).
    """
    import re

    from . import config
    from .i18n import t

    key = key.strip().upper()
    if not re.fullmatch(r"[A-Z][A-Z0-9_]*", key):
        print(t("set_bad_key", key=key))
        return 2
    config.set_env_var(key, value.strip())
    shown = "***" if any(word in key for word in SECRET_WORDS) else value.strip()
    print(t("set_done", key=key, value=shown))
    return 0


def main(argv: list[str] | None = None) -> int:
    # Windows consoles may default to a legacy code page - make Polish letters and emoji safe.
    for stream in (sys.stdout, sys.stderr):
        if stream is not None and hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(prog="python -m moodle_sync",
                                     description="Moodle -> cloud storage, calendar and notifications.")
    parser.add_argument("--version", action="version", version=f"moodle-sync {__version__}")
    sub = parser.add_subparsers(dest="command", metavar="<command>")

    sub.add_parser("setup", help="interactive setup wizard (start here)")
    sub.add_parser("doctor", help="check the configuration")
    p = sub.add_parser("run", help="one full sync (what the scheduler runs)")
    p.add_argument("--log-file", help="append output to this file (used by scheduled runs)")
    sub.add_parser("token", help="get a new Moodle token")
    p = sub.add_parser("download", help="only download new files")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--limit", type=int, default=0)
    p.add_argument("--baseline", action="store_true", help="mark current files as done without downloading")
    p.add_argument("--reorganize", action="store_true",
                   help="confirm moving many already downloaded files after a settings change")
    p = sub.add_parser("upload", help="only upload to the cloud")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--check", action="store_true", help="only test the rclone remote")
    p = sub.add_parser("calendar", help="only sync the calendar")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--auth", action="store_true", help="log in to Google (one time)")
    p = sub.add_parser("watch", help="only check announcements and grades")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--force", action="store_true")
    sub.add_parser("courses", help="preview categories per course")
    p = sub.add_parser("plan", help="study plan: semester folders and subject cards")
    p.add_argument("--search", metavar="NAME", help="find your field of study in the ECTS catalogue")
    p.add_argument("--catalog", metavar="URL", default="", help="with --search: the catalogue's address")
    p.add_argument("--cards", action="store_true", help="download subject cards now")
    p.add_argument("--force", action="store_true", help="with --cards: re-check every card")
    p.add_argument("--dry-run", action="store_true")
    sub.add_parser("ics", help="print the calendar subscription URL")
    p = sub.add_parser("bot", help="run the Telegram bot")
    p.add_argument("--setup", action="store_true", help="connect the bot to your chat")
    sub.add_parser("notify-test", help="send a test notification")
    p = sub.add_parser("set", help="change one setting in .env safely, e.g.: set LANGUAGE pl")
    p.add_argument("key")
    p.add_argument("value")

    args = parser.parse_args(argv)
    cmd = args.command
    if cmd is None:
        parser.print_help()
        return 0

    # Imports per command: `bot` and `run` shouldn't load what they don't need.
    if cmd == "setup":
        from .setup_wizard import run
        return run()
    if cmd == "token":
        from .setup_wizard import run_token_only
        return run_token_only()
    if cmd == "doctor":
        from .doctor import run
        return run()
    if cmd == "run":
        from .runner import run
        return run(log_file=args.log_file)
    if cmd == "download":
        from .files import run
        return run(dry_run=args.dry_run, limit=args.limit, baseline=args.baseline, reorganize=args.reorganize)
    if cmd == "set":
        return set_setting(args.key, args.value)
    if cmd == "upload":
        from . import storage
        return storage.check() if args.check else storage.run(dry_run=args.dry_run)
    if cmd == "calendar":
        from . import calendar_sync
        return calendar_sync.authorize() if args.auth else calendar_sync.run(dry_run=args.dry_run)
    if cmd == "watch":
        from .watch import run
        return run(force=args.force, dry_run=args.dry_run)
    if cmd == "courses":
        from .files import preview
        return preview()
    if cmd == "plan":
        from . import studyplan
        if args.search:
            return studyplan.search(args.search, args.catalog)
        if args.cards:
            return studyplan.run(dry_run=args.dry_run, force=args.force)
        return studyplan.preview()
    if cmd == "ics":
        from .calendar_sync import ics_url
        return ics_url()
    if cmd == "bot":
        from . import telegram_bot
        return telegram_bot.setup() if args.setup else telegram_bot.run()
    if cmd == "notify-test":
        from .i18n import t
        from .notify import channels, notify
        if not channels():
            print(t("doc_notify", channels=t("doc_none")))
            return 2
        notify("test", t("wiz_test_title"), t("wiz_test_body"))
        print(t("wiz_test_sent", channels=", ".join(channels())))
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
