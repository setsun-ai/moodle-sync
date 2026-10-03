# moodle-sync

[![CI](https://github.com/setsun-ai/moodle-sync/actions/workflows/ci.yml/badge.svg)](https://github.com/setsun-ai/moodle-sync/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/setsun-ai/moodle-sync)](https://github.com/setsun-ai/moodle-sync/releases/latest)
![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

🇵🇱 **[Polska wersja →](README.pl.md)**

**Never miss course materials, deadlines or announcements from Moodle again.**
moodle-sync downloads your course files into tidy folders in the cloud, puts deadlines into your calendar and notifies you on your phone about what's new. It works with any Moodle, on Windows, macOS, Linux or a Raspberry Pi.

> ⚖️ **For personal use only.** Course materials are copyrighted by their authors, and announcements can contain other
> students' data. Keep everything **private** and follow your university's rules. Please read
> **[Responsible use](docs/en/responsible-use.md)** and **[Privacy](PRIVACY.md)** before you start.

```
📚 New course materials (3)
• Algorithms: Lecture 5 - graphs.pdf
• Algorithms: lab5_instructions.pdf
• Databases: project_requirements.docx

📅 Changed deadlines (1)
• 12.11 23:59  ⏰ [Databases] Lab report 3 (due)

🎓 Grade: 90 / 100 — Lab report 2
Databases
Teacher's feedback: Good work, see comments in section 3.
```

## Features

- 📂 **Files → folders in the cloud.** Every course is sorted into *Lectures / Exercises / Labs / Projects / Other*. A teacher's replaced file gets updated in place. Works with Google Drive, OneDrive (incl. university Microsoft 365), Dropbox and [70+ more](https://rclone.org), or with no cloud at all.
- 🗂️ **Semesters and subject cards.** Point it at your field of study in the ECTS catalogue (for now: Gdańsk Tech, ects.pg.edu.pl) and courses go into *Semester 1 / Semester 2 …* folders named after the subjects, with each subject's card (syllabus) downloaded next to its materials and re-checked for changes.
- 📅 **Deadlines → Google Calendar.** Submitted assignments get ✅ and stop reminding you. Moved deadlines are updated and notified. Classes go into a separate calendar you can hide. Outlook or Apple Calendar can use a subscription link instead.
- 📢 **Announcements and 🎓 grades** from teachers go straight to your phone, including teacher feedback.
- 🔔 **Your choice of channel:** Telegram (with commands like `/deadlines`, `/sync`), Discord, ntfy or e-mail.
- 🧙 **Setup wizard:** finds out how your university logs in (password or SSO) and guides you. `doctor` checks everything.
- 🖥️ **Runs how you want:** double-click when you feel like it, automatically while your computer is on, or 24/7 on a Raspberry Pi.
- 🌍 **English and Polish:** messages, bot and documentation.
- 🔒 **Private and read-only:** your data stays on your computer and your cloud. It never submits or posts anything.

## Quick start

1. Install **Python 3.10+** ([how](docs/en/getting-started.md#1-install-python-310-or-newer)).
2. **Code → Download ZIP** on this page, unpack it.
3. Double-click **`install.bat`** on Windows, or run `bash install.sh` on macOS/Linux, and follow the wizard.

Full walk-through: **[Getting started](docs/en/getting-started.md)**.

## How to run it

| You have... | Do this |
|---|---|
| a laptop, and you sync when you want | double-click `sync.bat` / `./sync.sh` |
| a computer that's on during the day | [automatic sync every 30 min](docs/en/running.md#automatically-on-your-computer) (Windows Task Scheduler / macOS / Linux) |
| a Raspberry Pi or home server | [24/7 every 15 min + Telegram bot](docs/en/raspberry-pi.md) |

## Documentation

| | |
|---|---|
| [Getting started](docs/en/getting-started.md) | Install, setup wizard, all commands |
| [Token](docs/en/token.md) | How access to Moodle works: SSO, renewing, revoking |
| [Running](docs/en/running.md) | Manually, automatically, moving to another machine |
| [Raspberry Pi](docs/en/raspberry-pi.md) | 24/7 setup, maintenance, recovery |
| [Notifications](docs/en/notifications.md) | Telegram, Discord, ntfy, e-mail, dead-man alarm |
| [Storage](docs/en/storage.md) | Synced folder, Google Drive, OneDrive, rclone |
| [Google Calendar](docs/en/google-calendar.md) | Calendar sync or subscription link |
| [Configuration](docs/en/configuration.md) | Every option, `courses.json`, categories |
| [Troubleshooting & FAQ](docs/en/troubleshooting.md) | Errors and questions |
| [How it works](docs/en/how-it-works.md) | Architecture and design decisions, for learning |
| [Responsible use](docs/en/responsible-use.md) · [Privacy](PRIVACY.md) · [Security](SECURITY.md) | Copyright, university rules, what data goes where |

## Is this allowed? Is it safe?

- **Allowed use:** moodle-sync uses the **official Moodle mobile app API** with **your own** account, the same way the Moodle app on your phone does. It only **reads** your data, and it does so politely: a few dozen requests per run, with a user agent that names the project.
- **Materials stay private:** course materials belong to their authors. Keep them in **your private** storage and **never share the folder or links publicly**. Don't forward announcements with other people's data either. → **[Responsible use](docs/en/responsible-use.md)**
- **Your data:** it stays on your computer and in the services **you** choose. There are no project servers and no telemetry. → **[Privacy](PRIVACY.md)**
- **Your token is a password-equivalent:** it stays in `.env`, and is never logged or uploaded. → **[Security](SECURITY.md)**
- **Not affiliated** with Moodle or any university; no warranty. Always double-check important deadlines in Moodle itself.

## Contributing

Ideas, bugs and pull requests are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md). New to open source? It lists good first issues.

## License

[MIT](LICENSE). Made by a student of Gdańsk University of Technology, for students everywhere.
