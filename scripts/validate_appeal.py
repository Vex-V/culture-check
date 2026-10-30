"""Test 6 of eval/VALIDATION.md: does the judged appeal track which generation
preferred an ad? Uses the run-2 reports already made (no video is read again),
and judges each twice: with Qloo's evidence, and from the cues alone.

    python scripts/validate_appeal.py            # judge what is missing, then score
    python scripts/validate_appeal.py --table    # score what is already judged

Calls the LLM: two calls per ad. The judgements are kept in each report
(`appeal`, `appeal_noqloo`), so a re-run costs nothing.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from culturecheck import appeal, report  # noqa: E402
from culturecheck.config import settings  # noqa: E402
from scripts.validate import ADS  # noqa: E402

SUFFIX = "-r2"
YOUNG, OLD = "24_and_younger", "55_and_older"


async def judge(rid: str) -> None:
    r = report.load(rid)
    if r is None:
        return
    if "appeal" not in r:
        r["appeal"] = await appeal.appeal(r, with_qloo=True)
    if "appeal_noqloo" not in r:
        r["appeal_noqloo"] = await appeal.appeal(r, with_qloo=False)
    report._write(report.folder(rid) / "report.json", r)
    print(f"  {rid}", flush=True)


def gap(judged: dict) -> float | None:
    y, o = judged["by_age"][YOUNG]["appeal"], judged["by_age"][OLD]["appeal"]
    return None if y is None or o is None else round(y - o, 3)


def table() -> dict:
    rows = []
    for name, title, group, _ in ADS:
        r = report.load(name + SUFFIX)
        if r is None or "appeal" not in r or "appeal_noqloo" not in r:
            continue
        rows.append({"id": name, "title": title, "group": group,
                     "qloo": gap(r["appeal"]), "alone": gap(r["appeal_noqloo"])})
    out = {"rows": rows}
    for key in ("qloo", "alone"):
        genz = [x[key] for x in rows if x["group"] == "genz" and x[key] is not None]
        lead = [x[key] for x in rows if x["group"] == "leader" and x[key] is not None]
        right = sum(1 for a in genz for b in lead if a > b)
        ties = sum(1 for a in genz for b in lead if a == b)
        out[key] = {"right": right, "ties": ties, "pairs": len(genz) * len(lead)}
    by = {x["id"]: x for x in rows}
    if {"jaguar-copy-nothing", "jaguar-epace"} <= set(by):
        for key in ("qloo", "alone"):
            r1, r2 = (report.load(n + SUFFIX) for n in ("jaguar-copy-nothing", "jaguar-epace"))
            name = "appeal" if key == "qloo" else "appeal_noqloo"
            cn = r1[name]["by_age"]["45_to_54"]["appeal"]
            ep = r2[name]["by_age"]["45_to_54"]["appeal"]
            out[key]["P3"] = (cn is not None and ep is not None and cn < ep, cn, ep)
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--table", action="store_true")
    a = ap.parse_args()
    if not a.table:
        for name, *_ in ADS:
            try:
                asyncio.run(judge(name + SUFFIX))
            except Exception as exc:                       # noqa: BLE001
                print(f"  {name}: FAILED {type(exc).__name__}: {exc}", flush=True)
    out = table()
    print(f"\n{'ad':42} {'group':7} {'with Qloo':>10} {'cues alone':>11}")
    for x in out["rows"]:
        f = lambda v: "   -  " if v is None else f"{v:+.2f}"
        print(f"{x['title']:42} {x['group']:7} {f(x['qloo']):>10} {f(x['alone']):>11}")
    for key, name in (("qloo", "judged with Qloo"), ("alone", "judged from cues alone")):
        s = out[key]
        print(f"  P6 {name}: {s['right']}/{s['pairs']} pairs right, {s['ties']} ties"
              + (f"; P3 Copy Nothing below E-PACE for 45-54: {s['P3']}" if "P3" in s else ""))
    path = settings().data / "eval" / "results-appeal.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
