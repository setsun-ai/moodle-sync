# Security / Bezpieczeństwo

🇬🇧 English below · 🇵🇱 [po polsku niżej](#po-polsku)

## Your secrets

| File | What it grants | Where it lives |
|---|---|---|
| `.env` → `MOODLE_TOKEN` | acting as **you** in Moodle (incl. submitting, posting) | only your machine |
| `.env` → `MOODLE_PRIVATE_TOKEN` | opening Moodle web pages **logged in as you** (used only for attendance) | only your machine |
| `.env` → `TELEGRAM_BOT_TOKEN`, `DISCORD_WEBHOOK_URL`, `SMTP_PASSWORD` | sending messages as your bot / webhook / mailbox | only your machine |
| `google_token.json` | the calendars created by moodle-sync | only your machine |
| `rclone.conf` | your cloud storage | only your machine |

All of them are in `.gitignore`. **Never commit, paste or share them.** Screenshots of `.env` count as sharing.

What the code does to protect them:
- Tokens are never printed. Error messages pass through a redaction step, because HTTP libraries put full URLs (with tokens) into exceptions.
- Only the Moodle server you configured ever receives your Moodle token. The optional password login sends your password only to your Moodle's own `login/token.php` over HTTPS, once, and never stores it.
- moodle-sync is **read-only** towards Moodle unless you set `MOODLE_ACTIONS=1`; then the Telegram bot submits, posts or marks attendance only after a ✅ tap on a summary, and only for `TELEGRAM_CHAT_ID`.
- Passwords you type into the bot (attendance) are deleted from the chat right away.
- The cloud backup (`state.json`) contains no secrets.
- Google access is limited to calendars the app created (`calendar.app.created`); with `scope=drive.file`, Drive access is limited to files rclone created.
- The Telegram bot answers only your chat id.
- Tests run with all secrets removed from the environment.

**If a token leaked:**
- **Moodle:** Preferences → Security keys → *Reset* (see [docs/en/token.md](docs/en/token.md#revoking-the-token-eg-if-it-leaked)).
- **Telegram:** @BotFather → `/revoke`.
- **Discord:** delete the webhook.
- **Google:** <https://myaccount.google.com/permissions> → remove moodle-sync.

## Reporting a vulnerability

Please **don't open a public issue** for security problems. Use GitHub's *Security → Report a vulnerability* (private advisory) on this repository instead.

---

## Po polsku

**Sekrety:**
- `MOODLE_TOKEN` pozwala działać w Moodle **jako Ty**.
- `MOODLE_PRIVATE_TOKEN` pozwala otwierać strony Moodle **zalogowany jako Ty** (używany tylko do obecności).
- Z `MOODLE_ACTIONS=1` bot oddaje, publikuje i zaznacza obecność tylko po Twoim ✅; hasła wpisane w bocie od razu usuwa z czatu.
- Tokeny Telegram/Discord/SMTP pozwalają wysyłać wiadomości jako Twój bot, webhook albo skrzynka.
- `google_token.json` daje dostęp do kalendarzy utworzonych przez moodle-sync.
- `rclone.conf` daje dostęp do Twojej chmury.

Wszystkie są w `.gitignore`, a kod nigdy ich nie wypisuje ani nie wysyła nigdzie poza właściwą usługę. **Nigdy ich nie commituj, nie wklejaj i nie udostępniaj** (zrzut ekranu `.env` też się liczy).

**Gdy token wycieknie:**
- **Moodle:** Preferencje → Klucze bezpieczeństwa → *Resetuj*.
- **Telegram:** @BotFather → `/revoke`.
- **Discord:** usuń webhook.
- **Google:** <https://myaccount.google.com/permissions> → usuń moodle-sync.

**Luki bezpieczeństwa** zgłaszaj prywatnie przez *Security → Report a vulnerability* na GitHubie, a nie w publicznym zgłoszeniu (issue).
