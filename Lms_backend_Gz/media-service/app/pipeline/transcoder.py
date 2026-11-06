"""Orchestrates one asset's transcode: download the original, probe it, encode a rendition
ladder capped at the source's own resolution (never upscaled), upload each rendition, clean up.

Runs entirely in the worker (see app/events/consumers/pipeline_events.py), never inside a
request handler — a real clip can take seconds to minutes to encode.
"""

import tempfile
from dataclasses import dataclass
from pathlib import Path

from anyio import to_thread

from app.core.config import Settings
from app.pipeline import ffmpeg
from app.storage import s3
from app.storage.keys import rendition_object_key

# (max_height, label). Only rungs at or below the source's own height are produced, so a
# 480p source never gets upscaled to a blurry "1080p" file.
LADDER: tuple[tuple[int, str], ...] = ((1080, "1080p"), (720, "720p"), (480, "480p"))


@dataclass(frozen=True, slots=True)
class RenditionResult:
    label: str
    storage_key: str
    byte_size: int


@dataclass(frozen=True, slots=True)
class ProcessResult:
    duration_seconds: int
    renditions: list[RenditionResult]


def _file_size(path: str) -> int:
    return Path(path).stat().st_size


def _targets_for(source_height: int) -> list[tuple[int, str]]:
    applicable = [(height, label) for height, label in LADDER if height <= source_height]
    return applicable or [(source_height, "native")]  # source smaller than the smallest rung


async def process_upload(settings: Settings, *, storage_key: str, asset_public_id: int) -> ProcessResult:
    with tempfile.TemporaryDirectory() as tmp_dir:
        source_path = str(Path(tmp_dir) / "source")
        await s3.download_file(settings, storage_key, source_path)

        info = await ffmpeg.probe_video(source_path)
        renditions: list[RenditionResult] = []
        for height, label in _targets_for(info.height):
            output_path = str(Path(tmp_dir) / f"{label}.mp4")
            await ffmpeg.transcode_rendition(source_path, output_path, max_height=height)

            dest_key = rendition_object_key(asset_public_id, label)
            await s3.upload_file(settings, output_path, dest_key, content_type="video/mp4")
            byte_size = await to_thread.run_sync(_file_size, output_path)
            renditions.append(RenditionResult(label=label, storage_key=dest_key, byte_size=byte_size))

        return ProcessResult(duration_seconds=info.duration_seconds, renditions=renditions)
