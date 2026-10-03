# Problemy i FAQ

🇬🇧 [English version](../en/troubleshooting.md) · [← README](../../README.pl.md)

**Zawsze zacznij od** `python -m moodle_sync doctor`. Sprawdza całość i mówi, co naprawić.

## Błędy

**`invalidtoken` / „Token Moodle wygasł albo został unieważniony”**
Zdobądź nowy przez `python -m moodle_sync token`. Na Raspberry Pi zrestartuj też bota: `sudo systemctl restart moodle-sync-bot`. Zobacz [Token](token.md#gdy-token-przestaje-działać).

**`nopermissiontoviewgrades` w logach**
To normalne. Wiele uczelni ukrywa dziennik ocen przed studentami. Oceny są wtedy czytane z zadań i quizów, więc oceny końcowe wpisane tylko do dziennika albo do USOS-a nie dotrą.

**„nie odpowiada jak Moodle z włączoną aplikacją mobilną”**
- Sprawdź adres w przeglądarce.
- Niektóre uczelnie mają osobny Moodle na każdy rok, zobacz [Token](token.md#osobny-moodle-na-każdy-rok-akademicki).
- Jeśli adres jest dobry, serwer ma wyłączony dostęp mobilny.

**`invalid_grant` (Google)**
Logowanie do Google wygasło. Zwykle aplikacja w Google Cloud jest nadal w statusie *Testing*: [opublikuj ją](google-calendar.md#1-projekt-w-google-cloud-raz-10-min). Potem zaloguj się ponownie:
- kalendarz: `python -m moodle_sync calendar --auth`
- Dysk: `rclone config reconnect gdrive:`

**Dwa foldery o tej samej nazwie na Dysku Google**
Folder został utworzony ręcznie, a rclone z `drive.file` go nie widzi ([dlaczego](storage.md#dysk-google)). Przenieś zawartość i usuń pusty folder.

**Bot Telegram nie odpowiada**
- Czy działa? `journalctl -u moodle-sync-bot -n 30` albo uruchom `python -m moodle_sync bot` samodzielnie.
- `409 Conflict` oznacza, że bot działa też na innej maszynie. Zatrzymaj jedną z nich.
- Powiadomienia działają bez bota. Tylko komendy go potrzebują.

**Windows: w tle nic się nie dzieje**
- Otwórz *Harmonogram zadań → moodle-sync → Historia*.
- Zajrzyj do `logs\sync.log`.
- Czy folder projektu został przeniesiony? Uruchom ponownie `deploy\windows\schedule.bat`.

**macOS: `Operation not permitted`**
Projekt albo `DOWNLOAD_DIR` leży w Dokumentach, na Biurku albo w Pobranych. Zobacz [Uruchamianie → macOS](running.md#macos).

**Raspberry Pi gubi Wi-Fi**
Wyłącz oszczędzanie energii Wi-Fi, zobacz [Raspberry Pi → Odporność](raspberry-pi.md#odporność).

**„UWAGA: obecne ustawienia przeniosłyby N już pobranych plików”**
To bezpiecznik. Zmiana ustawień przemeblowałaby dużą część archiwum, więc niczego nie przeniesiono ani nie pobrano.
- Zwykle to wypadek. Klasyczny przykład: linia dopisana przez `echo "LANGUAGE=pl" >> .env` skleiła się z poprzednią, bo plik nie kończył się znakiem nowej linii. `LANGUAGE` po cichu wróciło do angielskiego, więc wszystkie foldery zmieniłyby nazwy.
- Uruchom `python -m moodle_sync doctor`. Wskaże zepsute linie `.env`. Popraw je poleceniem `python -m moodle_sync set KLUCZ WARTOŚĆ`.
- Jeśli naprawdę zmieniasz układ celowo (nowy język, nowe reguły w `courses.json`), zatwierdź to raz: `python -m moodle_sync download --reorganize`. Kolejne `upload` przeniesie wtedy pliki w chmurze bez ponownego wysyłania.

**Pierwsze sprawdzenie ogłoszeń nic nie wysłało**
Tak ma być. Pierwsze sprawdzenie tylko zapamiętuje istniejące wpisy, podobnie jak każde forum, które zacznie być obserwowane później. Powiadomienia przychodzą tylko o nowszych wpisach.

## FAQ

**Czy tak wolno?**
moodle-sync używa oficjalnego API aplikacji mobilnej na **Twoim własnym** koncie i tylko czyta Twoje dane, jak aplikacja, i to mniejszą liczbą zapytań. O czym pamiętać:
- Regulaminy IT uczelni zwykle zakazują udostępniania danych logowania i przeciążania serwerów. Prywatna automatyzacja własnego konta jest z reguły w porządku, ale w razie wątpliwości sprawdź regulamin albo zapytaj dział IT.
- Materiały z kursów są objęte prawem autorskim prowadzących. Trzymanie ich w **swojej prywatnej** chmurze to użytek osobisty. **Nie udostępniaj folderu publicznie ani linków do niego.**

Szczegóły w **[Zasadach korzystania](responsible-use.md)** i **[Prywatności](../../PRIVACY.md#po-polsku)**.

**Gdzie są moje dane?**
Tylko na Twoim komputerze i w chmurze, którą **Ty** wybrałeś. Ten projekt nie ma żadnych serwerów. Powiadomienia idą przez wybrany przez Ciebie serwis (np. Telegram).

**Jak wymusić pełną synchronizację od nowa?**
Zatrzymaj harmonogram i przenieś `state.json` w inne miejsce. Wszystko pobierze się ponownie. Nic się nie zdubluje ani w chmurze (rclone porównuje rozmiar i datę), ani w kalendarzu (wydarzenia mają stałe identyfikatory).

**Chcę tylko nowe pliki, bez całego archiwum.**
Uruchom raz `python -m moodle_sync download --baseline`. Oznacza wszystko, co jest teraz, jako załatwione.

**Czy zadziała na mojej uczelni?**
Zadziała, jeśli Twój Moodle ma włączoną aplikację mobilną (prawie zawsze). Projekt powstał na Moodle 5.1 na Politechnice Gdańskiej i używa tylko standardowych funkcji API dostępnych od Moodle 3.9.

**Czy może oddawać zadania albo pisać za mnie?**
Nie. Celowo tylko czyta.
