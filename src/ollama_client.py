"""Generate YouTube metadata from an audio filename via Ollama Cloud (DeepSeek)."""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Optional

import requests
from tenacity import retry, stop_after_attempt, wait_exponential

from .config import Config

log = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
You are the metadata writer for "Daily Wisdom Faith", a Christian gospel and
prayer YouTube channel that posts a 5–10 minute meditation audio video each day
at 9 AM IST. Subscribers come for warm, reverent, scripture-grounded content.

Given the kebab-case audio filename and optional user notes, return STRICT JSON
matching the schema below — no prose, no markdown, no code fences. Just JSON.

The voice is: gentle, hopeful, scripture-quoting, never preachy. Avoid
clickbait, ALL CAPS in titles, emojis in titles. Hashtags belong only in the
description footer (max 5).

Always include this AI-disclosure line at the END of the description:

  "🎵 The music in this video is AI-generated. Use it as a quiet companion for
   prayer, devotion, and reflection."

Schema (all keys required):

{
  "title":               string, ≤ 95 chars, includes a hook + scripture if relevant + duration phrase like "5 Min Prayer Music",
  "description":         string, 350–600 words, opens with a one-line blessing, quotes a relevant scripture verse, invites stillness, ends with 3–5 hashtags then the AI-disclosure line above,
  "tags":                array of 12–18 short SEO tags, lowercase, no leading hash,
  "thumbnail_words":     string, 1–3 words, the hero phrase for the thumbnail (e.g. "PSALM 23", "BE STILL", "TRUST"),
  "thumbnail_subtitle":  string, 2–6 words, secondary line under the hero phrase (e.g. "Trust in the Lord"),
  "category_id":         string, one of "10" (Music), "22" (People & Blogs), "29" (Nonprofits & Activism); pick the best fit,
  "scripture_reference": string, e.g. "Psalm 23:1-6" or "" if none specifically applies
}
"""

USER_TEMPLATE = """\
Audio filename: {filename}
User notes: {notes}

Return JSON only.
"""


@dataclass
class Metadata:
    title: str
    description: str
    tags: list[str]
    thumbnail_words: str
    thumbnail_subtitle: str
    category_id: str
    scripture_reference: str

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "description": self.description,
            "tags": self.tags,
            "thumbnail_words": self.thumbnail_words,
            "thumbnail_subtitle": self.thumbnail_subtitle,
            "category_id": self.category_id,
            "scripture_reference": self.scripture_reference,
        }


def _extract_json(text: str) -> dict:
    """Pull the first JSON object out of a model response, even if surrounded
    by stray text or fenced in markdown."""
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fence:
        return json.loads(fence.group(1))
    brace = re.search(r"\{.*\}", text, re.DOTALL)
    if brace:
        return json.loads(brace.group(0))
    raise ValueError(f"No JSON object in model response: {text[:200]!r}")


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, min=2, max=20),
    reraise=True,
)
def generate_metadata(
    cfg: Config, *, audio_filename_stem: str, notes: Optional[str]
) -> Metadata:
    """Call Ollama Cloud chat completion and parse a Metadata object."""
    url = f"{cfg.ollama_api_base.rstrip('/')}/chat"
    headers = {
        "Authorization": f"Bearer {cfg.ollama_api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": cfg.ollama_model,
        "stream": False,
        "format": "json",
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": USER_TEMPLATE.format(
                    filename=audio_filename_stem,
                    notes=notes or "(none)",
                ),
            },
        ],
        "options": {"temperature": 0.7},
    }
    log.info("Requesting metadata from %s (model=%s)", url, cfg.ollama_model)
    resp = requests.post(url, json=payload, headers=headers, timeout=120)
    resp.raise_for_status()
    body = resp.json()

    # Ollama chat response: {"message": {"content": "..."}}
    content = ""
    if isinstance(body, dict):
        msg = body.get("message") or {}
        content = msg.get("content", "") or body.get("response", "")
    if not content:
        raise ValueError(f"Empty response from Ollama: {body!r}")

    raw = _extract_json(content)
    return Metadata(
        title=raw["title"].strip()[:95],
        description=raw["description"].strip(),
        tags=[t.strip().lstrip("#").lower() for t in raw["tags"] if t.strip()][:18],
        thumbnail_words=raw["thumbnail_words"].strip().upper()[:24],
        thumbnail_subtitle=raw["thumbnail_subtitle"].strip()[:48],
        category_id=str(raw.get("category_id", "10")),
        scripture_reference=raw.get("scripture_reference", "").strip(),
    )
