# Configuration reference

🇵🇱 [Wersja polska](../pl/configuration.md) · [← README](../../README.md)

Everything lives in two files in the project folder (or in `MOODLE_SYNC_DATA_DIR`, if set):

| File | Content |
|---|---|
| `.env` | Settings and **secrets**. Created by the wizard. Template: `.env.example`. |
| `courses.json` | Optional per-course names, categories and skips. Template: `courses.example.json`. |

Changes take effect on the next run. The Telegram bot reads `.env` only at start, so restart it after editing.

## `.env`

### Required

| Variable | Example |
|---|---|
| `MOODLE_BASE_URL` | `https://moodle.example.edu`: the address of your Moodle (the wizard normalises it). |
| `MOODLE_TOKEN` | Your token, see [Token](token.md). |

### General

| Variable | Default | Meaning |
|---|---|---|
| `LANGUAGE` | `en` | `en` / `pl`: messages, notifications, bot, folder names. |
| `SITE_LABEL` | `Moodle` | Short school name used in calendar names, e.g. `UNI`. |
| `MOODLE_LANG` | = `LANGUAGE` | Which variant to keep from multi-language names (`{mlang pl}…{mlang en}…`). |
| `TIMEZONE` | `Europe/Warsaw` (pl) / `UTC` | IANA time zone for created calendars. |

### Files

| Variable | Default | Meaning |
|---|---|---|
| `DOWNLOAD_DIR` | `downloads` | Relative to the project or absolute, e.g. inside your OneDrive folder. |
| `MAX_FILE_MB` | `0` | Skip files bigger than N MB (0 = no limit). Skipped files are fetched automatically once you raise the limit. |

### Semesters and subject cards

Files can go into one folder per semester, with the course folders named after the subjects of your study plan
and each subject's card (syllabus) next to its materials:

```
Semester 1/
  Mathematics II/
    Subject card.pdf
    Lectures/...
Semester 2/...
```

| Variable | Default | Meaning |
|---|---|---|
| `STUDY_CATALOG` | – | Address of your university's ECTS catalogue, e.g. `https://ects.example.edu`. Only needed for `plan --search`. |
| `STUDY_PLAN_URL` | – | Your field of study (or specialisation) in the ECTS catalogue. Find it with `python -m moodle_sync plan --search "name" --catalog <address>`. The catalogue must show the plan by semesters ("Semestr 1 (2025/2026 - zimowy)") with a PDF card per subject. |
| `STUDY_START` | – | Without a catalogue: your first semester, e.g. `2025/2026-winter`. Semester numbers are counted from the course start dates. |
| `SEMESTER_FOLDERS` | on with one of the above | `0` = keep the old layout, only rename the course folders after the plan. |
| `SYLLABUS` | on with `STUDY_PLAN_URL` | `0` = don't download subject cards. Cards are re-checked every 30 days; a changed card is notified. |

- `python -m moodle_sync plan` shows the semesters, the subjects and which Moodle course feeds which folder.
- A Moodle course gets the subject whose words all appear in its name (the most specific one: "Mathematics II"
  beats "Mathematics"). Courses without a subject get their semester from their start date.
- Compulsory subjects get their card even before they appear in Moodle; elective ones only when you have the course.
- **Switching it on moves your existing files.** To be safe, the first run stops and asks you to confirm once:
  `python -m moodle_sync download --reorganize`. The cloud copy is moved too.
- If the catalogue is offline, the plan saved on the last successful check is used.
- **Own folder names, cards, several semesters:** in `/assign` a course can get its own folder name (✏️), a second semester (➕ - one Moodle course for "Project I" and "Project II", files split by their dates); `/card` adds your own link to the card of a subject the catalogue has none for (e.g. from another university).
- **Folder names come from the plan** (written readably when the catalogue uses capitals); Moodle courses are put into them. When the automatic match is wrong or missing, `/assign` in the bot puts a course under any subject - or a whole elective module, e.g. for a course taken at another university.
- **Elective modules:** pick what you chose with `/electives` in the Telegram bot. Options are numbered and link to their subject cards, because several can share a name; "another university" covers electives from outside the catalogue. An elective you have a Moodle course for counts as chosen; the bot reminds you of modules without a choice.
- Subjects whose card isn't published in the catalogue are listed in `plan` and notified once.

### Telegram bot: submitting, forums, attendance

| Variable | Default | Meaning |
|---|---|---|
| `MOODLE_ACTIONS` | `0` | `1` = the bot may submit assignments, post to forums and mark attendance - each only after your ✅. |
| `STUDENT_ID` | – | Your student number, used in submitted file names. |
| `SUBMISSION_NAME` | `{assignment} {course} {student_id}` | File name template for submissions; also `{original}`. Example: *Report LCMS 123456.pdf*. |
| `MOODLE_PRIVATE_TOKEN` | – | Saved by `python -m moodle_sync token`; needed only for attendance (no web service exists for it, so the bot opens the page like the Moodle app does). Treat it like a password. |

- QR codes: send the bot the link (scan the code with your phone's camera and share it), or a photo of the code if
  `zbarimg` is installed (`sudo apt install zbar-tools`).
- No private token (some universities don't issue it - the reset button in *Security keys* is missing): attendance links, QR photos and `/attendance` give an "✋ Open attendance" button instead, which opens the page on your phone.
- Telegram lets bots download files up to 20 MB.

### A second Moodle site (e.g. one inter-university course)

One copy of the code can serve a second site with its own data folder (`MOODLE_SYNC_DATA_DIR`): its own `.env`,
token and `courses.json`, the files going into the same cloud folder.

```bash
mkdir -p ~/moodle-sync-2
cd ~/moodle-sync && MOODLE_SYNC_DATA_DIR=$HOME/moodle-sync-2 .venv/bin/python -m moodle_sync setup
```

In the wizard give the second site's address; skip the Telegram bot (the first copy's bot is enough -
notifications from both arrive in the same chat). Then, in the same terminal:

```bash
export MOODLE_SYNC_DATA_DIR=$HOME/moodle-sync-2
.venv/bin/python -m moodle_sync set STATE_BACKUP_DEST _moodle_sync_2   # never share the state backup
.venv/bin/python -m moodle_sync set SYLLABUS 0                         # cards come from the first copy
echo '{"only": ["part of the course name"]}' > ~/moodle-sync-2/courses.json
```

`only` (in `courses.json`) syncs just the courses whose names contain one of the fragments. Give it the same
`STUDY_PLAN_URL` to put the course into the right semester folder. A second timer on a Raspberry Pi / server:

```bash
sudo sed "s#^Environment=\(.*\)#Environment=\1 MOODLE_SYNC_DATA_DIR=$HOME/moodle-sync-2#" /etc/systemd/system/moodle-sync.service | sudo tee /etc/systemd/system/moodle-sync-2.service
sudo cp /etc/systemd/system/moodle-sync.timer /etc/systemd/system/moodle-sync-2.timer
sudo systemctl daemon-reload && sudo systemctl enable --now moodle-sync-2.timer
```

Google Calendar for the second site: copy the first copy's Google login (`google_token.json` - `client_secret.json`
is needed only for the first login and may not be on this machine), and give the site its own label -
its calendars are then "UG – deadlines" and "UG – classes", next to the first site's:

```bash
cp ~/moodle-sync/google_token.json ~/moodle-sync-2/
MOODLE_SYNC_DATA_DIR=$HOME/moodle-sync-2 .venv/bin/python -m moodle_sync set SITE_LABEL UG
```

### Cloud (rclone): see [Storage](storage.md)

| Variable | Default | Meaning |
|---|---|---|
| `RCLONE_REMOTE` | (empty) | rclone remote name. Empty = no upload. |
| `DRIVE_DEST` | `Moodle` | Target folder in the cloud. |
| `KEEP_LOCAL` | `1` | `0` = delete local copies after upload. |
| `RCLONE_BIN` | `rclone` | Path to rclone if it isn't on PATH. |
| `STATE_BACKUP_DEST` | `_moodle_sync` next to `DRIVE_DEST` | Where the `state.json` backup goes. |

### Calendar: see [Google Calendar](google-calendar.md)

| Variable | Default | Meaning |
|---|---|---|
| `SYNC_CLASSES` | `1` | `0` = don't put attendance sessions (the timetable) into the calendar. |

### Notifications: see [Notifications](notifications.md)

| Variable | Meaning |
|---|---|
| `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` | Telegram (the chat id is set by `bot --setup`). |
| `DISCORD_WEBHOOK_URL` | Discord channel webhook. |
| `NTFY_TOPIC`, `NTFY_SERVER` | ntfy push. |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `EMAIL_TO`, `EMAIL_FROM` | E-mail. |
| `NOTIFY_FILES`, `NOTIFY_DEADLINES`, `NOTIFY_ANNOUNCEMENTS`, `NOTIFY_GRADES`, `NOTIFY_ERRORS`, `NOTIFY_SUMMARY` | `0` mutes that kind. |
| `WATCH_ALL_FORUMS` | `1` = all forums, not just announcements. Includes student discussions, so it can be noisy. |
| `HEALTHCHECK_URL` | Dead-man alarm (healthchecks.io ping URL). |

## `courses.json`

See how your courses look now, and what a change would do:

```
python -m moodle_sync courses
```

```json
{
  "names": {
    "Introduction to Programming 2025/2026 (group 3)": "Programming"
  },
  "default_category": {
    "Foreign language course": "exercises"
  },
  "skip": ["Library training", "Sandbox"],
  "category_rules": [
    { "folder": "Seminars", "pattern": "seminar" },
    { "folder": "Exams", "pattern": "egzamin|exam|kolokw" }
  ]
}
```

- **Keys** in `names`, `default_category` and `skip` are *fragments* of the course name as it appears in Moodle (case-insensitive).
- **`names`:** the folder name, also used in calendar event titles and notifications.
- **`default_category`:** the category for files that no rule recognised. Use a built-in key (`lectures`, `exercises`, `labs`, `projects`, `other`) or any folder name.
- **`skip`:** ignore these courses completely (files, calendar, announcements, grades).
- **`plan`:** which subject of the study plan a course is, when its Moodle name doesn't say it (`"Maths for engineers": "Mathematics II"`).
- **`only`:** sync only the courses whose names contain one of these fragments (e.g. a second Moodle site, see below).
- **`semester`:** force the semester of a course (`"Sandbox": 1`).
- **`category_rules`:** your own rules, checked **before** the built-in ones. `pattern` is a [regular expression](https://regex101.com) matched against text **without diacritics, in lower case** (write `wyklad`, not `Wykład`).

The legacy file name `przedmioty.json` with the keys `nazwy` / `kategoria_domyslna` still works.

## Categories

For each file, moodle-sync looks at three names, **in this order**, and the first match wins:
1. the **section** name, because teachers usually organise sections by class type,
2. the **module** name, e.g. "Lecture 3 slides",
3. the **folder path and file name**.

Built-in rules, checked in this order:

| Folder (en / pl) | Matches (Polish and English words) |
|---|---|
| Labs / Laboratoria | `lab…` (not *syllabus*) |
| Projects / Projekty | `projekt`, `project` |
| Lectures / Wyklady | `wyklad`, `lecture`, `slajd`, `slides` |
| Exercises / Cwiczenia | `cwicz`, `exercise`, `tutorial`, `seminar`, `class` |
| Other materials / Inne materialy | everything else, or `default_category` |

Change anything and the next run **moves** existing files, locally and in the cloud.

## Intervals (in the code)

| Where | What |
|---|---|
| `deploy/*` | How often the whole sync runs (default 15-30 min). |
| `moodle_sync/watch.py` | `FORUM_INTERVAL` (30 min), `GRADES_INTERVAL` (1 h), `GRADED_RECHECK` (24 h). |
| `moodle_sync/runner.py` | `WEEKLY_DAY` / `WEEKLY_HOUR` of the weekly summary, `ALERT_REPEAT_HOURS`. |
| `moodle_sync/calendar_sync.py` | `REMINDERS`, `PAST_DAYS`, `FUTURE_DAYS`. |
