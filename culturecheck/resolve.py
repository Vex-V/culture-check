"""Cues to Qloo: each cue's candidates from `/search` (a named thing) or
`/v2/tags` (a kind of thing), then one model call picks the candidate that is
the cue, or none.

A name alone is ambiguous ("Apple", "Sailor Jerry", "Pulp"), so the choice is
made with the cue's label and why, and every pick is shown on the page, where
the user can change it. A cue with no fitting candidate stays unresolved and
is reported as such rather than scored on a guess.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

from .models import INT, STR, arr, complete, obj, strict
from .qloo import Qloo, QlooError, entity_id

PROMPT = """Match each cultural cue from a video to the Qloo entry that IS that thing.

{items}

For each cue, give the index of the matching candidate, or -1 when none of them is
the thing the cue means (a different company with the same name, a film when the
cue is a band, a tag broader or unrelated). A named brand never matches a dish, a menu
item or a kind of place. For a tag, the closest tag that still means the same thing
counts ("1950s diner" -> "Diner"), and so does the nearest tag for the same kind of
thing ("beer and alcohol coolers" -> "Beer"). Never pick a tag that is only a colour, or a
word so broad it says nothing about taste ("Fashion", "Art", "Lifestyle", "Visual",
"Studio", "Modeling", "Pop Culture", "Celebration", "Shopping"): give -1 instead. Candidates marked `"audience": true` carry
Qloo audience data: among candidates that mean the thing equally well, choose one of those."""

SCHEMA = strict("matches", {"matches": arr(obj({"cue": STR, "pick": INT, "note": STR}))})

#: The most tag candidates kept per cue.
TAG_OPTIONS = 10
#: Tags never offered: a colour says nothing about who a thing is for, and Qloo's
#: colour tags carry strong, meaningless profiles.
COLOURS = {"red", "blue", "green", "yellow", "orange", "pink", "purple", "black", "white",
           "grey", "gray", "brown", "gold", "silver", "beige", "teal", "neon"}


def _brief(e: dict[str, Any]) -> dict[str, Any]:
    props = e.get("properties") or {}
    return {"name": e.get("name"), "type": e.get("subtype") or e.get("type"),
            "about": (props.get("short_description") or props.get("description")
                      or "")[:140],
            "popularity": e.get("popularity")}


async def _tag_options(q: Qloo, cue: dict[str, Any]) -> list[dict[str, Any]]:
    """Tags for the cue's keyword and its synonyms, those describing the cue's
    own entity type first."""
    words = [cue["lookup"], *(cue.get("also") or [])][:3]
    asks = [q.tags(w, take=6, parent=cue["qloo_type"]) for w in words]
    asks.append(q.tags(cue["lookup"], take=6))
    found = await asyncio.gather(*asks)
    seen, out = set(), []
    for tags in found:
        for t in tags:
            if (t["name"] or "").strip().lower() in COLOURS:
                continue
            if t["id"] and t["id"] not in seen:
                seen.add(t["id"])
                out.append({"kind": "tag", "id": t["id"], "name": t["name"], "type": t["type"],
                            "brief": {"name": t["name"], "type": t["type"],
                                      "describes": t["parents"]},
                            "raw": t["raw"]})
    return out[:TAG_OPTIONS]


async def _candidates(q: Qloo, cue: dict[str, Any]) -> list[dict[str, Any]]:
    try:
        if cue["route"] == "entity":
            hits = await q.search(cue["lookup"], [cue["qloo_type"]], take=5)
            if hits:
                return [{"kind": "entity", "id": entity_id(e), "name": e.get("name"),
                         "type": cue["qloo_type"], "brief": _brief(e), "raw": e}
                        for e in hits if entity_id(e)]
        return await _tag_options(q, cue)
    except QlooError as exc:
        cue["problem"] = str(exc)
        return []


async def resolve(q: Qloo, cues: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Sets `qloo` on each cue ({kind, id, name, type}) or None, and keeps the
    candidates (`options`) so the page can offer the others."""
    found = await asyncio.gather(*(_candidates(q, c) for c in cues))
    # A tag with no audience cannot be scored, so it is not offered: the cue
    # stays unresolved and the page says Qloo holds no audience for it.
    every = [o["id"] for options in found for o in options]
    known = await q.demographics(every) if every else {}
    found = [[o for o in options if o["kind"] == "entity" or o["id"] in known]
             for options in found]
    for options in found:
        for o in options:
            o["brief"]["audience"] = o["id"] in known
    items = []
    for cue, options in zip(cues, found):
        cue["options"] = [{k: o[k] for k in ("kind", "id", "name", "type")} for o in options]
        if options:
            items.append(json.dumps({"cue": cue["id"], "label": cue["label"],
                                     "kind": cue["kind"], "why": cue["why"],
                                     "candidates": [o["brief"] for o in options]},
                                    ensure_ascii=False))
    picks: dict[str, int] = {}
    if items:
        answer = await complete(PROMPT.format(items="\n".join(items)), schema=SCHEMA)
        picks = {m["cue"]: m["pick"] for m in answer.get("matches") or []}
    for cue, options in zip(cues, found):
        i = picks.get(cue["id"], -1)
        cue["qloo"] = cue["options"][i] if 0 <= i < len(options) else None
        if options and 0 <= i < len(options) and options[i]["kind"] == "entity":
            cue["entity"] = options[i]["raw"]     # its tags seed the swaps
    return cues
