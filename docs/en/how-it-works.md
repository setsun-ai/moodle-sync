# How it works (for curious students)

🇵🇱 [Wersja polska](../pl/how-it-works.md) · [← README](../../README.md)

moodle-sync is small (~2000 lines), but it's built like "real" software. This page explains the decisions behind it. Each of them solves a problem you'll meet in your own projects.

## Architecture

```
                     ┌──────────── python -m moodle_sync run  (runner.py) ────────────┐
Moodle REST API ───► │ 1. files.py      new files        -> DOWNLOAD_DIR               │
(moodle.py)          │ 2. storage.py    DOWNLOAD_DIR     -> cloud (rclone)             │
                     │ 3. calendar_sync deadlines        -> Google Calendar            │
                     │ 4. watch.py      announcements/grades -> notifications          │
                     └──────────────┬──────────────────────────────────────┬──────────┘
                                    │ state.json (memory between runs)     │ notify.py
                                    ▼                                      ▼
                             state.py (atomic writes)         Telegram / Discord / ntfy / e-mail
```

| File | Role |
|---|---|
| `__main__.py` | Command line (argparse sub-commands). |
| `config.py` | Settings from `.env`, read at call time so the wizard can change them live. |
| `moodle.py` | API client: retries, errors, getting a token. |
| `files.py` | Scanning, categorising, downloading, moving files. |
| `storage.py` | Uploading with rclone. |
| `calendar_sync.py` | Google Calendar. |
| `watch.py` | Announcements and grades. |
| `courseprefs.py` | Per-course settings: what each course may push or put into the calendar. Written by the bot, only read by the steps. |
| `notify.py` | Notification channels. |
| `telegram_bot.py` | Bot commands. |
| `runner.py` | Runs all steps, handles errors, weekly summary. |
| `setup_wizard.py`, `doctor.py` | Setup wizard and diagnostics. |
| `i18n.py` | All user-facing text, in PL and EN. |
| `textutil.py` | Pure text functions: multi-language names, HTML to text, safe file names. |

## Ideas worth stealing

**1. Idempotency: running twice = running once.**
- Every step checks what's already done (`state.json`) and only does the rest.
- Calendar events get a **fixed id** derived from the Moodle id, so re-sending one updates it instead of creating a duplicate.
- rclone compares size + modification time.

That's why deleting `state.json`, a crash halfway through, or a double click are all harmless.

**2. Stable identity vs. logical identity.**
- A file's *id* is its URL, which contains a revision number. A new version = a new id = "download again".
- Its *logical key* (course + module + name) stays the same, so the new version **replaces** the old one at the same path instead of creating `file (2).pdf`.
- Two different things with the same name get `(2)`. [`files.plan_paths`](../../moodle_sync/files.py)

**3. Never leave half-written files.**
- Downloads go to `name.part` and are renamed with `os.replace` only when complete. On every OS, `os.replace` is *atomic*: another program sees either the old file or the new one, never half of it.
- `state.json` is written the same way. A power cut mid-write can't corrupt it.

**4. Plan, then diff.**
The target path of *every* file is computed from scratch on each run. Changing the category rules just produces a different plan. The difference between the plan and `state.json` becomes a list of moves: locally with `os.replace`, in the cloud with `rclone moveto`.

**5. Expect the network to fail.**
- Requests are retried with growing pauses (2 s, 5 s, 15 s), but only for *temporary* problems (connection reset, timeout, HTTP 5xx). A Moodle error like "invalid token" isn't retried, because retrying can't fix it.
- The steps are independent: one failing doesn't stop the others.

**6. Don't be annoying.**
- **Baseline:** the first check only remembers existing posts and grades. The same applies to every forum that starts being watched later: [that exact bug happened](../../tests/test_moodle_calendar_watch.py) and a regression test now guards it.
- **Throttling:** the same error is notified at most every 6 h. The "same" error is recognised by a fingerprint of the message with digits removed.
- **Politeness to the server:** forums are checked every 30 min, grades every hour. The User-Agent names the project, so admins know who's calling.

**7. Secrets never leak.**
- Tokens live only in `.env`, which is git-ignored.
- `requests` puts full URLs (with the token!) into error messages, so every error is passed through `redact()` before it's printed or sent.
- Tests remove all secrets from the environment, so they can't accidentally message you.

**8. Copy, don't sync.**
`rclone sync` would make the cloud a mirror of the local folder: deleting local files would delete them in the cloud. `copy` can only add. Choose the operation whose worst case you can live with.

**9. One run at a time.**
A lock file (`msvcrt.locking` on Windows, `fcntl.flock` elsewhere) stops a manual run from overlapping a scheduled one. The OS releases the lock automatically if the process dies.

**10. Every text is translatable.**
User-facing strings go through `t("key")`. A test checks that every key used in the code exists in both languages with the same `{placeholders}`.

## Tests

```
pip install -r requirements-dev.txt
python -m pytest
python -m ruff check .
```

- Tests cover the pure logic: names, categories, paths, collisions, decoding, notification formatting, throttling, translations.
- They need no network and no account.
- `tests/conftest.py` gives every test its own temporary folder and an empty environment.
- GitHub Actions runs them on Windows, macOS and Linux for every push ([`.github/workflows/ci.yml`](../../.github/workflows/ci.yml)).

## Ideas for your first contribution

See [CONTRIBUTING.md](../../CONTRIBUTING.md). A few examples:
- a Discord bot with commands,
- Matrix notifications,
- exporting deadlines to an `.ics` file,
- a Docker image,
- a German translation (add `"de"` to `i18n.py`).
