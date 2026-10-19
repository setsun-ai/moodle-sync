# Powiadomienia

🇬🇧 [English version](../en/notifications.md) · [← README](../../README.pl.md)

Wszystkie kanały są opcjonalne i można je łączyć. Kreator (`python -m moodle_sync setup`) je konfiguruje i wysyła wiadomość testową; `python -m moodle_sync notify-test` wyśle kolejną w dowolnej chwili.

## Co dostajesz

| | Kiedy | Wyciszenie |
|---|---|---|
| 📚 Nowe materiały | pobrano nowe albo podmienione pliki, pogrupowane według kursów. W Telegramie z przyciskami **⬇️ Pobierz** | `NOTIFY_FILES=0` |
| 📅 Nowe / zmienione terminy | prowadzący dodał albo **przesunął** termin (wymaga [kalendarza Google](google-calendar.md)) | `NOTIFY_DEADLINES=0` |
| ⏰ Przypomnienie | zadanie albo quiz, którego **jeszcze nie oddałeś**, ma termin za 24 h i ponownie za 3 h (`REMIND_HOURS`). Nigdy o tym, co już oddane | `NOTIFY_REMINDERS=0` |
| 📢 Ogłoszenie | nowy wpis na forum *Ogłoszenia* kursu: pełna treść + link | `NOTIFY_ANNOUNCEMENTS=0` |
| 🎓 Ocena | nowa albo zmieniona ocena zadania lub quizu, z komentarzem prowadzącego | `NOTIFY_GRADES=0` |
| 🚨 Błąd | coś nie działa albo kończy się miejsce na dysku (`LOW_DISK_GB`, raz dziennie). Powiadomienie mówi, co zrobić (np. „odnów token”). Ten sam błąd najwyżej raz na 6 h. Serwer, który nie odpowiada, albo brak sieci: dopiero po 2 synchronizacjach z rzędu, bez tracebacku (jest w `/bledy`) | `NOTIFY_ERRORS=0` |
| ✅ Podsumowanie tygodnia | w niedzielę wieczorem: co przyszło + terminy na 7 dni, razem z drugim Moodle (`OTHER_SITES`) | `NOTIFY_SUMMARY=0` |

Pierwsze uruchomienie tylko *zapamiętuje* istniejące ogłoszenia i oceny, więc nie dostaniesz 50 powiadomień o starych rzeczach.

- **Cisza nocna:** `QUIET_HOURS=23-7` - w nocy powiadomienia dalej przychodzą od razu, ale bez dźwięku (Telegram: wyciszone, ntfy: niski priorytet), więc nic nie czeka do rana i nic Cię nie budzi.
- **Dwa Moodle na jednym czacie:** `NOTIFY_LABEL=1` w `.env` drugiej kopii dodaje `[UG]` (jej `SITE_LABEL`) przed tytułem jej powiadomień.

## Który kanał?

| | Telegram | Discord | ntfy | E-mail |
|---|---|---|---|---|
| Czas konfiguracji | 3 min | 2 min | 1 min | 5 min |
| Komendy (`/terminy`, `/sync`...) | ✅ | – | – | – |
| Potrzebne konto | Telegram | Discord | żadne | poczta z SMTP |

## Telegram (polecany)

1. W Telegramie otwórz **@BotFather** (niebieski znaczek) i wyślij `/newbot`.
2. Podaj nazwę (np. *Mój Moodle*) i login kończący się na `bot`.
3. Skopiuj **token** (`123456789:AAH...`). Kreator o niego zapyta; możesz też wpisać go do `.env` jako `TELEGRAM_BOT_TOKEN=...`.
4. Połącz bota ze swoim czatem:
   ```
   python -m moodle_sync bot --setup
   ```
   Napisz cokolwiek do swojego bota. Skrypt zapisze Twój `TELEGRAM_CHAT_ID`, a bot odpisze „Połączono!”.

**Komendy.** Działają w obu językach. Menu pod **/** (w Twoim `LANGUAGE`) pokazuje tylko te na co dzień;
**`/menu`** (albo `/start`) otwiera wszystko jako kafelki w jednej wiadomości – kafelek otwiera się w miejscu,
**↩️ Menu** wraca. Każda komenda z tabeli nadal działa, gdy ją wpiszesz:

| | |
|---|---|
| `/menu` `/start` | wszystko jako kafelki: 📅 terminy, 📚 nowe, 🎓 oceny, 📘 kursy, 🗓 dziś, 🔎 szukaj, ✋ obecność, ⚙️ ustawienia oraz grupy 🗂 Studia ▸ i 🛠 Serwis ▸ (oddawanie i forum pojawiają się przy `MOODLE_ACTIONS=1`, Studia przy planie studiów) |
| `/terminy` `/deadlines` | najbliższe terminy (14 dni) prosto z Moodle, ✅ = już oddane; także drugiego Moodle (`OTHER_SITES`) |
| `/nowe` `/new` | ostatnio pobrane materiały, także z drugiego Moodle |
| `/oceny` `/grades` | ostatnie oceny, także z drugiego Moodle |
| `/status` | ostatni przebieg, wynik każdego kroku, wolne miejsce, czas działania - także drugiego Moodle |
| `/kursy` `/courses` | kurs → sekcje → materiały, z linkami do kopii na Dysku, udostępnionymi linkami i Moodle. Kursy drugiego Moodle (`OTHER_SITES`) też są na liście, jako „UG · kurs”. Ukryte kursy czekają pod **🙈 Ukryte** ([niżej](#ukryte-kursy)) |
| `/dzis` `/today` | co pojawiło się dziś w kursach (na każdym Moodle); `/dzis wczoraj`, `/dzis 12.10` = wybrany dzień |
| `/oddaj` `/submit` albo po prostu wyślij plik | oddaj go do zadania (wymaga `MOODLE_ACTIONS=1`, zobacz [Konfiguracja](configuration.md)) |
| `/forum` | załóż wątek na forum kursu (`MOODLE_ACTIONS=1`) |
| `/obecnosc` `/attendance` albo wyślij link / zdjęcie QR | zaznacz obecność (`MOODLE_ACTIONS=1`) |
| `/obieralne` `/electives` | wybierz przedmioty obieralne (plan studiów) |
| `/przypisz` `/assign` | przypisz kurs z Moodle do przedmiotu albo modułu z planu, zmień nazwę folderu, dodaj semestr |
| `/karta` `/card` | Twój link do karty przedmiotu spoza katalogu |
| `/bledy` `/errors` | ostatnia synchronizacja krok po kroku, z pełnym wynikiem kroków z błędem - także drugiego Moodle |
| `/ustawienia` `/settings` | włączaj i wyciszaj rodzaje powiadomień, wybierz ciszę nocną i godziny przypomnień - także drugiego Moodle, bez SSH (zapisuje `.env`); **📘 Ustawienia kursów** dla każdego kursu osobno ([niżej](#ustawienia-kursów)) |
| `/szukaj` `/search` | znajdź pobrany plik po kursie albo nazwie na każdym Moodle (`/szukaj wyklad 3`, polskie znaki niepotrzebne), z przyciskami **⬇️** |
| `/porzadki` `/cleanup` | znajdź i usuń stare kopie plików po przenosinach (po potwierdzeniu) |
| `/sync` | synchronizuj teraz: aktualne kursy (jak timer), wybrany kurs albo **🙈 pliki z ukrytych kursów** |
| `/pauza` `/pause` | wstrzymaj synchronizację na 1 dzień, 7 dni albo do odwołania i wznów ją - także drugiego Moodle (`OTHER_SITES`, zobacz [Konfiguracja](configuration.md)). Wstrzymana kopia niczego nie pobiera i nic nie wysyła; timer działa dalej, a healthchecks nadal dostaje sygnał |
| `/update` | zainstaluj najnowsze wydanie z GitHuba i zrestartuj bota (kopia rozpakowana z archiwum wydania; w klonie git użyj `git pull`) |
| `/rollback` | wróć do wersji sprzed ostatniego `/update` |
| `/plan` | semestry i przedmioty z planu studiów (zobacz [Konfiguracja](configuration.md)) |
| `/reorganize` | zatwierdź przeniesienie pobranych plików do nowego układu, np. folderów semestrów |
| `/pomoc` `/help` | lista komend |

- Komendy wymagają działającego procesu bota: `python -m moodle_sync bot`. Na Raspberry Pi działa on jako usługa automatycznie ([instrukcja](raspberry-pi.md)).
- Powiadomienia działają **bez** procesu bota.
- **⬇️ Pobierz** pod *Nowymi materiałami*: bot wysyła Ci sam plik, z `DOWNLOAD_DIR` albo, przy `KEEP_LOCAL=0`, pobrany z chmury. Przycisk dla każdego pliku (pierwszych 6) i *Pobierz wszystkie*. Telegram pozwala botowi wysłać najwyżej 50 MB; przy większym pliku dostajesz link do kopii na Dysku. Jeśli nie uruchamiasz procesu bota, ustaw `TELEGRAM_FILE_BUTTONS=0`.
- Bot odpowiada **tylko Twojemu czatowi**, a wszystkich innych ignoruje.

### Ustawienia kursów

Każdy kurs ustawisz osobno: **/ustawienia → 📘 Ustawienia kursów** albo **/kursy → kurs → ⚙️ Ustawienia kursu**.
Kliknięcie włącza ✅ albo wyłącza 🔕:

| | |
|---|---|
| Materiały | powiadomienie *Nowe materiały* (pliki i tak się pobierają) |
| Ogłoszenia | nowe ogłoszenia |
| Oceny | nowe oceny |
| Zmiany terminów | *Nowe / zmienione terminy*. Zauważa je synchronizacja kalendarza, więc potrzebują włączonych *Terminów w kalendarzu* |
| Przypomnienia | przypomnienia o tym, czego jeszcze nie oddałeś |
| Terminy w kalendarzu | terminy kursu w kalendarzu Google „– terminy”. Po wyłączeniu znikają z niego; po ponownym włączeniu wracają bez powiadomienia o „nowych terminach” |
| Zajęcia w kalendarzu | zajęcia kursu w kalendarzu „– zajęcia” |
| 📨 Pliki na czat | **domyślnie wyłączone.** Nowe pliki kursu przychodzą na czat Telegrama jako dokumenty, bez klikania ⬇️ (do 10 na synchronizację, do 50 MB każdy; większe zostają z przyciskiem ⬇️). Działa bez procesu bota. `/ustawienia` → **📨 Nowe pliki na czat: wszystkie kursy** włącza je dla wszystkich kursów (`AUTOSEND_FILES=1`) |

- **🔕 Wycisz cały kurs** wyłącza wszystko naraz (**🔔 Włącz wszystko** nie rusza 📨); lista pokazuje 🔔 wszystko włączone, 🔉 część wyciszona, 🔕 wszystko wyłączone.
- Przełączniki z /ustawienia nadal obowiązują: rodzaj wyciszony tam jest wyciszony dla każdego kursu (ekran kursu o tym mówi).
- Te ustawienia decydują o tym, co bot Ci **wysyła sam**. Gdy pytasz – `/terminy`, `/dzis`, `/kursy`, `/oceny`, podsumowanie tygodnia – widzisz każdy kurs, który nie jest ukryty.
- Pod ogłoszeniem i oceną jest **🔕 Wycisz to z tego kursu**: jedno kliknięcie i ten rodzaj z tego kursu milknie, także dla drugiego Moodle (`OTHER_SITES`). `TELEGRAM_FILE_BUTTONS=0` ukrywa go razem z przyciskami pobierania.
- Bot zapisuje wybory w `course_settings.json` obok `state.json`; trafia on do kopii w chmurze i wraca z nią przez `restore`. Bez bota użyj `"mute"` w [`courses.json`](configuration.md#coursesjson).

### Ukryte kursy

Jak *Ukryj z panelu* na eNauczaniu: stare semestry i kursy, których nie śledzisz, nie przeszkadzają.

- **Kurs ukryty na panelu Moodle jest ukryty i tutaj.** W bocie: `/kursy` → kurs → **🙈 Ukryj kurs**, a **👁 Pokaż kurs** go przywraca.
- Ukryty kurs **nie synchronizuje się**: żadnych plików, wpisów w kalendarzu, ogłoszeń, ocen ani przypomnień, i znika z `/kursy`, `/dzis` i `/terminy`. Już pobrane pliki zostają na miejscu.
- `/kursy` pokazuje aktualne kursy i przycisk **🙈 Ukryte (N)** z resztą. `/sync` → **🙈 Pliki z ukrytych kursów** pobiera ich pliki raz, na żądanie; pojedynczy kurs też z **📚 Wybierz kurs**.
- Po ponownym pokazaniu wpisy w kalendarzu wracają bez powiadomienia o „nowych terminach”, a stare ogłoszenia nie przychodzą drugi raz; ocena wystawiona w międzyczasie przyjdzie.
- Przy `MOODLE_ACTIONS=1` ukrycie w bocie ukrywa kurs także na panelu Moodle (to samo ustawienie, które zmienia aplikacja Moodle). Bez tego albo gdy Moodle odmówi, kurs jest ukryty tylko w bocie.

## Discord

Powiadomienia idą przez **webhook**, czyli adres, który publikuje na jednym kanale. Nie trzeba hostować bota.

1. Załóż serwer tylko dla siebie (**+** w Discordzie → *Stwórz własny*) albo użyj kanału, którym zarządzasz.
2. **Ustawienia kanału → Integracje → Webhooki → Nowy webhook → Kopiuj URL webhooka.**
3. Podaj go kreatorowi albo ustaw `DISCORD_WEBHOOK_URL=...`.

Wiadomości nikogo nie oznaczają. `@everyone` w poście z forum jest pokazywane jako zwykły tekst.

> Czemu bez komend na Discordzie? Wymagałyby stale połączonego bota i większej biblioteki. Komendy obsługuje Telegram; bot na Discorda to świetny [pomysł na kontrybucję](../../CONTRIBUTING.md).

## ntfy

Darmowe powiadomienia push bez zakładania konta: <https://ntfy.sh>.

1. Zainstaluj aplikację **ntfy** (Android / iOS).
2. Kliknij **+ → Subscribe to topic** i wpisz długą, losową nazwę, np. `moodle-7f3k9x2qa81`. Kreator ją zaproponuje.
3. Ustaw `NTFY_TOPIC=moodle-7f3k9x2qa81`.

Nazwa tematu działa jak hasło: kto ją zna, czyta Twoje wiadomości. Niech będzie losowa. ntfy możesz też postawić u siebie (`NTFY_SERVER`).

## E-mail

```
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=ty@example.com
SMTP_PASSWORD=abcd efgh ijkl mnop
EMAIL_TO=ty@example.com
```

- **Gmail** wymaga **hasła do aplikacji**, a nie zwykłego hasła. Utworzysz je w *Konto Google → Bezpieczeństwo → Weryfikacja dwuetapowa → Hasła do aplikacji*, co wymaga włączonej weryfikacji dwuetapowej.
- **Konta Outlook/Microsoft** w większości nie pozwalają już na zwykłe hasła SMTP. Wybierz Gmail albo inny kanał.
- Port 465 = SSL, każdy inny = STARTTLS.

## Alarm „nie działa” (healthchecks.io)

Gdy komputer albo Raspberry Pi z synchronizacją padnie, nie może Ci o tym powiedzieć. [healthchecks.io](https://healthchecks.io) (darmowe) działa odwrotnie: każdy przebieg melduje „żyję”, a gdy meldunki ustaną, **serwis** wysyła alarm, także na Telegram albo Discord.

1. Załóż konto i kliknij **Add Check**.
2. Harmonogram:
   - **Period:** częstotliwość synchronizacji (np. 15 min),
   - **Grace:** 1 godzina, żeby wybaczyć krótkie przerwy w Wi-Fi.
3. Skopiuj **Ping URL** do `.env`: `HEALTHCHECK_URL=https://hc-ping.com/<uuid>`.
4. **Integrations:** dodaj Telegram, Discord albo e-mail.

Nieudane przebiegi też są zgłaszane (`/fail`), a na stronie widać podsumowanie każdego przebiegu.

Przy laptopie, który bywa wyłączony, alarm „nie działa” nie ma większego sensu. Tam wystarczy podsumowanie tygodnia.
