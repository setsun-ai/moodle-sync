# Pierwsze kroki

🇬🇧 [English version](../en/getting-started.md) · [← README](../../README.pl.md)

Zajmie Ci to około **10 minut**. Potrzebujesz komputera (Windows, macOS albo Linux) i swojego loginu do Moodle. Nie musisz umieć programować.

## 1. Zainstaluj Pythona (3.10 lub nowszy)

| System | Jak |
|---|---|
| **Windows** | W PowerShell uruchom `winget install Python.Python.3.12` albo pobierz instalator z [python.org](https://www.python.org/downloads/) i **zaznacz „Add python.exe to PATH”**. |
| **macOS** | `brew install python` ([Homebrew](https://brew.sh)) albo instalator z [python.org](https://www.python.org/downloads/). |
| **Linux / Raspberry Pi** | Zwykle już jest. Sprawdź: `python3 --version`. Na Debianie, Ubuntu i Raspberry Pi OS doinstaluj też `sudo apt install python3-venv`. |

## 2. Pobierz moodle-sync

- **Najprościej:** na stronie GitHuba kliknij **Code → Download ZIP** i rozpakuj, np. do `C:\moodle-sync` albo `~/moodle-sync`.
- **Przez git:** `git clone https://github.com/setsun-ai/moodle-sync.git moodle-sync`

> **macOS:** nie wrzucaj projektu do *Dokumentów*, na *Biurko* ani do *Pobranych*. Zadania w tle nie mają tam dostępu bez dodatkowych uprawnień ([szczegóły](running.md#macos)).

## 3. Instalacja i kreator

> Zanim zaczniesz, przeczytaj **[Zasady korzystania](responsible-use.md)**. To krótki tekst o materiałach z kursów, cudzych danych i regulaminach uczelni.

| System | Jak |
|---|---|
| **Windows** | Kliknij dwukrotnie **`install.bat`** |
| **macOS / Linux** | W terminalu, w folderze projektu: `bash install.sh` |

Skrypt tworzy prywatne środowisko Pythona (`.venv`), instaluje biblioteki i uruchamia **kreator konfiguracji**:

1. **Adres Moodle.** Wklej dowolną stronę swojego Moodle, np. `https://moodle.example.edu.pl/2025/my/`. Kreator sprawdzi, jak uczelnia loguje użytkowników.
2. **Token (dostęp do konta).**
   - Zwykły formularz logowania: wpisujesz login i hasło. Trafiają tylko do Twojego Moodle, jednorazowo, i nie są nigdzie zapisywane.
   - Logowanie przez uczelnię, Microsoft albo Google (SSO): kreator otworzy przeglądarkę i pokaże dokładnie, co skopiować. Pomoc znajdziesz w rozdziale [Token](token.md).
3. **Nazwa i folder.** Krótka nazwa uczelni (do nazw kalendarzy, np. `UNI`) i miejsce na pliki.
   Wskazówka: wybierz folder w swoim **Dysku Google / OneDrive / Dropboxie** na komputerze, a pliki trafią do chmury bez żadnej dodatkowej konfiguracji.
4. **Powiadomienia** (opcjonalnie): Telegram, Discord, ntfy albo e-mail. Na koniec przyjdzie wiadomość testowa. Zobacz [Powiadomienia](notifications.md).
5. **Chmura** (opcjonalnie): tylko dla rclone (np. na Raspberry Pi). Zobacz [Chmura](storage.md).
6. **Kalendarz Google** (opcjonalnie): zobacz [Kalendarz](google-calendar.md).
7. **Pierwsza synchronizacja:** pobierz wszystko teraz albo zapamiętaj, co jest, i pobieraj tylko nowości.

Kreator możesz uruchomić ponownie w każdej chwili. Obecne ustawienia podpowie jako domyślne:

```
.venv\Scripts\python -m moodle_sync setup      (Windows)
.venv/bin/python -m moodle_sync setup          (macOS / Linux)
```

## 4. Sprawdź całość

```
python -m moodle_sync doctor
```

Każda linia to jedno sprawdzenie:
- ✅ działa,
- ⏭ opcjonalne i nieskonfigurowane,
- ❌ problem, razem z podpowiedzią, jak go naprawić.

> We wszystkich poleceniach `python` oznacza Pythona ze środowiska projektu:
> `.venv\Scripts\python` na Windows, `.venv/bin/python` na macOS i Linuksie.
> Możesz też raz na terminal aktywować środowisko (`.venv\Scripts\activate` / `source .venv/bin/activate`) i dalej pisać samo `python`.

## 5. Wybierz sposób uruchamiania

| Masz... | Zrób tak | Instrukcja |
|---|---|---|
| laptopa i synchronizujesz, kiedy chcesz | dwuklik `sync.bat` / `./sync.sh` | [Uruchamianie](running.md#ręcznie) |
| komputer włączony w ciągu dnia | automatycznie co 30 min, gdy jesteś zalogowany | [Uruchamianie](running.md#automatycznie-na-komputerze) |
| Raspberry Pi / serwer domowy | 24/7 co 15 min + bot Telegram | [Raspberry Pi](raspberry-pi.md) |

## Wszystkie komendy

| Komenda | Co robi |
|---|---|
| `setup` | Kreator konfiguracji. |
| `doctor` | Sprawdzenie konfiguracji. |
| `run` | Pełna synchronizacja: pliki → chmura → kalendarz → ogłoszenia i oceny. |
| `token` | Nowy token Moodle (gdy stary wygasł). |
| `download [--dry-run] [--limit N] [--baseline]` | Tylko pobieranie nowych plików. `--dry-run` pokazuje plan bez wykonywania. |
| `upload [--dry-run] [--check]` | Tylko wysyłka do chmury (rclone). |
| `calendar [--dry-run] [--auth]` | Tylko kalendarz Google. `--auth` = jednorazowe logowanie. |
| `watch [--dry-run] [--force]` | Tylko ogłoszenia i oceny. |
| `courses` | Podgląd, jak pliki każdego kursu zostaną podzielone na kategorie. |
| `ics` | Adres subskrypcji kalendarza (Outlook / Apple). |
| `bot [--setup]` | Bot Telegram / połączenie bota z Twoim czatem. |
| `notify-test` | Testowe powiadomienie na wszystkie kanały. |
| `set KLUCZ WARTOŚĆ` | Bezpieczna zmiana jednego ustawienia w `.env`, np. `set LANGUAGE pl`. Używaj zamiast `echo ... >> .env`. |
