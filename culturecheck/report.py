"""One video, start to finish, and what is kept of it.

    analyse   the video (vidra) -> cues -> Qloo entries -> audience profiles
              -> the judged appeal to every age group: everything that does not
              depend on who the video is for, kept as `reports/<id>/report.json`
    view      one audience over that: local following, fit, swaps and the brief,
              kept as `views/<audience>.json`

So a second audience costs a few Qloo calls and a few model calls, never the
video again.
"""

from __future__ import annotations

import asyncio
import copy
import json
import logging
import time
from pathlib import Path
from typing import Any, Callable, Optional

from . import appeal as appeal_mod
from . import brief as brief_mod
from . import cues as cue_mod
from . import extract
from . import fit as fitting
from .config import settings
from .qloo import Qloo
from .resolve import resolve
from .swaps import swaps

log = logging.getLogger("culturecheck.report")

#: What a run reports to `on_step`, in order, with the page's wording.
STEPS = {
    "media": "Reading the file", "audio": "Transcribing the soundtrack",
    "boundaries.evidence": "Finding the cuts", "boundaries": "Splitting into shots",
    "video": "Sampling frames", "cut": "Lining up the words", "describe":
    "Reading every shot", "embed": "Indexing the shots", "cues": "Listing cultural cues",
    "qloo": "Finding each cue in Qloo", "profiles": "Asking Qloo who each cue reaches",
    "appeal": "Judging who it appeals to",
    "fit": "Scoring the audience", "swaps": "Finding replacements",
    "brief": "Writing the brief",
}

Step = Optional[Callable[[str], None]]


def folder(report_id: str) -> Path:
    return settings().reports / report_id


def _write(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(path)


def load(report_id: str) -> Optional[dict[str, Any]]:
    path = folder(report_id) / "report.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def load_view(report_id: str, aud: dict[str, Any]) -> Optional[dict[str, Any]]:
    path = folder(report_id) / "views" / f"{fitting.key(aud)}.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def cached_view(report: dict[str, Any], aud: dict[str, Any]) -> Optional[dict[str, Any]]:
    """The kept view for this audience, with the report's appeal for its age
    group (a view kept before the appeal was judged does not carry it)."""
    kept = load_view(report["id"], aud)
    if kept is None:
        return None
    for old in ("baseline", "compare"):              # in views kept by earlier runs
        kept.pop(old, None)
    if "appeal" in report:
        kept["appeal"] = appeal_mod.for_audience(report["appeal"], aud)
    return kept


def _slim(cue: dict[str, Any]) -> dict[str, Any]:
    """A cue as kept: Qloo's raw entity reduced to what the page shows."""
    raw = cue.pop("entity", None)
    if raw:
        props = raw.get("properties") or {}
        cue["info"] = {"image": (props.get("image") or {}).get("url"),
                       "about": props.get("short_description") or "",
                       "tags": [t["name"] for t in (raw.get("tags") or [])
                                if t.get("type") in ("urn:tag:genre", "urn:tag:genre:place",
                                                     "urn:tag:category:place",
                                                     "urn:tag:style:qloo")][:8],
                     # its most specific genres, which keep a swap in its category
                     "genres": sorted({t["tag_id"] for t in raw.get("tags") or []
                                       if t.get("type", "").startswith("urn:tag:genre")},
                                      key=lambda i: -i.count(":"))[:3]}
    return cue


async def analyse(report_id: str, video: Path, aud: dict[str, Any], *,
                  music: Optional[str] = None, cast: Optional[str] = None,
                  title: Optional[str] = None, on_step: Step = None) -> dict[str, Any]:
    say = on_step or (lambda _: None)
    timings: dict[str, float] = {}
    t0 = time.perf_counter()
    where = await asyncio.to_thread(extract.extract, video, report_id, say)
    shots = extract.shots(where)
    timings["video"] = round(time.perf_counter() - t0, 1)

    say("cues")
    merged = await cue_mod.merge(shots, music, cast)
    cues = merged["cues"]
    t1 = time.perf_counter()
    async with Qloo() as q:
        say("qloo")
        await resolve(q, cues)
        say("profiles")
        await fitting.profiles(q, cues)
        calls = q.calls
    timings["qloo"] = round(time.perf_counter() - t1, 1)
    timings["cues"] = round(t1 - t0 - timings["video"], 1)

    duration = shots[-1]["end"] if shots else 0.0
    report = {"id": report_id, "title": title or video.stem, "video": video.name,
              "duration": duration, "music": music, "talent": cast, "shots": shots,
              "cues": [_slim(c) for c in cues], "cast": merged["cast"],
              "read": merged["read"], "created": time.strftime("%Y-%m-%dT%H:%M:%SZ",
                                                              time.gmtime()),
              "timings": timings, "qloo_calls": calls, "first_audience": aud}
    _write(folder(report_id) / "report.json", report)
    say("appeal")
    await judged(report)
    await view(report_id, aud, on_step=say, report=report)
    return report


async def judged(report: dict[str, Any]) -> dict[str, Any]:
    """The report's appeal to every age group, judged once and kept in it."""
    if "appeal" not in report:
        report["appeal"] = await appeal_mod.appeal(report)
        _write(folder(report["id"]) / "report.json", report)
    return report["appeal"]


async def view(report_id: str, aud: dict[str, Any], *, on_step: Step = None,
               report: Optional[dict[str, Any]] = None, fresh: bool = False
               ) -> dict[str, Any]:
    """The report for one audience, computed once and kept."""
    report = report or load(report_id)
    if report is None:
        raise KeyError(report_id)
    if not fresh:
        kept = cached_view(report, aud)
        if kept:
            return kept
    say = on_step or (lambda _: None)
    judgement = appeal_mod.for_audience(await judged(report), aud)
    cues = copy.deepcopy(report["cues"])
    t0 = time.perf_counter()
    async with Qloo() as q:
        say("fit")
        await fitting.local(q, cues, aud.get("location"))
        overall = fitting.rate(cues, aud)
        say("swaps")
        found = await swaps(q, cues, aud)
        calls = q.calls
    result = {"audience": aud, "label": fitting.describe(aud), "overall": overall,
              "appeal": judgement,
              "cues": cues, "swaps": found}
    say("brief")
    result["brief"] = await brief_mod.brief(report, result)
    result["qloo_calls"] = calls
    result["seconds"] = round(time.perf_counter() - t0, 1)
    _write(folder(report_id) / "views" / f"{fitting.key(aud)}.json", result)
    return result
