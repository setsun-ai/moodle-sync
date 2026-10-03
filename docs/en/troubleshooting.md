# Troubleshooting & FAQ

🇵🇱 [Wersja polska](../pl/troubleshooting.md) · [← README](../../README.md)

**Always start with** `python -m moodle_sync doctor`. It checks everything and says what to fix.

## Errors

**`invalidtoken` / "The Moodle token expired or was revoked"**
Get a new one with `python -m moodle_sync token`. On a Raspberry Pi, also restart the bot: `sudo systemctl restart moodle-sync-bot`. See [Token](token.md#when-the-token-stops-working).

**`nopermissiontoviewgrades` in the logs**
That's normal. Many schools hide the gradebook from students. Grades are read from assignments and quizzes instead, so final grades entered only in the gradebook or the student system won't show up.

**"doesn't respond like Moodle with the mobile app enabled"**
- Check the address in a browser.
- Some sites run a separate Moodle per academic year, see [Token](token.md#one-moodle-per-academic-year).
- If it's right, the site has mobile access turned off.

**`invalid_grant` (Google)**
Your Google login expired. Usually the Google Cloud app is still in *Testing* status: [publish it](google-calendar.md#1-google-cloud-project-once-10-min). Then log in again:
- calendar: `python -m moodle_sync calendar --auth`
- Drive: `rclone config reconnect gdrive:`

**Two folders with the same name on Google Drive**
You created the folder by hand, and rclone with `drive.file` can't see it ([why](storage.md#google-drive)). Move the contents over and delete the empty folder.

**Telegram bot doesn't answer**
- Is it running? `journalctl -u moodle-sync-bot -n 30`, or run `python -m moodle_sync bot` yourself.
- `409 Conflict` means the bot also runs on another machine. Stop one of them.
- Notifications work without the bot. Only commands need it.

**Windows: nothing happens in the background**
- Open *Task Scheduler → moodle-sync → History*.
- Look into `logs\sync.log`.
- Did you move the project folder? Run `deploy\windows\schedule.bat` again.

**macOS: `Operation not permitted`**
The project or `DOWNLOAD_DIR` is in Documents, Desktop or Downloads. See [Running → macOS](running.md#macos).

**Raspberry Pi keeps losing Wi-Fi**
Turn off Wi-Fi power saving, see [Raspberry Pi → Robustness](raspberry-pi.md#robustness).

**"WARNING: the current settings would move N already downloaded files"**
This is a safety fuse. A settings change would re-sort a large part of your archive, so nothing was moved or downloaded.
- Usually it's an accident. The classic one: a line added with `echo "LANGUAGE=pl" >> .env` got glued to the previous line, because the file didn't end with a newline. `LANGUAGE` silently fell back to English, and every folder would be renamed.
- Run `python -m moodle_sync doctor`. It points to broken `.env` lines. Fix them with `python -m moodle_sync set KEY VALUE`.
- If you really changed the layout on purpose (new language, new `courses.json` rules), confirm it once with `python -m moodle_sync download --reorganize`. The next `upload` then moves the files in the cloud, without uploading them again.

**The first announcement check sends nothing**
That's by design. The first check only remembers existing posts, and so does any forum that starts being watched later. Only newer posts are notified.

## FAQ

**Is this allowed?**
moodle-sync uses the official mobile app API with **your own** account and only reads your data, like the app does, and with fewer requests. Things to keep in mind:
- Your university's IT rules usually forbid sharing your login or overloading servers. Personal automation is generally fine, but if in doubt, check the rules or ask your IT department.
- Course materials are copyrighted by their authors. Keeping them in **your private** cloud is personal use. **Don't make the folder public or share the links.**

The details are in **[Responsible use](responsible-use.md)** and **[Privacy](../../PRIVACY.md)**.

**Where is my data?**
Only on your computer and in the cloud **you** chose. No servers of this project exist. Notifications go through the service you picked (e.g. Telegram).

**Can I force a full resync?**
Stop the scheduler and move `state.json` away. Everything is downloaded again. Nothing is duplicated in the cloud (rclone compares size and date) or in the calendar (events have fixed ids).

**I only want new files, not the whole archive.**
Run `python -m moodle_sync download --baseline` once. It marks everything that exists now as done.

**Does it work with my university?**
It works if your Moodle has the mobile app enabled (almost always). It was developed on Moodle 5.1 and uses only standard API functions available since Moodle 3.9.

**Can it submit assignments / post for me?**
No. By design it's read-only.
