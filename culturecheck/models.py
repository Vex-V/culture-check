"""Which models answer, built once from the settings, and the one call the app
makes to an LLM itself. Describing frames always goes through the library."""

from __future__ import annotations

import logging
import time
from functools import lru_cache
from typing import Any, Optional

from .config import settings

log = logging.getLogger("culturecheck.models")


@lru_cache(maxsize=1)
def models():
    from vidra import Models, OpenAI, OpenAIEmbedder

    s = settings()
    vlm = OpenAI(s.vlm) if s.vlm else OpenAI()
    llm = OpenAI(s.llm) if s.llm else OpenAI()
    return Models(vlm=vlm, llm=llm, embedder=OpenAIEmbedder())


async def complete(prompt: str, schema: Optional[dict[str, Any]] = None,
                   system: Optional[str] = None, max_output_tokens: int = 8000) -> Any:
    """One LLM call, through the library's wrapper: a concurrency cap, JSON
    parsed for a schema, and any failure raised as `ModelFailed`."""
    from vidra.shared.models.base import calls

    llm = calls("llm", models().llm)
    t0 = time.perf_counter()
    answer = await llm.complete(prompt, schema=schema, system=system,
                                max_output_tokens=max_output_tokens)
    log.info("llm %s: %.1fs", (schema or {}).get("name", "text"), time.perf_counter() - t0)
    return answer


def strict(name: str, properties: dict[str, Any]) -> dict[str, Any]:
    """A strict JSON schema: every property required, nothing else allowed."""
    return {"name": name, "schema": {"type": "object", "properties": properties,
                                     "required": list(properties),
                                     "additionalProperties": False}}


def obj(properties: dict[str, Any]) -> dict[str, Any]:
    """A nested strict object, for use inside `strict`."""
    return {"type": "object", "properties": properties,
            "required": list(properties), "additionalProperties": False}


STR = {"type": "string"}
INT = {"type": "integer"}
NUM = {"type": "number"}


def arr(items: dict[str, Any]) -> dict[str, Any]:
    return {"type": "array", "items": items}
