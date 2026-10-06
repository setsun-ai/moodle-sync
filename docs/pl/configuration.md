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
| `SUBMITTED_FILES` | `1` | Pobieraj też pliki wysłane przez ciebie do zadań, do `Wyslane zadania/<zadanie>/` w folderze przedmiotu (sprawdzane co godzinę, bez powiadomienia). `0` = wyłączone. |

### Semestry i karty przedmiotów

Pliki mogą trafiać do folderu na każdy semestr, z folderami przedmiotów nazwanymi jak w planie studiów i z kartą
przedmiotu (sylabusem) obok materiałów:

```
Semestr 1/
  Matematyka II/
    Karta przedmiotu.pdf
    Wyklady/...
Semestr 2/...
```

| Zmienna | Domyślnie | Znaczenie |
|---|---|---|
| `STUDY_CATALOG` | – | Adres katalogu ECTS Twojej uczelni, np. `https://ects.uczelnia.edu.pl`. Potrzebny tylko do `plan --search`. |
| `STUDY_PLAN_URL` | – | Twój kierunek (albo specjalność) w katalogu ECTS. Znajdziesz go: `python -m moodle_sync plan --search "nazwa" --catalog <adres>`. Katalog musi pokazywać plan według semestrów („Semestr 1 (2025/2026 - zimowy)”) z kartą przedmiotu w PDF. |
| `STUDY_START` | – | Bez katalogu: Twój pierwszy semestr, np. `2025/2026-winter`. Numery semestrów liczone są z dat rozpoczęcia kursów. |
| `SEMESTER_FOLDERS` | włączone z jednym z powyższych | `0` = bez folderów semestrów, tylko nazwy przedmiotów z planu. |
| `SYLLABUS` | włączone z `STUDY_PLAN_URL` | `0` = nie pobieraj kart przedmiotów. Karty są sprawdzane co 30 dni; o zmianie dostajesz powiadomienie. |

- `python -m moodle_sync plan` pokazuje semestry, przedmioty i to, który kurs z Moodle trafia do którego folderu.
- Kurs z Moodle dostaje przedmiot, którego wszystkie słowa są w jego nazwie (najdokładniejszy: „Matematyka II”
  wygrywa z „Matematyka”). Kursy bez przedmiotu dostają semestr z daty rozpoczęcia.
- Przedmioty obowiązkowe dostają kartę, zanim pojawią się w Moodle; obieralne tylko wtedy, gdy masz ten kurs.
- **Włączenie przenosi już pobrane pliki.** Dla bezpieczeństwa pierwsze uruchomienie zatrzyma się i poprosi
  o jednorazowe potwierdzenie: `python -m moodle_sync download --reorganize`. Kopia w chmurze też się przeniesie.
- Gdy katalog nie działa, używany jest plan zapisany przy ostatnim udanym sprawdzeniu.
- **Własne nazwy, karty, kilka semestrów:** w `/przypisz` kurs może dostać własną nazwę folderu (✏️) i drugi semestr (➕ - jeden kurs Moodle dla „Projekt I” i „Projekt II”, pliki dzielone według dat); `/karta` dodaje Twój link do karty przedmiotu, którego nie ma w katalogu (np. z innej uczelni).
- **Nazwy folderów pochodzą z planu** (czytelnie zapisane, gdy katalog używa wielkich liter), a kursy z Moodle trafiają do nich. Gdy automatyczne dopasowanie jest błędne albo go brak, `/przypisz` w bocie przypisze kurs do dowolnego przedmiotu – albo do całego modułu obieralnego, np. dla kursu z innej uczelni.
- **Moduły obieralne:** zaznacz swój wybór komendą `/obieralne` w bocie Telegram. Opcje są ponumerowane i mają link do karty przedmiotu, bo kilka może mieć tę samą nazwę; „inna uczelnia” obejmuje obieralne spoza katalogu. Obieralny, do którego masz kurs w Moodle, liczy się jako wybrany; bot przypomina o modułach bez wyboru.
- Przedmioty bez opublikowanej karty w katalogu są wypisane w `plan` i zgłoszone raz w powiadomieniu.

### Bot Telegram: oddawanie zadań, fora, obecność

| Zmienna | Domyślnie | Znaczenie |
|---|---|---|
| `MOODLE_ACTIONS` | `0` | `1` = bot może oddawać zadania, pisać na forach i zaznaczać obecność – zawsze dopiero po Twoim ✅. |
| `STUDENT_ID` | – | Twój numer albumu, używany w nazwach oddawanych plików. |
| `SUBMISSION_NAME` | `{assignment} {course} {student_id}` | Szablon nazwy oddawanego pliku; jest też `{original}`. Przykład: *Sprawozdanie LCMS 123456.pdf*. |
| `MOODLE_PRIVATE_TOKEN` | – | Zapisuje go `python -m moodle_sync token`; potrzebny tylko do obecności (nie ma do niej funkcji API, więc bot otwiera stronę tak jak aplikacja Moodle). Traktuj go jak hasło. |

- Kody QR: wyślij botowi link (zeskanuj kod aparatem telefonu i udostępnij go) albo zdjęcie kodu, jeśli masz
  `zbarimg` (`sudo apt install zbar-tools`).
- Bez „private tokenu” (część uczelni go nie wydaje – w *Kluczach bezpieczeństwa* nie ma przycisku resetu): linki obecności, zdjęcia QR i `/obecnosc` dają przycisk „✋ Otwórz obecność”, który otwiera stronę w telefonie.
- Telegram pozwala botom pobierać pliki do 20 MB.

### Drugi Moodle (np. jeden kurs międzyuczelniany)

Ta sama kopia kodu może obsługiwać drugą stronę z osobnym folderem danych (`MOODLE_SYNC_DATA_DIR`): własnym
`.env`, tokenem i `courses.json`, a pliki trafiają do tego samego folderu w chmurze.

```bash
mkdir -p ~/moodle-sync-2
cd ~/moodle-sync && MOODLE_SYNC_DATA_DIR=$HOME/moodle-sync-2 .venv/bin/python -m moodle_sync setup
```

W kreatorze podaj adres drugiego Moodle; bota Telegram pomiń (wystarczy bot pierwszej kopii – powiadomienia z obu
przyjdą na ten sam czat). Potem w tym samym terminalu:

```bash
export MOODLE_SYNC_DATA_DIR=$HOME/moodle-sync-2
.venv/bin/python -m moodle_sync set STATE_BACKUP_DEST _moodle_sync_2   # nigdy wspólna kopia stanu
.venv/bin/python -m moodle_sync set SYLLABUS 0                         # karty pobiera pierwsza kopia
echo '{"only": ["fragment nazwy kursu"]}' > ~/moodle-sync-2/courses.json
```

`only` (w `courses.json`) synchronizuje tylko kursy, których nazwa zawiera któryś fragment. Ustaw ten sam
`STUDY_PLAN_URL`, a kurs trafi do właściwego folderu semestru. Drugi timer na Raspberry Pi / serwerze:

```bash
sudo sed "s#^Environment=\(.*\)#Environment=\1 MOODLE_SYNC_DATA_DIR=$HOME/moodle-sync-2#" /etc/systemd/system/moodle-sync.service | sudo tee /etc/systemd/system/moodle-sync-2.service
sudo cp /etc/systemd/system/moodle-sync.timer /etc/systemd/system/moodle-sync-2.timer
sudo systemctl daemon-reload && sudo systemctl enable --now moodle-sync-2.timer
```

Kalendarz Google dla drugiego Moodle: skopiuj logowanie Google z pierwszej kopii (`google_token.json` -
`client_secret.json` jest potrzebny tylko przy pierwszym logowaniu i może go tu nie być) i nadaj stronie własną etykietę -
powstaną kalendarze „UG – terminy” i „UG – zajęcia”, obok kalendarzy pierwszej uczelni:

```bash
cp ~/moodle-sync/google_token.json ~/moodle-sync-2/
MOODLE_SYNC_DATA_DIR=$HOME/moodle-sync-2 .venv/bin/python -m moodle_sync set SITE_LABEL UG
```

### Stara strona, do której wchodzisz tylko przez przeglądarkę

Gdy logowanie uczelniane wydaje tokeny tylko dla nowej strony, a stara nie ma logowania hasłem, `archive`
kopiuje starą stronę jednorazowo przez sesję przeglądarki zamiast tokenu:

```bash
cd ~/moodle-sync && .venv/bin/python -m moodle_sync archive https://moodle.example.edu/stara --dest Studia/Licencjat
```

Program powie, gdzie znaleźć ciasteczko `MoodleSession` (F12 -> Aplikacja -> Pliki cookie), i poprosi o nie bez
wyświetlania; ciasteczko nie jest nigdzie zapisywane. Pliki trafiają do `archive/` w folderze danych, w zwykłym
układzie (kurs / kategoria / plik, twoje wysłane zadania w `Wyslane zadania/`), a potem są kopiowane do folderu
w chmurze. `--list` tylko pokazuje znalezione kursy i aktywności. Gdy sesja wygaśnie w trakcie, zaloguj się
jeszcze raz i uruchom to samo polecenie - zacznie od miejsca, w którym skończył.

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
| `TELEGRAM_FILE_BUTTONS` | `0` = bez przycisków „⬇️ Pobierz” pod *Nowymi materiałami*. Domyślnie `1`; przyciski wymagają procesu bota. |
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
- **`plan`:** który to przedmiot z planu studiów, gdy nazwa w Moodle tego nie mówi (`"Matematyka dla inżynierów": "Matematyka II"`).
- **`only`:** synchronizuj tylko kursy, których nazwa zawiera któryś z tych fragmentów (np. drugi Moodle, zobacz niżej).
- **`semester`:** wymuszony semestr kursu (`"Piaskownica": 1`).
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
