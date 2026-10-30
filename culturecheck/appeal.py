"""How much a video as a whole tends to appeal to each age group.

The mean of the cues' Qloo profiles says who the video's ingredients belong
to, and on real ads that alone did not predict which generation liked them
(eval/VALIDATION.md): a background setting's profile counts as much as the
star's, and humour or story are not cues at all. So the verdict is a
judgement, made once per video for all six age groups, by a model that reads:

    the Qloo evidence   each cue's affinity by age, weighed by how salient the
                        cue is (talent, music and brand over a background)
    what Qloo cannot    tone, humour, story, format: named, with the age group
    measure             each pulls toward, so the page shows what was used

Every group's answer cites the cues that pull toward it and away from it. With
`with_qloo=False` the same judge works from the cues alone: the ablation that
says what Qloo's numbers add.
"""

from __future__ import annotations

import json
from typing import Any

from . import fit as fitting
from .models import NUM, STR, arr, complete, obj, strict
from .qloo import AGES

SYSTEM = ("You judge which age groups a video appeals to, as a media strategist would. "
          "Where measured audience data is given, it outranks your own impressions of who "
          "likes what.")

PROMPT = """The video: {read}
On screen: {cast}

Its cues -- what is in it -- with how salient each is (weight 1-3, and the share of the
video's shots it appears in){evidence_note}:
{cues}

For each age group ({ages}), judge how much the video as a whole tends to appeal to that
group, from -1 (it pushes them away) through 0 (neither) to 1 (it is made for them).
{evidence_rules}- Also weigh what the cues cannot carry: tone, humour, pacing, story, format, and how
  references are used. List these as `factors`, each with the age group it pulls toward
  ("none" when it is broad).
- For each group, cite the cue ids that pull it toward the group (`toward`) and away
  (`away`), and give a one-line reason.
- summary: two sentences on who this video is really for."""

EVIDENCE_NOTE = (", and Qloo's measured affinity of each age group for it (-1..1: how much "
                 "that group over- or under-indexes on it; absent when Qloo holds no data)")
EVIDENCE_RULES = (
    "- Ground the judgement in the Qloo affinities, weighed by salience: the talent, the\n"
    "  music, the brand and what fills the screen count most. A setting or kind of place\n"
    "  says who visits such places, which is weak evidence about a video; never let\n"
    "  several background settings outweigh the star or the soundtrack.\n")

SCHEMA = strict("appeal", {
    "groups": arr(obj({"age": {"type": "string", "enum": AGES}, "appeal": NUM,
                       "reason": STR, "toward": arr(STR), "away": arr(STR)})),
    "factors": arr(obj({"factor": STR,
                        "toward": {"type": "string", "enum": [*AGES, "none"]},
                        "note": STR})),
    "summary": STR,
})


def _cues(report: dict[str, Any], with_qloo: bool) -> str:
    n = max(1, len(report["shots"]))
    lines = []
    for c in report["cues"]:
        entry: dict[str, Any] = {"id": c["id"], "label": c["label"], "kind": c["kind"],
                                 "source": c["source"], "weight": c.get("weight", 1),
                                 "screen": round(len(c["shots"]) / n, 2)}
        if with_qloo and c.get("profile"):
            entry["qloo"] = c["qloo"]["name"]
            entry["by_age"] = {fitting.AGE_LABELS[a]: round(v, 2)
                               for a, v in c["profile"]["age"].items()}
        lines.append(json.dumps(entry, ensure_ascii=False))
    return "\n".join(lines)


async def appeal(report: dict[str, Any], with_qloo: bool = True) -> dict[str, Any]:
    """{"by_age": {age: {appeal, reason, toward, away}}, "factors", "summary",
    "with_qloo"}: every age group present, `appeal` None for one the model
    left out."""
    answer = await complete(PROMPT.format(
        read=report["read"], cast=report["cast"], cues=_cues(report, with_qloo),
        ages=", ".join(fitting.AGE_LABELS[a] for a in AGES),
        evidence_note=EVIDENCE_NOTE if with_qloo else "",
        evidence_rules=EVIDENCE_RULES if with_qloo else ""), schema=SCHEMA, system=SYSTEM)
    return tidy(answer, report, with_qloo)


def tidy(answer: dict[str, Any], report: dict[str, Any], with_qloo: bool) -> dict[str, Any]:
    """The model's answer kept to known ages and cue ids, scores clamped."""
    known = {c["id"] for c in report["cues"]}
    by_age: dict[str, dict[str, Any]] = {a: {"appeal": None, "reason": "", "toward": [],
                                            "away": []} for a in AGES}
    for g in answer.get("groups") or []:
        if g.get("age") in by_age:
            by_age[g["age"]] = {
                "appeal": round(max(-1.0, min(1.0, float(g.get("appeal") or 0))), 2),
                "reason": g.get("reason", ""),
                "toward": [i for i in g.get("toward") or [] if i in known],
                "away": [i for i in g.get("away") or [] if i in known]}
    factors = [f for f in answer.get("factors") or []
               if f.get("toward") in (*AGES, "none")]
    return {"by_age": by_age, "factors": factors, "summary": answer.get("summary", ""),
            "with_qloo": with_qloo}


def for_audience(judged: dict[str, Any], aud: dict[str, Any]) -> dict[str, Any]:
    """The judgement for one audience's age group, with its verdict."""
    got = judged["by_age"][aud["age"]]
    return {**got, "verdict": fitting.verdict(got["appeal"])}
