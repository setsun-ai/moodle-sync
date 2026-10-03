# Where the files go

🇵🇱 [Wersja polska](../pl/storage.md) · [← README](../../README.md)

Files are always saved into `DOWNLOAD_DIR` (default: `downloads/` in the project), sorted like this:

```
<Course>/
    Lectures/
    Exercises/
    Labs/
    Projects/
    Other materials/
```

With `LANGUAGE=pl` the folders are named `Wyklady`, `Cwiczenia`, `Laboratoria`, `Projekty`, `Inne materialy`. How the category is chosen, and how to change it: [Configuration → Categories](configuration.md#categories).

To get the files into the cloud, pick one of three options:

| Option | Setup | Best for |
|---|---|---|
| **A. A synced folder** | none | a computer with Google Drive / OneDrive / Dropbox installed |
| **B. rclone** | 5-15 min | Raspberry Pi / server, or no desktop sync app |
| **C. Local only** | none | you just want the files on your disk |

## A. A synced folder (simplest)

If you have **Google Drive for desktop**, **OneDrive** or **Dropbox** installed, set `DOWNLOAD_DIR` to a folder inside it. The wizard asks for this.

```
DOWNLOAD_DIR=C:\Users\You\OneDrive\Moodle            (Windows)
DOWNLOAD_DIR=/Users/you/Library/CloudStorage/GoogleDrive-you@example.com/My Drive/Moodle   (macOS)
```

The desktop app uploads everything. Leave `RCLONE_REMOTE` empty.

> Many universities give students **Microsoft 365 with 1 TB OneDrive**. It's a great target.

## B. rclone (Raspberry Pi, servers)

[rclone](https://rclone.org) uploads to 70+ services. moodle-sync runs `rclone copy`:
- it only adds and updates files, and **never deletes anything in the cloud**;
- with `KEEP_LOCAL=0` it uses `rclone move` instead, so local copies are deleted after a successful upload.

**Install:**
- Windows: `winget install Rclone.Rclone`
- macOS: `brew install rclone`
- Linux / Raspberry Pi: `curl https://rclone.org/install.sh | sudo bash`

### Google Drive

1. *(Recommended)* Create your own OAuth client, which is faster than rclone's shared one. Follow steps 1-4 of [Google Calendar](google-calendar.md#1-google-cloud-project-once-10-min) (enable **Google Drive API**). One client works for both Drive and Calendar.
2. Create the remote:
   ```
   rclone config create gdrive drive scope=drive.file client_id=YOUR_ID client_secret=YOUR_SECRET
   ```
   A browser opens: log in and allow access. Without your own client, leave out `client_id`/`client_secret`.
3. In `.env`: `RCLONE_REMOTE=gdrive` and `DRIVE_DEST=Moodle` (the target folder).
4. Test: `python -m moodle_sync upload --check`.

> **About `scope=drive.file`:** rclone can then only see files it created itself, not your whole Drive. The catch: **don't create the target folder by hand**, because rclone won't see it and will create a second one with the same name. Let it create `DRIVE_DEST` itself. To use an existing folder, use `scope=drive` instead (full Drive access).

### OneDrive (incl. university Microsoft 365)

```
rclone config
```

In the interactive setup:
1. `n` (new remote), name `onedrive`, storage type **Microsoft OneDrive**, all defaults.
2. Log in in the browser.
3. Choose **OneDrive (business)** for a university account.

Then set `RCLONE_REMOTE=onedrive` in `.env`.

> If Microsoft says *"Need admin approval"*, your university blocks third-party apps. Use option A (the OneDrive desktop app on your computer) instead.

### Others

Dropbox, Nextcloud, pCloud, Mega, SFTP, S3...: `rclone config` walks you through them. Only `RCLONE_REMOTE` changes.

### rclone on a Raspberry Pi (no browser)

1. Configure the remote on your computer, as above.
2. Copy the config file to the Pi:
   - Windows: `%APPDATA%\rclone\rclone.conf`
   - macOS/Linux: `~/.config/rclone/rclone.conf`
   - Pi: `~/.config/rclone/rclone.conf`

The file must stay writable, because rclone saves refreshed tokens into it. Treat it like a password.

### Backup of the program's memory

After every upload, `state.json` (plus `courses.json`) is copied to `_moodle_sync/` next to `DRIVE_DEST` (`STATE_BACKUP_DEST`). After a disk failure, restore it with `rclone copyto` ([how](raspberry-pi.md#sd-card-died)). Secrets are never uploaded.

## Changing categories later

If you edit `courses.json` or the category rules, the next run **moves** already downloaded files:
- locally: immediately;
- in the cloud: with `rclone moveto`, without uploading them again.

With option A, the desktop app handles the move by itself.
