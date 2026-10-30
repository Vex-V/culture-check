"""The web app: one page, and the routes it calls.

    POST /api/upload-token            leave to upload one video to the Blob store
    POST /api/run                     a video in; progress, then the report, out
    POST /api/view                    one audience over a report the page holds
    POST /api/chat                    a follow-up question about it
    GET  /api/reports/{id}            an example report (audience-independent)
    GET  /api/reports/{id}/frames/N   a frame the model was shown
    GET  /api/reports/{id}/video      the video, in ranges
    GET  /api/samples                 the reports shown on the front page
    GET  /api/tested                  ads checked against Meta's published reach

Stateless, so it can run on a host that may stop between requests: an upload
lives for one response and is deleted when the report has been sent. The page
holds that report and sends it back with each question. Limits count per
instance. One instance checks one video at a time: a small CPU host transcribes
one well and two badly.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import logging
import mimetypes
import re
import secrets
import shutil
import time
from pathlib import Path
from typing import Any, AsyncIterator, Iterator, Optional

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from starlette.requests import HTTPConnection

from . import agent, blob, fit, report
from .config import settings, start_vidra

log = logging.getLogger("culturecheck.app")

STATIC = Path(__file__).parent / "static"
VIDEO_TYPES = {".mp4", ".mov", ".m4v", ".webm", ".mkv"}
ID = re.compile(r"^[a-z0-9][a-z0-9_-]{0,47}$")
#: New audiences a visitor may ask for per day (each costs Qloo and model calls).
VIEWS_PER_VISITOR_DAY = 40

#: Vercel refuses a response over 4.5 MB, so a video goes out in ranges below that.
VIDEO_RANGE = 4 * 1024 * 1024
#: Seconds a long step may stay silent: a proxy drops a quiet response.
HEARTBEAT_S = 10
#: The timeline shows a frame this wide; the page holds it, so it stays small.
THUMBNAIL_WIDTH = 320

app = FastAPI(title="Culture Check")
running = asyncio.Lock()


# ---------------------------------------------------------------- limits

def _visitor(request: HTTPConnection) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    ip = forwarded.split(",")[0].strip() or (request.client.host if request.client else "?")
    return hashlib.sha256(ip.encode()).hexdigest()[:16]


def _spend(request: HTTPConnection, what: str, per_visitor: int, total: Optional[int]) -> None:
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


# ---------------------------------------------------------------- uploads

@app.on_event("startup")
async def _start() -> None:
    start_vidra()


def _duration(path: Path) -> float:
    import av

    with av.open(str(path)) as c:
        if not c.streams.video:
            raise HTTPException(400, "That file has no video in it.")
        if c.duration:
            return c.duration / 1_000_000
        s = c.streams.video[0]
        return float(s.duration * s.time_base) if s.duration else 0.0


def _extension(name: str) -> str:
    ext = Path(name).suffix.lower()
    if ext not in VIDEO_TYPES:
        raise HTTPException(400, "Upload an .mp4, .mov, .m4v, .webm or .mkv video.")
    return ext


def _too_big() -> HTTPException:
    return HTTPException(413, f"Videos up to {settings().max_mb:.0f} MB, please.")


async def _receive(video: UploadFile, dest: Path) -> None:
    limit = int(settings().max_mb * 1024 * 1024)
    dest.parent.mkdir(parents=True, exist_ok=True)
    size = 0
    with dest.open("wb") as out:
        while chunk := await video.read(1 << 20):
            size += len(chunk)
            if size > limit:
                raise _too_big()
            out.write(chunk)


def _checked_length(path: Path) -> float:
    s = settings()
    try:
        seconds = _duration(path)
    except HTTPException:
        raise
    except Exception:                                     # noqa: BLE001
        raise HTTPException(400, "That file could not be read as a video.") from None
    if seconds > s.max_seconds + 0.5:
        raise HTTPException(400, f"Videos up to {s.max_seconds:.0f} seconds, please "
                                 f"(this one is {seconds:.0f}).")
    return seconds


def _shown(found: dict[str, Any]) -> dict[str, Any]:
    """A report with what the page derives from it."""
    return {**found, "ages": fit.AGE_LABELS, "age_map": fit.age_map(found["cues"]),
            "shot_ages": fit.shot_ages(found["cues"], found["shots"])}


def _line(**message: Any) -> str:
    return json.dumps(message, ensure_ascii=False) + "\n"


def _thumbnail(path: Path) -> str:
    import cv2

    image = cv2.imread(str(path))
    scale = THUMBNAIL_WIDTH / image.shape[1]
    small = cv2.resize(image, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    return base64.b64encode(cv2.imencode(".jpg", small, [cv2.IMWRITE_JPEG_QUALITY, 75])[1]
                            .tobytes()).decode()


def _frames(job: str, found: dict[str, Any]) -> Iterator[str]:
    """One frame per shot, for the timeline: nothing keeps them after this."""
    for shot in found["shots"]:
        if shot["frames"]:
            index = shot["frames"][len(shot["frames"]) // 2]
            yield _line(type="frame", index=index,
                        jpg=_thumbnail(settings().out / job / "store" / f"{index:07d}.jpg"))


async def _stream(job: str, video: Path, aud: dict[str, Any], given: dict[str, Any],
                  seconds: float) -> AsyncIterator[str]:
    """Each step as it starts, then the report, one JSON message per line."""
    loop = asyncio.get_running_loop()
    steps: "asyncio.Queue[Optional[str]]" = asyncio.Queue()
    work: Optional["asyncio.Task[dict[str, Any]]"] = None
    try:
        async with running:
            yield _line(type="start", steps=report.STEPS, seconds=round(seconds, 1))
            work = asyncio.create_task(report.analyse(
                job, video, aud, **given,
                on_step=lambda name: loop.call_soon_threadsafe(steps.put_nowait, name)))
            work.add_done_callback(lambda _: steps.put_nowait(None))
            while True:
                try:
                    step = await asyncio.wait_for(steps.get(), HEARTBEAT_S)
                except asyncio.TimeoutError:
                    yield _line(type="tick")
                    continue
                if step is None:
                    break
                yield _line(type="step", step=step)
            found = work.result()
            for frame in _frames(job, found):
                yield frame
            yield _line(type="done", report=_shown(found), view=report.cached_view(found, aud))
    except Exception as exc:                              # noqa: BLE001
        log.exception("job %s failed", job)
        yield _line(type="error", error=f"{type(exc).__name__}: {str(exc)[:300]}")
    finally:
        if work is not None:
            work.cancel()
        video.unlink(missing_ok=True)
        shutil.rmtree(settings().out / job, ignore_errors=True)
        shutil.rmtree(report.folder(job), ignore_errors=True)


class Upload(BaseModel):
    name: str
    size: int


@app.post("/api/upload-token")
async def upload_token(body: Upload) -> dict[str, str]:
    s = settings()
    if not blob.enabled():
        raise HTTPException(404, "Uploads go straight to /api/run here.")
    ext = _extension(body.name)
    limit = int(s.max_mb * 1024 * 1024)
    if body.size > limit:
        raise _too_big()
    pathname = f"uploads/{secrets.token_hex(8)}{ext}"
    return {"pathname": pathname, "token": blob.client_token(pathname, limit)}


@app.post("/api/run")
async def run(request: Request, video: Optional[UploadFile] = File(None), url: str = Form(""),
              name: str = Form(""), age: str = Form(...), gender: str = Form(""),
              location: str = Form(""), music: str = Form(""), cast: str = Form("")
              ) -> StreamingResponse:
    """A video as a file, or as a URL in the Blob store."""
    s = settings()
    try:
        aud = fit.audience(age, gender or None, location[:80])
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from None
    if running.locked():
        raise HTTPException(429, "Another video is being checked. Try again in a minute.")
    name = (video.filename if video else name) or ""
    job = secrets.token_hex(5)
    dest = s.uploads / f"{job}{_extension(name)}"
    try:
        if url:
            if not (blob.enabled() and blob.ours(url)):
                raise HTTPException(400, "That is not an upload of ours.")
            if not await blob.fetch(url, dest, int(s.max_mb * 1024 * 1024)):
                raise _too_big()
        elif video:
            await _receive(video, dest)
        else:
            raise HTTPException(400, "Send a video.")
        seconds = await asyncio.to_thread(_checked_length, dest)
        _spend(request, "uploads", s.per_visitor_day, s.per_day)
    except BaseException:
        dest.unlink(missing_ok=True)
        raise
    finally:
        if url and blob.enabled() and blob.ours(url):
            await blob.delete(url)
    given = {"music": music.strip()[:120] or None, "cast": cast.strip()[:200] or None,
             "title": Path(name).stem[:80]}
    return StreamingResponse(_stream(job, dest, aud, given, seconds),
                             media_type="application/x-ndjson",
                             headers={"X-Accel-Buffering": "no", "Cache-Control": "no-store"})


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
    return _shown(_report(report_id))


class Asked(BaseModel):
    """A report the page holds, and the audience it is being read for."""
    report: dict[str, Any]
    age: str
    gender: str = ""
    location: str = ""


def _held(body: Asked) -> tuple[dict[str, Any], dict[str, Any]]:
    held = body.report
    if not ID.match(str(held.get("id"))) or not isinstance(held.get("cues"), list):
        raise HTTPException(400, "That is not a report.")
    try:
        return held, fit.audience(body.age, body.gender or None, body.location[:80])
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from None


@app.post("/api/view")
async def post_view(request: Request, body: Asked) -> dict[str, Any]:
    held, aud = _held(body)
    kept = report.cached_view(held, aud)
    if kept:
        return kept
    _spend(request, "views", VIEWS_PER_VISITOR_DAY, None)
    return await report.view(held["id"], aud, report=held, fresh=True)


class Message(BaseModel):
    role: str
    content: str


class Chat(Asked):
    view: dict[str, Any]
    messages: list[Message]


@app.post("/api/chat")
async def post_chat(request: Request, body: Chat) -> dict[str, Any]:
    held, _ = _held(body)
    _spend(request, "chat", 60, 2000)
    msgs = [{"role": m.role, "content": m.content[:2000]} for m in body.messages][-12:]
    return await agent.chat(held, body.view, msgs)


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
async def video_file(request: Request, report_id: str) -> Response:
    """Always one range, at most VIDEO_RANGE long: a browser asks for the rest."""
    found = _report(report_id)
    path = settings().uploads / found["video"]
    if not path.exists():
        raise HTTPException(404)
    size = path.stat().st_size
    asked = re.match(r"bytes=(\d+)-(\d*)", request.headers.get("range", ""))
    start = int(asked[1]) if asked else 0
    if start >= size:
        raise HTTPException(416, "Past the end of the video.")
    end = min(size - 1, start + VIDEO_RANGE - 1, int(asked[2]) if asked and asked[2] else size - 1)
    with path.open("rb") as f:
        f.seek(start)
        body = f.read(end - start + 1)
    return Response(body, 206, media_type=mimetypes.guess_type(path.name)[0] or "video/mp4",
                    headers={"Content-Range": f"bytes {start}-{end}/{size}",
                             "Accept-Ranges": "bytes"})


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
    return {"max_seconds": s.max_seconds, "max_mb": s.max_mb, "ages": fit.AGE_LABELS,
            "blob": blob.enabled()}


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
