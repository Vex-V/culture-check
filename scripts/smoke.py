"""The app over HTTP, as a visitor uses it: refusals, an upload followed to its
report, another audience, a chat question, a frame and the video.

    python scripts/smoke.py http://127.0.0.1:8765 VIDEO [TOO_LONG_VIDEO]
    python scripts/smoke.py http://127.0.0.1:8765 --job ID     # only the report half
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import httpx

base = sys.argv[1]
given_job = sys.argv[3] if sys.argv[2] == "--job" else None
video = None if given_job else Path(sys.argv[2])
too_long = Path(sys.argv[3]) if len(sys.argv) > 3 and not given_job else None
c = httpx.Client(base_url=base, timeout=300)
ok = True


def check(name: str, cond: bool, detail: str = "") -> None:
    global ok
    ok &= bool(cond)
    print(f"  {'ok  ' if cond else 'FAIL'} {name} {detail}")


def upload_half() -> str:
    global r
    r = c.get("/")
    check("page", r.status_code == 200 and "Culture Check" in r.text)
    check("limits", c.get("/api/limits").status_code == 200)
    r = c.post("/api/analyse", data={"age": "nope"}, files={"video": (video.name, b"x", "video/mp4")})
    check("bad age refused", r.status_code == 400, r.json().get("error", ""))
    r = c.post("/api/analyse", data={"age": "25_to_29"},
               files={"video": ("notes.txt", b"hello", "text/plain")})
    check("not a video refused", r.status_code == 400, r.json().get("error", ""))
    r = c.post("/api/analyse", data={"age": "25_to_29"},
               files={"video": ("fake.mp4", b"\x00" * 2048, "video/mp4")})
    check("unreadable video refused", r.status_code == 400, r.json().get("error", ""))
    if too_long:
        r = c.post("/api/analyse", data={"age": "25_to_29"},
                   files={"video": (too_long.name, too_long.read_bytes(), "video/mp4")})
        check("too long refused", r.status_code == 400, r.json().get("error", ""))

    t0 = time.perf_counter()
    r = c.post("/api/analyse", data={"age": "35_to_44", "gender": "female", "location": "Chicago"},
               files={"video": (video.name, video.read_bytes(), "video/mp4")})
    check("upload accepted", r.status_code == 200, str(r.json()))
    job = r.json()["job"]
    seen = []
    while True:
        s = c.get(f"/api/jobs/{job}").json()
        if s.get("step") and s["step"] not in seen:
            seen.append(s["step"])
        if s["state"] in ("done", "failed"):
            break
        time.sleep(1)
    check("job finished", s["state"] == "done", f"{time.perf_counter() - t0:.0f}s, error={s.get('error')}")
    print("    steps:", " > ".join(seen))

    return job


job = given_job or upload_half()
rep = c.get(f"/api/reports/{job}").json()
check("report", "cues" in rep and rep["shots"], f"{len(rep.get('shots', []))} shots, {len(rep.get('cues', []))} cues")
v = c.get(f"/api/reports/{job}/view", params={"age": "35_to_44", "gender": "female",
                                              "location": "Chicago"}).json()
check("first view kept", "overall" in v, f"fit {v.get('overall', {}).get('fit')}")
t1 = time.perf_counter()
v2 = c.get(f"/api/reports/{job}/view", params={"age": "55_and_older"}).json()
check("second audience", "overall" in v2, f"fit {v2.get('overall', {}).get('fit')} in {time.perf_counter() - t1:.0f}s")
t1 = time.perf_counter()
c.get(f"/api/reports/{job}/view", params={"age": "55_and_older"})
check("second audience cached", time.perf_counter() - t1 < 1.0)
r = c.post(f"/api/reports/{job}/chat", json={"age": "35_to_44", "gender": "female",
           "location": "Chicago", "messages": [{"role": "user",
           "content": "Which cue hurts most for this audience, and what should replace it?"}]})
check("chat", r.status_code == 200 and r.json().get("text"),
      f"{len(r.json().get('steps', []))} tool calls")
for st in r.json().get("steps", []):
    print("    ~", st["summary"])
frame = rep["shots"][0]["frames"][0]
r = c.get(f"/api/reports/{job}/frames/{frame}.jpg")
check("frame", r.status_code == 200 and r.headers["content-type"] == "image/jpeg")
r = c.get(f"/api/reports/{job}/video", headers={"Range": "bytes=0-1023"})
check("video range", r.status_code == 206 and len(r.content) == 1024, str(r.status_code))
check("unknown report 404", c.get("/api/reports/doesnotexist").status_code == 404)
check("bad id 404", c.get("/api/reports/..%2F..%2Fetc/view?age=25_to_29").status_code == 404)
check("report page route", c.get(f"/r/{job}").status_code == 200)
print("ALL OK" if ok else "SOME FAILED", "report:", f"{base}/r/{job}")
