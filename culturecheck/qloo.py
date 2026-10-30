"""Qloo's API: `/search` (a name to entities), `/v2/tags` (a keyword to tags) and
`/v2/insights` (entities ranked by affinity to signals).

Every request is a GET with the key in `X-Api-Key`, on the hackathon host only.
Responses are cached on disk by request, privately (Qloo allows private
caching and forbids publishing responses; `data/` is gitignored), so a report
re-rendered or a sample re-run costs no call.

Insights quietly ignores a parameter the `filter.type` does not support and
answers 200 with nothing, so `insights()` refuses any parameter not in
`SUPPORTED` for that type rather than sending it.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from typing import Any, Optional

import httpx

from .config import settings

log = logging.getLogger("culturecheck.qloo")

AGES = ["24_and_younger", "25_to_29", "30_to_34", "35_to_44", "45_to_54", "55_and_older"]
GENDERS = ["male", "female"]

ENTITY = "urn:entity:"

#: Parameters each output type takes beyond the ones every type does, from
#: Qloo's "available parameters by entity type".
_EVERY = {"filter.type", "bias.trends", "filter.exclude.entities", "filter.exclude.tags",
          "operator.exclude.tags", "filter.external.exists",
          "operator.filter.external.exists", "filter.parents.types",
          "filter.popularity.min", "filter.popularity.max", "filter.results.entities",
          "filter.results.entities.query", "filter.tags", "operator.filter.tags",
          "offset", "signal.demographics.age", "signal.demographics.audiences",
          "signal.demographics.audiences.weight", "signal.demographics.gender",
          "signal.interests.entities", "signal.interests.tags", "take",
          "feature.explainability", "page", "signal.location", "signal.location.query",
          "operator.signal.interests.tags"}
_PLACE = {"bias.quality", "filter.address", "filter.geocode.name",
          "filter.geocode.admin1_region", "filter.geocode.admin2_region",
          "filter.geocode.country_code", "filter.hotel_class.min", "filter.hotel_class.max",
          "filter.hours", "filter.location", "filter.location.query",
          "filter.location.radius", "filter.location.geohash", "filter.price_level.min",
          "filter.price_level.max", "sort_by"}
_SCREEN = {"filter.content_rating", "filter.release_year.min", "filter.release_year.max",
           "filter.release_country", "filter.rating.min", "filter.rating.max"}
SUPPORTED: dict[str, set[str]] = {
    "artist": _EVERY, "brand": _EVERY, "podcast": _EVERY,
    "book": _EVERY | {"filter.publication_year.min", "filter.publication_year.max"},
    "person": _EVERY | {"filter.gender"},
    "movie": _EVERY | _SCREEN,
    "tv_show": _EVERY | _SCREEN | {"filter.finale_year.min", "filter.finale_year.max"},
    "place": _EVERY | _PLACE,
    "destination": _EVERY | {"filter.geocode.name", "filter.geocode.country_code",
                             "filter.location", "filter.location.query"},
}


class QlooError(RuntimeError):
    pass


class Qloo:
    def __init__(self, key: Optional[str] = None, base: Optional[str] = None,
                 cache: bool = True):
        s = settings()
        self.key = key if key is not None else s.qloo_key
        self.base = (base or s.qloo_base).rstrip("/")
        self.cache_dir = s.qloo_cache if cache else None
        self._client: Optional[httpx.AsyncClient] = None
        self._gate = asyncio.Semaphore(8)
        self.calls = 0                       # requests actually sent (not cached)

    async def __aenter__(self) -> "Qloo":
        if not self.key:
            raise QlooError("no QLOO_API_KEY: the hackathon key, from "
                            "docs.qloo.com's hackathon developer guide")
        self._client = httpx.AsyncClient(base_url=self.base, timeout=30,
                                         headers={"X-Api-Key": self.key})
        return self

    async def __aexit__(self, *exc: Any) -> None:
        if self._client is not None:
            await self._client.aclose()

    async def get(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        flat = {k: _flat(v) for k, v in params.items() if v not in (None, "", [])}
        key = hashlib.sha256(json.dumps([path, sorted(flat.items())]).encode()).hexdigest()
        cached = self.cache_dir / f"{key[:2]}/{key}.json" if self.cache_dir else None
        if cached is not None and cached.exists():
            return json.loads(cached.read_text(encoding="utf-8"))
        assert self._client is not None, "use `async with Qloo() as q:`"
        async with self._gate:
            for attempt in range(3):
                try:
                    r = await self._client.get(path, params=flat)
                except httpx.TransportError:
                    if attempt == 2:
                        raise
                    await asyncio.sleep(1 + attempt)
                    continue
                if r.status_code == 429 or r.status_code >= 500:
                    if attempt < 2:
                        await asyncio.sleep(2 * (attempt + 1))
                        continue
                break
        self.calls += 1
        if r.status_code != 200:
            raise QlooError(f"{path} {r.status_code}: {r.text[:300]}")
        data = r.json()
        if cached is not None:
            cached.parent.mkdir(parents=True, exist_ok=True)
            cached.write_text(json.dumps(data), encoding="utf-8")
        return data

    async def search(self, query: str, types: Optional[list[str]] = None,
                     take: int = 5) -> list[dict[str, Any]]:
        """Entities whose name matches, best first."""
        data = await self.get("/search", {"query": query, "take": take,
                                          "types": [_urn(t) for t in types or []]})
        return _entities(data)

    async def tags(self, query: str, take: int = 8,
                   parent: Optional[str] = None) -> list[dict[str, Any]]:
        """Tags matching a keyword: [{id, name, type, parents}], only those
        describing `parent` (an entity type) when one is given."""
        data = await self.get("/v2/tags", {"filter.query": query, "take": take,
                                           "filter.parents.types": _urn(parent) if parent
                                           else None})
        return _tags(data)

    async def insights(self, kind: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        """Entities of `kind` (`artist`, `place`, ...) ranked for the signals in
        `params`, keyed by Qloo's own dotted names."""
        unknown = set(params) - SUPPORTED[kind]
        if unknown:
            raise QlooError(f"{', '.join(sorted(unknown))}: not taken by "
                            f"urn:entity:{kind}, and Qloo would ignore it silently")
        data = await self.get("/v2/insights", {**params, "filter.type": _urn(kind)})
        return _entities(data)

    async def demographics(self, ids: list[str]) -> dict[str, dict[str, Any]]:
        """Who likes each entity or tag: {id: {"age": {group: -1..1},
        "gender": {male, female}}}. Entities and tags go in one call, and an
        id Qloo holds no audience for is simply absent."""
        entities = sorted({i for i in ids if i and not i.startswith("urn:tag:")})
        tags = sorted({i for i in ids if i.startswith("urn:tag:")})
        out: dict[str, dict[str, Any]] = {}
        for start in range(0, max(len(entities), len(tags)), 40):
            part_e, part_t = entities[start:start + 40], tags[start:start + 40]
            data = await self.get("/v2/insights", {
                "filter.type": "urn:demographics",
                "signal.interests.entities": part_e, "signal.interests.tags": part_t})
            for row in (data.get("results") or {}).get("demographics") or []:
                q = row.get("query") or {}
                if q.get("age"):
                    out[row["entity_id"]] = {"age": q["age"], "gender": q.get("gender") or {}}
        return out


def _urn(kind: str) -> str:
    return kind if kind.startswith("urn:") else ENTITY + kind


def _flat(value: Any) -> Any:
    if isinstance(value, (list, tuple, set)):
        return ",".join(str(v) for v in value)
    if isinstance(value, bool):
        return "true" if value else "false"
    return value


def _entities(data: dict[str, Any]) -> list[dict[str, Any]]:
    results = data.get("results", data)
    if isinstance(results, dict):
        results = results.get("entities", [])
    return list(results or [])


def _tags(data: dict[str, Any]) -> list[dict[str, Any]]:
    results = data.get("results", data)
    if isinstance(results, dict):
        results = results.get("tags", results.get("entities", []))
    out = []
    for t in results or []:
        out.append({"id": t.get("id") or t.get("tag_id") or t.get("entity_id"),
                    "name": t.get("name"), "type": t.get("type") or t.get("subtype"),
                    "parents": [p.get("type") for p in t.get("parents") or []],
                    "raw": t})
    return out


def entity_id(e: dict[str, Any]) -> str:
    return e.get("entity_id") or e.get("id") or ""


def affinity(e: dict[str, Any]) -> Optional[float]:
    q = e.get("query") or {}
    value = q.get("affinity") if isinstance(q, dict) else None
    return float(value) if isinstance(value, (int, float)) else None
