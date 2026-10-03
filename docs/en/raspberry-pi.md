# Raspberry Pi / home server (24/7)

🇵🇱 [Wersja polska](../pl/raspberry-pi.md) · [← README](../../README.md)

Any Raspberry Pi works, even the smallest **Pi 3 A+ (512 MB RAM)**. moodle-sync uses about 60-100 MB of RAM for a few seconds every 15 minutes. The same steps work on any Debian/Ubuntu machine (old laptop, NAS with Docker/VM, VPS).

**You need:**
- a Raspberry Pi,
- a microSD card (8 GB+, a known brand, class A1),
- a **proper power supply** (Pi 3: 5 V / 2.5 A). A weak one is the #1 cause of weird problems.

## 1. Prepare the SD card (on your computer)

1. Install **Raspberry Pi Imager**: <https://www.raspberrypi.com/software/>.
2. **Device:** your Pi.
3. **OS:** *Raspberry Pi OS (other)* → **Raspberry Pi OS Lite** (no desktop). Choose 32-bit for 512 MB models; 64-bit is fine otherwise.
4. **Storage:** the card.
5. In **Edit settings**:
   - hostname: `moodlesync`,
   - username and password,
   - **Wi-Fi** (name, password, country),
   - time zone,
   - **Services → Enable SSH**.
6. Write the card, insert it and power the Pi on. The first boot takes 2-5 minutes.

## 2. Connect and update

From your computer:

```bash
ssh <user>@moodlesync.local
```

If `.local` doesn't resolve, find the Pi's IP in your router's device list. Then, on the Pi:

```bash
sudo apt update && sudo apt full-upgrade -y
sudo apt install -y git python3-venv
curl https://rclone.org/install.sh | sudo bash     # only if you use rclone
```

The rclone from `apt` is very old; the official script installs the current version.

## 3. Get the project onto the Pi

You have two options.

**A) Fresh setup on the Pi:**

```bash
git clone https://github.com/setsun-ai/moodle-sync.git ~/moodle-sync
cd ~/moodle-sync
bash install.sh              # creates .venv and runs the setup wizard
```

For SSO logins, the wizard's browser step can be done on any computer: open the printed link there, then paste the `moodlemobile://` result into the SSH session.

**B) Move a working setup from your computer** (e.g. after the first big download on a fast connection):

```bash
# on the Pi:
git clone https://github.com/setsun-ai/moodle-sync.git ~/moodle-sync
# on your computer (Windows PowerShell or macOS/Linux terminal), in the project folder:
scp .env state.json google_token.json <user>@moodlesync.local:~/moodle-sync/
scp courses.json <user>@moodlesync.local:~/moodle-sync/          # if you have it
ssh <user>@moodlesync.local "mkdir -p ~/.config/rclone"
scp "$env:APPDATA\rclone\rclone.conf" <user>@moodlesync.local:~/.config/rclone/   # Windows, if you use rclone
# macOS/Linux: scp ~/.config/rclone/rclone.conf <user>@moodlesync.local:~/.config/rclone/
```

- Don't copy `downloads/`: thanks to `state.json`, the Pi knows what is already in the cloud and only fetches new files.
- Then **turn off the sync on your computer** (see [Running → Moving](running.md#moving-to-another-machine)).

## 4. Install the timer (and the Telegram bot)

```bash
cd ~/moodle-sync
bash deploy/linux/install-server.sh
```

The script:
- installs **automatic security updates** (`unattended-upgrades`),
- creates `.venv`,
- runs `doctor`,
- installs a systemd timer that runs the sync **3 min after boot and then 15 min after each run finishes**, so runs never overlap and it survives reboots and power cuts,
- starts the **Telegram bot** service, if Telegram is configured.

Test it right away:

```bash
sudo systemctl start moodle-sync
journalctl -u moodle-sync -n 40 --no-pager
```

## Day-to-day

With Telegram you rarely need SSH: `/status` shows the last run, free disk space and uptime, and `/sync` runs a sync now.

| What | Command |
|---|---|
| Last/next run | `systemctl list-timers moodle-sync.timer` |
| Logs today | `journalctl -u moodle-sync --since today` |
| Live logs | `journalctl -u moodle-sync -f` |
| Run now | `sudo systemctl start moodle-sync` |
| Pause / resume | `sudo systemctl stop moodle-sync.timer` / `start` |
| Bot logs | `journalctl -u moodle-sync-bot -n 50` |
| After editing `.env` | `sudo systemctl restart moodle-sync-bot` (the sync reloads `.env` every run by itself) |
| Free space | `df -h /` |
| Change interval | edit `OnUnitInactiveSec=` in `deploy/linux/moodle-sync.timer`, then re-run `install-server.sh` |

**Changing a setting:** `.venv/bin/python -m moodle_sync set LANGUAGE pl`, then `sudo systemctl restart moodle-sync-bot`. Don't append to `.env` with `echo >>`: if the file doesn't end with a newline, the new line gets glued to the last one.

**Updating moodle-sync:**

```bash
cd ~/moodle-sync && git pull && bash deploy/linux/install-server.sh
```

A copy unpacked from a release archive (not a git clone) can also be updated from Telegram: `/update` (and `/rollback`).

**Disk space:** a semester is usually well under 1 GB, so a 32 GB card lasts for years. Local copies are a free backup of your cloud. To delete them after upload anyway, set `KEEP_LOCAL=0`.

## Robustness

- **Wi-Fi drops:** requests are retried, downloads resume on the next run, and nothing is half-written.
- **Wi-Fi keeps disconnecting:** turn off Wi-Fi power saving, then reboot:
  ```bash
  sudo nmcli connection modify preconfigured wifi.powersave 2
  ```
  (`nmcli connection show` lists the connection names.)
- **Know when it dies:** set up [healthchecks.io](notifications.md#dead-man-alarm-healthchecksio). If the Pi stops reporting, *it* notifies you.

## SD card died

1. Set up a new card (steps 1-4).
2. Before `install-server.sh`, restore the state from the cloud backup, which is made on every run (if you use rclone):
   ```bash
   cd ~/moodle-sync
   rclone copyto <remote>:_moodle_sync/state.json state.json
   rclone copyto <remote>:_moodle_sync/courses.json courses.json   # if you had one
   ```
   The backup lives next to `DRIVE_DEST`, e.g. `gdrive:_moodle_sync/`.

Secrets (`.env`, `google_token.json`, `rclone.conf`) are **deliberately not** in the cloud backup. **Keep a copy of them on your computer.** Without `state.json` nothing breaks: the Pi re-downloads everything (nothing is duplicated in the cloud or the calendar) and sends one big "new files" notification.
