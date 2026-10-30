"""The report's written brief: what the numbers say, in a strategist's words.

Written last, from everything measured: the cues and their Qloo fit, who each
one actually reaches, the local following and the swaps. It may only cite cues
and shots that exist,
and every claim about who likes what must come from Qloo's numbers.
"""

from __future__ import annotations

import json
from typing import Any

from . import fit as fitting
from .models import INT, STR, arr, complete, obj, strict

SYSTEM = ("You are a brand strategist writing a short, concrete brief. Every claim about "
          "who likes what comes from the Qloo numbers you are given, never from your own "
          "assumptions; where Qloo has no data, say so.")

PROMPT = """Target audience: {audience}.
The video, before any audience data: {read}
On screen: {cast}
How much the video as a whole appeals to {age}, on -1..1: {appeal} ({appeal_verdict}).
{appeal_reason}
That figure is a model's judgement from the Qloo evidence and what the cues cannot carry, for
the age group alone. Word it as a judgement about {age}: never credit it to Qloo, and never
apply it to a gender or a city.
The plain average of the cues' Qloo fit: {overall} ({verdict}).

Cues (fit is Qloo's, for this audience; peak is the age group Qloo says likes it most;
local is its following in the audience's location, 0..1, when one was given):
{cues}

Qloo's replacements for the cues that miss:
{swaps}

Write the brief:
- headline: one line, the verdict in plain words (lead with the judged appeal).
- summary: 2-3 sentences.
- findings: 3-5, the most important first, each a short title and 1-2 sentences of detail.
  In the text, name cues by what they are and shots by time, never by id; list the cue ids
  and shot numbers the finding is about in `cues` and `shots`.
- changes: the concrete edits to make, each the cue id and what to swap it for (from the
  replacements only) and why, in plain words.
- keep: cues that work and should stay, by id."""

SCHEMA = strict("brief", {
    "headline": STR, "summary": STR,
    "findings": arr(obj({"title": STR, "detail": STR, "cues": arr(STR), "shots": arr(INT)})),
    "changes": arr(obj({"cue": STR, "to": STR, "why": STR})),
    "keep": arr(STR),
})


def _cue_line(c: dict[str, Any]) -> str:
    entry: dict[str, Any] = {"id": c["id"], "label": c["label"], "kind": c["kind"],
                             "shots": c["shots"], "weight": c.get("weight"),
                             "qloo": c["qloo"]["name"] if c.get("qloo") else None,
                             "fit": c.get("fit")}
    if c.get("profile"):
        entry["peak"] = fitting.AGE_LABELS[fitting.best_age(c["profile"])]
    if c.get("local") is not None:
        entry["local"] = c["local"]
    return json.dumps(entry, ensure_ascii=False)


async def brief(report: dict[str, Any], view: dict[str, Any]) -> dict[str, Any]:
    cues = view["cues"]
    swaps = "\n".join(
        f"{cid}: " + "; ".join(f"{s['name']} (fit {s['fit']})" for s in got)
        for cid, got in view["swaps"].items() if got) or "(none)"
    answer = await complete(PROMPT.format(
        audience=fitting.describe(view["audience"]), read=report["read"], cast=report["cast"],
        age=fitting.AGE_LABELS[view["audience"]["age"]],
        overall=view["overall"]["fit"], verdict=view["overall"]["verdict"],
        appeal=view["appeal"]["appeal"], appeal_verdict=view["appeal"]["verdict"],
        appeal_reason=view["appeal"]["reason"],
        cues="\n".join(_cue_line(c) for c in cues), swaps=swaps),
        schema=SCHEMA, system=SYSTEM)
    known = {c["id"] for c in cues}
    shots = {s["shot"] for s in report["shots"]}
    for f in answer.get("findings") or []:
        f["cues"] = [c for c in f["cues"] if c in known]
        f["shots"] = [s for s in f["shots"] if s in shots]
    answer["changes"] = [c for c in answer.get("changes") or [] if c["cue"] in known]
    answer["keep"] = [c for c in answer.get("keep") or [] if c in known]
    return answer
