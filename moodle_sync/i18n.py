"""
Translations of everything the user sees: console output, notifications,
bot replies and the setup wizard. LANGUAGE=pl|en in .env.

Adding a language = adding a third entry to every message (a test checks
that all keys used in the code exist in every language).
"""

from . import config

WEEKDAYS = {
    "pl": ["pon", "wt", "śr", "czw", "pt", "sob", "nd"],
    "en": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
}

MESSAGES: dict[str, dict[str, str]] = {
    # --- general ---
    "error": {"pl": "BŁĄD: {error}", "en": "ERROR: {error}"},
    "dry_run_note": {"pl": "(--dry-run: niczego nie zmieniono)", "en": "(--dry-run: nothing was changed)"},
    "summary": {"pl": "podsumowanie", "en": "summary"},
    "result_skipped": {"pl": "pominięto (nieskonfigurowane)", "en": "skipped (not configured)"},
    "result_error": {"pl": "BŁĄD (kod {code})", "en": "ERROR (code {code})"},
    "run_busy": {"pl": "Inne uruchomienie jeszcze trwa - kończę.", "en": "Another run is still in progress - exiting."},
    "step_files": {"pl": "Pobieranie plików", "en": "Downloading files"},
    "step_storage": {"pl": "Wysyłka do chmury", "en": "Upload to cloud"},
    "step_calendar": {"pl": "Kalendarz", "en": "Calendar"},
    "step_watch": {"pl": "Ogłoszenia i oceny", "en": "Announcements and grades"},
    "course_skipped": {"pl": "[pominięto] {course}: {error}", "en": "[skipped] {course}: {error}"},
    "choose_number": {"pl": "Wybierz numer", "en": "Choose a number"},
    "yes_no_default_yes": {"pl": "[T/n]", "en": "[Y/n]"},
    "yes_no_default_no": {"pl": "[t/N]", "en": "[y/N]"},
    "attachments": {"pl": "Załączniki", "en": "Attachments"},

    # --- files ---
    "files_relocating": {"pl": "Przenoszenie {n} plików (zmiana kategorii/nazw):",
                         "en": "Moving {n} files (category/name change):"},
    "files_to_download": {"pl": "Do pobrania: {n} plików (~{mb:.1f} MB) -> {dir}",
                          "en": "To download: {n} files (~{mb:.1f} MB) -> {dir}"},
    "files_none": {"pl": "Brak plików do pobrania.", "en": "No files to download."},
    "files_too_large": {"pl": "pominięto: większy niż MAX_FILE_MB={mb:g}", "en": "skipped: larger than MAX_FILE_MB={mb:g}"},
    "files_incomplete": {"pl": "niepełny plik: {got} z {expected} B", "en": "incomplete file: {got} of {expected} B"},
    "files_summary": {"pl": "Pobrano: {ok}, błędy: {failed}", "en": "Downloaded: {ok}, errors: {failed}"},
    "files_baseline": {"pl": "Oznaczono {n} plików jako pobrane (bez pobierania).",
                       "en": "Marked {n} files as done (without downloading)."},
    "files_mass_move": {"pl": "UWAGA: obecne ustawienia przeniosłyby {n} już pobranych plików do innych folderów\n"
                              "(np. po zmianie LANGUAGE, nazw kursów albo reguł kategorii). Dla bezpieczeństwa niczego nie\n"
                              "przenoszę ani nie pobieram. Sprawdź ustawienia: python -m moodle_sync doctor\n"
                              "Jeśli ta zmiana jest zamierzona, zatwierdź ją raz: python -m moodle_sync download --reorganize",
                        "en": "WARNING: the current settings would move {n} already downloaded files to other folders\n"
                              "(e.g. after changing LANGUAGE, course names or category rules). To be safe, nothing is moved\n"
                              "or downloaded. Check the settings: python -m moodle_sync doctor\n"
                              "If the change is intended, confirm it once: python -m moodle_sync download --reorganize"},
    "notify_files_title": {"pl": "Nowe materiały ({n})", "en": "New course materials ({n})"},
    "courses_header": {"pl": "Kursy: {n}. Nazwy i kategorie możesz zmienić w {file} (patrz courses.example.json).",
                       "en": "Courses: {n}. You can change names and categories in {file} (see courses.example.json)."},
    "courses_no_files": {"pl": "brak plików", "en": "no files"},

    # --- storage ---
    "storage_disabled": {"pl": "Wysyłka do chmury wyłączona (brak RCLONE_REMOTE) - pliki zostają w folderze lokalnym.",
                         "en": "Cloud upload disabled (no RCLONE_REMOTE) - files stay in the local folder."},
    "storage_no_rclone": {"pl": "Nie znaleziono programu '{bin}' - zainstaluj rclone (docs: storage).",
                          "en": "Program '{bin}' not found - install rclone (docs: storage)."},
    "storage_no_remote": {"pl": "rclone nie ma remote'a '{remote}:' - skonfiguruj: rclone config",
                          "en": "rclone has no remote '{remote}:' - configure it: rclone config"},
    "storage_moving": {"pl": "Przenoszenie w chmurze: {n} plików (z {queued} w kolejce - reszta jest już na miejscu)",
                       "en": "Moving in the cloud: {n} files (of {queued} queued - the rest is already in place)"},
    "storage_list_failed": {"pl": "Nie udało się pobrać listy plików z chmury - przenosiny ponowię przy następnym przebiegu.",
                            "en": "Couldn't list the cloud files - moves will be retried next run."},
    "storage_move_gave_up": {"pl": "odpuszczam po {n} próbach: {path}", "en": "giving up after {n} attempts: {path}"},
    "storage_nothing": {"pl": "Brak folderu {dir} - nie ma nic do wysłania.", "en": "Folder {dir} doesn't exist - nothing to upload."},
    "storage_backup_failed": {"pl": "[kopia] nie udało się skopiować {name} (spróbuję następnym razem)",
                              "en": "[backup] couldn't copy {name} (will retry next time)"},

    # --- calendar ---
    "cal_deadlines": {"pl": "terminy", "en": "deadlines"},
    "cal_classes": {"pl": "zajęcia", "en": "classes"},
    "cal_course": {"pl": "Kurs", "en": "Course"},
    "cal_summary": {"pl": "Wydarzenia w Moodle: {events} | do dodania/aktualizacji: {upsert} | do usunięcia: {delete}",
                    "en": "Events in Moodle: {events} | to add/update: {upsert} | to delete: {delete}"},
    "cal_timeline_failed": {"pl": "[oś czasu] nie pobrano statusu zadań: {error}",
                            "en": "[timeline] couldn't get assignment status: {error}"},
    "cal_created": {"pl": "Utworzono kalendarz Google: {name}", "en": "Created Google calendar: {name}"},
    "cal_no_client_secret": {"pl": "Brak {file} - pobierz klienta OAuth z Google Cloud (docs: google-calendar).",
                             "en": "Missing {file} - download the OAuth client from Google Cloud (docs: google-calendar)."},
    "cal_authorized": {"pl": "Zapisano {file}. Traktuj go jak hasło.", "en": "Saved {file}. Treat it like a password."},
    "cal_not_configured": {"pl": "Kalendarz Google nieskonfigurowany (brak google_token.json).",
                           "en": "Google Calendar not configured (no google_token.json)."},
    "cal_no_libs": {"pl": "Brak bibliotek Google - uruchom: pip install -r requirements.txt",
                    "en": "Google libraries missing - run: pip install -r requirements.txt"},
    "notify_new_deadlines": {"pl": "Nowe terminy ({n})", "en": "New deadlines ({n})"},
    "notify_moved_deadlines": {"pl": "Zmienione terminy ({n})", "en": "Changed deadlines ({n})"},
    "ics_intro": {"pl": "Twój prywatny adres subskrypcji kalendarza Moodle (Outlook: Dodaj kalendarz -> Z internetu;\n"
                        "Apple: Plik -> Nowa subskrypcja). Adres zawiera tajny klucz - nie udostępniaj go:",
                  "en": "Your private Moodle calendar subscription URL (Outlook: Add calendar -> From internet;\n"
                        "Apple: File -> New Calendar Subscription). It contains a secret key - don't share it:"},
    "ics_unavailable": {"pl": "Ten serwer Moodle nie udostępnia eksportu kalendarza.",
                        "en": "This Moodle site doesn't offer calendar export."},

    # --- watch ---
    "watch_announcement": {"pl": "ogłoszenie: {title}", "en": "announcement: {title}"},
    "watch_forums_baseline": {"pl": "fora: zapamiętano {n} istniejących wątków (bez powiadomień)",
                              "en": "forums: remembered {n} existing discussions (no notifications)"},
    "watch_grades_baseline": {"pl": "oceny: zapamiętano {n} pozycji (bez powiadomień)",
                              "en": "grades: remembered {n} items (no notifications)"},
    "watch_forums_result": {"pl": "Ogłoszenia: nowych {n}", "en": "Announcements: {n} new"},
    "watch_forums_recent": {"pl": "Ogłoszenia: sprawdzone niedawno, pomijam", "en": "Announcements: checked recently, skipping"},
    "watch_grades_result": {"pl": "Oceny: nowych/zmienionych {n}", "en": "Grades: {n} new/changed"},
    "notify_grade_title": {"pl": "Ocena: {grade} — {name}", "en": "Grade: {grade} — {name}"},
    "grade_previous": {"pl": "(poprzednio: {old})", "en": "(previously: {old})"},
    "grade_feedback": {"pl": "Komentarz prowadzącego", "en": "Teacher's feedback"},

    # --- runner ---
    "notify_error_title": {"pl": "Błąd: {step}", "en": "Error: {step}"},
    "hint_moodle_token": {"pl": "Token Moodle wygasł albo został unieważniony (np. po zmianie hasła). "
                                "Odnów go: python -m moodle_sync token",
                          "en": "The Moodle token expired or was revoked (e.g. after a password change). "
                                "Renew it: python -m moodle_sync token"},
    "hint_google_token": {"pl": "Google odrzucił token. Zaloguj się ponownie: python -m moodle_sync calendar --auth "
                                "(i sprawdź, czy aplikacja w Google Cloud ma status 'In production').",
                          "en": "Google rejected the token. Log in again: python -m moodle_sync calendar --auth "
                                "(and check the Google Cloud app is 'In production')."},
    "hint_rclone_token": {"pl": "rclone nie może odświeżyć logowania do chmury: rclone config reconnect <remote>:",
                          "en": "rclone can't refresh the cloud login: rclone config reconnect <remote>:"},
    "hint_mass_move": {"pl": "Nic nie zostało przeniesione. Najczęstsza przyczyna: literówka albo sklejona linia w .env "
                             "- sprawdź: python -m moodle_sync doctor",
                       "en": "Nothing was moved. The most common cause: a typo or a glued line in .env "
                             "- check: python -m moodle_sync doctor"},
    "hint_network": {"pl": "Brak sieci / DNS - sprawdź połączenie z internetem.",
                     "en": "No network / DNS - check the internet connection."},
    "weekly_title": {"pl": "Działam — podsumowanie tygodnia", "en": "Still running — weekly summary"},
    "weekly_counts": {"pl": "W tym tygodniu: {files} nowych plików, {posts} ogłoszeń, {grades} ocen.",
                      "en": "This week: {files} new files, {posts} announcements, {grades} grades."},
    "weekly_deadlines": {"pl": "Terminy na najbliższe 7 dni:", "en": "Deadlines in the next 7 days:"},
    "weekly_none": {"pl": "brak 🎉", "en": "none 🎉"},
    "weekly_deadlines_failed": {"pl": "(Nie udało się pobrać terminów: {error})", "en": "(Couldn't get deadlines: {error})"},

    # --- Telegram bot ---
    "bot_help": {"pl": "Komendy:\n/terminy — najbliższe terminy (14 dni)\n/nowe — ostatnio pobrane materiały\n"
                       "/oceny — ostatnie oceny\n/status — stan automatu\n/sync — synchronizuj teraz\n"
                       "/update — zainstaluj najnowszą wersję\n/rollback — wróć do poprzedniej wersji\n/pomoc — ta lista",
                 "en": "Commands:\n/deadlines — upcoming deadlines (14 days)\n/new — recently downloaded materials\n"
                       "/grades — latest grades\n/status — status of the sync\n/sync — sync now\n"
                       "/update — install the newest version\n/rollback — go back to the previous version\n/help — this list"},
    "bot_cmd_deadlines": {"pl": "Najbliższe terminy (14 dni)", "en": "Upcoming deadlines (14 days)"},
    "bot_cmd_new": {"pl": "Ostatnio pobrane materiały", "en": "Recently downloaded materials"},
    "bot_cmd_grades": {"pl": "Ostatnie oceny", "en": "Latest grades"},
    "bot_cmd_status": {"pl": "Stan automatu", "en": "Status of the sync"},
    "bot_cmd_sync": {"pl": "Synchronizuj teraz", "en": "Sync now"},
    "bot_cmd_help": {"pl": "Lista komend", "en": "List of commands"},
    "bot_cmd_update": {"pl": "Zainstaluj najnowszą wersję z GitHuba", "en": "Install the newest version from GitHub"},
    "bot_cmd_rollback": {"pl": "Wróć do poprzedniej wersji", "en": "Go back to the previous version"},
    "bot_update_checking": {"pl": "Szukam nowej wersji na GitHubie…", "en": "Checking GitHub for a new version…"},
    "bot_update_latest": {"pl": "{version} to najnowsza wersja.", "en": "{version} is the newest version."},
    "bot_update_installing": {"pl": "Instaluję {tag} (teraz {version}). Zależności mogą instalować się kilka minut…",
                              "en": "Installing {tag} (now {version}). Dependencies may take a few minutes…"},
    "bot_update_failed": {"pl": "Aktualizacja nie udała się, działa dalej {version}.",
                          "en": "Update failed, still running {version}."},
    "bot_update_restart": {"pl": "Zainstalowano {tag}, restartuję bota… Jeśli coś jest nie tak: /rollback",
                           "en": "{tag} installed, restarting the bot… If something is wrong: /rollback"},
    "bot_rollback_none": {"pl": "Nie ma poprzedniej wersji do przywrócenia.",
                          "en": "There is no previous version to go back to."},
    "bot_rollback_restart": {"pl": "Wracam do {version}, restartuję bota…", "en": "Back to {version}, restarting the bot…"},
    "bot_no_deadlines": {"pl": "Brak terminów w ciągu najbliższych 14 dni.", "en": "No deadlines in the next 14 days."},
    "bot_deadlines_header": {"pl": "Najbliższe terminy (14 dni)", "en": "Upcoming deadlines (14 days)"},
    "bot_no_new": {"pl": "Nie pobrano jeszcze nowych plików.", "en": "No new files downloaded yet."},
    "bot_new_header": {"pl": "Ostatnio pobrane", "en": "Recently downloaded"},
    "bot_no_grades": {"pl": "Brak ocen.", "en": "No grades."},
    "bot_grades_header": {"pl": "Oceny (najnowsze na górze)", "en": "Grades (newest first)"},
    "bot_status_header": {"pl": "Status", "en": "Status"},
    "bot_last_run": {"pl": "Ostatni przebieg: {when} ({secs} s)", "en": "Last run: {when} ({secs} s)"},
    "bot_next_run": {"pl": "Następny: ok. {time}", "en": "Next: around {time}"},
    "bot_never_ran": {"pl": "Automat jeszcze się nie uruchomił.", "en": "The sync hasn't run yet."},
    "bot_files_count": {"pl": "Plików w archiwum: {n}", "en": "Files in the archive: {n}"},
    "bot_disk": {"pl": "Wolne miejsce: {free:.1f} GB z {total:.0f} GB", "en": "Free space: {free:.1f} GB of {total:.0f} GB"},
    "bot_uptime": {"pl": "Czas działania: {d} d {h} h", "en": "Uptime: {d} d {h} h"},
    "bot_sync_started": {"pl": "Uruchamiam synchronizację…", "en": "Starting the sync…"},
    "bot_sync_busy": {"pl": "Synchronizacja właśnie trwa - sprawdź /status za chwilę.",
                      "en": "A sync is running right now - check /status in a moment."},
    "bot_sync_done": {"pl": "Synchronizacja zakończona", "en": "Sync finished"},
    "bot_not_configured": {"pl": "Brak TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID - uruchom: python -m moodle_sync bot --setup",
                           "en": "Missing TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID - run: python -m moodle_sync bot --setup"},
    "bot_running": {"pl": "Bot działa, czekam na komendy… (Ctrl+C kończy)", "en": "Bot running, waiting for commands… (Ctrl+C to stop)"},
    "bot_need_token": {"pl": "Najpierw dopisz do .env: TELEGRAM_BOT_TOKEN=<token od @BotFather>",
                       "en": "First add to .env: TELEGRAM_BOT_TOKEN=<token from @BotFather>"},
    "bot_bad_token": {"pl": "Telegram odrzucił token - sprawdź TELEGRAM_BOT_TOKEN.", "en": "Telegram rejected the token - check TELEGRAM_BOT_TOKEN."},
    "bot_send_message": {"pl": "Otwórz Telegram, znajdź @{username} i wyślij mu dowolną wiadomość (np. /start). Czekam do 3 minut…",
                         "en": "Open Telegram, find @{username} and send it any message (e.g. /start). Waiting up to 3 minutes…"},
    "bot_connected": {"pl": "Połączono! Tu będą przychodzić powiadomienia z Moodle.",
                      "en": "Connected! Moodle notifications will arrive here."},
    "bot_setup_done": {"pl": "Zapisano TELEGRAM_CHAT_ID={chat_id} w .env. Gotowe.", "en": "Saved TELEGRAM_CHAT_ID={chat_id} to .env. Done."},
    "bot_setup_timeout": {"pl": "Nie dostałem wiadomości w ciągu 3 minut - spróbuj ponownie.",
                          "en": "No message received within 3 minutes - try again."},

    # --- doctor ---
    "doc_header": {"pl": "Sprawdzam konfigurację…", "en": "Checking the configuration…"},
    "doc_no_env": {"pl": "Brak pliku .env - uruchom: python -m moodle_sync setup",
                   "en": "No .env file - run: python -m moodle_sync setup"},
    "doc_env_bad_line": {"pl": ".env, linia {n}: brak '=' i brak '#' - linia jest pomijana (dodaj '#' na początku)",
                         "en": ".env, line {n}: no '=' and no '#' - the line is ignored (add '#' in front)"},
    "doc_env_glued": {"pl": ".env, linia {n}: wartość {key} zawiera kolejne ustawienie - dwie linie sklejone w jedną "
                            "(brak nowej linii). Popraw: python -m moodle_sync set <KLUCZ> <WARTOŚĆ>",
                      "en": ".env, line {n}: the value of {key} contains another setting - two lines glued into one "
                            "(missing newline). Fix: python -m moodle_sync set <KEY> <VALUE>"},
    "doc_settings": {"pl": "Język: {lang}, nazwa: {label}, foldery: {folders}",
                     "en": "Language: {lang}, label: {label}, folders: {folders}"},
    "set_bad_key": {"pl": "Nieprawidłowa nazwa ustawienia: {key} (dozwolone: WIELKIE_LITERY_I_CYFRY)",
                    "en": "Invalid setting name: {key} (allowed: UPPER_CASE_AND_DIGITS)"},
    "set_done": {"pl": "Zapisano w .env: {key}={value}", "en": "Saved to .env: {key}={value}"},
    "doc_no_url": {"pl": "Brak MOODLE_BASE_URL w .env - uruchom: python -m moodle_sync setup",
                   "en": "No MOODLE_BASE_URL in .env - run: python -m moodle_sync setup"},
    "doc_site_ok": {"pl": "Moodle: {name} ({url})", "en": "Moodle: {name} ({url})"},
    "doc_site_failed": {"pl": "Nie mogę połączyć się z {url}: {error}", "en": "Can't connect to {url}: {error}"},
    "doc_token_ok": {"pl": "Token działa - zalogowano jako {name} (Moodle {release})",
                     "en": "Token works - logged in as {name} (Moodle {release})"},
    "doc_token_failed": {"pl": "Token nie działa: {error} -> python -m moodle_sync token",
                         "en": "Token doesn't work: {error} -> python -m moodle_sync token"},
    "doc_fn_missing": {"pl": "Token nie ma dostępu do {fn} - nie zadziała: {feature}",
                       "en": "The token can't use {fn} - this won't work: {feature}"},
    "doc_fn_courses": {"pl": "lista kursów", "en": "course list"},
    "doc_fn_files": {"pl": "pobieranie plików", "en": "file downloads"},
    "doc_fn_calendar": {"pl": "kalendarz", "en": "calendar"},
    "doc_fn_forums": {"pl": "ogłoszenia", "en": "announcements"},
    "doc_fn_grades": {"pl": "oceny", "en": "grades"},
    "doc_courses": {"pl": "Kursy: {n}", "en": "Courses: {n}"},
    "doc_folder": {"pl": "Folder na pliki: {dir} (wolne: {free:.1f} GB)", "en": "Download folder: {dir} (free: {free:.1f} GB)"},
    "doc_folder_failed": {"pl": "Nie mogę użyć folderu {dir}: {error}", "en": "Can't use folder {dir}: {error}"},
    "doc_storage": {"pl": "Chmura: {status}", "en": "Cloud: {status}"},
    "doc_calendar": {"pl": "Kalendarz Google: {status}", "en": "Google Calendar: {status}"},
    "doc_notify": {"pl": "Powiadomienia: {channels}", "en": "Notifications: {channels}"},
    "doc_none": {"pl": "brak", "en": "none"},
    "doc_healthcheck": {"pl": "Alarm „nie działa” (healthchecks.io)", "en": "Dead-man alarm (healthchecks.io)"},
    "doc_courses_file": {"pl": "Plik {file} poprawny", "en": "File {file} is valid"},
    "doc_courses_file_bad": {"pl": "Błąd w pliku {file}: {error}", "en": "Error in {file}: {error}"},
    "doc_all_ok": {"pl": "Wszystko w porządku. ✨", "en": "All good. ✨"},
    "doc_problems": {"pl": "Problemów do naprawy: {n} (opis przy ❌).", "en": "Problems to fix: {n} (see ❌ lines)."},

    # --- setup wizard ---
    "wiz_cancelled": {"pl": "Przerwano. Kreator możesz uruchomić ponownie w każdej chwili.",
                      "en": "Cancelled. You can run the wizard again any time."},
    "wiz_rules_header": {"pl": "Zanim zaczniesz - zasady", "en": "Before you start - the rules"},
    "wiz_rules_text": {"pl": "moodle-sync jest do użytku OSOBISTEGO, na Twoim własnym koncie:\n"
                             "  • materiały z kursów należą do prowadzących - trzymaj je prywatnie, nie udostępniaj\n"
                             "    folderu ani linków publicznie i nie wrzucaj ich na grupy roku,\n"
                             "  • ogłoszenia mogą zawierać dane innych studentów - nie przesyłaj ich dalej,\n"
                             "  • token to hasło - nie dawaj go nikomu i nie uruchamiaj programu dla innych,\n"
                             "  • przestrzegaj regulaminów swojej uczelni.\n"
                             "Dane zostają na Twoim komputerze i w usługach, które sam wybierzesz (projekt nie ma serwerów).\n"
                             "Więcej: docs/pl/responsible-use.md oraz PRIVACY.md",
                       "en": "moodle-sync is for PERSONAL use, on your own account:\n"
                             "  • course materials belong to the teachers - keep them private, never share the folder\n"
                             "    or links publicly, don't post them to group chats,\n"
                             "  • announcements may contain other students' data - don't forward them,\n"
                             "  • the token is a password - never give it to anyone or run the tool for others,\n"
                             "  • follow your university's rules.\n"
                             "Your data stays on your computer and in services you choose (the project has no servers).\n"
                             "More: docs/en/responsible-use.md and PRIVACY.md"},
    "wiz_rules_continue": {"pl": "Enter = rozumiem, dalej (Ctrl+C = przerwij) ", "en": "Enter = I understand, continue (Ctrl+C = cancel) "},
    "wiz_site_header": {"pl": "1/6  Adres Twojego Moodle", "en": "1/6  Your Moodle address"},
    "wiz_site_help": {"pl": "Wklej adres strony Moodle Twojej uczelni - może być dowolna jej podstrona,\n"
                            "np. https://moodle.example.edu.pl/2025/my/",
                      "en": "Paste the address of your school's Moodle - any page of it works,\n"
                            "e.g. https://moodle.example.edu/my/"},
    "wiz_site_prompt": {"pl": "Adres Moodle", "en": "Moodle address"},
    "wiz_site_ok": {"pl": "Znaleziono: {name} ({url})", "en": "Found: {name} ({url})"},
    "wiz_site_failed": {"pl": "{url} nie odpowiada jak Moodle z włączoną aplikacją mobilną ({error}). Sprawdź adres.",
                        "en": "{url} doesn't respond like Moodle with the mobile app enabled ({error}). Check the address."},
    "wiz_token_header": {"pl": "2/6  Dostęp do Twojego konta (token)", "en": "2/6  Access to your account (token)"},
    "wiz_token_keep": {"pl": "Obecny token działa ({name}). Zostawić go?", "en": "The current token works ({name}). Keep it?"},
    "wiz_token_existing_invalid": {"pl": "Obecny token nie działa - zdobądźmy nowy.", "en": "The current token doesn't work - let's get a new one."},
    "wiz_login_sso": {"pl": "Twoja uczelnia loguje przez przeglądarkę (SSO) - polecana metoda: przeglądarka.",
                      "en": "Your school logs in via the browser (SSO) - recommended method: browser."},
    "wiz_login_password": {"pl": "Twoja uczelnia używa zwykłego logowania - polecana metoda: login i hasło.",
                           "en": "Your school uses a normal login form - recommended method: username and password."},
    "wiz_method_prompt": {"pl": "Jak zdobyć token?", "en": "How to get the token?"},
    "wiz_method_sso": {"pl": "Przez przeglądarkę (SSO, np. logowanie uczelniane / Microsoft / Google)",
                       "en": "Via the browser (SSO, e.g. university / Microsoft / Google login)"},
    "wiz_method_password": {"pl": "Login i hasło Moodle", "en": "Moodle username and password"},
    "wiz_method_paste": {"pl": "Mam już token - wkleję go", "en": "I already have a token - I'll paste it"},
    "wiz_sso_steps": {"pl": "\nZa chwilę otworzy się przeglądarka (albo otwórz ten adres ręcznie):\n  {url}\n\n"
                            "  1. Zaloguj się jak zwykle. Potem strona „nic nie zrobi” albo zapyta o aplikację Moodle -\n"
                            "     to normalne (ewentualne okienko anuluj).\n"
                            "  2. Naciśnij F12 i otwórz zakładkę Console (Konsola). Zobaczysz błąd w stylu:\n"
                            "       Failed to launch 'moodlemobile://token=AbCd...'\n"
                            "     (Firefox: zakładka Sieć / Network -> ostatnie przekierowanie.)\n"
                            "  3. Skopiuj adres zaczynający się od moodlemobile://token= i wklej go poniżej.\n",
                      "en": "\nA browser will open now (or open this address manually):\n  {url}\n\n"
                            "  1. Log in as usual. Afterwards the page will \"do nothing\" or ask about the Moodle app -\n"
                            "     that's expected (cancel the popup if there is one).\n"
                            "  2. Press F12 and open the Console tab. You'll see an error like:\n"
                            "       Failed to launch 'moodlemobile://token=AbCd...'\n"
                            "     (Firefox: Network tab -> the last redirect.)\n"
                            "  3. Copy the address starting with moodlemobile://token= and paste it below.\n"},
    "wiz_sso_paste": {"pl": "Wklej moodlemobile://token=... (Enter = wróć)", "en": "Paste moodlemobile://token=... (Enter = back)"},
    "wiz_sso_bad": {"pl": "To nie wygląda na token - skopiuj cały adres moodlemobile://token=...",
                    "en": "That doesn't look like a token - copy the whole moodlemobile://token=... address"},
    "wiz_password_note": {"pl": "Hasło trafia tylko do Twojego Moodle (HTTPS), jednorazowo, i nie jest nigdzie zapisywane.",
                          "en": "The password goes only to your Moodle (HTTPS), once, and is never stored."},
    "wiz_username": {"pl": "Login", "en": "Username"},
    "wiz_password": {"pl": "Hasło (nie będzie widoczne)", "en": "Password (hidden)"},
    "wiz_password_failed": {"pl": "Logowanie nie powiodło się: {error}", "en": "Login failed: {error}"},
    "wiz_paste_token": {"pl": "Token", "en": "Token"},
    "wiz_token_invalid": {"pl": "Token nie działa: {error}", "en": "The token doesn't work: {error}"},
    "wiz_token_ok": {"pl": "Zalogowano jako {name}. Token zapisany w .env (traktuj go jak hasło).",
                     "en": "Logged in as {name}. Token saved to .env (treat it like a password)."},
    "wiz_courses_found": {"pl": "Twoich kursów: {n}", "en": "Your courses: {n}"},
    "wiz_basics_header": {"pl": "3/6  Nazwa i folder", "en": "3/6  Name and folder"},
    "wiz_label_prompt": {"pl": "Krótka nazwa uczelni (do nazw kalendarzy, np. UNI)",
                         "en": "Short name of your school (for calendar names, e.g. MIT)"},
    "wiz_folder_help": {"pl": "Gdzie zapisywać materiały? Wskazówka: jeśli masz na komputerze Dysk Google / OneDrive /\n"
                              "Dropbox, podaj folder wewnątrz nich (np. C:\\Users\\Ty\\OneDrive\\Moodle) - wtedy pliki\n"
                              "trafią do chmury bez żadnej dodatkowej konfiguracji.",
                        "en": "Where to save the materials? Tip: if you have Google Drive / OneDrive / Dropbox on your\n"
                              "computer, point to a folder inside it (e.g. C:\\Users\\You\\OneDrive\\Moodle) - files then\n"
                              "reach the cloud with no extra setup."},
    "wiz_folder_prompt": {"pl": "Folder na materiały", "en": "Folder for materials"},
    "wiz_notify_header": {"pl": "4/6  Powiadomienia (opcjonalne)", "en": "4/6  Notifications (optional)"},
    "wiz_notify_help": {"pl": "Możesz wybrać kilka. Telegram jako jedyny obsługuje też komendy (/terminy, /sync...).\n"
                              "Kanał ma być PRYWATNY (Twój czat / Twój serwer) - powiadomienia zawierają treść ogłoszeń i Twoje oceny.",
                        "en": "You can pick several. Only Telegram also supports commands (/deadlines, /sync...).\n"
                              "Keep the channel PRIVATE (your own chat / server) - notifications contain announcements and your grades."},
    "wiz_notify_current": {"pl": "Obecnie skonfigurowane: {channels}", "en": "Currently configured: {channels}"},
    "wiz_keep_existing": {"pl": "Zostawić obecne ustawienia?", "en": "Keep the current settings?"},
    "wiz_telegram_q": {"pl": "Telegram?", "en": "Telegram?"},
    "wiz_telegram_steps": {"pl": "  1. W Telegramie otwórz @BotFather i wyślij /newbot\n"
                                 "  2. Podaj nazwę i login kończący się na 'bot'\n"
                                 "  3. Skopiuj token (wygląda jak 123456789:AAH...)",
                           "en": "  1. In Telegram, open @BotFather and send /newbot\n"
                                 "  2. Choose a name and a username ending in 'bot'\n"
                                 "  3. Copy the token (looks like 123456789:AAH...)"},
    "wiz_telegram_token": {"pl": "Token bota", "en": "Bot token"},
    "wiz_discord_q": {"pl": "Discord?", "en": "Discord?"},
    "wiz_discord_steps": {"pl": "  Na swoim (np. prywatnym, tylko dla siebie) serwerze Discord: ustawienia kanału ->\n"
                                "  Integracje -> Webhooki -> Nowy webhook -> Kopiuj URL webhooka",
                          "en": "  On your (e.g. private, just-for-you) Discord server: channel settings ->\n"
                                "  Integrations -> Webhooks -> New Webhook -> Copy Webhook URL"},
    "wiz_discord_url": {"pl": "URL webhooka", "en": "Webhook URL"},
    "wiz_ntfy_q": {"pl": "ntfy (aplikacja push, bez konta)?", "en": "ntfy (push app, no account)?"},
    "wiz_ntfy_topic": {"pl": "Temat (działa jak hasło - zostaw losowy)", "en": "Topic (works like a password - keep it random)"},
    "wiz_ntfy_steps": {"pl": "  Zainstaluj aplikację ntfy -> + -> Subscribe to topic -> wpisz: {topic}",
                       "en": "  Install the ntfy app -> + -> Subscribe to topic -> enter: {topic}"},
    "wiz_email_q": {"pl": "E-mail?", "en": "E-mail?"},
    "wiz_email_help": {"pl": "  Gmail: potrzebne „hasło do aplikacji” (Konto Google -> Bezpieczeństwo -> Weryfikacja\n"
                             "  dwuetapowa -> Hasła do aplikacji), NIE Twoje zwykłe hasło.",
                       "en": "  Gmail: you need an \"app password\" (Google Account -> Security -> 2-Step Verification ->\n"
                             "  App passwords), NOT your normal password."},
    "wiz_email_user": {"pl": "Login SMTP (adres e-mail)", "en": "SMTP login (e-mail address)"},
    "wiz_email_password": {"pl": "Hasło SMTP / hasło aplikacji (nie będzie widoczne)", "en": "SMTP / app password (hidden)"},
    "wiz_email_to": {"pl": "Wysyłaj na adres", "en": "Send to"},
    "wiz_test_title": {"pl": "Test powiadomień", "en": "Notification test"},
    "wiz_test_body": {"pl": "Jeśli to widzisz, powiadomienia z moodle-sync działają. 🎉",
                      "en": "If you can see this, moodle-sync notifications work. 🎉"},
    "wiz_test_sent": {"pl": "Wysłano test na: {channels} - sprawdź, czy doszedł.", "en": "Test sent to: {channels} - check it arrived."},
    "wiz_storage_header": {"pl": "5/6  Chmura (opcjonalne)", "en": "5/6  Cloud storage (optional)"},
    "wiz_storage_help": {"pl": "Jeśli folder z kroku 3 jest w Dysku Google/OneDrive na tym komputerze - możesz to pominąć.\n"
                               "rclone przydaje się na Raspberry Pi/serwerze (docs: storage).",
                         "en": "If the folder from step 3 is inside Google Drive/OneDrive on this computer - skip this.\n"
                               "rclone is useful on a Raspberry Pi/server (docs: storage)."},
    "wiz_storage_no_rclone": {"pl": "rclone nie jest zainstalowany - pomijam (instrukcja: docs/pl/storage.md).",
                              "en": "rclone is not installed - skipping (guide: docs/en/storage.md)."},
    "wiz_storage_no_remotes": {"pl": "rclone nie ma żadnego remote'a - uruchom 'rclone config' (docs/pl/storage.md), potem ponownie kreator.",
                               "en": "rclone has no remotes - run 'rclone config' (docs/en/storage.md), then the wizard again."},
    "wiz_storage_remotes": {"pl": "Remote'y rclone: {remotes}", "en": "rclone remotes: {remotes}"},
    "wiz_storage_remote": {"pl": "Którego użyć (puste = bez chmury)", "en": "Which one to use (empty = no cloud)"},
    "wiz_storage_dest": {"pl": "Folder docelowy w chmurze", "en": "Target folder in the cloud"},
    "wiz_calendar_header": {"pl": "6/6  Kalendarz Google (opcjonalne)", "en": "6/6  Google Calendar (optional)"},
    "wiz_calendar_ok": {"pl": "Kalendarz Google już skonfigurowany.", "en": "Google Calendar already configured."},
    "wiz_calendar_help": {"pl": "Wymaga jednorazowej konfiguracji w Google Cloud (~10 min): docs/pl/google-calendar.md\n"
                                "Outlook/Apple: zamiast tego użyj adresu z: python -m moodle_sync ics",
                          "en": "Needs a one-time Google Cloud setup (~10 min): docs/en/google-calendar.md\n"
                                "Outlook/Apple: use the URL from: python -m moodle_sync ics instead"},
    "wiz_calendar_login_q": {"pl": "Znaleziono client_secret.json - zalogować do Google teraz?",
                             "en": "Found client_secret.json - log in to Google now?"},
    "wiz_first_header": {"pl": "Pierwsza synchronizacja", "en": "First sync"},
    "wiz_first_prompt": {"pl": "Na Twoich kursach jest {n} plików (~{mb:.0f} MB). Co zrobić?",
                         "en": "Your courses have {n} files (~{mb:.0f} MB). What to do?"},
    "wiz_first_all": {"pl": "Pobierz wszystko teraz", "en": "Download everything now"},
    "wiz_first_baseline": {"pl": "Pomiń istniejące, pobieraj tylko nowe od teraz", "en": "Skip existing, only download new ones from now on"},
    "wiz_first_later": {"pl": "Później", "en": "Later"},
    "wiz_done_header": {"pl": "Gotowe!", "en": "Done!"},
    "wiz_done_common": {"pl": "Sprawdzenie całości:  python -m moodle_sync doctor\nDokumentacja:         docs/pl/",
                        "en": "Check everything:  python -m moodle_sync doctor\nDocumentation:     docs/en/"},
    "wiz_done_windows": {"pl": "Ręcznie: dwuklik na sync.bat\n"
                               "Automatycznie co 30 min, gdy komputer jest włączony:\n"
                               "  powershell -ExecutionPolicy Bypass -File deploy\\windows\\schedule.ps1",
                         "en": "Manually: double-click sync.bat\n"
                               "Automatically every 30 min while the computer is on:\n"
                               "  powershell -ExecutionPolicy Bypass -File deploy\\windows\\schedule.ps1"},
    "wiz_done_macos": {"pl": "Ręcznie: ./sync.sh\nAutomatycznie co 30 min, gdy Mac jest włączony:\n  bash deploy/macos/schedule.sh",
                       "en": "Manually: ./sync.sh\nAutomatically every 30 min while the Mac is on:\n  bash deploy/macos/schedule.sh"},
    "wiz_done_linux": {"pl": "Ręcznie: ./sync.sh\nAutomatycznie na tym komputerze: bash deploy/linux/schedule-user.sh\n"
                             "Raspberry Pi / serwer 24/7:      bash deploy/linux/install-server.sh",
                       "en": "Manually: ./sync.sh\nAutomatically on this computer: bash deploy/linux/schedule-user.sh\n"
                             "Raspberry Pi / 24/7 server:     bash deploy/linux/install-server.sh"},
}


def t(message_key: str, /, **kwargs) -> str:
    """Message in the configured language, formatted with kwargs (which may include `key`)."""
    entry = MESSAGES.get(message_key)
    if entry is None:
        return message_key
    text = entry.get(config.language()) or entry["en"]
    return text.format(**kwargs) if kwargs else text


def weekday(index: int) -> str:
    return WEEKDAYS[config.language()][index]
