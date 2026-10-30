"""The same question without Qloo: a model alone judges each cue's fit.

It is given exactly what the Qloo path was -- the cues, their shots and why
they matter, and the audience -- and answers on the same -1..1 scale. The page
puts the two side by side, and `compare` lists where they disagree, which is
where the taste graph earned its place (or did not).
"""

from __future__ import annotations

import json
from typing import Any

from . import fit as fitting
from .models import NUM, STR, arr, complete, obj, strict

PROMPT = """A brand strategist is checking whether a video's cultural cues fit its target
audience: {audience}.

The video: {read}
Cues:
{items}

For each cue, rate how well it fits that audience, from -1 (works against it) through 0
(neutral) to 1 (strongly appeals), with one short reason. For each cue rated below 0.2,
suggest up to 2 same-role replacements that would fit better."""

SCHEMA = strict("baseline", {"ratings": arr(obj({
    "cue": STR, "fit": NUM, "reason": STR, "swaps": arr(STR)}))})


async def baseline(cues: list[dict[str, Any]], read: str,
                   aud: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """{cue id: {fit, verdict, reason, swaps}}"""
    items = "\n".join(json.dumps({"cue": c["id"], "label": c["label"], "kind": c["kind"],
                                  "why": c["why"]}, ensure_ascii=False) for c in cues)
    answer = await complete(PROMPT.format(audience=fitting.describe(aud), read=read,
                                          items=items), schema=SCHEMA)
    out = {}
    for r in answer.get("ratings") or []:
        value = max(-1.0, min(1.0, float(r.get("fit") or 0)))
        out[r["cue"]] = {"fit": round(value, 2), "verdict": fitting.verdict(value),
                         "reason": r.get("reason", ""), "swaps": r.get("swaps") or []}
    return out


def compare(cues: list[dict[str, Any]], guess: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Where Qloo and the model alone disagree: a different verdict, or a
    gap of 0.4 or more on the scale."""
    both = [c for c in cues if c.get("fit") is not None and c["id"] in guess]
    differ = []
    for c in both:
        g = guess[c["id"]]
        if g["verdict"] != c["verdict"] or abs(g["fit"] - c["fit"]) >= 0.4:
            differ.append({"cue": c["id"], "label": c["label"], "qloo": c["fit"],
                           "model": g["fit"], "reason": g["reason"]})
    differ.sort(key=lambda d: -abs(d["qloo"] - d["model"]))
    return {"compared": len(both), "agree": len(both) - len(differ), "differ": differ}
