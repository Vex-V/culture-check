"""Run the ads in eval/VALIDATION.md through the pipeline and score the
predictions written there before any of them was run.

    python scripts/validate.py            # every ad, then the table
    python scripts/validate.py --table    # the table from reports already made

Videos are read from data/eval-videos/ (not in the repo: the ads are
copyrighted). Each ad is one report, viewed for under-25s, for 55+, and for
the audience its test names; results go to data/eval/results.json.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from culturecheck import fit, report  # noqa: E402
from culturecheck.config import settings  # noqa: E402

VIDEOS = settings().data / "eval-videos"
YOUNG, OLD = fit.audience("24_and_younger"), fit.audience("55_and_older")

#: Run 2 only: who appears and the soundtrack, as named in each ad's own title and
#: press (what an uploader would type); ads with no named talent get nothing.
GIVEN = {
    "pringles-pringleleo": {"cast": "Sabrina Carpenter"},
    "bud-light-keg": {"cast": "Post Malone, Peyton Manning, Shane Gillis"},
    "nerds": {"cast": "Andy Cohen"},
    "hellmanns": {"cast": "Andy Samberg, Elle Fanning, Neil Diamond"},
    "pepsi-live-for-now": {"cast": "Kendall Jenner", "music": "Skip Marley - Lions"},
    # Test 4 (held out)
    "uber-eats": {"cast": "Matthew McConaughey, Bradley Cooper, Parker Posey"},
    "franks-redhot": {"cast": "Ludacris"},
    "kinder-bueno": {"cast": "William Fichtner, Paige DeSorbo"},
    "novartis-tight-end": {"cast": "Rob Gronkowski, Tony Gonzalez"},
    "xfinity-jurassic-park": {"cast": "Jeff Goldblum, Sam Neill"},
    "budweiser-american-icons": {"music": "Lynyrd Skynyrd - Free Bird"},
}

#: id, title, group, the audience its test names
ADS = [
    ("lays-last-harvest", "Lay's · Last Harvest", "leader", fit.audience("35_to_44")),
    ("ring-be-a-hero", "Ring · Be A Hero In Your Neighborhood", "leader",
     fit.audience("35_to_44")),
    ("google-new-home", "Google · New Home", "leader", fit.audience("35_to_44")),
    ("pringles-pringleleo", "Pringles · Pringleleo", "genz", YOUNG),
    ("nfl-champion", "NFL · Champion", "genz", YOUNG),
    ("bud-light-keg", "Bud Light · Keg", "genz", YOUNG),
    ("nerds", "Nerds · Juicy Gummy Clusters", "genz", YOUNG),
    ("hellmanns", "Hellmann's · Big Game", "genz", YOUNG),
    ("jaguar-copy-nothing", "Jaguar · Copy Nothing", "jaguar",
     fit.audience("45_to_54", "male")),
    ("jaguar-epace", "Jaguar · E-PACE", "jaguar", fit.audience("45_to_54", "male")),
    ("pepsi-live-for-now", "Pepsi · Live for Now", "pepsi", fit.audience("25_to_29")),
    # Test 4: held out, written before these were run
    ("uber-eats", "Uber Eats · Hungry for the Truth", "genz", YOUNG),
    ("franks-redhot", "Frank's RedHot · Eat the Goat", "genz", YOUNG),
    ("kinder-bueno", "Kinder Bueno · Yes Bueno", "genz", YOUNG),
    ("pepsi-the-choice", "Pepsi · The Choice", "leader", fit.audience("35_to_44")),
    ("dove-game-is-ours", "Dove · The Game Is Ours", "leader", fit.audience("35_to_44")),
    ("novartis-tight-end", "Novartis · Relax Your Tight End", "leader",
     fit.audience("35_to_44")),
    ("budweiser-american-icons", "Budweiser · American Icons", "leader",
     fit.audience("35_to_44")),
    ("xfinity-jurassic-park", "Xfinity · Jurassic Park... Works", "leader",
     fit.audience("35_to_44")),
    ("nfl-you-are-special", "NFL · You Are Special", "leader", fit.audience("35_to_44")),
    ("blue-square-sticky-note", "Blue Square · Sticky Note", "psa", fit.audience("35_to_44")),
]


SUFFIX = ""          # "-r2" for run 2, which also passes GIVEN


async def run_one(name: str, title: str, aud: dict) -> None:
    video = VIDEOS / f"{name}.mp4"
    rid = name + SUFFIX
    given = GIVEN.get(name, {}) if SUFFIX else {}
    t0 = time.perf_counter()
    if report.load(rid) is None:
        await report.analyse(rid, video, aud, title=title, **given)
    for a in (aud, YOUNG, OLD):
        await report.view(rid, a)
    print(f"  {rid}: {time.perf_counter() - t0:.0f}s", flush=True)


def table() -> dict:
    rows = []
    for name, title, group, aud in ADS:
        rid = name + SUFFIX
        if report.load(rid) is None:
            continue
        named, young, old = (report.load_view(rid, a) for a in (aud, YOUNG, OLD))
        if not (named and young and old):
            continue
        rows.append({"id": name, "title": title, "group": group, "named": named["label"],
                     "fit": named["overall"]["fit"], "young": young["overall"]["fit"],
                     "old": old["overall"]["fit"],
                     "gap": round((young["overall"]["fit"] or 0) - (old["overall"]["fit"] or 0), 3),
                     "model_fit": _model_overall(named),
                     "scored": sum(1 for c in named["cues"] if c["fit"] is not None),
                     "cues": len(named["cues"])})
    by = {r["id"]: r for r in rows}
    mean = lambda g: round(sum(r["gap"] for r in rows if r["group"] == g)
                           / max(1, sum(1 for r in rows if r["group"] == g)), 3)
    checks = {}
    if {"pringles-pringleleo", "lays-last-harvest"} <= set(by):
        checks["P1 Pringles leans younger than Lay's"] = (
            by["pringles-pringleleo"]["gap"] > by["lays-last-harvest"]["gap"],
            f"{by['pringles-pringleleo']['gap']:+.3f} vs {by['lays-last-harvest']['gap']:+.3f}")
    checks["P2 Gen Z favourites lean younger than the leaders"] = (
        mean("genz") > mean("leader"), f"{mean('genz'):+.3f} vs {mean('leader'):+.3f}")
    genz = [r["gap"] for r in rows if r["group"] == "genz"]
    lead = [r["gap"] for r in rows if r["group"] == "leader"]
    if genz and lead:
        right = sum(1 for a in genz for b in lead if a > b)
        checks["P6 pairs: Gen Z overperformer leans younger than leader"] = (
            right > len(genz) * len(lead) / 2,
            f"{right}/{len(genz) * len(lead)} ({100 * right / (len(genz) * len(lead)):.0f}%)")
    if {"jaguar-copy-nothing", "jaguar-epace"} <= set(by):
        cn, ep = by["jaguar-copy-nothing"], by["jaguar-epace"]
        checks["P3 Copy Nothing below E-PACE for men 45-54"] = (
            cn["fit"] < ep["fit"], f"{cn['fit']:+.3f} vs {ep['fit']:+.3f}")
        checks["P4 Copy Nothing leans young"] = (cn["gap"] > 0, f"gap {cn['gap']:+.3f}")
    if "pepsi-live-for-now" in by:
        p = by["pepsi-live-for-now"]
        checks["P5 Pepsi rated as fitting 25-29s (the limitation)"] = (
            fit.verdict(p["fit"]) == "fits", f"{p['fit']:+.3f} ({fit.verdict(p['fit'])})")
    return {"rows": rows, "checks": checks}


def _model_overall(view: dict) -> float | None:
    """The model-alone baseline's overall, weighted as Qloo's is."""
    total = weights = 0.0
    for c in view["cues"]:
        g = view.get("baseline", {}).get(c["id"])
        if g is not None:
            total += g["fit"] * c.get("weight", 1)
            weights += c.get("weight", 1)
    return round(total / weights, 3) if weights else None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--table", action="store_true")
    ap.add_argument("--run", type=int, default=1, help="2: names given, ids end in -r2")
    a = ap.parse_args()
    global SUFFIX
    SUFFIX = "-r2" if a.run == 2 else ""
    if not a.table:
        for rid, title, _, aud in ADS:
            try:
                asyncio.run(run_one(rid, title, aud))
            except Exception as exc:                       # noqa: BLE001
                print(f"  {rid}: FAILED {type(exc).__name__}: {exc}", flush=True)
    out = table()
    print(f"\n{'ad':42} {'group':7} {'named audience':22} {'fit':>6} {'model':>6} "
          f"{'<25':>6} {'55+':>6} {'gap':>6} scored")
    for r in out["rows"]:
        print(f"{r['title']:42} {r['group']:7} {r['named']:22} {r['fit']:+6.2f} "
              f"{(r['model_fit'] or 0):+6.2f} {r['young']:+6.2f} {r['old']:+6.2f} "
              f"{r['gap']:+6.2f} {r['scored']}/{r['cues']}")
    print()
    for name, (ok, detail) in out["checks"].items():
        print(f"  {'PASS' if ok else 'FAIL'}  {name}: {detail}")
    path = settings().data / "eval" / f"results-run{a.run}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
