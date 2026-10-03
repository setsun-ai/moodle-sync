# Token Moodle

🇬🇧 [English version](../en/token.md) · [← README](../../README.pl.md)

## Co to jest

moodle-sync rozmawia z Moodle przez oficjalne **API Web Service**, to samo, którego używa oficjalna **aplikacja mobilna Moodle**. Potrzebuje do tego **tokenu**: długiego losowego ciągu, który działa jak hasło do **Twojego** konta, ograniczone do tego, co może aplikacja mobilna.

- Token leży tylko w pliku `.env` na Twoim komputerze. Nie jest nigdzie wysyłany ani wypisywany w logach.
- moodle-sync tylko **czyta** Twoje dane. Niczego nie oddaje, nie publikuje ani nie zmienia w Moodle.
- **Traktuj token jak hasło.** Kto go ma, może w Moodle działać jako Ty (także oddawać zadania i pisać na forach).

## Jak go zdobyć: najprościej

Uruchom `python -m moodle_sync setup` (albo `python -m moodle_sync token`, żeby tylko odnowić token). Kreator zapyta Moodle, jak się logujesz, i wybierze metodę.

### A) Zwykły formularz logowania (login + hasło)

Kreator pyta o login i hasło i wymienia je na token w `<moodle>/login/token.php`, standardowym mechanizmie Moodle. Hasło trafia tylko do Twojego Moodle przez HTTPS, jednorazowo, i nie jest zapisywane.

### B) Logowanie przez przeglądarkę (SSO: CAS, logowanie uczelniane, Microsoft, Google...)

Tu Moodle nie widzi Twojego hasła, więc token trzeba odebrać przez przeglądarkę, dokładnie tak jak robi to aplikacja mobilna:

1. Kreator otwiera link w stylu
   `https://<twoje-moodle>/admin/tool/mobile/launch.php?service=moodle_mobile_app&passport=...&urlscheme=moodlemobile`
2. Zaloguj się jak zwykle. Moodle spróbuje wtedy przekazać token do aplikacji Moodle linkiem `moodlemobile://token=...`. Przeglądarka nie umie go otworzyć: strona „nic nie robi” albo pyta, czy otworzyć aplikację. Anuluj to okienko.
3. Wyciągnij ten link:
   - **Chrome / Edge:** naciśnij **F12** i otwórz zakładkę **Console (Konsola)**. Będzie tam błąd w stylu
     `Failed to launch 'moodlemobile://token=ZmY1...' because the scheme does not have a registered handler.`
     Skopiuj tekst od `moodlemobile://` do zamykającego apostrofu.
   - **Firefox:** naciśnij **F12** i otwórz zakładkę **Sieć (Network)**. W razie potrzeby odśwież stronę logowania. Ostatnie żądanie (`launch.php`) ma w odpowiedzi nagłówek `Location: moodlemobile://token=...`.
4. Wklej go do kreatora. Kreator rozkoduje token i od razu sprawdzi, czy działa.

> Jeśli w konsoli nic się nie pojawia, otwórz narzędzia deweloperskie *przed* logowaniem (F12, potem jeszcze raz otwórz link).

### C) Masz już token

Wybierz „Mam już token” i wklej go.

## Gdy token przestaje działać

Dostaniesz powiadomienie o błędzie („Token Moodle wygasł...”) albo zobaczysz `invalidtoken` w logach. Najczęstsze przyczyny:
- serwer ogranicza ważność tokenów,
- zmiana hasła,
- reset kluczy (patrz niżej).

Naprawisz to poleceniem `python -m moodle_sync token`. Na Raspberry Pi zrestartuj też bota: `sudo systemctl restart moodle-sync-bot`.

## Unieważnienie tokenu (np. gdy wyciekł)

W Moodle otwórz **menu profilu → Preferencje → Klucze bezpieczeństwa** (`/user/managetoken.php`) i kliknij **Resetuj** przy *Moodle mobile web service*. Stary token od razu przestaje działać. Wyloguje to też aplikację mobilną Moodle, więc zaloguj się w niej ponownie.

## „Ten serwer nie pozwala na aplikację mobilną”

moodle-sync działa tylko wtedy, gdy serwer ma włączone *usługi mobilne* (Administracja → Aplikacja mobilna). Prawie wszystkie uczelnie je mają, bo studenci używają aplikacji. Jeśli Twoja nie ma, kreator zgłosi, że serwer nie odpowiada jak Moodle z włączoną aplikacją mobilną. Wtedy jedyne wyjście to prośba do administratorów.

## Osobny Moodle na każdy rok akademicki?

Niektóre uczelnie uruchamiają co roku nową instancję (`https://moodle.example.edu.pl/2025` → `/2026`). Wtedy na początku roku uruchom `python -m moodle_sync token`, podaj nowy adres i zaloguj się. Nowe kursy trafią do nowych folderów, a stare pliki zostaną na miejscu.
