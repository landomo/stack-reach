#!/usr/bin/env python3
"""
Substack Engagement Agent — headless CLI.

Fetches your live Notes feed, scores each note for relevance, drafts reply
angles, and writes scored_notes.json (the same file the UI reads).

Usage:
  python main.py             # fetch + score, write scored_notes.json
  python main.py --check     # just verify the session cookie is still valid

For the interactive UI (meter, digest, refresh button) run serve.py instead.
"""

import os
import sys
import json
import argparse
from dotenv import load_dotenv

load_dotenv()


def check_env():
    if not os.environ.get("SUBSTACK_SESSION_COOKIE"):
        print("Missing SUBSTACK_SESSION_COOKIE in .env")
        print("Copy .env.example to .env and fill in the values.")
        sys.exit(1)

    from scorer import is_llm_available, BASE_URL
    if not is_llm_available():
        print(f"Local LLM not reachable at {BASE_URL}")
        print("Start the LM Studio server and load a model, then retry.")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="Verify the session cookie")
    args = parser.parse_args()

    from scraper import fetch_notes_feed, is_session_valid

    cookie = os.environ.get("SUBSTACK_SESSION_COOKIE", "")

    if args.check:
        if not cookie:
            print("✗ SUBSTACK_SESSION_COOKIE not set in .env")
            sys.exit(1)
        if is_session_valid(cookie):
            print("✓ Session cookie is valid")
        else:
            print("✗ Session expired — grab a fresh substack.sid from DevTools")
            sys.exit(1)
        return

    check_env()

    if not is_session_valid(cookie):
        print("✗ Session expired — grab a fresh substack.sid from DevTools and update .env")
        sys.exit(1)

    from scorer import score_and_draft

    print("Fetching Notes feed…")
    notes = fetch_notes_feed(cookie, limit=80)
    print(f"Fetched {len(notes)} notes. Scoring…")

    scored = score_and_draft(notes)
    hv = [n for n in scored if n.get("opportunity_type") == "high_visibility"]
    peers = [n for n in scored if n.get("opportunity_type") == "peer"]

    import datetime
    from profile import TOPIC_TAGS
    out = {
        "high_visibility": hv[:8],
        "peers": peers[:8],
        "all": scored,
        "topic_vocab": TOPIC_TAGS,
        "generated_at": datetime.datetime.now().isoformat(timespec="seconds"),
    }
    with open("scored_notes.json", "w") as f:
        json.dump(out, f, indent=2)

    print(f"Wrote scored_notes.json — {len(hv)} high-visibility, {len(peers)} peers")


if __name__ == "__main__":
    main()
