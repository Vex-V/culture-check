"""How well each cue fits an audience, by Qloo's taste graph.

Every resolved cue -- an entity or a tag -- gets Qloo's audience profile in one
batched `urn:demographics` call: an affinity from -1 to 1 for each of six age
groups and for each gender. That profile does not depend on who the video is
for, so it is fetched once per video, and scoring another audience is
arithmetic (`score`, mirrored in the page's script).

A place in the audience narrows it further. Qloo answers location through
`signal.location.query`, and asked with `filter.results.entities` it returns
only the cues that have a following there -- so `local` is that affinity, or 0
for a cue nobody there follows. Tags have no such answer and stay None.
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import Any, Optional

from .qloo import AGES, GENDERS, Qloo, QlooError, affinity, entity_id

AGE_LABELS = {"24_and_younger": "under 25", "25_to_29": "25-29", "30_to_34": "30-34",
              "35_to_44": "35-44", "45_to_54": "45-54", "55_and_older": "55+"}

#: How much the gender lean counts against the age one, when a gender is given.
GENDER_SHARE = 0.35
#: Above this a cue fits the audience; below its negative it works against it.
FITS, OFF = 0.2, -0.2


def audience(age: str, gender: Optional[str] = None,
             location: Optional[str] = None) -> dict[str, Any]:
    if age not in AGES:
        raise ValueError(f"age must be one of {', '.join(AGES)}")
    if gender not in (None, "", *GENDERS):
        raise ValueError(f"gender must be one of {', '.join(GENDERS)}, or left out")
    return {"age": age, "gender": gender or None,
            "location": (location or "").strip() or None}


def describe(aud: dict[str, Any]) -> str:
    parts = [AGE_LABELS[aud["age"]]]
    if aud.get("gender"):
        parts.append("women" if aud["gender"] == "female" else "men")
    text = " ".join(parts) if len(parts) == 1 else f"{parts[1]} {parts[0]}"
    return f"{text} in {aud['location']}" if aud.get("location") else text


def key(aud: dict[str, Any]) -> str:
    """A file-safe name for one audience."""
    loc = "".join(ch if ch.isalnum() else "-" for ch in (aud.get("location") or "").lower())
    return "_".join(p for p in (aud["age"], aud.get("gender") or "any", loc.strip("-")) if p)


def score(profile: Optional[dict[str, Any]], aud: dict[str, Any]) -> Optional[float]:
    """A cue's fit, -1..1: its affinity with the audience's age group, leaned by
    its gender affinity when a gender is given. None with no profile."""
    if not profile:
        return None
    fit = float(profile["age"].get(aud["age"], 0.0))
    if aud.get("gender"):
        fit = (1 - GENDER_SHARE) * fit + GENDER_SHARE * float(
            (profile.get("gender") or {}).get(aud["gender"], 0.0))
    return round(fit, 3)


def verdict(fit: Optional[float]) -> str:
    if fit is None:
        return "unknown"
    return "fits" if fit >= FITS else "off" if fit <= OFF else "neutral"


def best_age(profile: dict[str, Any]) -> str:
    return max(profile["age"], key=lambda a: profile["age"][a])


async def profiles(q: Qloo, cues: list[dict[str, Any]]) -> None:
    """Sets `profile` on every resolved cue (None when Qloo has no audience)."""
    ids = [c["qloo"]["id"] for c in cues if c.get("qloo")]
    found = await q.demographics(ids) if ids else {}
    for c in cues:
        c["profile"] = found.get(c["qloo"]["id"]) if c.get("qloo") else None


async def local(q: Qloo, cues: list[dict[str, Any]], location: Optional[str]) -> None:
    """Sets `local` on every entity cue: its affinity in `location`, 0 when it
    has no following there, None with no location or for a tag."""
    for c in cues:
        c["local"] = None
    if not location:
        return
    by_kind: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for c in cues:
        if c.get("qloo") and c["qloo"]["kind"] == "entity":
            by_kind[c["qloo"]["type"]].append(c)

    async def ask(kind: str, group: list[dict[str, Any]]) -> None:
        ids = sorted({c["qloo"]["id"] for c in group})
        try:
            got = await q.insights(kind, {"filter.results.entities": ids,
                                          "signal.location.query": location,
                                          "take": len(ids)})
        except QlooError:
            return
        seen = {entity_id(e): affinity(e) or 0.0 for e in got}
        for c in group:
            c["local"] = round(seen.get(c["qloo"]["id"], 0.0), 3)

    await asyncio.gather(*(ask(k, g) for k, g in by_kind.items()))


def rate(cues: list[dict[str, Any]], aud: dict[str, Any]) -> dict[str, Any]:
    """Sets `fit` and `verdict` on each cue; returns the video's overall fit
    (the cues' fits weighted by `weight`) and the counts."""
    total = weights = 0.0
    counts = {"fits": 0, "neutral": 0, "off": 0, "unknown": 0}
    for c in cues:
        c["fit"] = score(c.get("profile"), aud)
        c["verdict"] = verdict(c["fit"])
        counts[c["verdict"]] += 1
        if c["fit"] is not None:
            total += c["fit"] * c.get("weight", 1)
            weights += c.get("weight", 1)
    overall = round(total / weights, 3) if weights else None
    return {"fit": overall, "verdict": verdict(overall), "counts": counts}


#: A cue "reaches" an age group when that group over-indexes on it by this much.
REACHES = 0.2


def age_map(cues: list[dict[str, Any]], top: int = 8) -> dict[str, list[dict[str, Any]]]:
    """For each age group, the cues it over-indexes on most: {age: [{id, label,
    value}]}, strongest first. From Qloo's profiles alone, so the same for every
    audience."""
    out: dict[str, list[dict[str, Any]]] = {a: [] for a in AGES}
    for c in cues:
        for age, value in ((c.get("profile") or {}).get("age") or {}).items():
            if value >= REACHES and age in out:
                out[age].append({"id": c["id"], "label": c["label"], "value": round(value, 2),
                                 "weight": c.get("weight", 1)})
    for age in out:
        out[age].sort(key=lambda x: (-x["value"] * x["weight"], -x["value"]))
        out[age] = out[age][:top]
    return out


def shot_ages(cues: list[dict[str, Any]], shots: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Which moments reach which age group: for each shot, the weighted mean of
    the Qloo affinities of the profiled cues in it, by age group, and how many
    cues that rests on."""
    out = []
    for s in shots:
        here = [c for c in cues if s["shot"] in c["shots"] and c.get("profile")]
        weights = sum(c.get("weight", 1) for c in here)
        ages = {a: (round(sum(c["profile"]["age"].get(a, 0.0) * c.get("weight", 1)
                              for c in here) / weights, 3) if weights else None)
                for a in AGES}
        out.append({"shot": s["shot"], "ages": ages, "cues": len(here)})
    return out
