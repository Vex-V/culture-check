"""Test 7 of eval/VALIDATION.md: did each ad reach the ages it was predicted to?

Ads are listed in data/eval/reach/ads.txt, and each video is saved as
data/eval-videos/reach/<library id>.mp4. Neither is in the repo: the ads are copyrighted.
Each entry starts with a line of the ad's library link and brand, then the "EU ad delivery"
text pasted from its page:

    === https://www.facebook.com/ads/library/?id=123 | Vinted
    EU ad audience
    ...

    python scripts/reach.py --check      # what was parsed from ads.txt; no calls
    python scripts/reach.py --predict    # predict from the saved videos; never reads reach
    python scripts/reach.py --score      # the predictions against actual reach
"""

from __future__ import annotations

import argparse
import asyncio
import json
import random
import re
import sys
from itertools import combinations
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from culturecheck import appeal, baseline, fit, report  # noqa: E402
from culturecheck.config import settings  # noqa: E402

HOME = settings().data / "eval" / "reach"
ADS_FILE, PREDICTIONS = HOME / "ads.txt", HOME / "predictions.json"
YOUNG, OLD = fit.audience("24_and_younger"), fit.audience("55_and_older")

#: Bucket midpoints, as pre-registered. 13-17 is not targeted by these ads.
AGES = {"18-24": 21, "25-34": 29.5, "35-44": 39.5, "45-54": 49.5, "55-64": 59.5, "65+": 70}
GENDERS = ("Female", "Male", "Unknown")
ARMS = ("judged", "judged_alone", "qloo_mean", "llm_cues")


def blocks(text: str) -> list[dict]:
    """ads.txt as [{url, brand, id, body}]."""
    out = []
    for chunk in re.split(r"^===[ \t]*", text, flags=re.M)[1:]:
        head, _, body = chunk.partition("\n")
        url, _, brand = head.partition("|")
        found = re.search(r"[?&]id=(\d+)", url)
        out.append({"url": url.strip(), "brand": brand.strip(),
                    "id": found.group(1) if found else "", "body": body})
    return out


def _after(lines: list[str], label: str) -> str:
    return next((lines[i + 1] for i in range(len(lines) - 1) if lines[i] == label), "")


def parse(body: str) -> dict:
    """The targeting, total reach and table of one ad's pasted text."""
    lines = [x.strip() for x in body.splitlines() if x.strip()]
    rows = []
    for i in range(len(lines) - 3):
        place, age, gender, reach = lines[i:i + 4]
        if age in AGES and gender in GENDERS and re.fullmatch(r"[\d,.]+", reach):
            rows.append({"place": place, "age": age, "gender": gender,
                         "reach": int(re.sub(r"\D", "", reach))})
    total = re.sub(r"\D", "", _after(lines, "Reach"))
    return {"target_age": _after(lines, "Age"), "target_gender": _after(lines, "Gender"),
            "reach": int(total) if total else None, "rows": rows}


def mean_age(parsed: dict) -> float | None:
    seen = sum(r["reach"] for r in parsed["rows"])
    return (sum(AGES[r["age"]] * r["reach"] for r in parsed["rows"]) / seen) if seen else None


def problems(parsed: dict) -> list[str]:
    """Why an ad cannot be scored, or breaks the rules fixed in advance."""
    out = []
    if not parsed["target_age"].startswith("18-65+"):
        out.append(f"targeted at {parsed['target_age']!r}, not 18-65+")
    if parsed["target_gender"] != "All":
        out.append(f"gender {parsed['target_gender']!r}, not All")
    if (parsed["reach"] or 0) < 50_000:
        out.append(f"reach {parsed['reach']} is under 50,000")
    missing = [a for a in AGES if not any(r["age"] == a for r in parsed["rows"])]
    if missing:
        out.append("no rows for " + ", ".join(missing))
    seen = sum(r["reach"] for r in parsed["rows"])
    if parsed["reach"] and seen < 0.8 * parsed["reach"]:
        out.append(f"table adds up to {seen:,} of {parsed['reach']:,}: pasted in part?")
    return out


def check() -> None:
    for ad in blocks(ADS_FILE.read_text(encoding="utf-8")):
        got = parse(ad["body"])
        bad = problems(got)
        print(f"{ad['brand']:14} {ad['id']:18} {len(got['rows']):3} rows  "
              + ("; ".join(bad) if bad else "ok"))


def saved_video(ad: dict) -> Path:
    out = settings().data / "eval-videos" / "reach" / f"{ad['id']}.mp4"
    if not out.exists():
        raise FileNotFoundError(f"save this ad's video as {out}")
    return out


def _weighted(cues: list[dict], guess: dict) -> float | None:
    rated = [(guess[c["id"]]["fit"], c.get("weight", 1)) for c in cues if c["id"] in guess]
    weights = sum(w for _, w in rated)
    return sum(v * w for v, w in rated) / weights if weights else None


def _gap(judged: dict) -> float | None:
    y, o = (judged["by_age"][a["age"]]["appeal"] for a in (YOUNG, OLD))
    return None if y is None or o is None else round(y - o, 3)


async def predict_one(ad: dict) -> dict:
    rid = f"reach-{ad['id']}"
    video = saved_video(ad)
    r = report.load(rid) or await report.analyse(rid, video, YOUNG, title=ad["brand"])
    if "appeal_noqloo" not in r:
        r["appeal_noqloo"] = await appeal.appeal(r, with_qloo=False)
        report._write(report.folder(rid) / "report.json", r)
    cues = [dict(c) for c in r["cues"]]
    young = fit.rate(cues, YOUNG)["fit"]
    old = fit.rate(cues, OLD)["fit"]
    guess_y, guess_o = await asyncio.gather(baseline.baseline(cues, r["read"], YOUNG),
                                            baseline.baseline(cues, r["read"], OLD))
    gy, go = _weighted(cues, guess_y), _weighted(cues, guess_o)
    return {"id": ad["id"], "brand": ad["brand"], "seconds": r["duration"],
            "judged": _gap(r["appeal"]), "judged_alone": _gap(r["appeal_noqloo"]),
            "qloo_mean": None if young is None or old is None else round(young - old, 3),
            "llm_cues": None if gy is None or go is None else round(gy - go, 3)}


def predict() -> None:
    made = json.loads(PREDICTIONS.read_text(encoding="utf-8")) if PREDICTIONS.exists() else {}
    for ad in blocks(ADS_FILE.read_text(encoding="utf-8")):
        if ad["id"] in made:
            continue
        try:
            made[ad["id"]] = asyncio.run(predict_one(ad))
            PREDICTIONS.write_text(json.dumps(made, indent=1, ensure_ascii=False), encoding="utf-8")
            print(f"  {ad['brand']} {ad['id']}", flush=True)
        except Exception as exc:                           # noqa: BLE001
            print(f"  {ad['brand']} {ad['id']}: FAILED {type(exc).__name__}: {exc}", flush=True)


def ranks(values: list[float]) -> list[float]:
    order = sorted(range(len(values)), key=values.__getitem__)
    out = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        for k in range(i, j + 1):
            out[order[k]] = (i + j) / 2
        i = j + 1
    return out


def spearman(a: list[float], b: list[float]) -> float:
    x, y = ranks(a), ranks(b)
    mx, my = sum(x) / len(x), sum(y) / len(y)
    top = sum((p - mx) * (q - my) for p, q in zip(x, y))
    down = (sum((p - mx) ** 2 for p in x) * sum((q - my) ** 2 for q in y)) ** 0.5
    return top / down if down else 0.0


def permutation_p(pred: list[float], real: list[float], tries: int = 20000) -> float:
    random.seed(0)
    seen, shuffled = spearman(pred, real), list(real)
    hits = 0
    for _ in range(tries):
        random.shuffle(shuffled)
        hits += spearman(pred, shuffled) >= seen
    return hits / tries


def pairs_right(rows: list[dict], arm: str, same_brand: bool) -> tuple[float, int]:
    right = total = 0.0
    for a, b in combinations(rows, 2):
        if same_brand and a["brand"] != b["brand"]:
            continue
        if a["youth"] == b["youth"]:
            continue
        total += 1
        younger, older = (a, b) if a["youth"] > b["youth"] else (b, a)
        right += (younger[arm] > older[arm]) + 0.5 * (younger[arm] == older[arm])
    return right, int(total)


def score() -> None:
    made = json.loads(PREDICTIONS.read_text(encoding="utf-8"))
    rows, left_out = [], []
    for ad in blocks(ADS_FILE.read_text(encoding="utf-8")):
        got = parse(ad["body"])
        bad = problems(got)
        if bad or ad["id"] not in made or any(made[ad["id"]][a] is None for a in ARMS):
            left_out.append((ad["brand"], ad["id"], bad or ["no prediction"]))
            continue
        age = mean_age(got)
        rows.append({**made[ad["id"]], "mean_age": round(age, 2), "youth": -age})
    print(f"{'brand':14} {'id':18} {'mean age':>8}  " + "".join(f"{a:>14}" for a in ARMS))
    for r in sorted(rows, key=lambda x: x["mean_age"]):
        print(f"{r['brand']:14} {r['id']:18} {r['mean_age']:8.1f}  "
              + "".join(f"{r[a]:+14.2f}" for a in ARMS))
    real = [r["youth"] for r in rows]
    print(f"\n{len(rows)} ads scored, {len(left_out)} left out")
    for a in ARMS:
        pred = [r[a] for r in rows]
        right, total = pairs_right(rows, a, False)
        same, within = pairs_right(rows, a, True)
        print(f"  {a:14} rho {spearman(pred, real):+.2f}  p={permutation_p(pred, real):.3f}  "
              f"all pairs {right:.1f}/{total}  within brand {same:.1f}/{within}")
    for item in left_out:
        print("  left out:", *item)
    (HOME / "results.json").write_text(json.dumps({"rows": rows, "left_out": left_out}, indent=1,
                                                  ensure_ascii=False), encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--predict", action="store_true")
    ap.add_argument("--score", action="store_true")
    a = ap.parse_args()
    HOME.mkdir(parents=True, exist_ok=True)
    if a.check:
        check()
    if a.predict:
        predict()
    if a.score:
        score()


if __name__ == "__main__":
    main()
