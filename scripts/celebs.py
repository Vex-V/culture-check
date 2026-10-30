"""Test 5 of eval/VALIDATION.md: do Qloo's audience profiles point the way
YouGov's survey does, person by person? The LLM alone answers the same.

    python scripts/celebs.py
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from culturecheck.config import settings  # noqa: E402
from culturecheck.models import NUM, STR, arr, complete, obj, strict  # noqa: E402
from culturecheck.qloo import Qloo, entity_id  # noqa: E402

#: name, Qloo type, YouGov's direction (age: +1 younger / -1 older; gender: +1
#: women / -1 men), and YouGov's figures, from the 2026 celebrity-recall article.
CONTRASTS = [
    ("Sabrina Carpenter", "artist", "age", +1, "Gen Z 42% vs Boomers 14%"),
    ("MrBeast", "person", "age", +1, "Gen Z 33% vs Boomers 10%"),
    ("IShowSpeed", "person", "age", +1, "Gen Z 22% vs Boomers 1%"),
    ("Druski", "person", "age", +1, "Gen Z 18% vs Boomers 4%"),
    ("Lady Gaga", "artist", "age", +1, "Gen Z 52% vs overall 43%"),
    ("Ted Danson", "person", "age", -1, "Boomers 40% vs Gen Z 9%"),
    ("Jason Alexander", "person", "age", -1, "Boomers 27% vs Gen Z 5%"),
    ("Tom Brady", "person", "gender", -1, "men 47% vs women 31%"),
    ("Rob Gronkowski", "person", "gender", -1, "men 29% vs women 14%"),
    ("Peyton Manning", "person", "gender", -1, "men 33% vs women 19%"),
    ("Kendall Jenner", "person", "gender", +1, "women 22% vs men 14%"),
    ("Lady Gaga", "artist", "gender", +1, "women 48% vs men 39%"),
]

GUESS = """For each person, estimate their US audience skew:
- age: how much more under-25s than over-55s follow them, -1 (far more over-55s) to 1
  (far more under-25s);
- gender: -1 (far more men) to 1 (far more women).
{names}"""
SCHEMA = strict("skews", {"people": arr(obj({"name": STR, "age": NUM, "gender": NUM}))})


async def main() -> None:
    names = sorted({c[0] for c in CONTRASTS})
    types = {c[0]: c[1] for c in CONTRASTS}
    async with Qloo() as q:
        found = {}
        for n in names:
            hits = await q.search(n, [types[n]], take=1) or await q.search(n, None, take=1)
            found[n] = (hits[0].get("name"), entity_id(hits[0])) if hits else (None, None)
        prof = await q.demographics([i for _, i in found.values() if i])
    guess = await complete(GUESS.format(names="\n".join(names)), schema=SCHEMA)
    llm = {g["name"]: g for g in guess.get("people") or []}

    rows, q_right, l_right = [], 0, 0
    for name, _, axis, truth, figures in CONTRASTS:
        matched, pid = found[name]
        p = prof.get(pid)
        if p is None:
            qv = None
        elif axis == "age":
            qv = p["age"]["24_and_younger"] - p["age"]["55_and_older"]
        else:
            qv = p["gender"].get("female", 0) - p["gender"].get("male", 0)
        lv = (llm.get(name) or {}).get(axis)
        qok = qv is not None and (qv > 0) == (truth > 0)
        lok = lv is not None and (lv > 0) == (truth > 0)
        q_right += qok
        l_right += lok
        rows.append({"name": name, "matched": matched, "axis": axis, "yougov": figures,
                     "truth": truth, "qloo": None if qv is None else round(qv, 2),
                     "llm": lv, "qloo_ok": qok, "llm_ok": lok})
        print(f"  {name:18} {axis:6} YouGov {'+' if truth > 0 else '-'} ({figures:26}) "
              f"Qloo {'  -  ' if qv is None else f'{qv:+.2f}'} {'ok ' if qok else 'NO '} "
              f"LLM {'  -  ' if lv is None else f'{lv:+.2f}'} {'ok' if lok else 'NO'}")
    print(f"\nQloo agrees with YouGov on {q_right}/{len(CONTRASTS)}; "
          f"the LLM alone on {l_right}/{len(CONTRASTS)}")
    out = settings().data / "eval" / "celebs.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rows, indent=1), encoding="utf-8")


if __name__ == "__main__":
    asyncio.run(main())
