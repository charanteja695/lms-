"""Thin async wrappers around the ``ffmpeg``/``ffprobe`` binaries. Both must be on PATH (the
runtime Docker image installs them; see Dockerfile). Every call is a real subprocess run with
``asyncio.create_subprocess_exec`` — no shell, no string-built commands, so a filename can never
inject an extra flag.

These two functions are the only things a test needs to monkeypatch to exercise the pipeline
without a real ffmpeg binary (see tests/unit/test_pipeline.py).
"""

import asyncio
import json
from dataclasses import dataclass


class TranscodeError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class VideoInfo:
    duration_seconds: int
    height: int


async def probe_video(local_path: str) -> VideoInfo:
    process = await asyncio.create_subprocess_exec(
        "ffprobe", "-v", "error", "-print_format", "json", "-show_format", "-show_streams", local_path,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate()
    if process.returncode != 0:
        raise TranscodeError(f"ffprobe failed: {stderr.decode(errors='replace')[:500]}")

    data = json.loads(stdout)
    video_stream = next((s for s in data.get("streams", []) if s.get("codec_type") == "video"), None)
    if video_stream is None:
        raise TranscodeError("No video stream found")
    duration = float(data.get("format", {}).get("duration") or video_stream.get("duration") or 0)
    return VideoInfo(duration_seconds=round(duration), height=int(video_stream["height"]))


async def transcode_rendition(source_path: str, output_path: str, *, max_height: int, crf: int = 23) -> None:
    """Re-encode to H.264/AAC, quality-targeted (CRF) rather than a fixed bitrate, scaled down
    to at most ``max_height`` (never upscaled — callers only request heights <= the source)."""
    process = await asyncio.create_subprocess_exec(
        "ffmpeg", "-y", "-i", source_path,
        "-vf", f"scale=-2:'min({max_height},ih)'",
        "-c:v", "libx264", "-preset", "medium", "-crf", str(crf),
        "-c:a", "aac", "-b:a", "128k",
        "-movflags", "+faststart",
        output_path,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await process.communicate()
    if process.returncode != 0:
        raise TranscodeError(f"ffmpeg failed: {stderr.decode(errors='replace')[:500]}")
