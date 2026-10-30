"""What Qloo's hackathon API actually returns, before anything is built on it.

    python scripts/spike.py

1. /search: what an entity carries (fields, tags, popularity).
2. /v2/tags: the query parameter and the shape.
3. The scoring call: `filter.results.entities` + one age group at a time.
   Does each entity get an affinity, and does it change between age groups?
4. Explainability, with interests as the signal.
5. A place query with a location and a tag.

Prints shapes and numbers; writes the raw responses to data/spike/ (gitignored).
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from culturecheck.config import settings  # noqa: E402
from culturecheck.qloo import AGES, Qloo, QlooError, affinity, entity_id  # noqa: E402

OUT = settings().data / "spike"


def save(name: str, data) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"{name}.json").write_text(json.dumps(data, indent=1), encoding="utf-8")


def shape(e: dict, depth: int = 0) -> str:
    keys = []
    for k, v in e.items():
        if isinstance(v, dict) and depth < 1:
            keys.append(f"{k}{{{shape(v, depth + 1)}}}")
        elif isinstance(v, list):
            keys.append(f"{k}[{len(v)}]")
        else:
            keys.append(k)
    return ", ".join(keys)


async def main() -> None:
    async with Qloo(cache=False) as q:
        print("== 1. /search")
        found = {}
        for name, kind in [("Taylor Swift", "artist"), ("Frank Sinatra", "artist"),
                           ("Bad Bunny", "artist"), ("Nike", "brand"),
                           ("Pulp Fiction", "movie")]:
            try:
                hits = await q.search(name, [kind], take=3)
            except QlooError as exc:
                print(f"  {name}: {exc}")
                continue
            save(f"search-{name}", hits)
            if hits:
                top = hits[0]
                found[name] = top
                print(f"  {name!r} -> {top.get('name')!r} {entity_id(top)} "
                      f"popularity={top.get('popularity')}")
            else:
                print(f"  {name!r} -> nothing")
        if found:
            first = next(iter(found.values()))
            print("  entity fields:", shape(first))
            tags = first.get("tags") or (first.get("properties") or {}).get("tags") or []
            print("  tags sample:", json.dumps(tags[:3])[:400])

        print("\n== 2. /v2/tags")
        for params in ({"filter.query": "diner"}, {"query": "diner"},
                       {"filter.query": "streetwear"}):
            try:
                data = await q.get("/v2/tags", {**params, "take": 5})
                save(f"tags-{'-'.join(params.values())}", data)
                print(f"  {params} -> top-level {list(data)[:5]}; "
                      f"{json.dumps(data)[:300]}")
            except QlooError as exc:
                print(f"  {params}: {exc}")

        artists = [entity_id(found[n]) for n in ("Taylor Swift", "Frank Sinatra", "Bad Bunny")
                   if n in found]
        if artists:
            print("\n== 3. scoring: filter.results.entities x age")
            names = {entity_id(found[n]): n for n in found}
            table, sample = {}, None
            for age in AGES:
                try:
                    got = await q.insights("artist", {"filter.results.entities": artists,
                                                      "signal.demographics.age": age,
                                                      "take": len(artists)})
                except QlooError as exc:
                    print(f"  {age}: {exc}")
                    continue
                save(f"score-{age}", got)
                sample = sample or (got[0] if got else None)
                table[age] = {names.get(entity_id(e), e.get("name")): affinity(e)
                              for e in got}
                print(f"  {age:15} " + "  ".join(f"{k}={v}" for k, v in table[age].items()))
            if sample:
                print("  a scored result:", shape(sample))
                print("  its query:", json.dumps(sample.get("query"))[:300])

            print("\n== 4. explainability: artists like Frank Sinatra, for 55+")
            try:
                got = await q.insights("artist", {
                    "signal.interests.entities": [entity_id(found["Frank Sinatra"])],
                    "signal.demographics.age": "55_and_older",
                    "feature.explainability": True, "take": 5})
                save("explain", got)
                for e in got:
                    print(f"  {e.get('name')}: affinity={affinity(e)} "
                          f"explain={json.dumps((e.get('query') or {}).get('explainability'))[:160]}")
            except (QlooError, KeyError) as exc:
                print(f"  {exc}")

        print("\n== 5. places in Austin, tag from /v2/tags 'diner'")
        try:
            tags = await q.tags("diner", take=3)
            print("  tags:", [(t["id"], t["name"], t["type"]) for t in tags])
            if tags:
                got = await q.insights("place", {"filter.location.query": "Austin",
                                                 "filter.tags": [tags[0]["id"]],
                                                 "signal.demographics.age": "25_to_29",
                                                 "take": 5})
                save("places", got)
                for e in got:
                    print(f"  {e.get('name')}: affinity={affinity(e)}")
        except QlooError as exc:
            print(f"  {exc}")
        print(f"\n{q.calls} calls; raw responses in {OUT}")


if __name__ == "__main__":
    asyncio.run(main())
