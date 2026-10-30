"""The web app: one page, and the routes it calls.

    POST /api/analyse                 a video and an audience -> a job
    GET  /api/jobs/{id}               where the job is
    GET  /api/reports/{id}            the video's report (audience-independent)
    GET  /api/reports/{id}/view       one audience over it (computed once, kept)
    POST /api/reports/{id}/chat       a follow-up question
    GET  /api/reports/{id}/frames/N   a frame the model was shown
    GET  /api/reports/{id}/video      the video
    GET  /api/samples                 the reports shown on the front page
    GET  /api/tested                  ads checked against Meta's published reach

One worker runs jobs one at a time: a small CPU host transcribes one video at
a time well and two badly. Uploads are capped by size, length, and count per
visitor and in total per day.
"""

from __future__ import annotations

import asyncio
import hashlib
import itertools
import json
import logging
import re
import secrets
import time
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import agent, fit, report
from .config import settings, start_vidra

log = logging.getLogger("culturecheck.app")

STATIC = Path(__file__).parent / "static"
VIDEO_TYPES = {".mp4", ".mov", ".m4v", ".webm", ".mkv"}
ID = re.compile(r"^[a-z0-9][a-z0-9_-]{0,47}$")
#: New audiences a visitor may ask for per day (each costs Qloo and model calls).
VIEWS_PER_VISITOR_DAY = 40

app = FastAPI(title="Culture Check")
jobs: dict[str, dict[str, Any]] = {}
queue: "asyncio.Queue[str]" = asyncio.Queue()
_order = itertools.count()


# ---------------------------------------------------------------- limits

def _visitor(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    ip = forwarded.split(",")[0].strip() or (request.client.host if request.client else "?")
    return hashlib.sha256(ip.encode()).hexdigest()[:16]


def _spend(request: Request, what: str, per_visitor: int, total: Optional[int]) -> None:
    """Counts one `what` for this visitor today, or refuses with 429."""
    path = settings().data / "limits.json"
    today = time.strftime("%Y-%m-%d", time.gmtime())
    held = json.loads(path.read_text()) if path.exists() else {}
    day = held.get(today, {})
    counts = day.setdefault(what, {"total": 0, "visitors": {}})
    who = _visitor(request)
    if counts["visitors"].get(who, 0) >= per_visitor:
        raise HTTPException(429, f"That's today's limit of {per_visitor} for one visitor; "
                                 "the samples are always free to explore.")
    if total is not None and counts["total"] >= total:
        raise HTTPException(429, "The demo has reached today's limit; please try the samples.")
    counts["total"] += 1
    counts["visitors"][who] = counts["visitors"].get(who, 0) + 1
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({today: day}))


# ---------------------------------------------------------------- jobs

async def _worker() -> None:
    while True:
        job_id = await queue.get()
        job = jobs[job_id]
        job["state"] = "running"

        def step(name: str, job: dict[str, Any] = job) -> None:
            job["step"] = name
            job["done"].append(name)

        try:
            await report.analyse(job_id, Path(job["video"]), job["audience"],
                                 music=job["music"], cast=job["cast"], title=job["title"],
                                 on_step=step)
            job["state"] = "done"
        except Exception as exc:                          # noqa: BLE001
            log.exception("job %s failed", job_id)
            job["state"] = "failed"
            job["error"] = f"{type(exc).__name__}: {str(exc)[:300]}"
        finally:
            queue.task_done()


@app.on_event("startup")
async def _start() -> None:
    start_vidra()
    asyncio.create_task(_worker())


def _duration(path: Path) -> float:
    import av

    with av.open(str(path)) as c:
        if not c.streams.video:
            raise HTTPException(400, "That file has no video in it.")
        if c.duration:
            return c.duration / 1_000_000
        s = c.streams.video[0]
        return float(s.duration * s.time_base) if s.duration else 0.0


@app.post("/api/analyse")
async def analyse(request: Request, video: UploadFile = File(...), age: str = Form(...),
                  gender: str = Form(""), location: str = Form(""), music: str = Form(""),
                  cast: str = Form(""), title: str = Form("")) -> dict[str, Any]:
    s = settings()
    try:
        aud = fit.audience(age, gender or None, location[:80])
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from None
    ext = Path(video.filename or "").suffix.lower()
    if ext not in VIDEO_TYPES:
        raise HTTPException(400, "Upload an .mp4, .mov, .m4v, .webm or .mkv video.")
    job_id = secrets.token_hex(5)
    dest = s.uploads / f"{job_id}{ext}"
    dest.parent.mkdir(parents=True, exist_ok=True)
    size, limit = 0, int(s.max_mb * 1024 * 1024)
    with dest.open("wb") as out:
        while chunk := await video.read(1 << 20):
            size += len(chunk)
            if size > limit:
                out.close()
                dest.unlink(missing_ok=True)
                raise HTTPException(413, f"Videos up to {s.max_mb:.0f} MB, please.")
            out.write(chunk)
    try:
        seconds = await asyncio.to_thread(_duration, dest)
    except HTTPException:
        dest.unlink(missing_ok=True)
        raise
    except Exception:                                     # noqa: BLE001
        dest.unlink(missing_ok=True)
        raise HTTPException(400, "That file could not be read as a video.") from None
    if seconds > s.max_seconds + 0.5:
        dest.unlink(missing_ok=True)
        raise HTTPException(400, f"Videos up to {s.max_seconds:.0f} seconds, please "
                                 f"(this one is {seconds:.0f}).")
    try:
        _spend(request, "uploads", s.per_visitor_day, s.per_day)
    except HTTPException:
        dest.unlink(missing_ok=True)
        raise
    jobs[job_id] = {"id": job_id, "seq": next(_order), "state": "queued", "step": None, "done": [],
                    "video": str(dest), "audience": aud, "music": music.strip()[:120] or None,
                    "cast": cast.strip()[:200] or None,
                    "title": title.strip()[:80] or Path(video.filename or "video").stem[:80],
                    "seconds": round(seconds, 1), "error": None}
    await queue.put(job_id)
    return {"job": job_id}


@app.get("/api/jobs/{job_id}")
async def job_state(job_id: str) -> dict[str, Any]:
    job = jobs.get(job_id)
    if job is None:
        if report.load(job_id) if ID.match(job_id) else None:
            return {"id": job_id, "state": "done"}
        raise HTTPException(404, "No such job.")
    ahead = 0
    if job["state"] == "queued":
        ahead = sum(1 for j in jobs.values() if j["state"] == "running") + sum(
            1 for j in list(jobs.values()) if j["state"] == "queued" and j["seq"] < job["seq"])
    return {"id": job_id, "state": job["state"], "step": job["step"], "done": job["done"],
            "steps": report.STEPS, "error": job["error"], "ahead": ahead,
            "seconds": job["seconds"]}


# ---------------------------------------------------------------- reports

def _report(report_id: str) -> dict[str, Any]:
    if not ID.match(report_id):
        raise HTTPException(404, "No such report.")
    found = report.load(report_id)
    if found is None:
        raise HTTPException(404, "No such report.")
    return found


@app.get("/api/reports/{report_id}")
async def get_report(report_id: str) -> dict[str, Any]:
    found = _report(report_id)
    views = sorted(p.stem for p in (report.folder(report_id) / "views").glob("*.json"))
    return {**found, "views": views, "ages": fit.AGE_LABELS,
            "age_map": fit.age_map(found["cues"]),
            "shot_ages": fit.shot_ages(found["cues"], found["shots"])}


@app.get("/api/reports/{report_id}/view")
async def get_view(request: Request, report_id: str, age: str, gender: str = "",
                   location: str = "") -> dict[str, Any]:
    found = _report(report_id)
    try:
        aud = fit.audience(age, gender or None, location[:80])
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from None
    kept = report.cached_view(found, aud)
    if kept:
        return kept
    _spend(request, "views", VIEWS_PER_VISITOR_DAY, None)
    return await report.view(report_id, aud)


class Message(BaseModel):
    role: str
    content: str


class Chat(BaseModel):
    age: str
    gender: str = ""
    location: str = ""
    messages: list[Message]


@app.post("/api/reports/{report_id}/chat")
async def post_chat(request: Request, report_id: str, body: Chat) -> dict[str, Any]:
    found = _report(report_id)
    aud = fit.audience(body.age, body.gender or None, body.location[:80])
    view = report.cached_view(found, aud)
    if view is None:
        raise HTTPException(409, "Open the report for this audience first.")
    _spend(request, "chat", 60, 2000)
    msgs = [{"role": m.role, "content": m.content[:2000]} for m in body.messages][-12:]
    return await agent.chat(found, view, msgs)


@app.get("/api/reports/{report_id}/frames/{index}.jpg")
async def frame(report_id: str, index: int) -> FileResponse:
    if not ID.match(report_id):
        raise HTTPException(404)
    path = settings().out / report_id / "store" / f"{index:07d}.jpg"
    if not path.exists():
        raise HTTPException(404)
    return FileResponse(path, media_type="image/jpeg",
                        headers={"Cache-Control": "public, max-age=86400"})


@app.get("/api/reports/{report_id}/video")
async def video_file(report_id: str) -> FileResponse:
    found = _report(report_id)
    path = settings().uploads / found["video"]
    if not path.exists():
        raise HTTPException(404)
    return FileResponse(path)


@app.get("/api/samples")
async def samples() -> list[dict[str, Any]]:
    path = settings().data / "samples.json"
    out = []
    for sid in json.loads(path.read_text()) if path.exists() else []:
        found = report.load(sid)
        if found:
            first = found["first_audience"]
            kept = report.load_view(sid, first) or {}
            shot = found["shots"][len(found["shots"]) // 3] if found["shots"] else None
            out.append({"id": sid, "title": found["title"], "duration": found["duration"],
                        "shots": len(found["shots"]), "cues": len(found["cues"]),
                        "audience": first, "label": fit.describe(first),
                        "fit": ((found.get("appeal") or {}).get("by_age", {})
                                .get(first["age"]) or {}).get("appeal",
                                (kept.get("overall") or {}).get("fit")),
                        "headline": (kept.get("brief") or {}).get("headline"),
                        "frame": shot["frames"][len(shot["frames"]) // 2]
                        if shot and shot["frames"] else None})
    return out


@app.get("/api/tested")
async def tested() -> list[dict[str, Any]]:
    """data/tested.json's Meta figures, each ad with the appeal judged for it."""
    path = settings().data / "tested.json"
    groups = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
    for group in groups:
        for ad in group["ads"]:
            found = report.load(ad["report"]) or {}
            shots = found.get("shots") or []
            shot = shots[len(shots) // 3] if shots else None
            ad["appeal"] = (found.get("appeal") or {}).get("by_age", {})
            ad["summary"] = (found.get("appeal") or {}).get("summary", "")
            ad["seconds"] = found.get("duration")
            ad["cues"] = len(found.get("cues") or [])
            ad["frame"] = shot["frames"][len(shot["frames"]) // 2] if shot and shot["frames"] else None
    return groups


@app.get("/api/limits")
async def limits() -> dict[str, Any]:
    s = settings()
    return {"max_seconds": s.max_seconds, "max_mb": s.max_mb, "ages": fit.AGE_LABELS}


@app.exception_handler(HTTPException)
async def _http_error(_: Request, exc: HTTPException) -> JSONResponse:
    return JSONResponse({"error": exc.detail}, status_code=exc.status_code)


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(STATIC / "index.html")


@app.get("/tested")
async def tested_page() -> FileResponse:
    return FileResponse(STATIC / "index.html")


@app.get("/r/{report_id}")
async def report_page(report_id: str) -> FileResponse:
    return FileResponse(STATIC / "index.html")


app.mount("/static", StaticFiles(directory=STATIC), name="static")
