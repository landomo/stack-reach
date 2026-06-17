# Stack Reach

A small, local tool that helps Substack writers engage with intent. It reads
your Substack Notes feed, scores each note for relevance to your beat, drafts a
reply angle for the good ones, and lays them out on a simple dashboard — so you
spend your time replying, not scrolling.

**Runs entirely on your own machine. Read-only. Suggests; never posts.**

> Free and open source (MIT). Not affiliated with Substack.

---

## What it does

- Pulls your Substack **Notes feed** (including writers you don't follow yet —
  it's the same algorithmic feed you see on the Notes tab).
- Scores each note for relevance to **your** topics, learned from your bio and
  recent posts.
- Ranks opportunities along two axes — **peer** writers (mutual growth) and
  **high-visibility** accounts (reach) — with a meter to weight the mix.
- Lets you **emphasize topics** to spotlight a theme.
- Drafts a **reply angle** for each opportunity, in your voice.
- Tracks what you **responded to / skipped** in a local archive.

Nothing is ever posted on your behalf. You decide what to say and when.

## How it works

1. **You** supply your own logged-in Substack session (a cookie you copy once).
2. The tool reads *your* feed, locally, at human scale.
3. Scoring runs on an **LLM of your choice** — local (LM Studio, Ollama) or a
   cloud API (OpenAI, Claude, OpenRouter). Local keeps everything on your
   machine; cloud sends note content to that provider.

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env       # then fill in the two values below
```

**1. Substack session cookie** — open [substack.com/notes](https://substack.com/notes)
while logged in → DevTools (⌥⌘I) → Application → Cookies → `https://substack.com`
→ copy the `substack.sid` value into `.env`. (Cookies expire ~monthly; the UI
tells you when to refresh it.)

**2. Pick an LLM backend** in `.env` — see the presets in `.env.example`. The
default is LM Studio (fully local). To use Claude/OpenAI/OpenRouter instead,
set `LLM_BASE_URL`, `LLM_MODEL`, and `LLM_API_KEY`.

## Run

```bash
python3 serve.py     # opens the dashboard at http://localhost:8765
```

Or headless (e.g. for a cron job that refreshes scored results):

```bash
python3 main.py          # fetch + score → scored_notes.json
python3 main.py --check  # verify your session cookie is still valid
```

## Privacy & responsible use

- **Your data stays yours.** With a local LLM, nothing leaves your machine. If
  you choose a cloud LLM, note that note content is sent to that provider.
- **Read-only and suggest-only by design.** It never posts, follows, likes, or
  takes any action on your account — it surfaces and drafts; you act manually.
- **Use your own session, at a reasonable pace.** This tool accesses Substack's
  feed the way your browser does. You are responsible for using it in line with
  [Substack's Terms](https://substack.com/tos). Don't hammer the API or run it
  at scale.

## Files

```
serve.py          — local dashboard server (primary entrypoint)
ui.html           — the dashboard interface
main.py           — headless fetch + score CLI
profile.py        — your author profile + topic vocabulary
scraper.py        — Substack feed fetch + session check
scorer.py         — LLM relevance scoring + reply drafting (any OpenAI-compatible backend)
```

## License

MIT — see [LICENSE](LICENSE).
