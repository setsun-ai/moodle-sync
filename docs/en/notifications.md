# Notifications

🇵🇱 [Wersja polska](../pl/notifications.md) · [← README](../../README.md)

All channels are optional and can be combined. The wizard (`python -m moodle_sync setup`) sets them up and sends a test message; `python -m moodle_sync notify-test` sends another one any time.

## What you get

| | When | Mute with |
|---|---|---|
| 📚 New course materials | new or replaced files were downloaded, grouped by course. In Telegram with **⬇️ Download** buttons | `NOTIFY_FILES=0` |
| 📅 New / changed deadlines | a teacher added or **moved** a deadline (needs [Google Calendar](google-calendar.md)) | `NOTIFY_DEADLINES=0` |
| 📢 Announcement | a new post in a course's *Announcements* forum: full text + link | `NOTIFY_ANNOUNCEMENTS=0` |
| 🎓 Grade | a new or changed grade for an assignment or quiz, with the teacher's feedback | `NOTIFY_GRADES=0` |
| 🚨 Error | something broke. Tells you what to do (e.g. "renew the token"). The same error at most every 6 h | `NOTIFY_ERRORS=0` |
| ✅ Weekly summary | Sunday evening: what came in this week + deadlines for the next 7 days | `NOTIFY_SUMMARY=0` |

The first run only *remembers* existing announcements and grades, so you won't get 50 notifications about old things.

## Which channel?

| | Telegram | Discord | ntfy | E-mail |
|---|---|---|---|---|
| Setup time | 3 min | 2 min | 1 min | 5 min |
| Commands (`/deadlines`, `/sync`...) | ✅ | – | – | – |
| Account needed | Telegram | Discord | none | e-mail with SMTP |

## Telegram (recommended)

1. In Telegram open **@BotFather** (blue check mark) and send `/newbot`.
2. Pick a name (e.g. *My Moodle*) and a username ending in `bot`.
3. Copy the **token** (`123456789:AAH...`). The wizard asks for it; or put it in `.env` as `TELEGRAM_BOT_TOKEN=...`.
4. Connect the bot to your chat:
   ```
   python -m moodle_sync bot --setup
   ```
   Send any message to your bot. The script saves your `TELEGRAM_CHAT_ID` and the bot replies "Connected!".

**Commands.** Both languages work, and the menu under **/** follows `LANGUAGE`:

| | |
|---|---|
| `/deadlines` `/terminy` | upcoming deadlines (14 days) straight from Moodle, ✅ = already submitted |
| `/new` `/nowe` | recently downloaded materials |
| `/grades` `/oceny` | latest grades |
| `/status` | last run, result of each step, free disk space, uptime |
| `/courses` `/kursy` | a course → its sections → materials, with links to your Drive copy, shared links and Moodle |
| `/today` `/dzis` | what appeared in your courses today; `/today 1` = yesterday, `/today 12.10` = that day |
| `/submit` `/oddaj`, or just send a file | submit it to an assignment (needs `MOODLE_ACTIONS=1`, see [Configuration](configuration.md)) |
| `/forum` | start a discussion in a course forum (`MOODLE_ACTIONS=1`) |
| `/attendance` `/obecnosc`, or send a link / QR photo | mark attendance (`MOODLE_ACTIONS=1`) |
| `/electives` `/obieralne` | pick your elective subjects (study plan) |
| `/assign` `/przypisz` | put a Moodle course under a subject or module of the plan, rename its folder, add a semester |
| `/card` `/karta` | your own link to the card of a subject outside the catalogue |
| `/errors` `/bledy` | the last sync step by step, with the full output of failed steps |
| `/cleanup` `/porzadki` | find and delete old copies left next to moved files (after confirmation) |
| `/sync` | sync now: everything, or pick one course |
| `/update` | install the newest release from GitHub and restart the bot (copies unpacked from a release archive; in a git clone use `git pull`) |
| `/rollback` | go back to the version before the last `/update` |
| `/plan` | semesters and subjects of your study plan (see [Configuration](configuration.md)) |
| `/reorganize` | confirm moving downloaded files into a new layout, e.g. semester folders |
| `/help` `/pomoc` | list of commands |

- Commands need the bot process running: `python -m moodle_sync bot`. On a Raspberry Pi it runs as a service automatically ([guide](raspberry-pi.md)).
- Notifications work **without** the bot process.
- **⬇️ Download** under *New course materials*: the bot sends you the file itself, from `DOWNLOAD_DIR` or, with `KEEP_LOCAL=0`, fetched from the cloud. One button per file (the first 6) and *Download all*. Telegram lets a bot send at most 50 MB; for a bigger file you get a link to your Drive copy. Without the bot process, set `TELEGRAM_FILE_BUTTONS=0`.
- The bot answers **only your chat** and ignores everyone else.

## Discord

Notifications go through a **webhook**, a URL that posts into one channel. No bot hosting is needed.

1. Create a server just for yourself (**+** in Discord → *Create My Own*), or use a channel you own.
2. **Channel settings → Integrations → Webhooks → New Webhook → Copy Webhook URL.**
3. Give it to the wizard, or set `DISCORD_WEBHOOK_URL=...`.

Messages never ping anyone. `@everyone` in a forum post is shown as plain text.

> Why no Discord commands? They'd need a permanently connected bot using a larger library. Telegram covers that; a Discord bot is a nice [contribution idea](../../CONTRIBUTING.md).

## ntfy

A free push service without an account: <https://ntfy.sh>.

1. Install the **ntfy** app (Android / iOS).
2. Tap **+ → Subscribe to topic** and enter a long random name, e.g. `moodle-7f3k9x2qa81`. The wizard suggests one.
3. Set `NTFY_TOPIC=moodle-7f3k9x2qa81`.

The topic name works like a password: anyone who knows it can read your messages. Keep it random. You can also self-host ntfy (`NTFY_SERVER`).

## E-mail

```
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=you@example.com
SMTP_PASSWORD=abcd efgh ijkl mnop
EMAIL_TO=you@example.com
```

- **Gmail** needs an **app password**, not your normal one. You get it at *Google Account → Security → 2-Step Verification → App passwords*, which requires 2-Step Verification to be on.
- **Outlook/Microsoft accounts** mostly don't allow simple SMTP passwords anymore. Use Gmail or another channel.
- Port 465 = SSL, anything else = STARTTLS.

## Dead-man alarm (healthchecks.io)

If the computer or Raspberry Pi running the sync dies, it can't tell you. [healthchecks.io](https://healthchecks.io) (free) works the other way round: every run says "I'm alive", and when that stops, **the service** alerts you, also on Telegram or Discord.

1. Create an account and click **Add Check**.
2. Schedule:
   - **Period:** your sync interval (e.g. 15 min),
   - **Grace:** 1 hour, to tolerate short Wi-Fi drops.
3. Copy the **Ping URL** into `.env`: `HEALTHCHECK_URL=https://hc-ping.com/<uuid>`.
4. **Integrations:** add Telegram, Discord or e-mail.

Failed runs are reported too (`/fail`), with the summary of every run visible on the website.

For a laptop that's often off, a dead-man alarm makes little sense. The weekly summary is enough there.
