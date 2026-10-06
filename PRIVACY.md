# Privacy / Prywatność

🇬🇧 English below · 🇵🇱 [po polsku niżej](#po-polsku)

**Short version:** moodle-sync is a program you run on **your own** computer. The project has **no servers, no accounts, no analytics and no telemetry**; its authors never receive any of your data. Data only goes where **you** configure it to go, and this page lists exactly what goes where.

## What data is processed

moodle-sync reads, through the Moodle API, what **you** can see in your courses:
- course and section names, and the files in them,
- calendar events: deadlines, quizzes, classes,
- posts in announcement forums (including the author's name),
- your own grades and teachers' feedback on your work.

Announcements can contain **other people's personal data**, e.g. a table of grades with student ID numbers. moodle-sync doesn't analyse it, but it passes the announcement text on to your notifications (see [Responsible use](docs/en/responsible-use.md)).

## Where it goes

| Destination | What exactly | When |
|---|---|---|
| **Your Moodle server** | Your token and API requests. The User-Agent names this project. | always |
| **Your disk**: `.env` | Settings and secrets (tokens, passwords) | always |
| **Your disk**: `state.json` | List of downloaded files, calendar ids, ids of seen announcements, **your grades with assignment names**, results of recent runs | always |
| **Your disk**: `DOWNLOAD_DIR` | Course files | always |
| **Your disk**: `logs/` | Course and file names, errors; **secrets are masked** | scheduled runs on Windows/macOS |
| **Your cloud** (rclone: Google Drive, OneDrive...) | Course files + a backup of `state.json`. No authentication credentials, but private Moodle data such as your grades. | if `RCLONE_REMOTE` is set |
| **Google Calendar** (your account) | Deadline titles, course names, assignment descriptions | if you logged in to Google |
| **Telegram / Discord** | Notification text: file names, deadlines, **full announcement text**, your grades and teacher feedback | if configured |
| **ntfy** | Same as above. On the public `ntfy.sh` server anyone who knows your topic name can read it, and messages are kept there for a few hours. Use a long random topic or your own server. | if configured |
| **Your e-mail provider** (SMTP) | Same as above | if configured |
| **Your Moodle server** (bot actions) | Files you submit, forum posts you write, the attendance status you pick - only after your ✅ | with `MOODLE_ACTIONS=1` |
| **Telegram** (files you send) | A file you send the bot to submit stays in your Telegram chat | when you send one |
| **Telegram** (files you ask for) | A course file you request with **⬇️ Download** under a notification stays in your Telegram chat | when you tap it |
| **Your university's ECTS catalogue** | Ordinary public requests for the study plan and subject card PDFs. No personal data, no token. | if `STUDY_PLAN_URL` is set |
| **healthchecks.io** | Only "run started/finished/failed" + the short result summary (step names and OK/ERROR). No course data. | if `HEALTHCHECK_URL` is set |

### Data, storage and retention

| Data | Stored locally | Sent externally | Retention |
|---|---|---|---|
| Moodle token and channel credentials (Telegram, Discord, SMTP, healthchecks URL) | `.env` (plain text, git-ignored) | each credential only to its own service; the Moodle token only to your Moodle server | until you delete `.env` or revoke the token |
| Course files | `DOWNLOAD_DIR` | your cloud via rclone, if `RCLONE_REMOTE` is set | until you delete them; with `KEEP_LOCAL=0` local copies are deleted after upload |
| Your grades and teacher feedback | `state.json` | cloud backup of `state.json` (if rclone); notifications (if grade notifications are on) | `state.json` and its cloud copy: until you delete them (the backup is overwritten on every run); notifications: per provider |
| Announcement text (may contain other people's data) | only ids of seen announcements, in `state.json` | full text in notifications | per provider; public `ntfy.sh` keeps messages for a few hours |
| Deadlines, course names, assignment descriptions | `state.json` | Google Calendar (if you logged in); notifications | until you delete the calendars or messages |
| Run logs (course and file names, errors; secrets masked) | `logs/sync.log` + one rotated copy (rotation at 1 MB) | error lines in error notifications; run status and step summary to healthchecks.io | rolling, about 2 MB at most |

Each of those services processes data under **its own** privacy policy (Google, Microsoft, Telegram, Discord...). moodle-sync sends **nothing** anywhere else: no crash reports, no usage statistics, no update checks.

## Your control

- **See everything:** all data is in plain text files (`state.json`, `.env`) in the project folder.
- **Turn things off:** any channel or kind of notification (`NOTIFY_*=0`), classes in the calendar (`SYNC_CLASSES=0`), cloud upload (empty `RCLONE_REMOTE`).
- **Delete everything:**
  1. Turn off the scheduler (`schedule.ps1 -Remove`, `schedule.sh --remove`, or `systemctl disable --now moodle-sync.timer`).
  2. Delete the project folder and `DOWNLOAD_DIR`.
  3. **Moodle:** Preferences → Security keys → *Reset*, which invalidates the token.
  4. **Google:** delete the two calendars, then remove moodle-sync at <https://myaccount.google.com/permissions>.
  5. **Cloud:** delete the target folder and `_moodle_sync/`.
  6. **Telegram:** @BotFather → `/deletebot`. **Discord:** delete the webhook. **healthchecks.io:** delete the check.

## Responsibility

When you run moodle-sync, **you** decide what is processed and where, just as when you save files from Moodle by hand. Keep what you receive private; this matters especially for other people's data in announcements. See **[Responsible use](docs/en/responsible-use.md)**.

---

## Po polsku

**W skrócie:** moodle-sync to program, który uruchamiasz na **własnym** komputerze. Projekt **nie ma serwerów, kont, analityki ani telemetrii**, a jego autorzy nie dostają żadnych Twoich danych. Dane trafiają tylko tam, gdzie **Ty** je skierujesz. Poniżej dokładnie opisujemy, co i dokąd.

### Jakie dane są przetwarzane

moodle-sync czyta przez API Moodle to, co **Ty** widzisz na swoich kursach:
- nazwy kursów i sekcji oraz pliki,
- wydarzenia z kalendarza: terminy, quizy, zajęcia,
- wpisy na forach ogłoszeń (z imieniem i nazwiskiem autora),
- Twoje oceny i komentarze prowadzących do Twoich prac.

Ogłoszenia mogą zawierać **dane osobowe innych osób**, np. tabelę ocen z numerami indeksów. moodle-sync ich nie analizuje, ale przekazuje treść ogłoszenia do Twoich powiadomień (zobacz [Zasady korzystania](docs/pl/responsible-use.md)).

### Dokąd trafiają

| Miejsce | Co dokładnie | Kiedy |
|---|---|---|
| **Serwer Twojego Moodle** | Twój token i zapytania do API. User-Agent podaje nazwę projektu. | zawsze |
| **Twój dysk**: `.env` | Ustawienia i sekrety (tokeny, hasła) | zawsze |
| **Twój dysk**: `state.json` | Lista pobranych plików, identyfikatory kalendarzy, identyfikatory widzianych ogłoszeń, **Twoje oceny z nazwami zadań**, wyniki ostatnich przebiegów | zawsze |
| **Twój dysk**: `DOWNLOAD_DIR` | Pliki z kursów | zawsze |
| **Twój dysk**: `logs/` | Nazwy kursów i plików, błędy; **sekrety są maskowane** | przebiegi z harmonogramu na Windows/macOS |
| **Twoja chmura** (rclone: Dysk Google, OneDrive...) | Pliki z kursów + kopia `state.json`. Bez danych logowania, ale z prywatnymi danymi z Moodle, np. Twoimi ocenami. | gdy ustawisz `RCLONE_REMOTE` |
| **Kalendarz Google** (Twoje konto) | Tytuły terminów, nazwy kursów, opisy zadań | gdy zalogujesz się do Google |
| **Telegram / Discord** | Treść powiadomień: nazwy plików, terminy, **pełna treść ogłoszeń**, Twoje oceny i komentarze prowadzących | gdy skonfigurujesz |
| **ntfy** | To samo co wyżej. Na publicznym serwerze `ntfy.sh` może to przeczytać każdy, kto zna nazwę Twojego tematu, a wiadomości są tam przechowywane przez kilka godzin. Używaj długiego, losowego tematu albo własnego serwera. | gdy skonfigurujesz |
| **Dostawca poczty** (SMTP) | To samo co wyżej | gdy skonfigurujesz |
| **Serwer Twojego Moodle** (akcje bota) | Oddawane pliki, Twoje posty na forach, wybrany status obecności – tylko po Twoim ✅ | z `MOODLE_ACTIONS=1` |
| **Telegram** (wysyłane pliki) | Plik wysłany botowi do oddania zostaje w Twoim czacie Telegram | gdy go wyślesz |
| **Telegram** (pobierane pliki) | Plik z kursu, o który poprosisz przyciskiem **⬇️ Pobierz** pod powiadomieniem, zostaje w Twoim czacie Telegram | gdy go klikniesz |
| **Katalog ECTS Twojej uczelni** | Zwykłe publiczne zapytania o plan studiów i karty przedmiotów w PDF. Bez danych osobowych i bez tokenu. | gdy ustawisz `STUDY_PLAN_URL` |
| **healthchecks.io** | Tylko „start / koniec / błąd przebiegu” + krótkie podsumowanie (nazwy kroków i OK/BŁĄD). Bez danych z kursów. | gdy ustawisz `HEALTHCHECK_URL` |

### Dane, przechowywanie i retencja

| Dane | Przechowywane lokalnie | Wysyłane na zewnątrz | Retencja |
|---|---|---|---|
| Token Moodle i dane dostępowe kanałów (Telegram, Discord, SMTP, URL healthchecks) | `.env` (zwykły tekst, w `.gitignore`) | każde tylko do swojej usługi; token Moodle tylko do Twojego serwera Moodle | do usunięcia `.env` lub unieważnienia tokenu |
| Pliki z kursów | `DOWNLOAD_DIR` | Twoja chmura przez rclone, jeśli ustawisz `RCLONE_REMOTE` | do usunięcia; przy `KEEP_LOCAL=0` lokalne kopie są usuwane po wysłaniu |
| Twoje oceny i komentarze prowadzących | `state.json` | kopia `state.json` w chmurze (przy rclone); powiadomienia (jeśli włączone) | `state.json` i kopia w chmurze: do usunięcia (kopia nadpisywana przy każdym przebiegu); powiadomienia: według dostawcy |
| Treść ogłoszeń (może zawierać dane innych osób) | tylko identyfikatory widzianych ogłoszeń w `state.json` | pełna treść w powiadomieniach | według dostawcy; publiczny `ntfy.sh` trzyma wiadomości kilka godzin |
| Terminy, nazwy kursów, opisy zadań | `state.json` | Kalendarz Google (po zalogowaniu); powiadomienia | do usunięcia kalendarzy lub wiadomości |
| Logi przebiegów (nazwy kursów i plików, błędy; sekrety zamaskowane) | `logs/sync.log` + jedna starsza kopia (rotacja przy 1 MB) | linie błędów w powiadomieniach o błędach; status i podsumowanie kroków do healthchecks.io | rotacyjnie, łącznie ok. 2 MB |

Każda z tych usług przetwarza dane według **własnej** polityki prywatności (Google, Microsoft, Telegram, Discord...). moodle-sync **nie wysyła niczego nigdzie indziej**: żadnych raportów błędów, statystyk użycia ani sprawdzania aktualizacji.

### Masz nad tym kontrolę

- **Wgląd:** wszystkie dane są w zwykłych plikach tekstowych (`state.json`, `.env`) w folderze projektu.
- **Wyłączanie:** dowolny kanał lub rodzaj powiadomień (`NOTIFY_*=0`), zajęcia w kalendarzu (`SYNC_CLASSES=0`), wysyłkę do chmury (puste `RCLONE_REMOTE`).
- **Usunięcie wszystkiego:**
  1. Wyłącz harmonogram (`schedule.ps1 -Remove`, `schedule.sh --remove` albo `systemctl disable --now moodle-sync.timer`).
  2. Usuń folder projektu i `DOWNLOAD_DIR`.
  3. **Moodle:** Preferencje → Klucze bezpieczeństwa → *Resetuj*, co unieważnia token.
  4. **Google:** usuń oba kalendarze, potem usuń moodle-sync na <https://myaccount.google.com/permissions>.
  5. **Chmura:** usuń folder docelowy i `_moodle_sync/`.
  6. **Telegram:** @BotFather → `/deletebot`. **Discord:** usuń webhook. **healthchecks.io:** usuń sprawdzenie.

### Odpowiedzialność

Uruchamiając moodle-sync, to **Ty** decydujesz, co jest przetwarzane i gdzie, tak samo jak przy ręcznym zapisywaniu plików z Moodle. Zachowaj to, co dostajesz, dla siebie; dotyczy to zwłaszcza cudzych danych w ogłoszeniach. Zobacz **[Zasady korzystania](docs/pl/responsible-use.md)**.
