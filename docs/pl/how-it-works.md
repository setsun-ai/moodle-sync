# Jak to działa (dla ciekawskich)

🇬🇧 [English version](../en/how-it-works.md) · [← README](../../README.pl.md)

moodle-sync jest mały (~2000 linii), ale zbudowany jak „prawdziwe” oprogramowanie. Ta strona wyjaśnia decyzje, które za nim stoją. Każda z nich rozwiązuje problem, na który trafisz we własnych projektach.

## Architektura

```
                     ┌──────────── python -m moodle_sync run  (runner.py) ────────────┐
Moodle REST API ───► │ 1. files.py      nowe pliki         -> DOWNLOAD_DIR             │
(moodle.py)          │ 2. storage.py    DOWNLOAD_DIR       -> chmura (rclone)          │
                     │ 3. calendar_sync terminy            -> Kalendarz Google         │
                     │ 4. watch.py      ogłoszenia/oceny   -> powiadomienia            │
                     └──────────────┬──────────────────────────────────────┬──────────┘
                                    │ state.json (pamięć między przebiegami)│ notify.py
                                    ▼                                      ▼
                             state.py (zapis atomowy)         Telegram / Discord / ntfy / e-mail
```

| Plik | Rola |
|---|---|
| `__main__.py` | Wiersz poleceń (podkomendy argparse). |
| `config.py` | Ustawienia z `.env`, czytane w chwili użycia, żeby kreator mógł je zmieniać na żywo. |
| `moodle.py` | Klient API: ponawianie, błędy, zdobywanie tokenu. |
| `files.py` | Skanowanie, kategorie, pobieranie, przenoszenie plików. |
| `storage.py` | Wysyłka przez rclone. |
| `calendar_sync.py` | Kalendarz Google. |
| `watch.py` | Ogłoszenia i oceny. |
| `courseprefs.py` | Ustawienia kursów: co każdy kurs może wysyłać i wpisywać do kalendarza. Zapisuje je bot, kroki tylko czytają. |
| `notify.py` | Kanały powiadomień. |
| `telegram_bot.py` | Komendy bota. |
| `runner.py` | Uruchamia wszystkie kroki, obsługuje błędy, podsumowanie tygodnia. |
| `setup_wizard.py`, `doctor.py` | Kreator i diagnostyka. |
| `i18n.py` | Wszystkie teksty dla użytkownika, po polsku i angielsku. |
| `textutil.py` | Czyste funkcje tekstowe: nazwy wielojęzyczne, HTML na tekst, bezpieczne nazwy plików. |

## Pomysły warte ściągnięcia

**1. Idempotencja: dwa uruchomienia = jedno.**
- Każdy krok sprawdza, co już zrobiono (`state.json`), i robi tylko resztę.
- Wydarzenia w kalendarzu mają **stały identyfikator** wyliczony z id w Moodle, więc ponowne wysłanie aktualizuje wydarzenie zamiast tworzyć duplikat.
- rclone porównuje rozmiar i czas modyfikacji.

Dlatego usunięcie `state.json`, awaria w połowie czy podwójne kliknięcie niczego nie psują.

**2. Tożsamość techniczna a tożsamość logiczna.**
- *Id* pliku to jego adres, który zawiera numer rewizji. Nowa wersja = nowe id = „pobierz ponownie”.
- *Klucz logiczny* (kurs + moduł + nazwa) się nie zmienia, więc nowa wersja **zastępuje** starą w tym samym miejscu zamiast tworzyć `plik (2).pdf`.
- Dwie różne rzeczy o tej samej nazwie dostają `(2)`. [`files.plan_paths`](../../moodle_sync/files.py)

**3. Żadnych plików zapisanych do połowy.**
- Pobieranie idzie do `nazwa.part`, a zmiana nazwy przez `os.replace` następuje dopiero po zakończeniu. Na każdym systemie `os.replace` jest *atomowe*: inny program widzi albo stary plik, albo nowy, nigdy połowę.
- `state.json` zapisujemy tak samo. Zanik prądu w trakcie zapisu go nie uszkodzi.

**4. Najpierw plan, potem różnica.**
Docelowa ścieżka *każdego* pliku jest liczona od zera przy każdym przebiegu. Zmiana reguł kategorii daje po prostu inny plan. Różnica między planem a `state.json` staje się listą przeniesień: lokalnie przez `os.replace`, w chmurze przez `rclone moveto`.

**5. Zakładaj, że sieć zawiedzie.**
- Zapytania są ponawiane z rosnącą przerwą (2 s, 5 s, 15 s), ale tylko przy problemach *przejściowych* (zerwane połączenie, timeout, HTTP 5xx). Błąd Moodle, np. „zły token”, nie jest ponawiany, bo ponawianie go nie naprawi.
- Kroki są niezależne: awaria jednego nie zatrzymuje pozostałych.

**6. Nie bądź upierdliwy.**
- **Stan zastany:** pierwsze sprawdzenie tylko zapamiętuje istniejące wpisy i oceny. Dotyczy to też każdego forum, które zacznie być obserwowane później: [dokładnie ten błąd się zdarzył](../../tests/test_moodle_calendar_watch.py) i teraz pilnuje go test regresji.
- **Ograniczanie powtórzeń:** ten sam błąd jest zgłaszany najwyżej raz na 6 h. „Ten sam” błąd rozpoznajemy po odcisku komunikatu z usuniętymi cyframi.
- **Uprzejmość wobec serwera:** fora są sprawdzane co 30 min, oceny co godzinę. User-Agent podaje nazwę projektu, więc administratorzy wiedzą, kto pyta.

**7. Sekrety nie wyciekają.**
- Tokeny są tylko w `.env`, który jest ignorowany przez gita.
- `requests` wkleja pełne adresy (z tokenem!) do komunikatów błędów, więc każdy błąd przechodzi przez `redact()` przed wypisaniem lub wysłaniem.
- Testy usuwają wszystkie sekrety ze środowiska, więc nie mogą przypadkiem wysłać Ci wiadomości.

**8. Kopiuj, nie synchronizuj.**
`rclone sync` zrobiłby z chmury lustro lokalnego folderu: usunięcie plików lokalnie usunęłoby je z chmury. `copy` może tylko dodawać. Wybieraj operację, której najgorszy skutek jesteś w stanie zaakceptować.

**9. Jedno uruchomienie naraz.**
Plik blokady (`msvcrt.locking` na Windows, `fcntl.flock` gdzie indziej) nie pozwala, żeby ręczne uruchomienie nałożyło się na zaplanowane. System sam zwalnia blokadę, gdy proces padnie.

**10. Każdy tekst da się przetłumaczyć.**
Teksty dla użytkownika idą przez `t("klucz")`. Test sprawdza, że każdy klucz użyty w kodzie istnieje w obu językach z tymi samymi `{polami}`.

## Testy

```
pip install -r requirements-dev.txt
python -m pytest
python -m ruff check .
```

- Testy obejmują czystą logikę: nazwy, kategorie, ścieżki, kolizje, dekodowanie, formatowanie powiadomień, ograniczanie powtórzeń, tłumaczenia.
- Nie potrzebują sieci ani konta.
- `tests/conftest.py` daje każdemu testowi osobny folder tymczasowy i puste środowisko.
- GitHub Actions uruchamia je na Windows, macOS i Linuksie przy każdym pushu ([`.github/workflows/ci.yml`](../../.github/workflows/ci.yml)).

## Pomysły na pierwszą kontrybucję

Zobacz [CONTRIBUTING.md](../../CONTRIBUTING.md). Kilka przykładów:
- bot Discord z komendami,
- powiadomienia przez Matrix,
- eksport terminów do pliku `.ics`,
- obraz Dockera,
- tłumaczenie na niemiecki (dodaj `"de"` w `i18n.py`).
