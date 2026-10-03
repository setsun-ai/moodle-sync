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
