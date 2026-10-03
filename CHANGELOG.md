# Changelog

## 1.0.4 (2026-10)

- **`/update` in the Telegram bot**: downloads the newest GitHub release, runs `pip install -r requirements.txt` only if it changed, imports the new code once (selftest) and only then swaps `moodle_sync/` and restarts the bot. `.env`, `courses.json`, `state.json`, Google tokens and `downloads/` are never touched. It waits if a sync is running, and no sync can start during the swap. If anything fails, the old version keeps running and the error is shown.
- **`/rollback`**: back to the version that ran before the last `/update` (kept in `.update/previous`); a second `/rollback` goes forward again.
- The bot refreshes its command menu at every start, so new commands appear without `bot --setup`.
- For copies unpacked from a release archive; in a git clone keep using `git pull`.

## 1.0.3 (2026-09)

Maintenance release: no changes in behaviour.

- CI tests every supported Python (3.10-3.14) on Linux, and 3.10 and 3.14 on Windows and macOS.
- Dependabot opens weekly update PRs for Python packages and GitHub Actions; workflows use `actions/checkout@v7` and `actions/setup-python@v7`.

## 1.0.2 (2026-09)

- **Calendar: no more duplicate calendars.** A temporary Google error (expired login, a 5xx) while checking the calendars was treated as "calendar deleted", and a second "<SITE_LABEL> – deadlines" calendar was created. Now a calendar is recreated only when Google really says it's gone (404/410).
- **Calendar: a calendar deleted by hand is refilled completely** on the next run. Before, it came back only after the next change in Moodle, and only with the changed events. The refill doesn't send "new deadline" notifications.
- **Telegram:** a long message cut inside an HTML tag or entity was rejected by Telegram and lost. Such a message is now delivered as plain text.
- The Telegram bot survives a non-JSON answer (e.g. a proxy error page) instead of stopping.
- Releases: pushing a version tag runs the tests and publishes a GitHub release with notes from this file.

## 1.0.1 (2026-09)

- **Safety fuse:** if a settings change would move a large part of the already downloaded archive, nothing is moved or downloaded until you confirm with `download --reorganize`. The error notification explains why. Found in real use: `LANGUAGE` was lost in a glued `.env` line, and every folder started to be renamed to English.
- `doctor` shows the effective language and folder names, and detects broken `.env` lines (glued or without `=`).
- New `set KEY VALUE` command to change `.env` safely. `.env` is always written with LF line endings.
- **Cloud moves are "netted" first.** One listing of the cloud folder, then only the moves that are really needed: already-done moves and round trips (A→B→A) cost nothing, and chains collapse. They run 3 in parallel and save progress every 20 files. Before this, an interrupted re-organisation meant hundreds of useless ~8 s rclone calls on a Raspberry Pi, and "source doesn't exist" was wrongly retried as an error.

## 1.0.0 (2026-09)

First public release: a universal tool for any Moodle.

- Python package `moodle_sync` with one CLI: `setup`, `doctor`, `run`, `token`, `download`, `upload`, `calendar`, `watch`, `courses`, `ics`, `bot`, `notify-test`.
- **Setup wizard:** detects password vs. SSO login and gets the token (incl. the `moodlemobile://` flow).
- **Files:** categories (Lectures / Exercises / Labs / Projects / Other) in Polish or English, own rules and names in `courses.json`, automatic moving after rule changes (locally and in the cloud), safe file names for Windows and Linux, size limit.
- **Cloud:** rclone (Google Drive, OneDrive, Dropbox...), or simply a folder synced by a desktop app; backup of `state.json`.
- **Calendar:** Google Calendar sync with ✅ for submitted work, a separate calendar for classes, notifications about moved deadlines; `.ics` subscription URL for other calendars.
- **Watch:** announcements and grades (with teacher feedback), throttled requests, no floods on the first run or when a new forum gets watched.
- **Notifications:** Telegram (with commands), Discord webhook, ntfy, e-mail; per-kind muting; weekly summary; healthchecks.io dead-man alarm.
- **Running:** manual launchers, Windows Task Scheduler, macOS launchd, Linux user timer, Raspberry Pi / server systemd units with automatic security updates.
- Polish and English UI and docs, tests and CI on Windows, macOS and Linux.

## 0.x

Personal scripts for one university's Moodle, the origin of this project.
