"""A video through vidra, one component at a time: the components rather than
`video_rag()`, because the grid and the soundtrack need settings the pipeline
does not take (shots of 2-8 s; Whisper with no speaker model, so no torch).

    media -> audio (Whisper) -> scene cuts -> the grid -> frames -> transcript
          -> the `culture` question per shot -> embeddings (for "where in the
          video is ...")

Returns the video's folder; `answers()` and `transcript()` read it back.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Callable, Optional

from . import question
from .config import settings, start_vidra
from .models import models

log = logging.getLogger("culturecheck.extract")

#: Shot lengths: adverts cut every 1-3 s, so short shots merge up to MIN_S and
#: long takes split at MAX_S.
MIN_S, MAX_S = 2.0, 8.0
#: Frames read per second, and the most shown to the model for one shot.
PER_SECOND, MAX_FRAMES = 2.0, 6
WHISPER_MODEL = "small"

STEPS = ["media", "audio", "boundaries.evidence", "boundaries", "video", "cut",
         "describe", "embed"]


def extract(source: Path, video_id: str,
            on_step: Optional[Callable[[str], None]] = None) -> Path:
    from vidra.shared.config.paths import layout
    from vidra.video_rag.offline import (audio, boundaries, cut, describe, embed,
                                         media, video)
    from vidra.video_rag.samplers import Uniform

    say = on_step or (lambda _: None)
    start_vidra()
    question.register()
    m = models()

    say("media")
    first = media.media(source, settings().out, video_id=video_id, on_conflict="replace")
    folder = Path(first.stats["folder"])
    at = layout(folder)
    has_audio = "audio" not in set(first.skipped)

    if has_audio:
        say("audio")
        audio.audio(at["media"], at["raw_transcript"], transcriber="whisper",
                    diarizer="none", model=WHISPER_MODEL, device="cpu",
                    compute_type="int8")

    say("boundaries.evidence")
    boundaries.evidence(at["cuts"], "scene", media=at["media"])
    say("boundaries")
    boundaries.boundaries(at["media"], at["timeline"], "scene", cuts=at["cuts"],
                          chunk_s=MAX_S, min_s=MIN_S, max_s=MAX_S)

    say("video")
    video.video(at["media"], at["timeline"], at["manifest"], store=at["store"],
                sampler=Uniform(max_per_chunk=MAX_FRAMES, prompts=[question.NAME]),
                per_second=PER_SECOND)
    if has_audio:
        say("cut")
        cut.cut(at["timeline"], at["raw_transcript"], at["transcript"])

    say("describe")
    describe.describe(at["manifest"], at["timeline"], at["store"], at["descriptions"],
                      previous=at["descriptions"] if at["descriptions"].exists() else None,
                      vlm=m.vlm)
    say("embed")
    embed.embed(at["embedded"], descriptions=at["descriptions"],
                transcript=at["transcript"] if has_audio else None,
                previous=at["embedded"] if at["embedded"].exists() else None,
                timeline=at["timeline"], embedder=m.embedder)
    return folder


def shots(folder: Path) -> list[dict[str, Any]]:
    """One entry per shot: its id, times, the `culture` answer, what was said
    in it, and the frames shown to the model."""
    from vidra.shared.config.paths import layout
    from vidra.shared.contracts.documents import Descriptions, Manifest, Timeline, Transcript
    from vidra.shared.storage.files import read

    at = layout(folder)
    grid = read(at["timeline"], Timeline)
    described = read(at["descriptions"], Descriptions)
    manifest = read(at["manifest"], Manifest)
    told = read(at["transcript"], Transcript) if at["transcript"].exists() else None
    answer: dict[int, dict[str, Any]] = {}
    for chunk in described.chunks:
        for block in (chunk.get("samplers") or {}).values():
            if block.get("question") == question.NAME:
                answer[chunk["chunk_id"]] = {"summary": block.get("description", ""),
                                             **(block.get("structured") or {})}
    frames: dict[int, list[int]] = {}
    for chunk in manifest.chunks:
        for run in (chunk.get("samplers") or {}).values():
            frames.setdefault(chunk["chunk_id"], []).extend(
                f["index"] for f in run.get("frames", []))
    out = []
    for cid, (start, end) in enumerate(grid.spans):
        out.append({"shot": cid, "start": round(start, 2), "end": round(end, 2),
                    "seen": answer.get(cid, {}),
                    "said": told.text_of(cid).strip() if told else "",
                    "frames": sorted(set(frames.get(cid, [])))})
    return out
