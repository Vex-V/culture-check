"""Every shot's answer and what was said, merged into one list of cultural cues.

A cue is one thing that signals taste -- a brand, a setting, a style, a song --
with the shots it appears in, where it came from (seen, said, or given by the
user) and how Qloo should be asked about it:

    entity      a named thing: `/search` with `qloo_type` (an artist, a brand,
                a place, a film, ...)
    tag         a kind of thing: `/v2/tags` with `lookup` (a cuisine, a style,
                a genre, a kind of place)

One model call merges duplicates across shots ("the Nike swoosh" in shot 2 and
"Nike trainers" in shot 5 are one cue) and decides the route. The model never
invents a name: a cue is only `entity` when the shot named it.
"""

from __future__ import annotations

import json
from typing import Any, Optional

from .models import INT, STR, arr, complete, obj, strict

KINDS = ["music", "brand", "place", "setting", "wardrobe", "food_drink", "activity",
         "reference", "aesthetic"]

#: What Qloo can return, and so what an entity cue may be. (`video_game` is
#: listed by Qloo and refused for hackathon keys.)
ENTITY_TYPES = ["artist", "brand", "place", "destination", "movie", "tv_show", "book",
                "person", "podcast"]

SYSTEM = (
    "You turn a frame-by-frame reading of a video into the list of cultural cues "
    "a brand strategist would assess: what in it signals taste, and so who it "
    "speaks to. You never add a cue the reading does not support, and never "
    "invent or guess a name.")

PROMPT = """The video, shot by shot (seen: what the frames show; said: the soundtrack's words):

{shots}
{given}
Merge this into cultural cues.
- One cue per distinct thing; merge the same thing across shots and list every shot it is in.
- kind: one of {kinds}.
- route "entity" only for a specific named thing the reading names (a brand, a named place,
  an artist, a film, a person named on screen); qloo_type is then one of {types}, and
  lookup is its name as Qloo would know it ("Nike", "Times Square", "Taylor Swift").
- route "tag" for a kind of thing: a setting, a style, a cuisine, a genre, an activity,
  an aesthetic. qloo_type is then the entity type the tag describes best ("place" for a
  diner or a cuisine, "brand" for a fashion style, "artist" for a music genre, "movie"
  for a film genre), and lookup is a short tag keyword ("diner", "streetwear",
  "synth-pop", "skateboarding"). `also`: 2-3 other keywords Qloo might file the same
  thing under (streetwear: "street style", "urban fashion", "sneaker culture"); empty
  for an entity.
- source: "seen", "said" or "given" (given: supplied by the user, below).
- label: how the report should name it ("1950s chrome diner", "Nike trainers").
- why: one short line on what it signals.
- weight: 3 when it is central to the video (on screen long, or the product, or the
  soundtrack), 2 when clearly noticeable, 1 when incidental.
Leave out generic things with no taste signal (a table, a street, a phone), and the
advertised brand's own product only if it carries no style of its own. Never make a cue of
a colour, a camera or editing technique, or production polish ("red looks", "glossy ad
look", "fast cuts"): an aesthetic or wardrobe cue must name a recognisable style, era or
subculture ("Y2K", "mid-century modern", "streetwear", "cottagecore").
Also write `cast`: who appears, by age range and look, across the video (one line), and
`read`: two sentences on the video's overall cultural register, before any audience data."""

SCHEMA = strict("cues", {
    "cues": arr(obj({
        "kind": {"type": "string", "enum": KINDS},
        "label": STR,
        "route": {"type": "string", "enum": ["entity", "tag"]},
        "qloo_type": {"type": "string", "enum": ENTITY_TYPES},
        "lookup": STR,
        "also": arr(STR),
        "source": {"type": "string", "enum": ["seen", "said", "given"]},
        "shots": arr(INT),
        "weight": {"type": "integer", "enum": [1, 2, 3]},
        "why": STR,
    })),
    "cast": STR,
    "read": STR,
})


def _compact(shots: list[dict[str, Any]]) -> str:
    """The shots as short JSON lines: empty fields dropped, times kept."""
    lines = []
    for s in shots:
        seen = {k: v for k, v in (s.get("seen") or {}).items() if v not in ("", [], None)}
        entry = {"shot": s["shot"], "t": f"{s['start']:.1f}-{s['end']:.1f}s", "seen": seen}
        if s.get("said"):
            entry["said"] = s["said"]
        lines.append(json.dumps(entry, ensure_ascii=False))
    return "\n".join(lines)


async def merge(shots: list[dict[str, Any]], music: Optional[str] = None,
                cast: Optional[str] = None) -> dict[str, Any]:
    """{"cues": [...], "cast": str, "read": str}; each cue gets an `id`.

    `music` and `cast` are what the user says is in the video: the soundtrack, and
    who appears (the frames are never asked to name a person from their face)."""
    given = ""
    if music:
        given += (f"\nGiven by the user -- the soundtrack: {music}. Make it a music cue in "
                  "every shot, route entity, qloo_type artist, lookup the artist's name "
                  "(work it out from the track if only a track is given).\n")
    if cast:
        given += (f"\nGiven by the user -- who appears: {cast}. Make each named person a cue, "
                  "kind reference, source given, route entity, qloo_type artist for a "
                  "musician and person for anyone else, lookup their name, weight 3, in the "
                  "shots where the reading shows someone who could be them (every shot with "
                  "a featured person, when it cannot tell).\n")
    answer = await complete(PROMPT.format(shots=_compact(shots), given=given,
                                          kinds=", ".join(KINDS),
                                          types=", ".join(ENTITY_TYPES)),
                            schema=SCHEMA, system=SYSTEM)
    known = {s["shot"] for s in shots}
    cues = []
    for i, cue in enumerate(answer.get("cues") or []):
        cue["shots"] = sorted({s for s in cue.get("shots") or [] if s in known})
        cue["id"] = f"c{i}"
        cues.append(cue)
    return {"cues": cues, "cast": answer.get("cast", ""), "read": answer.get("read", "")}
