"""Same-role replacements for the cues that miss the audience.

Qloo proposes and Qloo judges; the model only keeps the role.

    entity  Qloo's neighbours of the cue (`signal.interests.entities`), asked
            with the audience as signals and kept to the cue's own genres
            (`filter.tags`), so the pool is things like it, in its category,
            that the audience is near
    tag     a model names kinds of thing that could fill the same role in the
            shot ("diner" -> "food hall", "ramen bar"), and `/v2/tags` turns
            each into a Qloo tag. The model is told not to aim at the audience:
            that judgement is Qloo's

Every candidate then gets its own `urn:demographics` profile and is scored for
the audience exactly as the cue was, and only candidates that beat the cue go
forward. Last, one model call keeps up to three per cue that would play the
same part in the shot -- Sinatra's role in a scene is "the soundtrack's warm
nostalgia", which a neighbour by listeners can miss.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

from . import fit as fitting
from .models import INT, STR, arr, complete, obj, strict
from .qloo import Qloo, QlooError, entity_id

#: How many cues get swaps, and how many survive per cue.
MAX_TARGETS, KEEP = 5, 3
#: A candidate must beat the cue by this much to be worth proposing.
MARGIN = 0.15

IDEAS = """Cues from a video, each a kind of thing (a Qloo tag) in its scene:

{items}

For each cue, name 8 different kinds of thing that could fill the SAME role in the same
shot -- the same job in the scene (a place to eat, a style of clothes, a music genre), varied
in era, region and subculture. Do not aim them at any audience; just make them plausible
alternatives. Each is a short keyword, as a tag would read ("food hall", "ramen bar")."""

IDEAS_SCHEMA = strict("ideas", {"ideas": arr(obj({"cue": STR, "keywords": arr(STR)}))})

PICK = """A video is being checked against its target audience: {audience}.
These cues miss that audience. Each comes with replacements Qloo's taste graph says fit the
audience better (fit is -1..1 for this audience; the cue's own fit is given).

{items}

For each cue, choose up to {keep} candidates (by index) that would play the same part in
the shot -- a stand-in a director could actually swap in -- best first. Leave out any that
would change what the scene is about, and any from a different category (a snack in place
of a beer, a film in place of a song): choose none rather than that. For each, write `how`: one short line on how the shot
would read with it."""

PICK_SCHEMA = strict("picks", {"picks": arr(obj({
    "cue": STR, "chosen": arr(obj({"index": INT, "how": STR}))}))})


def advertised(cues: list[dict[str, Any]]) -> set[str]:
    """The ids of the brand the video is for: the top-weight brand in the most
    shots. Told to leave it alone, the picking model still swapped Ring for Yelp."""
    brands = [c for c in cues if c["kind"] == "brand" and c.get("weight") == 3]
    most = max((len(c["shots"]) for c in brands), default=0)
    return {c["id"] for c in brands if len(c["shots"]) == most}


def targets(cues: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The cues worth replacing: resolved, profiled, not fitting and not the
    advertised brand, the most damaging (lowest fit times weight) first."""
    own = advertised(cues)
    misses = [c for c in cues if c.get("fit") is not None and c["verdict"] != "fits"
              and c["id"] not in own]
    misses.sort(key=lambda c: c["fit"] * c.get("weight", 1))
    return misses[:MAX_TARGETS]


async def _neighbours(q: Qloo, cue: dict[str, Any], aud: dict[str, Any]) -> list[dict]:
    kind = cue["qloo"]["type"]
    params: dict[str, Any] = {"signal.interests.entities": [cue["qloo"]["id"]],
                              "signal.demographics.age": aud["age"], "take": 30}
    genres = (cue.get("info") or {}).get("genres")
    if genres:                          # a beer stays a beer
        params["filter.tags"] = genres
        params["operator.filter.tags"] = "union"
    if aud.get("gender"):
        params["signal.demographics.gender"] = aud["gender"]
    if aud.get("location"):
        params["filter.location.query" if kind == "place"
               else "signal.location.query"] = aud["location"]
    try:
        got = await q.insights(kind, params)
    except QlooError:
        return []
    return [{"kind": "entity", "id": entity_id(e), "name": e.get("name"), "type": kind,
             "image": ((e.get("properties") or {}).get("image") or {}).get("url")}
            for e in got if entity_id(e) and entity_id(e) != cue["qloo"]["id"]]


async def _tag_ideas(q: Qloo, cues: list[dict[str, Any]]) -> dict[str, list[dict]]:
    if not cues:
        return {}
    items = "\n".join(json.dumps({"cue": c["id"], "label": c["label"], "tag": c["qloo"]["name"],
                                  "kind": c["kind"], "why": c["why"]}, ensure_ascii=False)
                      for c in cues)
    answer = await complete(IDEAS.format(items=items), schema=IDEAS_SCHEMA)
    ideas = {i["cue"]: i["keywords"] for i in answer.get("ideas") or []}

    async def tag_for(cue: dict[str, Any], word: str) -> dict | None:
        try:
            found = await q.tags(word, take=3)
        except QlooError:
            return None
        want = f"urn:entity:{cue['qloo']['type']}"
        found.sort(key=lambda t: 0 if any(p.get("type") == want for p in
                                           t["raw"].get("parents") or []) else 1)
        for t in found:
            if t["id"] and t["id"] != cue["qloo"]["id"]:
                return {"kind": "tag", "id": t["id"], "name": t["name"], "type": t["type"],
                        "image": None}
        return None

    out: dict[str, list[dict]] = {}
    for c in cues:
        words = ideas.get(c["id"], [])[:8]
        got = await asyncio.gather(*(tag_for(c, w) for w in words))
        seen, pool = set(), []
        for t in got:
            if t and t["id"] not in seen:
                seen.add(t["id"])
                pool.append(t)
        out[c["id"]] = pool
    return out


async def swaps(q: Qloo, cues: list[dict[str, Any]], aud: dict[str, Any]) -> dict[str, list]:
    """{cue id: [candidate, ...]}, each candidate {kind, id, name, type, image,
    fit, profile, how}, best first. Empty for a cue nothing beat."""
    chosen = targets(cues)
    if not chosen:
        return {}
    ents = [c for c in chosen if c["qloo"]["kind"] == "entity"]
    tags = [c for c in chosen if c["qloo"]["kind"] == "tag"]
    pools_e, pools_t = await asyncio.gather(
        asyncio.gather(*(_neighbours(q, c, aud) for c in ents)), _tag_ideas(q, tags))
    pools = {c["id"]: p for c, p in zip(ents, pools_e)} | pools_t

    every = [cand["id"] for pool in pools.values() for cand in pool]
    profiles = await q.demographics(every) if every else {}
    shortlists: dict[str, list[dict]] = {}
    for c in chosen:
        better = []
        for cand in pools.get(c["id"], []):
            cand["profile"] = profiles.get(cand["id"])
            cand["fit"] = fitting.score(cand["profile"], aud)
            if cand["fit"] is not None and cand["fit"] >= c["fit"] + MARGIN:
                better.append(cand)
        better.sort(key=lambda x: -x["fit"])
        shortlists[c["id"]] = better[:10]

    items = []
    for c in chosen:
        if shortlists[c["id"]]:
            items.append(json.dumps({
                "cue": c["id"], "label": c["label"], "kind": c["kind"], "why": c["why"],
                "its_fit": c["fit"],
                "candidates": [{"index": i, "name": x["name"], "fit": x["fit"]}
                               for i, x in enumerate(shortlists[c["id"]])]},
                ensure_ascii=False))
    if not items:
        return {c["id"]: [] for c in chosen}
    answer = await complete(PICK.format(audience=fitting.describe(aud), keep=KEEP,
                                        items="\n".join(items)), schema=PICK_SCHEMA)
    out: dict[str, list] = {c["id"]: [] for c in chosen}
    for pick in answer.get("picks") or []:
        if pick["cue"] not in out:
            continue
        short = shortlists[pick["cue"]]
        for ch in pick.get("chosen") or []:
            if 0 <= ch["index"] < len(short) and len(out[pick["cue"]]) < KEEP:
                out[pick["cue"]].append({**short[ch["index"]], "how": ch["how"]})
    for k in out:
        out[k].sort(key=lambda x: -x["fit"])
    return out
