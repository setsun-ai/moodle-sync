# Powiadomienia

🇬🇧 [English version](../en/notifications.md) · [← README](../../README.pl.md)

Wszystkie kanały są opcjonalne i można je łączyć. Kreator (`python -m moodle_sync setup`) je konfiguruje i wysyła wiadomość testową; `python -m moodle_sync notify-test` wyśle kolejną w dowolnej chwili.

## Co dostajesz

| | Kiedy | Wyciszenie |
|---|---|---|
| 📚 Nowe materiały | pobrano nowe albo podmienione pliki | `NOTIFY_FILES=0` |
| 📅 Nowe / zmienione terminy | prowadzący dodał albo **przesunął** termin (wymaga [kalendarza Google](google-calendar.md)) | `NOTIFY_DEADLINES=0` |
| 📢 Ogłoszenie | nowy wpis na forum *Ogłoszenia* kursu: pełna treść + link | `NOTIFY_ANNOUNCEMENTS=0` |
| 🎓 Ocena | nowa albo zmieniona ocena zadania lub quizu, z komentarzem prowadzącego | `NOTIFY_GRADES=0` |
| 🚨 Błąd | coś nie działa. Powiadomienie mówi, co zrobić (np. „odnów token”). Ten sam błąd najwyżej raz na 6 h | `NOTIFY_ERRORS=0` |
| ✅ Podsumowanie tygodnia | w niedzielę wieczorem: co przyszło + terminy na 7 dni | `NOTIFY_SUMMARY=0` |

Pierwsze uruchomienie tylko *zapamiętuje* istniejące ogłoszenia i oceny, więc nie dostaniesz 50 powiadomień o starych rzeczach.

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

**Komendy.** Działają w obu językach, a menu pod **/** idzie za `LANGUAGE`:

| | |
|---|---|
| `/terminy` `/deadlines` | najbliższe terminy (14 dni) prosto z Moodle, ✅ = już oddane |
| `/nowe` `/new` | ostatnio pobrane materiały |
| `/oceny` `/grades` | ostatnie oceny |
| `/status` | ostatni przebieg, wynik każdego kroku, wolne miejsce, czas działania |
| `/kursy` `/courses` | kurs → sekcje → materiały, z linkami do kopii na Dysku, udostępnionymi linkami i Moodle |
| `/dzis` `/today` | co pojawiło się dziś w kursach; `/dzis wczoraj`, `/dzis 12.10` = wybrany dzień |
| `/oddaj` `/submit` albo po prostu wyślij plik | oddaj go do zadania (wymaga `MOODLE_ACTIONS=1`, zobacz [Konfiguracja](configuration.md)) |
| `/forum` | załóż wątek na forum kursu (`MOODLE_ACTIONS=1`) |
| `/obecnosc` `/attendance` albo wyślij link / zdjęcie QR | zaznacz obecność (`MOODLE_ACTIONS=1`) |
| `/obieralne` `/electives` | wybierz przedmioty obieralne (plan studiów) |
| `/przypisz` `/assign` | przypisz kurs z Moodle do przedmiotu albo modułu z planu |
| `/porzadki` `/cleanup` | znajdź i usuń stare kopie plików po przenosinach (po potwierdzeniu) |
| `/sync` | synchronizuj teraz |
| `/update` | zainstaluj najnowsze wydanie z GitHuba i zrestartuj bota (kopia rozpakowana z archiwum wydania; w klonie git użyj `git pull`) |
| `/rollback` | wróć do wersji sprzed ostatniego `/update` |
| `/plan` | semestry i przedmioty z planu studiów (zobacz [Konfiguracja](configuration.md)) |
| `/reorganize` | zatwierdź przeniesienie pobranych plików do nowego układu, np. folderów semestrów |
| `/pomoc` `/help` | lista komend |

- Komendy wymagają działającego procesu bota: `python -m moodle_sync bot`. Na Raspberry Pi działa on jako usługa automatycznie ([instrukcja](raspberry-pi.md)).
- Powiadomienia działają **bez** procesu bota.
- Bot odpowiada **tylko Twojemu czatowi**, a wszystkich innych ignoruje.

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
