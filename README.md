# Daily Wisdom Faith — Auto-Upload System

Automated YouTube uploader for [@DailyWisdomFaith](https://www.youtube.com/@DailyWisdomFaith).
You drop three files into a Google Drive folder — audio, video, and a thumbnail
image. The system stitches them together, writes the title and description
with AI, and publishes to YouTube every day at **9:00 AM IST** — fully
automated, no server to maintain, $0/month.

## How you use it (every day)

1. Generate a song on Suno; download the .mp3
2. Pick any short looping video clip (.mp4) — the system will loop it to fit
3. Make a thumbnail image (.jpg or .png) — the system uses it as-is
4. Drop all three into Google Drive →
   `prayer-channel-queue/<YYYY-MM-DD>/`
   *(folders are pre-created for the next 30 days; you never need to make one)*
5. Done. The video posts at 9 AM IST on that date.

GitHub will email your account if anything fails. (Optional: set up a Gmail
App Password to also get success confirmations — see SETUP.md Step 5.)

## Naming convention (the only thing that matters for the AI)

Name the audio file in **kebab-case** with an optional scripture reference:

```
trust-in-the-lord-psalm-23.mp3
peace-be-still.mp3
amazing-grace-meditation.mp3
```

The filename is the seed — the AI infers the title, description, tags, and
thumbnail words from it. See `topics.txt` for 100 ready-to-use seeds.

## What the system does each morning at 9 IST

1. Reads today's Drive folder (audio + video + thumbnail)
2. Generates metadata with **OpenAI** (gpt-4o-mini) — title, description,
   tags, scripture reference
3. Resizes/crops your thumbnail to YouTube's 1280×720 spec, keeps it under 2 MB
4. Stitches video and audio with **FFmpeg** — loops the bg video to match audio
   length, fades audio in/out, encodes to YouTube-ready 1080p H.264
5. Uploads to YouTube via the YouTube Data API, scheduled to publish at 9 AM IST
6. Declares the video as containing AI-generated content (per YouTube TOS)
7. Archives the Drive folder under `published/`
8. Tops up the rolling 30-day window of empty future folders
9. Emails you a confirmation

## Project layout

```
.
├── src/
│   ├── main.py            # daily pipeline orchestrator (entry point)
│   ├── config.py          # env-var loader
│   ├── google_auth.py     # shared OAuth credential factory
│   ├── drive.py           # Drive folder maintenance + asset download
│   ├── openai_client.py   # OpenAI metadata generation (gpt-4o-mini)
│   ├── thumbnail.py       # resize/crop user thumbnail to YouTube spec
│   ├── video.py           # FFmpeg stitching
│   ├── youtube.py         # YouTube Data API v3 uploader
│   └── notifier.py        # Gmail SMTP success/failure emails
├── scripts/
│   ├── bootstrap.py       # one-time interactive setup (run on your Mac)
│   ├── maintain_folders.py# top up folder window manually
│   └── test_pipeline.py   # local dry-run of metadata + thumbnail
├── .github/workflows/
│   └── daily-upload.yml   # cron at 03:30 UTC = 09:00 IST
├── topics.txt             # 100 gospel filename seeds
├── DESIGN.md              # full architecture + design rationale
├── SETUP.md               # ← start here for first-time setup
├── requirements.txt
└── .env.example
```

## First-time setup

See [`SETUP.md`](./SETUP.md). The whole thing takes about 30 minutes the first
time and then you never touch it again.

## Cost

~$0.02/month. GitHub Actions, Google Drive, YouTube API, and Gmail SMTP are
free. OpenAI gpt-4o-mini for the daily metadata call costs ~$0.0005 per video
(roughly 2 cents per month at one video per day).

## License

Personal use.
