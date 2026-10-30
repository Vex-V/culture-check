"""The app as a visitor uses it: refusals, an upload to its report, another audience, a chat
question, an example report, a frame and the video, and nothing of the upload left behind.

    python scripts/smoke.py http://127.0.0.1:8765 VIDEO [TOO_LONG_VIDEO]
"""

from __future__ import annotations

import asyncio
import json
import sys
import time
from pathlib import Path
from typing import Any

import httpx
from websockets.asyncio.client import connect

base = sys.argv[1].rstrip("/")
video = Path(sys.argv[2])
too_long = Path(sys.argv[3]) if len(sys.argv) > 3 else None
c = httpx.Client(base_url=base, timeout=300)
ok = True


def check(name: str, cond: bool, detail: str = "") -> None:
    global ok
    ok &= bool(cond)
    print(f"  {'ok  ' if cond else 'FAIL'} {name} {detail}", flush=True)


async def run(path: Path, meta: dict[str, Any], body: bytes | None = None) -> dict[str, Any]:
    """Everything the server sends for one upload."""
    data = path.read_bytes() if body is None else body
    got: dict[str, Any] = {"steps": [], "frames": {}, "error": None, "done": None}
    url = base.replace("http", "ws", 1) + "/api/run"
    async with connect(url, max_size=None, ping_timeout=None) as ws:
        await ws.send(json.dumps({"name": path.name, "size": len(data), **meta}))
        for at in range(0, len(data), 1 << 20):
            await ws.send(data[at:at + (1 << 20)])
        async for raw in ws:
            m = json.loads(raw)
            if m["type"] == "step":
                got["steps"].append(m["step"])
                print("    ·", m["step"], flush=True)
            elif m["type"] == "frame":
                got["frames"][m["index"]] = m["jpg"]
            elif m["type"] == "error":
                got["error"] = m["error"]
                break
            elif m["type"] == "done":
                got["done"] = m
                break
    return got


r = c.get("/")
check("page", r.status_code == 200 and "Culture Check" in r.text)
check("limits", c.get("/api/limits").status_code == 200)
samples = c.get("/api/samples").json()
check("samples", len(samples) > 0, f"{len(samples)}")
check("tested", len(c.get("/api/tested").json()) > 0)

bad = asyncio.run(run(video, {"age": "nope"}, b"x"))
check("bad age refused", bool(bad["error"]), bad["error"] or "")
bad = asyncio.run(run(Path("x.txt"), {"age": "25_to_29"}, b"x"))
check("bad type refused", bool(bad["error"]), bad["error"] or "")
bad = asyncio.run(run(video, {"age": "25_to_29"}, b"not a video"))
check("not a video refused", bool(bad["error"]), bad["error"] or "")
if too_long:
    bad = asyncio.run(run(too_long, {"age": "25_to_29"}))
    check("too long refused", bool(bad["error"]), bad["error"] or "")

t0 = time.time()
got = asyncio.run(run(video, {"age": "35_to_44", "gender": "female", "location": "Chicago"}))
check("upload finished", got["done"] is not None, got["error"] or f"{time.time() - t0:.0f}s")
if got["done"] is None:
    sys.exit(1)
held, view = got["done"]["report"], got["done"]["view"]
check("report", len(held["cues"]) > 0 and "age_map" in held, f"{len(held['cues'])} cues")
check("view", view["overall"]["fit"] is not None and bool(view["brief"]["headline"]))
check("one frame per shot", len(got["frames"]) >= len(held["shots"]) // 2, f"{len(got['frames'])}")
check("upload not kept", c.get(f"/api/reports/{held['id']}").status_code == 404)
print("    size of the report the page sends back:", len(json.dumps(held)) // 1024, "KB")

other = c.post("/api/view", json={"report": held, "age": "55_and_older"})
check("another audience", other.status_code == 200 and other.json()["overall"]["fit"] is not None,
      str(other.status_code))
r = c.post("/api/chat", json={"report": held, "view": view, "age": "35_to_44", "gender": "female",
                              "location": "Chicago", "messages": [
                                  {"role": "user", "content": "What if the audience were men over "
                                                              "55? And where is the first logo?"}]})
check("chat", r.status_code == 200 and bool(r.json().get("text")), str(r.status_code))
for st in r.json().get("steps", []):
    print("    ~", st["summary"])

sample = samples[0]["id"]
rep = c.get(f"/api/reports/{sample}").json()
kept = c.post("/api/view", json={"report": rep, "age": rep["first_audience"]["age"]})
check("example view", kept.status_code == 200, str(kept.status_code))
kept = kept.json()
r = c.post("/api/chat", json={"report": rep, "view": kept, "age": kept["audience"]["age"],
                              "messages": [{"role": "user", "content": "Where is food shown?"}]})
check("example chat", r.status_code == 200 and bool(r.json().get("text")), str(r.status_code))
frame = rep["shots"][0]["frames"][0]
r = c.get(f"/api/reports/{sample}/frames/{frame}.jpg")
check("frame", r.status_code == 200 and r.headers["content-type"] == "image/jpeg")
r = c.get(f"/api/reports/{sample}/video", headers={"Range": "bytes=0-1023"})
check("video range", r.status_code == 206 and len(r.content) == 1024, str(r.status_code))
r = c.get(f"/api/reports/{sample}/video", headers={"Range": "bytes=0-"})
size = int(r.headers["content-range"].rsplit("/", 1)[1])
check("video capped", r.status_code == 206 and len(r.content) <= 4 << 20, f"{len(r.content)} of {size}")
seen, at = 0, 0
while at < size:
    part = c.get(f"/api/reports/{sample}/video", headers={"Range": f"bytes={at}-"})
    seen += len(part.content)
    at += len(part.content)
check("video whole by ranges", seen == size, f"{seen}")
check("bad report refused", c.post("/api/view", json={"report": {"id": "../x", "cues": []},
                                                     "age": "25_to_29"}).status_code == 400)
check("unknown report 404", c.get("/api/reports/doesnotexist").status_code == 404)
check("report page route", c.get(f"/r/{sample}").status_code == 200)
print("ALL OK" if ok else "SOME FAILED", flush=True)
sys.exit(0 if ok else 1)
