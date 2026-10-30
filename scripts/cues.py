"""A video to its shots and cultural cues, without Qloo.

    python scripts/cues.py VIDEO [--music "artist or track"] [--id ID]

Writes data/reports/<id>.cues.json and prints the cues.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from culturecheck import cues, extract  # noqa: E402
from culturecheck.config import settings  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("video", type=Path)
    ap.add_argument("--music")
    ap.add_argument("--id")
    a = ap.parse_args()
    video_id = a.id or a.video.stem
    t0 = time.perf_counter()
    folder = extract.extract(a.video, video_id,
                             on_step=lambda s: print(f"  {time.perf_counter() - t0:6.1f}s {s}"))
    shots = extract.shots(folder)
    print(f"{len(shots)} shots in {time.perf_counter() - t0:.1f}s")
    merged = asyncio.run(cues.merge(shots, a.music))
    print(f"cues in {time.perf_counter() - t0:.1f}s\n")
    print("read:", merged["read"])
    print("cast:", merged["cast"], "\n")
    for c in merged["cues"]:
        print(f"  {c['id']:4} {c['kind']:10} w{c['weight']} {c['route']:6} "
              f"{c['qloo_type']:11} {c['lookup']!r:28} shots={c['shots']}  {c['label']}")
    out = settings().reports / f"{video_id}.cues.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"shots": shots, **merged}, indent=1, ensure_ascii=False),
                   encoding="utf-8")
    print(f"\n{out}")


if __name__ == "__main__":
    main()
