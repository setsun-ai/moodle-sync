# Zasady korzystania

🇬🇧 [English version](../en/responsible-use.md) · [← README](../../README.pl.md) · [Prywatność](../../PRIVACY.md#po-polsku)

moodle-sync to **narzędzie osobiste**. Robi automatycznie to, co mógłbyś zrobić ręcznie: otworzyć swoje kursy i zapisać pliki. Obowiązują więc te same zasady co przy ręcznym pobieraniu. Przeczytaj to raz.

> To wskazówki, a nie porada prawna. Regulaminy Twojej uczelni i przepisy zawsze mają pierwszeństwo.

## 1. Materiały należą do autorów 📚

Wykłady, slajdy, instrukcje i egzaminy są objęte **prawem autorskim** prowadzących (albo uczelni). Możesz je pobierać do **własnej nauki**, bo po to są na Moodle.

✅ **Można:**
- trzymać je w **swoim prywatnym** folderze w chmurze,
- uczyć się z nich,
- robić do nich własne notatki.

❌ **Nie wolno:**
- udostępniać folderu **publicznym linkiem** albo w trybie „każdy, kto ma link”,
- wrzucać materiałów na serwisy z notatkami, do publicznych repozytoriów, na serwery Discorda czy grupy roku,
- przekazywać ich osobom spoza kursu,
- sprzedawać ich ani publikować.

Niektórzy prowadzący wprost zakazują jakiegokolwiek dalszego udostępniania, i wtedy obowiązują ich warunki. Dozwolony użytek prywatny (art. 23 ustawy o prawie autorskim) obejmuje własny użytek. Nie obejmuje publikowania ani szerokiego rozpowszechniania.

**Nigdy nie commituj `downloads/` do Gita** i nie umieszczaj materiałów w publicznym repozytorium. Właśnie dlatego ten folder jest w `.gitignore`.

## 2. Cudze dane osobowe 👥

Ogłoszenia czasem zawierają dane innych studentów: imiona i nazwiska, numery indeksów, oceny. moodle-sync przekazuje ogłoszenia na *Twój* Telegram/Discord/e-mail, więc te dane trafiają do Twoich powiadomień.
- Kanał powiadomień ma być **prywatny**: Twój własny czat albo serwer Discord, na którym jesteś sam. Nie grupa roku ani kanał publiczny.
- **Nie rób zrzutów ekranu** takich ogłoszeń i nie przesyłaj ich dalej na grupy.
- Według RODO zachowanie takich danych dla siebie to użytek osobisty. Rozpowszechnianie już nie.

## 3. Przestrzegaj regulaminów uczelni 🏫

Uczelnie mają regulamin studiów, zasady e-learningu i zasady korzystania z infrastruktury IT. Zwykle zakazują:
- **udostępniania loginu lub tokenu** komukolwiek,
- korzystania z systemów uczelni w sposób, który je **przeciąża**,
- dostępu do danych, do których nie masz uprawnień.

moodle-sync jest zaprojektowany tak, żeby mieścić się w takich zasadach:
- używa **oficjalnego API aplikacji mobilnej**, na **Twoim własnym** koncie, **tylko do odczytu**;
- wysyła kilkadziesiąt zapytań na przebieg, ogłoszenia sprawdza najwyżej co 30 minut, a oceny co godzinę;
- przedstawia się uczciwie (User-Agent z nazwą projektu).

W razie wątpliwości przeczytaj regulamin albo zapytaj dział IT. Lepiej zapytać, niż zgadywać.

## 4. Czego nie robić ⛔

- **Nie uruchamiaj moodle-sync dla innych.** Nie zbieraj tokenów znajomych, nie stawiaj wspólnej „usługi”, nie dziel się swoim `.env`. Token to hasło: jedna osoba, jedno konto.
- **Nie skracaj odstępów.** Nie uruchamiaj co minutę, nie usuwaj ograniczeń i nie puszczaj wielu kopii naraz. Serwery uczelni obsługują tysiące studentów.
- **Nie używaj narzędzia do obchodzenia ograniczeń**, np. materiałów ukrytych do określonej daty. moodle-sync widzi tylko to, co już widzisz w Moodle, i tak ma zostać.
- **Nie wrzucaj materiałów do zewnętrznych narzędzi AI**, chyba że uczelnia i prowadzący na to pozwalają. Część serwisów AI przechowuje wgrane treści albo uczy się na nich, co może naruszać prawa autorskie i zasady kursu.

## 5. Brak powiązań i gwarancji

moodle-sync to niezależny projekt studencki. **Nie jest powiązany** z Moodle Pty Ltd ani z żadną uczelnią i nie jest przez nie wspierany. Działa **bez gwarancji** ([licencja MIT](../../LICENSE)). Nie traktuj go jako jedynego źródła terminów i **w ważnych sprawach zawsze sprawdzaj w samym Moodle**.

---

**W skrócie:** pobieraj dla siebie, trzymaj prywatnie, szanuj regulaminy uczelni i ludzi z Twoich kursów.
