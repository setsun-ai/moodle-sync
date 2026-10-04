# Changelog

🇵🇱 [Po polsku](CHANGELOG.pl.md)

## 1.5.1 (2026-10)

- `/electives`: ✏️ renames the folder of a whole module - e.g. to the name of the course you take at another university, so its card (`/card`) lands next to its files.

## 1.5.0 (2026-10)

- **Fixed: duplicated folders in Google Drive.** Moves ran three at a time, and Google Drive allows several folders with the same name - three moves into a new folder created it three times ("English" x3). Target folders are now created one by one before moving. `/cleanup` also finds duplicated folders and merges them (`rclone dedupe`).
- **Errors you can read:** rclone's own messages now reach the log and the error notification (they used to show only the commands), the notification leads with the error lines, and `/errors` (`/bledy`) shows the last sync step by step with the full output of failed steps.
- **No false alarm after deliberate changes:** an update, `/assign`, `/electives` or `courses.json` moving many files is done right away with a "files moved" notification; the fuse (and its message, now pointing to `/reorganize`) is kept for unexplained mass moves such as a broken `.env`.
- **`/assign`:** each course shows when it started and how many files it has (two "English" courses are told apart), ✏️ renames its folder, ➕ adds another semester - one Moodle course for two subjects, files split by their dates.
- **`/card` (`/karta`):** your own link (PDF or page) to the card of a subject the catalogue has none for, e.g. a course from another university.
- **Calendar:** online classes get their join link (Teams, Zoom, Meet, Webex, BigBlueButton…) as the event's location and at the top of its description.
- Readable names keep proper nouns ("Język Python"); the setup wizard says plainly which login method to pick and what to type for the cloud remote and folder; docs: Google Calendar for a second Moodle site.

## 1.4.0 (2026-10)

- **Folders are named after the study plan**, always: a subject in capitals becomes readable ("Laboratorium dyplomowe I", "Modelowanie QSAR, QSPR"), and the Moodle courses go into those folders - no more one folder per Moodle spelling. Switching moves files once (`/reorganize`).
- **`/assign` (`/przypisz`)**: every Moodle course with its folder (✓ automatic, ✋ your choice, ❓ none); tap one to put it under any subject of any semester, under a whole elective module (e.g. a course from another university), under no subject, or back to automatic.
- **`/electives`**: options are numbered and link to their subject cards - ten options called "Team research project I" are told apart by the card; choices are stored per card. New "🌐 another university" option for electives taken outside the catalogue.

## 1.3.0 (2026-10)

- **Elective subjects:** the study plan now knows which alternatives belong to which elective module. `/electives` (`/obieralne`) in the bot shows each module with a toggle per subject; what you pick gets its card and folder. An elective you already have a Moodle course for counts as chosen, and the bot reminds you once about modules without a choice.
- **Subjects without a card** in the catalogue are no longer skipped silently: `plan` marks them and you get one message listing them (again only when the list changes).
- **Old copies after moving:** `upload --cleanup` (and `/cleanup` in the bot) finds files left behind when a move to the new folders failed - same name and size as a file moodle-sync keeps elsewhere - and deletes them, locally and in the cloud, after you confirm.
- **A second Moodle site:** `courses.json` → `only` syncs just the courses you list; docs show how to run a second copy (e.g. one inter-university course) with its own data folder and timer, into the same cloud folder.

## 1.2.2 (2026-10)

- **Attendance without the private token** (some universities never hand it out, and their key can't be reset): a QR link or photo gets an "✋ Open attendance" button - one tap, you're logged in as usual and the QR password is already in the link; `/attendance` lists the attendance activities of your courses as such buttons. This works without `MOODLE_ACTIONS` too.

## 1.2.1 (2026-10)

- Study plans written in CAPITALS no longer give SHOUTING folders: a subject with a Moodle course keeps the course's name, the others get normal capitalisation ("Otwarte bazy danych").

## 1.2.0 (2026-10)

- **Moodle in Telegram.** `/courses` (`/kursy`): a course → its sections → what's in them, every item with the most useful link - your Drive copy of a file (opens only for you), the link a teacher shared, links inside labels, or the activity in Moodle. `/today` (`/dzis`): what appeared in all your courses today, or `/today 1`, `/today 12.10`, with ◀ ▶ between days.
- **Submitting assignments** (with `MOODLE_ACTIONS=1`): send the bot a file, pick the assignment, the bot checks the allowed types, size and whether you can still change the submission, renames the file after the assignment (`SUBMISSION_NAME`, default `{assignment} {course} {student_id}`), shows a summary and uploads only after ✅. "Submit for grading" is a separate tap.
- **Forum posts** (`/forum`): course → forum → subject → message → preview → ✅.
- **Attendance** (`/attendance`, `/obecnosc`, or send the QR link / a photo of the QR code): the bot opens the attendance page logged in as you (autologin, like the Moodle app), shows the statuses your teacher allows (Present first) and submits the one you pick after ✅; a session password is asked for and deleted from the chat. Needs `MOODLE_PRIVATE_TOKEN`, now saved by `python -m moodle_sync token`.
- All new commands are in the Telegram menu. Read-only stays the default: without `MOODLE_ACTIONS=1` the bot never changes anything in Moodle.

## 1.1.1 (2026-10)

- **No university is hard-wired any more.** The ECTS catalogue address is a setting (`STUDY_CATALOG`, or taken from `STUDY_PLAN_URL`); `plan --search "name" --catalog <address>`; the setup wizard asks for it.
- Documentation and examples no longer name a particular university; PRIVACY lists the requests to the catalogue.
- Polish changelog: [CHANGELOG.pl.md](CHANGELOG.pl.md).

## 1.1.0 (2026-10)

- **Semester folders and subject cards.** Set `STUDY_PLAN_URL` to your field of study in the ECTS catalogue and files go into `Semester N/<subject>/…`, with course folders named after the subjects of the plan. Each subject's card (syllabus PDF) is downloaded next to its materials, re-checked every 30 days and notified when it changes. Compulsory subjects get their card before they appear in Moodle; electives only when you have the course.
- Without a catalogue, `STUDY_START=2025/2026-winter` numbers the semesters from the course start dates.
- `python -m moodle_sync plan` previews semesters, subjects and the Moodle course feeding each folder; `plan --search "name"` finds your field of study and its specialisations; `plan --cards` downloads the cards now. The setup wizard has an optional step for it.
- courses.json: `plan` (which subject a course is) and `semester` (force a semester).
- Telegram bot: `/plan` (semesters and subjects) and `/reorganize` (confirm the one-time move of downloaded files without logging in to the Raspberry Pi).
- Switching the layout on moves already downloaded files locally and in the cloud, after a one-time `download --reorganize` (or `/reorganize` in the bot). If the catalogue is offline, the last saved plan is used; with no saved plan nothing is moved.

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
