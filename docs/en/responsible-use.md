# Responsible use

🇵🇱 [Wersja polska](../pl/responsible-use.md) · [← README](../../README.md) · [Privacy](../../PRIVACY.md)

moodle-sync is a **personal tool**. It does automatically what you could do by hand: open your courses and save files. The same rules apply as when you do it yourself, so please read this once.

> This page is guidance, not legal advice. Your university's rules and your country's law always take precedence.

## 1. Course materials belong to their authors 📚

Lectures, slides, instructions and exams are **copyrighted** by the teachers (or the university). You may download them for **your own studying**, because that's why they're on Moodle.

✅ **OK:**
- keeping them in **your own private** cloud folder,
- studying from them,
- your own notes on them.

❌ **Not OK:**
- a **public link** to the folder, or sharing it with "anyone with the link",
- re-uploading materials to note-sharing sites, public repositories, Discord servers or group chats,
- sharing them with people who aren't in the course,
- selling or publishing them.

Some teachers explicitly forbid any redistribution, and their conditions apply. In Poland, *dozwolony użytek prywatny* (art. 23 of the Copyright Act) covers personal use. It does not cover publishing or wider sharing.

**Never commit `downloads/` to Git**, and never put course materials into a public repository. The folder is in `.gitignore` for this reason.

## 2. Other people's personal data 👥

Announcements sometimes contain other students' data: names, student ID numbers, grades. moodle-sync forwards announcements to *your* Telegram/Discord/e-mail, so that data ends up in your notifications.
- Keep your notification channel **private**: your own chat, or a Discord server only you are on. Don't use a group chat or a public channel.
- **Don't screenshot or forward** such announcements to group chats.
- Under the GDPR (RODO), keeping it for yourself is personal use. Spreading it is not.

## 3. Follow your university's rules 🏫

Universities have study regulations, e-learning rules and IT acceptable-use policies. They typically forbid:
- **sharing your login or token** with anyone,
- using university systems in a way that **overloads** them,
- accessing data you're not entitled to.

moodle-sync is designed to fit such rules:
- it uses the **official mobile app API**, on **your own** account, **read-only** unless you turn on `MOODLE_ACTIONS` - then it submits, posts and marks attendance only after you confirm each one;
- it makes a few dozen requests per run, and checks announcements at most every 30 minutes and grades every hour;
- it identifies itself honestly (User-Agent with the project's name).

If in doubt, read the rules or ask your IT department. Asking is always better than guessing.

## 4. Don'ts ⛔

- **Don't run moodle-sync for other people.** Don't collect classmates' tokens, don't set up a shared "service", don't share your `.env`. A token is a password; one person, one account.
- **Don't shorten the intervals.** Don't run it every minute, remove throttling, or run many copies at once. University servers serve thousands of students.
- **Don't use it to get around restrictions**, e.g. materials hidden until a certain date. moodle-sync only sees what you already see in Moodle, and should stay that way.
- **Don't upload course materials to third-party AI tools** unless your university and the teacher allow it. Some AI services store or train on uploaded content, which may breach copyright and course rules.

- **Mark attendance only when you are actually there.** The bot does what the Moodle app does - it can't know where you are, so honesty is on you. Sessions limited to the university network will refuse a bot running at home.
- **What you submit or post through the bot is yours**, exactly as if you clicked it in Moodle. Check the summary before you tap ✅.

## 5. No affiliation, no warranty

moodle-sync is an independent student project. It is **not affiliated with or endorsed by** Moodle Pty Ltd or any university. It comes **without warranty** ([MIT license](../../LICENSE)). Don't rely on it as your only source of deadlines, and **always check Moodle itself** for anything important.

---

**Summary:** download for yourself, keep it private, respect your university's rules and the people in your courses.
