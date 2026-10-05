# Media Service

> Status: **Done** (v1: upload + FFmpeg transcode + playback) · Roadmap phase: **1** · Local port: **8003** · Blueprint: [docs/PRODUCT.md](../../docs/PRODUCT.md)

Clip uploads direct to AWS S3 (presigned POST), an FFmpeg transcode pipeline that compresses to a
capped resolution ladder and deletes the raw original, and short-lived opaque playback tokens
that resolve to freshly presigned S3 GET URLs.

| | |
|---|---|
| Owns (own database) | media_assets, renditions, captions, transcripts, playback_tokens, outbox_events |
| Emits events | media.uploaded, media.ready, media.failed |
| Consumes events | media.uploaded (its own — drives the transcoder), course.retired (archives assets tagged with that course version) |

Follows the service template and conventions in [lms-backend/README.md](../README.md): verifies
access tokens against user-management's JWKS (never issues its own), checks the shared Redis
access-state keys for revocation, and gates authoring on the `content.author` scope — see
[app/permissions/scopes.py](app/permissions/scopes.py). Storage lives entirely behind
[app/storage/s3.py](app/storage/s3.py), the only file that imports boto3.

## Flow

```
POST /media/uploads              -> presigned S3 POST + asset (status=uploading)
  browser PUTs the file straight to S3, never through this service
POST /media/{id}/complete        -> HEAD the object, verify it exists
  video: status=uploaded, emits media.uploaded          (worker transcodes async, see below)
  image: status=ready immediately (no encoding needed)
[worker] media.uploaded          -> download original -> ffprobe -> ffmpeg per rendition ->
                                     upload renditions -> delete original -> status=ready,
                                     emits media.ready (or media.failed + status=failed)
POST /media/{id}/playback-tokens -> opaque short-lived token for a <video> tag
GET  /playback/{token}           -> 307 redirect to a fresh, short-lived presigned S3 GET URL
```

**Compression** (see [app/pipeline/](app/pipeline)): every video is re-encoded H.264/AAC at
CRF 23 ("visually lossless" in practice) and scaled to whichever of 1080p/720p/480p are at or
below the source's own height — never upscaled. The raw original is deleted from S3 once the
compressed renditions exist, so storage cost tracks the compressed size, not the raw upload.
Playback picks the highest-quality available rendition (no adaptive-bitrate player yet).

## Local development

```bash
cp .env.example .env    # set AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY / S3_BUCKET for a real run
python -m venv .venv && .venv/Scripts/pip install -r requirements-dev.txt
alembic upgrade head
uvicorn app.main:app --reload --port 8003   # http://localhost:8003/docs
python -m app.worker                          # outbox relay + transcoder + inbound event consumer
pytest                                        # mocks S3 (moto) and ffmpeg/ffprobe; no AWS account or binary needed
```

The worker needs the `ffmpeg`/`ffprobe` binaries on PATH to transcode for real (the Docker image
installs them; for bare local runs install FFmpeg yourself). Tests never invoke the real binary —
see the `stub_ffmpeg` fixture in `tests/conftest.py`.

## Tests

19 tests (`tests/unit`, `tests/integration`) cover authorization (missing token/scope), rejecting
unsupported content types and oversized uploads, the rendition-ladder selection logic, the full
upload → complete → worker-transcode → ready pipeline (including that the raw original is
deleted from S3 once renditions exist), image uploads skipping transcoding entirely, playback
token issuance and resolution (including "not ready yet" and "expired/unknown token"), archiving,
context-filtered listing, and both inbound event consumers (`media.uploaded`, `course.retired`).
S3 is mocked with `moto` and FFmpeg is stubbed, so the whole suite needs neither a real AWS
account nor the FFmpeg binary. Migrations are verified with a full upgrade → downgrade → upgrade
cycle on both SQLite and a real PostgreSQL instance, with autogenerate confirming no drift.

## Not yet wired

- **Captions/transcripts.** Tables exist; nothing populates them until an AI transcription
  pipeline exists.
- **Per-user watermarking / DRM.** Playback is access-controlled (opaque token, short-lived
  signed URL) but the video bytes themselves carry no watermark yet.
- **Adaptive bitrate.** Renditions exist as separate MP4 files, not an HLS/DASH manifest, so a
  player can't switch quality mid-playback yet; `/playback/{token}` always serves the best
  available rendition.
- **Thumbnail generation.** No automatic frame-grab thumbnail from an uploaded video yet — a
  thumbnail is just another image asset uploaded separately today.
