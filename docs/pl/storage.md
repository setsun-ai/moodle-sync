# Gdzie trafiają pliki

🇬🇧 [English version](../en/storage.md) · [← README](../../README.pl.md)

Pliki zawsze trafiają do `DOWNLOAD_DIR` (domyślnie `downloads/` w projekcie), ułożone tak:

```
<Przedmiot>/
    Wyklady/
    Cwiczenia/
    Laboratoria/
    Projekty/
    Inne materialy/
```

Nazwy folderów zależą od `LANGUAGE`. Jak wybierana jest kategoria i jak to zmienić: [Konfiguracja → Kategorie](configuration.md#kategorie).

Żeby pliki trafiły do chmury, wybierz jedną z trzech opcji:

| Opcja | Konfiguracja | Dla kogo |
|---|---|---|
| **A. Folder synchronizowany** | żadna | komputer z aplikacją Dysk Google / OneDrive / Dropbox |
| **B. rclone** | 5–15 min | Raspberry Pi / serwer albo brak aplikacji na komputerze |
| **C. Tylko lokalnie** | żadna | chcesz mieć pliki po prostu na dysku |

## A. Folder synchronizowany (najprościej)

Jeśli masz zainstalowany **Dysk Google na komputer**, **OneDrive** albo **Dropbox**, ustaw `DOWNLOAD_DIR` na folder wewnątrz nich. Kreator o to zapyta.

```
DOWNLOAD_DIR=C:\Users\Ty\OneDrive\Moodle            (Windows)
DOWNLOAD_DIR=/Users/ty/Library/CloudStorage/GoogleDrive-ty@example.com/Mój dysk/Moodle   (macOS)
```

Aplikacja na komputerze sama wszystko wyśle. `RCLONE_REMOTE` zostaw pusty.

> Wiele uczelni daje studentom **Microsoft 365 z 1 TB na OneDrive**. To świetne miejsce na materiały.

## B. rclone (Raspberry Pi, serwery)

[rclone](https://rclone.org) wysyła pliki do ponad 70 usług. moodle-sync używa `rclone copy`:
- dokłada i aktualizuje pliki, ale **nigdy niczego nie kasuje w chmurze**;
- z `KEEP_LOCAL=0` używa `rclone move`, czyli lokalne kopie znikają po udanym wysłaniu.

**Instalacja:**
- Windows: `winget install Rclone.Rclone`
- macOS: `brew install rclone`
- Linux / Raspberry Pi: `curl https://rclone.org/install.sh | sudo bash`

### Dysk Google

1. *(Zalecane)* Utwórz własnego klienta OAuth, bo jest szybszy niż współdzielony klient rclone. Wykonaj kroki 1–4 z rozdziału [Kalendarz Google](google-calendar.md#1-projekt-w-google-cloud-raz-10-min) (włącz **Google Drive API**). Jeden klient wystarczy dla Dysku i kalendarza.
2. Utwórz remote:
   ```
   rclone config create gdrive drive scope=drive.file client_id=TWOJ_ID client_secret=TWOJ_SECRET
   ```
   Otworzy się przeglądarka: zaloguj się i zezwól na dostęp. Bez własnego klienta pomiń `client_id` i `client_secret`.
3. W `.env`: `RCLONE_REMOTE=gdrive` i `DRIVE_DEST=Moodle` (folder docelowy).
4. Test: `python -m moodle_sync upload --check`.

> **O `scope=drive.file`:** rclone widzi wtedy tylko pliki, które sam utworzył, a nie cały Twój Dysk. Jest jeden haczyk: **nie twórz folderu docelowego ręcznie**, bo rclone go nie zobaczy i utworzy drugi o tej samej nazwie. Pozwól mu utworzyć `DRIVE_DEST` samemu. Jeśli chcesz użyć istniejącego folderu, podaj zamiast tego `scope=drive` (pełny dostęp do Dysku).

### OneDrive (także uczelniany Microsoft 365)

```
rclone config
```

W interaktywnej konfiguracji:
1. `n` (nowy remote), nazwa `onedrive`, typ **Microsoft OneDrive**, wszystko domyślnie.
2. Zaloguj się w przeglądarce.
3. Dla konta uczelnianego wybierz **OneDrive (business)**.

Potem w `.env` ustaw `RCLONE_REMOTE=onedrive`.

> Jeśli Microsoft pokaże *„Wymagana zgoda administratora”*, uczelnia blokuje zewnętrzne aplikacje. Użyj wtedy opcji A (aplikacja OneDrive na komputerze).

### Inne

Dropbox, Nextcloud, pCloud, Mega, SFTP, S3...: `rclone config` przeprowadzi Cię przez każdą z nich. Zmienia się tylko `RCLONE_REMOTE`.

### rclone na Raspberry Pi (bez przeglądarki)

1. Skonfiguruj remote na komputerze, jak wyżej.
2. Skopiuj plik konfiguracji na Pi:
   - Windows: `%APPDATA%\rclone\rclone.conf`
   - macOS/Linux: `~/.config/rclone/rclone.conf`
   - Pi: `~/.config/rclone/rclone.conf`

Plik musi być zapisywalny, bo rclone zapisuje w nim odświeżone tokeny. Traktuj go jak hasło.

### Kopia pamięci programu

Po każdej wysyłce `state.json` (oraz `courses.json` / `przedmioty.json`) trafia do `_moodle_sync/` obok `DRIVE_DEST` (`STATE_BACKUP_DEST`). Po awarii dysku przywrócisz go przez `rclone copyto` ([jak](raspberry-pi.md#karta-sd-padła)). Sekrety nigdy nie są wysyłane.

## Zmiana kategorii później

Gdy zmienisz `courses.json` albo reguły kategorii, kolejny przebieg **przeniesie** już pobrane pliki:
- lokalnie: od razu;
- w chmurze: przez `rclone moveto`, bez ponownego wysyłania.

W opcji A przeniesienie obsłuży sama aplikacja na komputerze.
