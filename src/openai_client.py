"""Generate YouTube metadata from an audio filename via the OpenAI Chat
Completions API. Uses gpt-4o-mini by default — fast and cheap, and excellent
at producing valid structured JSON via response_format=json_object."""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Optional

import requests
from tenacity import (
    retry,
    retry_if_not_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from .config import Config

log = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
You are the metadata writer for "Daily Wisdom Faith", a Christian gospel and
prayer YouTube channel that posts a 5–10 minute meditation audio video each day
at 9 AM IST. Subscribers come for warm, reverent, scripture-grounded content.

The kebab-case audio filename is your SOURCE OF TRUTH. Parse it to extract:
  • the theme / hero phrase  (e.g. "peace-be-still"      → "Peace Be Still")
  • the scripture reference  (e.g. "...-mark-4"          → "Mark 4")
  • the mood and bucket      (peace / trust / healing / hope / love / strength)
Every field you generate — title, description, tags, thumbnail — must be
grounded in what the filename says. Do not invent a different theme.

Return STRICT JSON matching the schema below — no prose, no markdown,
no code fences. Just JSON.

The voice is: gentle, hopeful, scripture-quoting, never preachy. Avoid
clickbait, ALL CAPS in titles, emojis in titles. Hashtags belong only in the
description footer (max 5).

TITLE RULES (strict):
  • Must contain the phrase "Gospel Song" — or a close equivalent such as
    "Christian Gospel Song", "Worship Song", "Prayer Song", or
    "Gospel Worship". Rotate naturally, do not use the same phrase every day.
  • Must reference the theme from the filename (e.g. "Peace Be Still").
  • Must include the scripture reference from the filename when present
    (e.g. "Mark 4", "Psalm 23", "Lamentations 3").
  • Should end with a duration / use cue such as "5 Min Prayer Music",
    "Music for Prayer & Meditation", or "Music for Worship".
  • ≤ 95 characters, title case, no ALL CAPS, no emojis.
  • Examples (style only — do not copy):
      - "Peace Be Still — Gospel Song for Anxiety | Mark 4 | Music for Prayer"
      - "His Mercies Are New | Lamentations 3 Christian Gospel Song for Hope"
      - "The Lord Is My Shepherd | Psalm 23 Worship Song for Peace & Rest"

Always include this AI-disclosure line at the END of the description:

  "🎵 The music in this video is AI-generated. Use it as a quiet companion for
   prayer, devotion, and reflection."

Schema (all keys required):

{
  "title":               string, follows the TITLE RULES above,
  "description":         string, 350–600 words, opens with a one-line blessing, names the gospel song theme from the filename, quotes the relevant scripture verse in full, invites stillness, ends with 3–5 hashtags (must include #gospelsong and #dailywisdomfaith) then the AI-disclosure line above,
  "tags":                array of 12–18 short SEO tags, lowercase, no leading hash; MUST include "gospel song", "christian gospel song", "worship song", "prayer music", and the scripture book/chapter from the filename,
  "thumbnail_words":     string, 1–3 words, the hero phrase for the thumbnail (e.g. "PSALM 23", "BE STILL", "TRUST"),
  "thumbnail_subtitle":  string, 2–6 words, secondary line under the hero phrase (e.g. "Trust in the Lord"),
  "category_id":         string, one of "10" (Music), "22" (People & Blogs), "29" (Nonprofits & Activism); default to "10" (Music) for gospel songs,
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


class _ClientError(Exception):
    """4xx error from OpenAI — don't retry, fail fast with the response body."""


def _extract_json(text: str) -> dict:
    """Pull the first JSON object out of a model response."""
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
    retry=retry_if_not_exception_type(_ClientError),
)
def generate_metadata(
    cfg: Config, *, audio_filename_stem: str, notes: Optional[str]
) -> Metadata:
    """Call OpenAI chat completion and parse a Metadata object."""
    url = f"{cfg.openai_api_base.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {cfg.openai_api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": cfg.openai_model,
        "temperature": 0.7,
        "response_format": {"type": "json_object"},
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
    }
    log.info("Requesting metadata from %s (model=%s)", url, cfg.openai_model)
    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=60)
    except requests.exceptions.Timeout as e:
        log.warning("OpenAI request timed out (will retry): %s", e)
        raise
    if 400 <= resp.status_code < 500:
        snippet = resp.text[:500].replace("\n", " ")
        raise _ClientError(
            f"OpenAI returned {resp.status_code} for model {cfg.openai_model!r}: "
            f"{snippet}. Check OPENAI_API_KEY and OPENAI_MODEL."
        )
    resp.raise_for_status()
    body = resp.json()

    try:
        content = body["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as e:
        raise ValueError(f"Unexpected OpenAI response shape: {body!r}") from e

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
