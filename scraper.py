"""Fetches Substack Notes using the authenticated session cookie."""

import os
import httpx
from urllib.parse import unquote
from typing import Optional


def _headers(cookie: str) -> dict:
    # Cookie may arrive URL-encoded from browser copy — decode it
    decoded = unquote(cookie)
    return {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json",
        "Referer": "https://substack.com/notes",
        "Cookie": f"substack.sid={decoded}",
    }


def is_session_valid(cookie: str) -> bool:
    """
    Probe an auth-gated endpoint to confirm the session cookie is still live.
    The Notes feed itself returns a generic feed when logged out (no 401), so we
    hit /subscriptions which returns 401 only when the session is invalid/expired.
    """
    if not cookie:
        return False
    try:
        with httpx.Client(follow_redirects=False) as client:
            resp = client.get(
                "https://substack.com/api/v1/subscriptions",
                headers=_headers(cookie),
                timeout=10,
            )
        # 401 = expired/invalid session. Anything else (200/400) = authenticated.
        return resp.status_code != 401
    except Exception:
        # Network error — don't cry wolf about an expired cookie
        return True


def fetch_notes_feed(
    cookie: str,
    limit: int = 80,
    pages: int = 6,
) -> list[dict]:
    """Fetches from the authenticated reader feed, paginating up to `pages` times."""
    all_items = []
    cursor = None

    with httpx.Client(follow_redirects=True) as client:
        for _ in range(pages):
            params = {"limit": min(limit, 25)}
            if cursor:
                params["cursor"] = cursor

            resp = client.get(
                "https://substack.com/api/v1/reader/feed",
                params=params,
                headers=_headers(cookie),
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()

            items = data.get("items", [])
            if not items:
                break

            all_items.extend(items)
            cursor = data.get("nextCursor")
            if not cursor or len(all_items) >= limit:
                break

    return _normalize(all_items)


def fetch_publication_posts(subdomain: str, limit: int = 10) -> list[dict]:
    """Fetches recent posts from a specific Substack publication (no auth needed)."""
    base = f"https://{subdomain}.substack.com"
    with httpx.Client(follow_redirects=True) as client:
        resp = client.get(
            f"{base}/api/v1/posts",
            params={"limit": limit},
            headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"},
            timeout=10,
        )
        if resp.status_code != 200:
            return []
        posts = resp.json()

    return [
        {
            "id": p.get("id"),
            "type": "post",
            "author": subdomain,
            "title": p.get("title", ""),
            "body": p.get("truncated_body_text") or p.get("description") or p.get("subtitle", ""),
            "url": p.get("canonical_url", ""),
            "reaction_count": p.get("reaction_count", 0),
            "comment_count": p.get("comment_count", 0),
            "restacks": p.get("restacks", 0),
            "post_date": p.get("post_date", ""),
            "subdomain": subdomain,
            "subscriber_count": None,
        }
        for p in posts
        if p.get("type") == "newsletter"
    ]


def _normalize(items: list) -> list[dict]:
    """Normalises reader feed items into a consistent shape."""
    results = []
    for item in items:
        # Only process notes (not reposts of articles etc.)
        if item.get("context", {}).get("type") != "note":
            continue

        c = item.get("comment") or {}
        pub = item.get("publication") or c.get("user_primary_publication") or {}

        # Author name/handle sit directly on the comment object
        author_name = c.get("name") or c.get("handle") or "unknown"
        author_handle = c.get("handle") or ""

        # Extract plain text from body_json paragraphs if body is empty
        body = c.get("body") or ""
        if not body and c.get("body_json"):
            try:
                bj = c["body_json"]
                if isinstance(bj, str):
                    import json
                    bj = json.loads(bj)
                body = " ".join(
                    n.get("text", "")
                    for block in bj.get("content", [])
                    for n in block.get("content", [])
                    if n.get("type") == "text"
                )
            except Exception:
                pass

        if not str(body).strip():
            continue

        # Build note URL — prefer a direct inbox link, fall back to author's publication
        subdomain = pub.get("subdomain") or ""
        custom_domain = pub.get("custom_domain") or ""
        post_id = c.get("post_id")
        note_id = c.get("id")

        if note_id:
            # Substack resolves this to the canonical profile note URL
            note_url = f"https://substack.com/note/c-{note_id}"
        elif subdomain:
            note_url = f"https://{subdomain}.substack.com"
        else:
            note_url = ""

        results.append({
            "id": c.get("id"),
            "type": "note",
            "author": author_name,
            "author_handle": author_handle,
            "body": str(body)[:2000],
            "url": note_url,
            "reaction_count": c.get("reaction_count", 0),
            "comment_count": c.get("children_count", 0),
            "restacks": c.get("restacks", 0),
            "post_date": c.get("date", ""),
            "subdomain": subdomain,
            "subscriber_count": pub.get("subscriber_count") or pub.get("subscriberCount"),
        })
    return results
