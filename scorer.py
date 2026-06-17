"""Scores Notes for relevance and drafts reply angles using any LLM you choose.

Talks to any OpenAI-compatible server. Configure via env:
  LLM_BASE_URL  — base URL (default LM Studio: http://localhost:1234/v1)
  LLM_MODEL     — model id (default: whatever a local server has loaded)
  LLM_API_KEY   — optional; set it for cloud providers (OpenAI, OpenRouter,
                  Anthropic's OpenAI-compatible endpoint, etc.). Leave blank
                  for local servers like LM Studio or Ollama — nothing leaves
                  your machine in that case.
"""

import os
import re
import json
import httpx
from profile import RELEVANCE_SYSTEM_PROMPT, TOPIC_TAGS

BASE_URL = os.environ.get("LLM_BASE_URL", "http://localhost:1234/v1").rstrip("/")
API_KEY = os.environ.get("LLM_API_KEY", "").strip()
# Local models handle smaller batches more reliably and emit cleaner JSON.
BATCH_SIZE = 10
REQUEST_TIMEOUT = 300  # local inference can be slow

_resolved_model = None


def _auth_headers() -> dict:
    """Bearer auth for cloud providers; empty for local servers."""
    return {"Authorization": f"Bearer {API_KEY}"} if API_KEY else {}


def _resolve_model() -> str:
    """Use LLM_MODEL if set, else ask the server which model is loaded."""
    global _resolved_model
    if _resolved_model:
        return _resolved_model

    env_model = os.environ.get("LLM_MODEL", "").strip()
    if env_model:
        _resolved_model = env_model
        return _resolved_model

    # Auto-detect the loaded model from the OpenAI-compatible /models endpoint
    try:
        r = httpx.get(f"{BASE_URL}/models", headers=_auth_headers(), timeout=10)
        r.raise_for_status()
        data = r.json().get("data", [])
        if data:
            _resolved_model = data[0]["id"]
            return _resolved_model
    except Exception:
        pass

    # Last resort — LM Studio ignores an unknown name and uses the loaded model
    _resolved_model = "local-model"
    return _resolved_model


def is_llm_available() -> bool:
    """Quick reachability check for the configured LLM server."""
    try:
        httpx.get(f"{BASE_URL}/models", headers=_auth_headers(), timeout=5).raise_for_status()
        return True
    except Exception:
        return False


def _extract_json_array(text: str):
    """Pull the first JSON array out of a model response, tolerating chatter."""
    text = text.strip()
    # Strip markdown code fences if present
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text
        text = text.rsplit("```", 1)[0]
    # Direct parse
    try:
        parsed = json.loads(text)
        if isinstance(parsed, list):
            return parsed
        if isinstance(parsed, dict):
            # Some models wrap the array, e.g. {"results": [...]}
            for v in parsed.values():
                if isinstance(v, list):
                    return v
    except json.JSONDecodeError:
        pass
    # Fall back to grabbing the outermost [...] span
    m = re.search(r"\[.*\]", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            return []
    return []


def score_and_draft(notes: list[dict]) -> list[dict]:
    """
    Takes a list of normalised note dicts, scores each for relevance,
    and drafts a reply angle for the top ones.
    Returns scored notes sorted by relevance desc.
    """
    if not notes:
        return []

    all_scored = []
    for i in range(0, len(notes), BATCH_SIZE):
        batch = notes[i : i + BATCH_SIZE]
        all_scored.extend(_score_batch(batch))

    all_scored.sort(key=lambda x: x.get("relevance_score", 0), reverse=True)
    return all_scored


def _classify(note: dict) -> str:
    """
    Decide high_visibility vs peer from concrete engagement signals rather than
    the model's world knowledge of who's famous — so it works with any local model.
    """
    subs = note.get("subscriber_count") or 0
    likes = note.get("reaction_count") or 0
    restacks = note.get("restacks") or 0
    if subs >= 10000 or likes >= 50 or restacks >= 15:
        return "high_visibility"
    return "peer"


def _score_batch(notes: list[dict]) -> list[dict]:
    notes_text = "\n\n".join(
        f"[{idx}] ID:{n['id']} | Author:{n['author']} | "
        f"Engagement:{n['reaction_count']} likes {n['comment_count']} replies {n['restacks']} restacks | "
        f"Subscribers:{n.get('subscriber_count') or 'unknown'}\n"
        f"Content: {n['body'][:400]}"
        for idx, n in enumerate(notes)
    )

    prompt = f"""Evaluate these Substack Notes for engagement opportunities.

{notes_text}

For each note, return a JSON array with objects containing:
- "idx": the index number [0], [1], etc.
- "relevance_score": 0-10 (how topically relevant to the author's profile)
- "topics": array of 1-3 labels chosen ONLY from this exact list (copy verbatim, no new labels):
  {json.dumps(TOPIC_TAGS)}
  Pick the labels that best capture what the note is about. If none fit well, use an empty array.
- "why": one sentence on why this is worth engaging
- "reply_angle": 2-3 sentences — a specific, substantive reply the author could post. Must add a distinct perspective from their expertise, not just agree. Reference their own work/POV where natural.

Only include notes with relevance_score >= 6.
Return ONLY valid JSON array, no other text."""

    payload = {
        "model": _resolve_model(),
        "messages": [
            {"role": "system", "content": RELEVANCE_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.3,
        "max_tokens": 3000,
        "stream": False,
    }

    try:
        r = httpx.post(
            f"{BASE_URL}/chat/completions",
            json=payload,
            headers=_auth_headers(),
            timeout=REQUEST_TIMEOUT,
        )
        r.raise_for_status()
        content = r.json()["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"  LLM request failed: {e}")
        return []

    scored = _extract_json_array(content)

    results = []
    for item in scored:
        if not isinstance(item, dict):
            continue
        idx = item.get("idx")
        if idx is None or not isinstance(idx, int) or idx >= len(notes):
            continue
        note = notes[idx].copy()
        note["relevance_score"] = item.get("relevance_score", 0)
        # Classify from engagement metrics, not the model's guess
        note["opportunity_type"] = _classify(note)
        # Keep only topics that are in the known vocabulary
        note["topics"] = [t for t in item.get("topics", []) if t in TOPIC_TAGS]
        note["why"] = item.get("why", "")
        note["reply_angle"] = item.get("reply_angle", "")
        results.append(note)

    return results
