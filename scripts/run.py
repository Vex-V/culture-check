"""A video to a whole report, from the command line.

    python scripts/run.py VIDEO --age 25_to_29 [--gender female] [--location Austin]
                          [--music "artist or track"] [--cast "names"] [--id ID]
                          [--title T]

Prints the fit, the swaps and the brief; the report
is kept under data/reports/<id>/.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from culturecheck import fit, report  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("video", type=Path)
    ap.add_argument("--age", required=True)
    ap.add_argument("--gender")
    ap.add_argument("--location")
    ap.add_argument("--music")
    ap.add_argument("--cast", help="who appears, comma-separated")
    ap.add_argument("--id")
    ap.add_argument("--title")
    a = ap.parse_args()
    logging.basicConfig(format="    %(name)s %(message)s")
    logging.getLogger("culturecheck").setLevel(logging.INFO)
    aud = fit.audience(a.age, a.gender, a.location)
    t0 = time.perf_counter()
    step = lambda s: print(f"  {time.perf_counter() - t0:6.1f}s {report.STEPS.get(s, s)}")
    rid = a.id or a.video.stem
    asyncio.run(report.analyse(rid, a.video, aud, music=a.music, cast=a.cast, title=a.title,
                               on_step=step))
    v = report.load_view(rid, aud)
    print(f"\n{v['label']}: overall {v['overall']}  ({time.perf_counter() - t0:.1f}s)\n")
    for c in sorted(v["cues"], key=lambda c: (c["fit"] is None, c["fit"] or 0)):
        q = c["qloo"]["name"] if c.get("qloo") else "-"
        peak = fit.AGE_LABELS[fit.best_age(c["profile"])] if c.get("profile") else ""
        print(f"  {c['id']:4} {str(c['fit']):>6} {c['verdict']:8} "
              f"peak={peak:9} local={c.get('local')!s:5} {c['label'][:34]:34} -> {q}")
    print("\nswaps:")
    for cid, got in v["swaps"].items():
        print(f"  {cid}: " + "; ".join(f"{s['name']} ({s['fit']})" for s in got))
    b = v["brief"]
    print(f"\n{b['headline']}\n{b['summary']}")
    for f in b["findings"]:
        print(f"  - {f['title']}: {f['detail']} {f['cues']} {f['shots']}")
    for ch in b["changes"]:
        print(f"  * {ch['cue']} -> {ch['to']}: {ch['why']}")


if __name__ == "__main__":
    main()
