# Daily Wisdom Faith — Auto-Upload System

**Goal**: Post one 5–10 minute gospel meditation video to
[@DailyWisdomFaith](https://www.youtube.com/@DailyWisdomFaith) every day at
9:00 AM IST, fully automated. The user uploads three files to a dated Google
Drive folder — a Suno-generated audio file, a short background video clip,
and a thumbnail image — and the system stitches and publishes the result
without human intervention.

## Architecture

```
┌─ User ───────────────────────────────────┐
│ Drops audio.mp3 + video.mp4 + thumb.jpg  │
│ into Google Drive: queue/YYYY-MM-DD/     │
└──────────────┬───────────────────────────┘
               │
               ▼
┌─ GitHub Actions cron (free) ─────┐
│ Daily at 03:30 UTC (09:00 IST)   │
│                                  │
│ 1. Pull today's Drive folder     │
│ 2. Generate metadata (DeepSeek)  │   ← title, desc, tags from filename
│ 3. Resize/crop thumbnail (Pillow)│   ← user image → 1280×720 / <2 MB
│ 4. Stitch video (FFmpeg)         │   ← loop bg to audio length, fades
│ 5. Upload to YouTube + schedule  │
│ 6. Move folder → published/      │
│ 7. Top up future folder window   │
│ 8. Email naveends798@gmail.com   │
└──────────────────────────────────┘
```

## Drive folder layout

```
prayer-channel-queue/
├── 2026-05-11/        ← today; system processes this folder
│   ├── audio.mp3      ← user-supplied (Suno download)
│   ├── video.mp4      ← user-supplied (any short loop clip)
│   ├── thumbnail.jpg  ← user-supplied (any 16:9-ish image)
│   └── notes.txt      ← optional overrides (title, scripture, etc.)
├── 2026-05-12/        ← tomorrow; pre-created, empty
├── 2026-05-13/
├── ...                ← rolling 30-day window of empty future folders
├── default/           ← fallback content used if today's folder is empty
│   ├── audio.mp3
│   ├── video.mp4
│   └── thumbnail.jpg
└── published/         ← processed folders moved here for archival
    └── 2026-05-10/
        ├── audio.mp3
        ├── video.mp4
        ├── thumbnail.jpg
        ├── final.mp4
        └── metadata.json
```

The audio filename is the only required input; everything else is derived. Name
files in kebab-case with optional scripture reference, e.g.
`trust-in-the-lord-psalm-23.mp3`.

## Metadata generation

A single structured prompt to DeepSeek (via Ollama Cloud) returns:

```json
{
  "title": "Trust in the Lord · Psalm 23 · 5 Min Prayer Music",
  "description": "...500 words: opening blessing, scripture quote, call to subscribe, hashtags, AI-disclosure footer...",
  "tags": ["gospel meditation", "psalm 23", "morning prayer music", ...],
  "thumbnail_words": "PSALM 23",
  "thumbnail_subtitle": "Trust in the Lord",
  "category_id": "10",
  "scripture_reference": "Psalm 23"
}
```

The `category_id` is YouTube's numeric category. `10` = Music; `22` = People &
Blogs; `29` = Nonprofits & Activism. The model picks based on song theme.

The `thumbnail_words` and `thumbnail_subtitle` fields are still produced by
the model but are unused at render time (kept in the schema for future
re-introduction of AI thumbnails or alternate templates without a model
prompt change).

## Thumbnail processing (1280×720)

The user provides their own thumbnail image (.jpg or .png) in the daily Drive
folder. The system:

- Center-crops to a 16:9 ratio (preserves the user's framing)
- Resizes to 1280×720 (YouTube's optimal thumbnail spec)
- Re-encodes as JPEG, decreasing quality until the file is under YouTube's
  2 MB upload limit (starting at quality 92, floor at 70)

No AI image generation, no text overlay — the user's visual is used as-is.
This gives full creative control to the channel owner and eliminates
Together.ai as a dependency.

## Video composition

- Loop `video.mp4` to match audio length (FFmpeg `-stream_loop`)
- Mix audio: fade in 2s, fade out 3s
- Encode: H.264 yuv420p, 1080p, AAC 192k stereo, faststart
- Output: `final.mp4`, ready for direct YouTube upload

## YouTube upload

- `videos.insert` with chunked upload (resilient to flaky network)
- `status.privacyStatus = private` initially, with
  `status.publishAt = today 09:00 IST` (RFC3339); YouTube auto-flips to public
- `status.containsSyntheticMedia = true` — declares AI-generated content per
  YouTube's synthetic media disclosure rule
- `status.madeForKids = false`
- After upload, `thumbnails.set` attaches the JPEG

## Failure handling

- Tenacity retries on transient errors (network, 5xx, 429): 3 attempts with
  exponential backoff
- Fatal errors: the workflow exits non-zero. GitHub Actions emails the
  account owner automatically on failure. If `SMTP_APP_PASSWORD` is set, a
  richer failure email with the last 50 log lines also goes to
  `naveends798@gmail.com`. Without it, the notifier is a no-op.
- Empty today-folder: the system falls back to the `default/` folder content
  with a fresh AI-generated title (so the channel never goes dark)
- Folder-window depletion: after each successful publish, a maintenance step
  ensures 30 future date folders exist

## Cost estimate

| Item                 | Cost                      |
| -------------------- | ------------------------- |
| GitHub Actions       | Free (well within 2000 min/mo) |
| Google Drive         | Free (15 GB included)     |
| YouTube Data API     | Free (default quota of 10k units/day; one upload uses ~1600) |
| Ollama Cloud         | Per existing subscription |
| Gmail SMTP           | Free                      |
| **Total**            | **$0/month** (excluding Ollama subscription) |

## Out of scope (deliberately)

- Whisper transcription (filename is sufficient grounding per user decision)
- AI thumbnail generation (user supplies their own thumbnail per current scope)
- Auto-replying to comments
- Auto-creating Shorts from the same audio
- Multi-channel support
