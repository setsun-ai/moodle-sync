# Zmiany

🇬🇧 [English](CHANGELOG.md)

## 1.3.0 (2026-10)

- **Przedmioty obieralne:** plan studiów wie teraz, które przedmioty należą do którego modułu obieralnego. `/obieralne` (`/electives`) w bocie pokazuje każdy moduł z przełącznikiem przy każdym przedmiocie; wybrane dostają kartę i folder. Obieralny, do którego masz już kurs w Moodle, liczy się jako wybrany, a bot raz przypomina o modułach bez wyboru.
- **Przedmioty bez karty** w katalogu nie są już po cichu pomijane: `plan` je oznacza, a Ty dostajesz jedną wiadomość z ich listą (kolejną dopiero, gdy lista się zmieni).
- **Stare kopie po przenosinach:** `upload --cleanup` (i `/porzadki` w bocie) znajduje pliki, które zostały po nieudanym przeniesieniu do nowych folderów – ta sama nazwa i rozmiar co plik trzymany przez moodle-sync gdzie indziej – i po potwierdzeniu usuwa je lokalnie i w chmurze.
- **Drugi Moodle:** `courses.json` → `only` synchronizuje tylko wskazane kursy; dokumentacja pokazuje, jak uruchomić drugą kopię (np. jeden kurs międzyuczelniany) z osobnym folderem danych i timerem, do tego samego folderu w chmurze.

## 1.2.2 (2026-10)

- **Obecność bez „private tokenu”** (część uczelni go nie wydaje, a klucza nie da się zresetować): link albo zdjęcie QR dostaje przycisk „✋ Otwórz obecność” – jedno dotknięcie, logujesz się jak zwykle, a hasło z QR jest już w linku; `/obecnosc` pokazuje moduły obecności z Twoich kursów jako takie przyciski. Działa też bez `MOODLE_ACTIONS`.

## 1.2.1 (2026-10)

- Plany studiów pisane WIELKIMI LITERAMI nie dają już krzyczących folderów: przedmiot z kursem w Moodle zachowuje nazwę kursu, pozostałe dostają zwykłą pisownię („Otwarte bazy danych”).

## 1.2.0 (2026-10)

- **Moodle w Telegramie.** `/kursy` (`/courses`): kurs → sekcje → zawartość, każdy element z najprzydatniejszym linkiem – Twoją kopią pliku na Dysku (otwiera się tylko dla Ciebie), linkiem udostępnionym przez prowadzącego, linkami z etykiet albo aktywnością w Moodle. `/dzis` (`/today`): co pojawiło się dziś we wszystkich kursach, albo `/dzis wczoraj`, `/dzis 12.10`, z ◀ ▶ między dniami.
- **Oddawanie zadań** (z `MOODLE_ACTIONS=1`): wysyłasz botowi plik, wybierasz zadanie, bot sprawdza dozwolone formaty, rozmiar i to, czy oddanie da się jeszcze zmienić, nazywa plik jak zadanie (`SUBMISSION_NAME`, domyślnie `{assignment} {course} {student_id}`), pokazuje podsumowanie i wysyła dopiero po ✅. „Prześlij do oceny” to osobny przycisk.
- **Posty na forach** (`/forum`): kurs → forum → temat → treść → podgląd → ✅.
- **Obecność** (`/obecnosc`, `/attendance` albo wyślij link z QR / zdjęcie kodu QR): bot otwiera stronę obecności zalogowany jako Ty (autologowanie, jak aplikacja Moodle), pokazuje statusy dozwolone przez prowadzącego („Obecny” na górze) i wysyła wybrany dopiero po ✅; o hasło sesji pyta i od razu usuwa je z czatu. Wymaga `MOODLE_PRIVATE_TOKEN`, który zapisuje teraz `python -m moodle_sync token`.
- Wszystkie nowe komendy są w menu Telegrama. Domyślnie nadal tylko do odczytu: bez `MOODLE_ACTIONS=1` bot niczego w Moodle nie zmienia.

## 1.1.1 (2026-10)

- **Żadna uczelnia nie jest już wpisana na sztywno.** Adres katalogu ECTS to ustawienie (`STUDY_CATALOG` albo odczytany ze `STUDY_PLAN_URL`); `plan --search "nazwa" --catalog <adres>`; kreator konfiguracji pyta o niego.
- Dokumentacja i przykłady nie wymieniają już konkretnej uczelni; PRIVACY opisuje zapytania do katalogu.
- Lista zmian po polsku: ten plik.

## 1.1.0 (2026-10)

- **Foldery semestrów i karty przedmiotów.** Ustaw `STUDY_PLAN_URL` na swój kierunek w katalogu ECTS, a pliki trafią do `Semestr N/<przedmiot>/…`, z folderami nazwanymi jak przedmioty w planie studiów. Karta każdego przedmiotu (sylabus w PDF) pobiera się obok materiałów, jest sprawdzana co 30 dni, a o jej zmianie dostajesz powiadomienie. Przedmioty obowiązkowe dostają kartę, zanim pojawią się w Moodle; obieralne tylko wtedy, gdy masz ten kurs.
- Bez katalogu `STUDY_START=2025/2026-winter` numeruje semestry według dat rozpoczęcia kursów.
- `python -m moodle_sync plan` pokazuje semestry, przedmioty i kurs z Moodle, który trafia do każdego folderu; `plan --search "nazwa"` znajduje kierunek i jego specjalności; `plan --cards` pobiera karty od razu. Kreator konfiguracji ma na to opcjonalny krok.
- courses.json: `plan` (który to przedmiot) i `semester` (wymuszony semestr).
- Bot Telegram: `/plan` (semestry i przedmioty) i `/reorganize` (jednorazowe zatwierdzenie przeniesienia pobranych plików bez logowania się na Raspberry Pi).
- Włączenie nowego układu przenosi już pobrane pliki lokalnie i w chmurze, po jednorazowym `download --reorganize` (albo `/reorganize` w bocie). Gdy katalog nie działa, używany jest ostatnio zapisany plan; bez zapisanego planu nic nie jest przenoszone.

## 1.0.4 (2026-10)

- **`/update` w bocie Telegram**: pobiera najnowsze wydanie z GitHuba, uruchamia `pip install -r requirements.txt` tylko wtedy, gdy plik się zmienił, raz importuje nowy kod (selftest) i dopiero wtedy podmienia `moodle_sync/` i restartuje bota. `.env`, `courses.json`, `state.json`, tokeny Google i `downloads/` zostają nietknięte. Czeka, jeśli trwa synchronizacja, i żadna synchronizacja nie wystartuje w trakcie podmiany. Jeśli coś pójdzie nie tak, działa dalej stara wersja, a Ty widzisz błąd.
- **`/rollback`**: powrót do wersji sprzed ostatniego `/update` (zapisanej w `.update/previous`); drugi `/rollback` wraca do nowszej.
- Bot odświeża menu komend przy każdym starcie, więc nowe komendy pojawiają się bez `bot --setup`.
- Dla kopii rozpakowanych z archiwum wydania; w klonie git dalej używaj `git pull`.

## 1.0.3 (2026-09)

Wydanie porządkowe: bez zmian w działaniu.

- CI testuje każdą obsługiwaną wersję Pythona (3.10-3.14) na Linuksie oraz 3.10 i 3.14 na Windows i macOS.
- Dependabot co tydzień otwiera PR-y z aktualizacjami pakietów Pythona i GitHub Actions; workflowy używają `actions/checkout@v7` i `actions/setup-python@v7`.

## 1.0.2 (2026-09)

- **Kalendarz: koniec z podwójnymi kalendarzami.** Chwilowy błąd Google (wygasłe logowanie, 5xx) podczas sprawdzania kalendarzy był traktowany jak „kalendarz usunięty” i powstawał drugi kalendarz „<SITE_LABEL> – terminy”. Teraz kalendarz jest tworzony od nowa tylko wtedy, gdy Google naprawdę mówi, że go nie ma (404/410).
- **Kalendarz: ręcznie usunięty kalendarz jest odtwarzany w całości** przy następnym przebiegu. Wcześniej wracał dopiero po kolejnej zmianie w Moodle i tylko ze zmienionymi wydarzeniami. Odtworzenie nie wysyła powiadomień o „nowych terminach”.
- **Telegram:** długa wiadomość ucięta w środku znacznika lub encji HTML była odrzucana przez Telegram i ginęła. Teraz taka wiadomość dociera jako zwykły tekst.
- Bot Telegram przetrwa odpowiedź, która nie jest JSON-em (np. stronę błędu proxy), zamiast się zatrzymać.
- Wydania: wypchnięcie tagu wersji uruchamia testy i publikuje wydanie na GitHubie z opisem z tego pliku.

## 1.0.1 (2026-09)

- **Bezpiecznik:** jeśli zmiana ustawień przeniosłaby dużą część już pobranego archiwum, nic nie jest przenoszone ani pobierane, dopóki nie potwierdzisz tego przez `download --reorganize`. Powiadomienie o błędzie wyjaśnia dlaczego. Znalezione w praktyce: `LANGUAGE` zgubiło się w sklejonej linii `.env` i wszystkie foldery zaczęły zmieniać nazwy na angielskie.
- `doctor` pokazuje używany język i nazwy folderów oraz wykrywa zepsute linie `.env` (sklejone albo bez `=`).
- Nowa komenda `set KLUCZ WARTOŚĆ` do bezpiecznej zmiany `.env`. `.env` jest zawsze zapisywany z końcami linii LF.
- **Przeniesienia w chmurze są najpierw „bilansowane”.** Jedna lista folderu w chmurze, a potem tylko te przeniesienia, które są naprawdę potrzebne: już wykonane i tam-i-z-powrotem (A→B→A) nic nie kosztują, a łańcuchy się skracają. Działają po 3 naraz i zapisują postęp co 20 plików. Wcześniej przerwana reorganizacja oznaczała setki bezużytecznych wywołań rclone po ~8 s na Raspberry Pi, a „źródło nie istnieje” było błędnie ponawiane jako błąd.

## 1.0.0 (2026-09)

Pierwsze publiczne wydanie: uniwersalne narzędzie dla każdego Moodle.

- Pakiet Pythona `moodle_sync` z jednym CLI: `setup`, `doctor`, `run`, `token`, `download`, `upload`, `calendar`, `watch`, `courses`, `ics`, `bot`, `notify-test`.
- **Kreator konfiguracji:** rozpoznaje logowanie hasłem i przez SSO oraz zdobywa token (także przez `moodlemobile://`).
- **Pliki:** kategorie (Wykłady / Ćwiczenia / Laboratoria / Projekty / Inne) po polsku albo angielsku, własne reguły i nazwy w `courses.json`, automatyczne przenoszenie po zmianie reguł (lokalnie i w chmurze), bezpieczne nazwy plików dla Windows i Linuksa, limit rozmiaru.
- **Chmura:** rclone (Dysk Google, OneDrive, Dropbox...) albo po prostu folder synchronizowany przez aplikację; kopia `state.json`.
- **Kalendarz:** synchronizacja z Kalendarzem Google z ✅ dla oddanych prac, osobny kalendarz na zajęcia, powiadomienia o przesuniętych terminach; link subskrypcji `.ics` dla innych kalendarzy.
- **Obserwowanie:** ogłoszenia i oceny (z komentarzem prowadzącego), ograniczone tempo zapytań, bez zalewu powiadomień przy pierwszym przebiegu czy po dodaniu nowego forum.
- **Powiadomienia:** Telegram (z komendami), webhook Discord, ntfy, e-mail; wyciszanie według rodzaju; podsumowanie tygodnia; alarm healthchecks.io.
- **Uruchamianie:** ręczne skróty, Harmonogram zadań Windows, launchd na macOS, timer użytkownika na Linuksie, usługi systemd na Raspberry Pi / serwerze z automatycznymi aktualizacjami bezpieczeństwa.
- Interfejs i dokumentacja po polsku i angielsku, testy i CI na Windows, macOS i Linuksie.

## 0.x

Prywatne skrypty dla Moodle jednej uczelni, z których wyrósł ten projekt.
