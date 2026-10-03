# Konfiguracja: pełny opis

🇬🇧 [English version](../en/configuration.md) · [← README](../../README.pl.md)

Wszystko jest w dwóch plikach w folderze projektu (albo w `MOODLE_SYNC_DATA_DIR`, jeśli ustawisz):

| Plik | Zawartość |
|---|---|
| `.env` | Ustawienia i **sekrety**. Tworzy go kreator. Wzór: `.env.example`. |
| `courses.json` | Opcjonalne nazwy, kategorie i pomijanie per kurs. Wzór: `courses.example.json`. |

Zmiany działają od następnego przebiegu. Bot Telegram czyta `.env` tylko przy starcie, więc po edycji go zrestartuj.

## `.env`

### Wymagane

| Zmienna | Przykład |
|---|---|
| `MOODLE_BASE_URL` | `https://moodle.example.edu.pl/2025`: adres Twojego Moodle (kreator go sam poprawi). |
| `MOODLE_TOKEN` | Twój token, zobacz [Token](token.md). |

### Ogólne

| Zmienna | Domyślnie | Znaczenie |
|---|---|---|
| `LANGUAGE` | `en` | `pl` / `en`: komunikaty, powiadomienia, bot, nazwy folderów. |
| `SITE_LABEL` | `Moodle` | Krótka nazwa uczelni do nazw kalendarzy, np. `UNI`. |
| `MOODLE_LANG` | = `LANGUAGE` | Który wariant brać z nazw wielojęzycznych (`{mlang pl}…{mlang en}…`). |
| `TIMEZONE` | `Europe/Warsaw` (pl) / `UTC` | Strefa czasowa (IANA) tworzonych kalendarzy. |

### Pliki

| Zmienna | Domyślnie | Znaczenie |
|---|---|---|
| `DOWNLOAD_DIR` | `downloads` | Względem projektu albo ścieżka bezwzględna, np. w folderze OneDrive. |
| `MAX_FILE_MB` | `0` | Pomijaj pliki większe niż N MB (0 = bez limitu). Po podniesieniu limitu pominięte pliki pobiorą się same. |

### Chmura (rclone): zobacz [Chmura](storage.md)

| Zmienna | Domyślnie | Znaczenie |
|---|---|---|
| `RCLONE_REMOTE` | (puste) | Nazwa remote'a rclone. Puste = bez wysyłki. |
| `DRIVE_DEST` | `Moodle` | Folder docelowy w chmurze. |
| `KEEP_LOCAL` | `1` | `0` = usuwaj lokalne kopie po wysłaniu. |
| `RCLONE_BIN` | `rclone` | Ścieżka do rclone, jeśli nie ma go w PATH. |
| `STATE_BACKUP_DEST` | `_moodle_sync` obok `DRIVE_DEST` | Gdzie trafia kopia `state.json`. |

### Kalendarz: zobacz [Kalendarz](google-calendar.md)

| Zmienna | Domyślnie | Znaczenie |
|---|---|---|
| `SYNC_CLASSES` | `1` | `0` = nie wstawiaj wpisów frekwencji (planu zajęć) do kalendarza. |

### Powiadomienia: zobacz [Powiadomienia](notifications.md)

| Zmienna | Znaczenie |
|---|---|
| `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` | Telegram (id czatu ustawia `bot --setup`). |
| `DISCORD_WEBHOOK_URL` | Webhook kanału Discord. |
| `NTFY_TOPIC`, `NTFY_SERVER` | Powiadomienia push ntfy. |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `EMAIL_TO`, `EMAIL_FROM` | E-mail. |
| `NOTIFY_FILES`, `NOTIFY_DEADLINES`, `NOTIFY_ANNOUNCEMENTS`, `NOTIFY_GRADES`, `NOTIFY_ERRORS`, `NOTIFY_SUMMARY` | `0` wycisza dany rodzaj. |
| `WATCH_ALL_FORUMS` | `1` = wszystkie fora, nie tylko ogłoszenia. Obejmuje też dyskusje studentów, więc bywa głośno. |
| `HEALTHCHECK_URL` | Alarm „nie działa” (Ping URL z healthchecks.io). |

## `courses.json`

Podejrzyj, jak wyglądają Twoje kursy teraz i co zmieniłaby edycja:

```
python -m moodle_sync courses
```

```json
{
  "names": {
    "Wstęp do programowania 2025/2026 (grupa 3)": "Programowanie"
  },
  "default_category": {
    "lektorat": "exercises"
  },
  "skip": ["Szkolenie biblioteczne", "Piaskownica"],
  "category_rules": [
    { "folder": "Seminaria", "pattern": "seminar" },
    { "folder": "Egzaminy", "pattern": "egzamin|exam|kolokw" }
  ]
}
```

- **Klucze** w `names`, `default_category` i `skip` to *fragmenty* nazwy kursu tak, jak wygląda w Moodle (bez rozróżniania wielkości liter).
- **`names`:** nazwa folderu, używana też w tytułach wydarzeń w kalendarzu i w powiadomieniach.
- **`default_category`:** kategoria dla plików, których nie rozpoznała żadna reguła. Użyj wbudowanego klucza (`lectures`, `exercises`, `labs`, `projects`, `other`) albo dowolnej nazwy folderu.
- **`skip`:** całkowicie pomijaj te kursy (pliki, kalendarz, ogłoszenia, oceny).
- **`category_rules`:** własne reguły, sprawdzane **przed** wbudowanymi. `pattern` to [wyrażenie regularne](https://regex101.com) dopasowywane do tekstu **bez polskich znaków, małymi literami** (pisz `wyklad`, nie `Wykład`).

Stara nazwa pliku `przedmioty.json` z kluczami `nazwy` / `kategoria_domyslna` nadal działa.

## Kategorie

Dla każdego pliku moodle-sync sprawdza trzy nazwy, **w tej kolejności**, i wygrywa pierwsze dopasowanie:
1. nazwę **sekcji**, bo prowadzący zwykle układają sekcje według formy zajęć,
2. nazwę **modułu**, np. „Slajdy do wykładu 3”,
3. **ścieżkę folderu i nazwę pliku**.

Wbudowane reguły, sprawdzane w tej kolejności:

| Folder (pl / en) | Pasuje do (słowa polskie i angielskie) |
|---|---|
| Laboratoria / Labs | `lab…` (ale nie *syllabus*) |
| Projekty / Projects | `projekt`, `project` |
| Wyklady / Lectures | `wyklad`, `lecture`, `slajd`, `slides` |
| Cwiczenia / Exercises | `cwicz`, `exercise`, `tutorial`, `seminar`, `class` |
| Inne materialy / Other materials | wszystko inne albo `default_category` |

Cokolwiek zmienisz, kolejny przebieg **przeniesie** istniejące pliki, lokalnie i w chmurze.

## Odstępy czasowe (w kodzie)

| Gdzie | Co |
|---|---|
| `deploy/*` | Jak często uruchamia się cała synchronizacja (domyślnie 15–30 min). |
| `moodle_sync/watch.py` | `FORUM_INTERVAL` (30 min), `GRADES_INTERVAL` (1 h), `GRADED_RECHECK` (24 h). |
| `moodle_sync/runner.py` | `WEEKLY_DAY` / `WEEKLY_HOUR` podsumowania tygodnia, `ALERT_REPEAT_HOURS`. |
| `moodle_sync/calendar_sync.py` | `REMINDERS`, `PAST_DAYS`, `FUTURE_DAYS`. |
