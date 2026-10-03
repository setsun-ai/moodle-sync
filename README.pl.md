# moodle-sync

[![CI](https://github.com/setsun-ai/moodle-sync/actions/workflows/ci.yml/badge.svg)](https://github.com/setsun-ai/moodle-sync/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/setsun-ai/moodle-sync)](https://github.com/setsun-ai/moodle-sync/releases/latest)
![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)
[![Licencja: MIT](https://img.shields.io/badge/licencja-MIT-green)](LICENSE)

🇬🇧 **[English version →](README.md)**

**Nie przegap już żadnego materiału, terminu ani ogłoszenia z Moodle.**
moodle-sync pobiera pliki z Twoich kursów do uporządkowanych folderów w chmurze, wpisuje terminy do kalendarza i powiadamia Cię na telefonie o nowościach. Działa z każdym Moodle, na Windows, macOS, Linuksie i Raspberry Pi.

> ⚖️ **Tylko do użytku osobistego.** Materiały z kursów są objęte prawem autorskim prowadzących, a ogłoszenia mogą zawierać
> dane innych studentów. Trzymaj wszystko **prywatnie** i przestrzegaj regulaminów uczelni. Zanim zaczniesz, przeczytaj
> **[Zasady korzystania](docs/pl/responsible-use.md)** i **[Prywatność](PRIVACY.md#po-polsku)**.

```
📚 Nowe materiały (3)
• Algorytmy: Wykład 5 - grafy.pdf
• Algorytmy: lab5_instrukcja.pdf
• Bazy danych: wymagania_projekt.docx

📅 Zmienione terminy (1)
• 12.11 23:59  ⏰ [Bazy danych] Sprawozdanie z lab 3 (termin oddania)

🎓 Ocena: 90 / 100 — Sprawozdanie z lab 2
Bazy danych
Komentarz prowadzącego: Dobra robota, uwagi w sekcji 3.
```

## Co potrafi

- 📂 **Pliki → foldery w chmurze.** Każdy przedmiot jest podzielony na *Wykłady / Ćwiczenia / Laboratoria / Projekty / Inne*. Plik podmieniony przez prowadzącego aktualizuje się na miejscu. Działa z Dyskiem Google, OneDrive (także uczelnianym Microsoft 365), Dropboxem i [ponad 70 innymi](https://rclone.org) albo w ogóle bez chmury.
- 📅 **Terminy → Kalendarz Google.** Oddane zadania dostają ✅ i przestają przypominać. Przesunięte terminy się aktualizują, a Ty dostajesz powiadomienie. Zajęcia trafiają do osobnego kalendarza, który możesz ukryć. Outlook i kalendarz Apple mogą zamiast tego korzystać z linku subskrypcji.
- 📢 **Ogłoszenia i 🎓 oceny** od prowadzących trafiają prosto na telefon, razem z komentarzem prowadzącego.
- 🔔 **Kanał do wyboru:** Telegram (z komendami `/terminy`, `/sync`...), Discord, ntfy albo e-mail.
- 🧙 **Kreator konfiguracji:** sam sprawdza, jak loguje Twoja uczelnia (hasło czy SSO), i prowadzi krok po kroku. `doctor` sprawdza całość.
- 🖥️ **Działa, jak chcesz:** dwuklik, kiedy masz ochotę, automatycznie, gdy komputer jest włączony, albo 24/7 na Raspberry Pi.
- 🌍 **Po polsku i po angielsku:** komunikaty, bot i dokumentacja.
- 🔒 **Prywatnie i tylko do odczytu:** Twoje dane zostają na Twoim komputerze i w Twojej chmurze. Niczego nie oddaje ani nie publikuje.

## Szybki start

1. Zainstaluj **Pythona 3.10+** ([jak](docs/pl/getting-started.md#1-zainstaluj-pythona-310-lub-nowszy)).
2. Na tej stronie kliknij **Code → Download ZIP** i rozpakuj.
3. Kliknij dwukrotnie **`install.bat`** na Windows albo uruchom `bash install.sh` na macOS/Linuksie i idź za kreatorem.

Pełna instrukcja: **[Pierwsze kroki](docs/pl/getting-started.md)**.

## Jak uruchamiać

| Masz... | Zrób tak |
|---|---|
| laptopa i synchronizujesz, kiedy chcesz | dwuklik `sync.bat` / `./sync.sh` |
| komputer włączony w ciągu dnia | [automatycznie co 30 min](docs/pl/running.md#automatycznie-na-komputerze) (Harmonogram zadań Windows / macOS / Linux) |
| Raspberry Pi albo serwer domowy | [24/7 co 15 min + bot Telegram](docs/pl/raspberry-pi.md) |

## Dokumentacja

| | |
|---|---|
| [Pierwsze kroki](docs/pl/getting-started.md) | Instalacja, kreator, wszystkie komendy |
| [Token](docs/pl/token.md) | Jak działa dostęp do Moodle: SSO, odnawianie, unieważnianie |
| [Uruchamianie](docs/pl/running.md) | Ręcznie, automatycznie, przenosiny na inną maszynę |
| [Raspberry Pi](docs/pl/raspberry-pi.md) | Praca 24/7, utrzymanie, odzyskiwanie |
| [Powiadomienia](docs/pl/notifications.md) | Telegram, Discord, ntfy, e-mail, alarm „nie działa” |
| [Chmura](docs/pl/storage.md) | Folder synchronizowany, Dysk Google, OneDrive, rclone |
| [Kalendarz](docs/pl/google-calendar.md) | Synchronizacja z Kalendarzem Google albo link subskrypcji |
| [Konfiguracja](docs/pl/configuration.md) | Wszystkie opcje, `courses.json`, kategorie |
| [Problemy i FAQ](docs/pl/troubleshooting.md) | Błędy i pytania |
| [Jak to działa](docs/pl/how-it-works.md) | Architektura i decyzje projektowe, do nauki |
| [Zasady korzystania](docs/pl/responsible-use.md) · [Prywatność](PRIVACY.md#po-polsku) · [Bezpieczeństwo](SECURITY.md#po-polsku) | Prawa autorskie, regulaminy uczelni, dokąd trafiają dane |

## Czy tak wolno? Czy to bezpieczne?

- **Dozwolony sposób:** moodle-sync korzysta z **oficjalnego API aplikacji mobilnej Moodle** na **Twoim własnym** koncie, tak samo jak aplikacja Moodle na telefonie. Tylko **czyta** Twoje dane i robi to kulturalnie: kilkadziesiąt zapytań na przebieg, z identyfikatorem, który podaje nazwę projektu.
- **Materiały zostają prywatne:** należą do autorów. Trzymaj je w **swojej prywatnej** chmurze i **nigdy nie udostępniaj folderu ani linków publicznie**. Nie przesyłaj też dalej ogłoszeń z cudzymi danymi. → **[Zasady korzystania](docs/pl/responsible-use.md)**
- **Twoje dane:** zostają na Twoim komputerze i w usługach, które **Ty** wybierzesz. Projekt nie ma serwerów ani telemetrii. → **[Prywatność](PRIVACY.md#po-polsku)**
- **Token to odpowiednik hasła:** zostaje w `.env` i nigdy nie trafia do logów ani do sieci. → **[Bezpieczeństwo](SECURITY.md#po-polsku)**
- **Brak powiązań** z Moodle ani żadną uczelnią i brak gwarancji. Ważne terminy zawsze sprawdzaj też w samym Moodle.

## Współtworzenie

Pomysły, zgłoszenia błędów i pull requesty są mile widziane. Zobacz [CONTRIBUTING.md](CONTRIBUTING.md). Dopiero zaczynasz z open source? Znajdziesz tam zadania na start.

## Licencja

[MIT](LICENSE). Stworzone przez studenta, dla studentów z każdej uczelni.
