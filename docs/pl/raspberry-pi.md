# Raspberry Pi / serwer domowy (24/7)

🇬🇧 [English version](../en/raspberry-pi.md) · [← README](../../README.pl.md)

Wystarczy dowolne Raspberry Pi, nawet najmniejsze **Pi 3 A+ (512 MB RAM)**. moodle-sync zużywa ok. 60–100 MB RAM przez kilka sekund co 15 minut. Te same kroki działają na każdej maszynie z Debianem lub Ubuntu (stary laptop, NAS z Dockerem/VM, VPS).

**Potrzebujesz:**
- Raspberry Pi,
- karty microSD (8 GB+, markowej, klasy A1),
- **porządnego zasilacza** (Pi 3: 5 V / 2,5 A). Słaby zasilacz to przyczyna nr 1 dziwnych problemów.

## 1. Przygotuj kartę SD (na komputerze)

1. Zainstaluj **Raspberry Pi Imager**: <https://www.raspberrypi.com/software/>.
2. **Device:** Twoje Pi.
3. **OS:** *Raspberry Pi OS (other)* → **Raspberry Pi OS Lite** (bez pulpitu). Na modele z 512 MB wybierz 32-bit; na pozostałe 64-bit też jest OK.
4. **Storage:** karta.
5. W **Edit settings**:
   - hostname: `moodlesync`,
   - użytkownik i hasło,
   - **Wi-Fi** (nazwa, hasło, kraj: PL),
   - strefa czasowa `Europe/Warsaw`,
   - **Services → Enable SSH**.
6. Zapisz kartę, włóż ją do Pi i włącz zasilanie. Pierwszy start trwa 2–5 minut.

## 2. Połączenie i aktualizacja

Z komputera:

```bash
ssh <użytkownik>@moodlesync.local
```

Jeśli `.local` nie działa, znajdź IP Pi na liście urządzeń w routerze. Potem na Pi:

```bash
sudo apt update && sudo apt full-upgrade -y
sudo apt install -y git python3-venv
curl https://rclone.org/install.sh | sudo bash     # tylko jeśli używasz rclone
```

rclone z `apt` jest mocno nieaktualny; oficjalny skrypt instaluje bieżącą wersję.

## 3. Projekt na Pi

Masz dwie drogi.

**A) Konfiguracja od zera na Pi:**

```bash
git clone https://github.com/setsun-ai/moodle-sync.git ~/moodle-sync
cd ~/moodle-sync
bash install.sh              # tworzy .venv i uruchamia kreator
```

Przy logowaniu SSO krok z przeglądarką zrobisz na dowolnym komputerze: otwórz tam wypisany link, a wynik `moodlemobile://` wklej w sesję SSH.

**B) Przeniesienie działającej konfiguracji z komputera** (np. po pierwszym dużym pobraniu na szybkim łączu):

```bash
# na Pi:
git clone https://github.com/setsun-ai/moodle-sync.git ~/moodle-sync
# na komputerze (PowerShell na Windows albo terminal macOS/Linux), w folderze projektu:
scp .env state.json google_token.json <użytkownik>@moodlesync.local:~/moodle-sync/
scp courses.json przedmioty.json <użytkownik>@moodlesync.local:~/moodle-sync/   # te, które masz
ssh <użytkownik>@moodlesync.local "mkdir -p ~/.config/rclone"
scp "$env:APPDATA\rclone\rclone.conf" <użytkownik>@moodlesync.local:~/.config/rclone/   # Windows, jeśli używasz rclone
# macOS/Linux: scp ~/.config/rclone/rclone.conf <użytkownik>@moodlesync.local:~/.config/rclone/
```

- Nie kopiuj `downloads/`: dzięki `state.json` Pi wie, co już jest w chmurze, i pobiera tylko nowości.
- Potem **wyłącz synchronizację na komputerze** (zobacz [Uruchamianie → Przenosiny](running.md#przenosiny-na-inną-maszynę)).

## 4. Instalacja timera (i bota Telegram)

```bash
cd ~/moodle-sync
bash deploy/linux/install-server.sh
```

Skrypt:
- instaluje **automatyczne aktualizacje bezpieczeństwa** (`unattended-upgrades`),
- tworzy `.venv`,
- uruchamia `doctor`,
- instaluje timer systemd, który uruchamia synchronizację **3 min po starcie, a potem 15 min po zakończeniu każdego przebiegu**, więc przebiegi się nie nakładają, a timer przetrwa restart i zanik prądu,
- włącza usługę **bota Telegram**, jeśli Telegram jest skonfigurowany.

Test od razu:

```bash
sudo systemctl start moodle-sync
journalctl -u moodle-sync -n 40 --no-pager
```

## Na co dzień

Z Telegramem SSH jest rzadko potrzebne: `/status` pokazuje ostatni przebieg, wolne miejsce i czas działania, a `/sync` uruchamia synchronizację od ręki.

| Co | Polecenie |
|---|---|
| Ostatni/następny przebieg | `systemctl list-timers moodle-sync.timer` |
| Logi z dzisiaj | `journalctl -u moodle-sync --since today` |
| Logi na żywo | `journalctl -u moodle-sync -f` |
| Uruchom teraz | `sudo systemctl start moodle-sync` |
| Wstrzymaj / wznów | `sudo systemctl stop moodle-sync.timer` / `start` |
| Logi bota | `journalctl -u moodle-sync-bot -n 50` |
| Po zmianie `.env` | `sudo systemctl restart moodle-sync-bot` (synchronizacja sama wczytuje `.env` przy każdym przebiegu) |
| Wolne miejsce | `df -h /` |
| Zmiana częstotliwości | zmień `OnUnitInactiveSec=` w `deploy/linux/moodle-sync.timer`, potem ponownie `install-server.sh` |

**Zmiana ustawienia:** `.venv/bin/python -m moodle_sync set LANGUAGE pl`, potem `sudo systemctl restart moodle-sync-bot`. Nie dopisuj do `.env` przez `echo >>`: jeśli plik nie kończy się znakiem nowej linii, nowa linia sklei się z ostatnią.

**Aktualizacja moodle-sync:**

```bash
cd ~/moodle-sync && git pull && bash deploy/linux/install-server.sh
```

Kopię rozpakowaną z archiwum wydania (nie klon git) można też zaktualizować z Telegrama: `/update` (i `/rollback`).

**Miejsce na karcie:** semestr to zwykle dużo poniżej 1 GB, więc karta 32 GB wystarczy na lata. Lokalne kopie to darmowy backup chmury. Jeśli mimo to chcesz je usuwać po wysłaniu, ustaw `KEEP_LOCAL=0`.

## Odporność

- **Zerwane Wi-Fi:** zapytania są ponawiane, pobieranie wznawia się przy następnym przebiegu i nic nie zostaje zapisane do połowy.
- **Wi-Fi co chwilę się rozłącza:** wyłącz oszczędzanie energii karty Wi-Fi i zrestartuj Pi:
  ```bash
  sudo nmcli connection modify preconfigured wifi.powersave 2
  ```
  (`nmcli connection show` pokaże nazwy połączeń.)
- **Wiadomość, gdy Pi padnie:** ustaw [healthchecks.io](notifications.md#alarm-nie-działa-healthchecksio). Jeśli Pi przestanie się zgłaszać, to *serwis* da Ci znać.

## Karta SD padła

1. Przygotuj nową kartę (kroki 1–4).
2. Przed `install-server.sh` przywróć stan z kopii w chmurze, robionej przy każdym przebiegu (jeśli używasz rclone):
   ```bash
   cd ~/moodle-sync
   rclone copyto <remote>:_moodle_sync/state.json state.json
   rclone copyto <remote>:_moodle_sync/przedmioty.json przedmioty.json   # albo courses.json, jeśli był
   ```
   Kopia leży obok `DRIVE_DEST`, np. dla `DRIVE_DEST=PG/eNauczanie` w `gdrive:PG/_moodle_sync/`.

Sekretów (`.env`, `google_token.json`, `rclone.conf`) w kopii **celowo nie ma**. **Trzymaj ich kopię na komputerze.** Bez `state.json` nic się nie zepsuje: Pi pobierze wszystko ponownie (w chmurze i kalendarzu nic się nie zdubluje) i wyśle jedno duże powiadomienie o „nowych” plikach.
