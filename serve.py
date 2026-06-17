#!/usr/bin/env python3
"""
Local UI server for the Substack Engagement Agent.
Run: python3 serve.py
Then open: http://localhost:8765
"""

import json
import os
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE = Path(__file__).parent
PORT = 8765
ARCHIVE_PATH = BASE / "archive.json"


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass  # quiet server

    def do_GET(self):
        if self.path == "/" or self.path == "/index.html":
            self._serve_file(BASE / "ui.html", "text/html")
        elif self.path == "/data":
            self._serve_json()
        elif self.path == "/refresh":
            self._refresh()
        elif self.path == "/check-auth":
            self._check_auth()
        elif self.path == "/archive":
            self._get_archive()
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        if self.path == "/archive":
            self._post_archive()
        elif self.path == "/archive/restore":
            self._restore_archive()
        elif self.path == "/archive/clear":
            self._clear_archive()
        else:
            self.send_response(404)
            self.end_headers()

    # ── helpers ──
    def _read_body(self) -> dict:
        length = int(self.headers.get("Content-Length", 0))
        if not length:
            return {}
        try:
            return json.loads(self.rfile.read(length))
        except Exception:
            return {}

    def _json(self, obj):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(obj).encode())

    @staticmethod
    def _load_archive() -> list:
        if ARCHIVE_PATH.exists():
            try:
                return json.loads(ARCHIVE_PATH.read_text())
            except Exception:
                return []
        return []

    @staticmethod
    def _save_archive(items: list):
        ARCHIVE_PATH.write_text(json.dumps(items, indent=2))

    # ── archive endpoints ──
    def _get_archive(self):
        self._json({"items": self._load_archive()})

    def _post_archive(self):
        """Add (or update) a note in the archive with a status + timestamp."""
        import datetime
        body = self._read_body()
        note = body.get("note") or {}
        status = body.get("status", "skipped")
        note_id = note.get("id")
        if note_id is None:
            self._json({"error": "missing note id"})
            return

        items = self._load_archive()
        items = [it for it in items if it.get("id") != note_id]  # dedupe
        entry = dict(note)
        entry["status"] = status
        entry["archived_at"] = datetime.datetime.now().isoformat(timespec="seconds")
        items.insert(0, entry)
        self._save_archive(items)
        self._json({"ok": True, "count": len(items)})

    def _restore_archive(self):
        """Remove a note from the archive (so it returns to the active board)."""
        body = self._read_body()
        note_id = body.get("id")
        items = [it for it in self._load_archive() if it.get("id") != note_id]
        self._save_archive(items)
        self._json({"ok": True, "count": len(items)})

    def _clear_archive(self):
        self._save_archive([])
        self._json({"ok": True, "count": 0})

    def _check_auth(self):
        """Lightweight probe: is the session cookie still valid?"""
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()

        cookie = os.environ.get("SUBSTACK_SESSION_COOKIE", "")
        if not cookie:
            self.wfile.write(json.dumps({"ok": False, "reason": "missing"}).encode())
            return
        try:
            sys.path.insert(0, str(BASE))
            from scraper import is_session_valid
            if is_session_valid(cookie):
                self.wfile.write(json.dumps({"ok": True}).encode())
            else:
                self.wfile.write(json.dumps({"ok": False, "reason": "expired"}).encode())
        except Exception as e:
            self.wfile.write(json.dumps({"ok": False, "reason": "error", "detail": str(e)}).encode())

    def _serve_file(self, path: Path, content_type: str):
        if not path.exists():
            self.send_response(404)
            self.end_headers()
            return
        data = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", len(data))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _serve_json(self):
        scored_path = BASE / "scored_notes.json"
        if not scored_path.exists():
            data = json.dumps({"error": "No scored notes yet. Run python3 main.py first."})
        else:
            data = scored_path.read_text()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(data.encode())

    def _refresh(self):
        """Fetch the live Notes feed, score it, write scored_notes.json, return it."""
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()

        cookie = os.environ.get("SUBSTACK_SESSION_COOKIE", "")
        if not cookie:
            self.wfile.write(json.dumps({
                "error": "SUBSTACK_SESSION_COOKIE not set in .env"
            }).encode())
            return

        try:
            sys.path.insert(0, str(BASE))
            from scraper import fetch_notes_feed, is_session_valid
            from scorer import score_and_draft, is_llm_available, BASE_URL

            if not is_session_valid(cookie):
                self.wfile.write(json.dumps({
                    "error": "session expired",
                    "auth_expired": True,
                }).encode())
                return

            if not is_llm_available():
                self.wfile.write(json.dumps({
                    "error": f"Local LLM not reachable at {BASE_URL} — start LM Studio and load a model",
                }).encode())
                return

            notes = fetch_notes_feed(cookie, limit=80)
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
            (BASE / "scored_notes.json").write_text(json.dumps(out, indent=2))

            out["fetched"] = len(notes)
            self.wfile.write(json.dumps(out).encode())
        except Exception as e:
            msg = str(e)
            expired = "401" in msg or "403" in msg
            self.wfile.write(json.dumps({
                "error": msg,
                "auth_expired": expired,
            }).encode())


def main():
    scored_path = BASE / "scored_notes.json"
    if not scored_path.exists():
        print("No scored_notes.json yet — click Refresh in the UI to fetch your feed.")

    server = HTTPServer(("localhost", PORT), Handler)
    url = f"http://localhost:{PORT}"
    print(f"Substack Agent UI → {url}")
    threading.Timer(0.5, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")


if __name__ == "__main__":
    main()
