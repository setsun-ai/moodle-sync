# Contributing / Współtworzenie

🇬🇧 English below · 🇵🇱 [po polsku niżej](#po-polsku)

Thanks for helping! This project is meant to be friendly to first-year students. A first pull request is very welcome.

## Setup

```bash
git clone https://github.com/setsun-ai/moodle-sync.git
cd moodle-sync
python -m venv .venv
.venv/bin/pip install -r requirements-dev.txt      # Windows: .venv\Scripts\pip ...
.venv/bin/python -m pytest                          # all tests must pass
.venv/bin/python -m ruff check .                    # lint must be clean
```

Read [How it works](docs/en/how-it-works.md) first. It explains the structure and the "why" behind it.

## Rules of thumb

- **Every user-facing text goes through `t("key")`.** Add the key to `moodle_sync/i18n.py` in **both** languages. A test checks this.
- **Pure logic gets a test** in `tests/`. Tests must never need the network or a real account; `conftest.py` isolates them.
- **Never log secrets.** Pass error texts through `moodle.redact()` / `notify._redact()`.
- **Be polite to university servers:** no new per-file or per-minute API loops without throttling.
- **Docs in both languages.** Changed behaviour means updated `docs/en/*` **and** `docs/pl/*`.
- Small, focused pull requests with a clear description.

## Good first issues

- 🌍 A new language (add `"de"`, `"uk"`... to every entry in `i18n.py` and `FOLDER_NAMES`).
- 💬 Discord bot **commands** (today Discord only receives notifications).
- 🔔 Matrix / Slack / Signal notification channels (`notify.py`).
- 📅 Export deadlines to an `.ics` file in `DOWNLOAD_DIR`.
- 🐳 A Dockerfile for NAS users.
- 🧪 More tests, e.g. for `storage.py` with a fake `rclone`.

Found a bug? Open an issue with the output of `python -m moodle_sync doctor`. Remove your name and anything personal from it first.

---

## Po polsku

Dzięki za pomoc! Projekt ma być przyjazny dla pierwszoroczniaków, więc pierwszy pull request jest bardzo mile widziany.

**Zasady w skrócie:**
- Uruchom testy (`python -m pytest`) i lint (`python -m ruff check .`); oba muszą przechodzić. Zacznij od lektury [Jak to działa](docs/pl/how-it-works.md).
- Każdy tekst dla użytkownika idzie przez `t("klucz")` z tłumaczeniem PL **i** EN w `i18n.py`.
- Czysta logika dostaje test, a testy nie mogą wymagać sieci ani konta.
- Sekrety nigdy nie trafiają do logów.
- Nie obciążaj serwerów uczelni.
- Dokumentację zmieniaj w obu językach.

**Pomysły na start:**
- nowy język,
- komendy dla bota Discord,
- powiadomienia przez Matrix, Slack albo Signal,
- eksport terminów do `.ics`,
- Dockerfile,
- więcej testów.

Błąd? Załóż zgłoszenie (issue) z wynikiem `python -m moodle_sync doctor`, z którego wcześniej usuniesz imię, nazwisko i inne dane osobiste.
