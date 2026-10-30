"""Follow-up questions about a report, answered by a model that can ask Qloo.

The model sees the report (cues, fits, swaps, brief) and has five tools, so it
answers "what about Olivia Rodrigo instead?" or "what if it were for men over
45?" with a measurement, not a guess:

    check_fit    any named thing, or a kind of thing, scored for the audience
    explore      what the audience likes in a category, optionally of a style
    what_if      every cue re-scored for another audience (no network: the
                 profiles are already held)
    find_moment  where in the video something happens (vidra's search)
    cue_detail   everything held about one cue

Every tool call is returned with the answer, so the page can show what was
asked of Qloo.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from . import fit as fitting
from .config import settings
from .qloo import AGES, GENDERS, Qloo, QlooError, affinity, entity_id

log = logging.getLogger("culturecheck.agent")

KINDS = ["artist", "brand", "place", "destination", "movie", "tv_show", "book", "person",
         "podcast", "tag"]
ROUNDS = 6

SYSTEM = """You are Culture Check's analyst. A video has been read shot by shot, its cultural
cues found, and each scored against a target audience with Qloo's taste graph (fit -1..1:
how much that audience over- or under-indexes on the thing). The video's overall appeal to
each age group was judged from that evidence plus what cues cannot carry (tone, humour,
story). Answer the user's follow-up questions about it.

Rules:
- Any claim about who likes something must come from Qloo: the report below, or a tool call.
  Use the tools rather than your own taste. If Qloo has no data, say so.
- Be brief and concrete: a few sentences or a short list, with the numbers.
- Refer to shots by number and time, and to cues by their label, never by their id.
- The appeal figures are a model's judgement for an age group: say so, and do not credit
  them to Qloo. A Qloo fit is a measurement.

The report:
{report}"""

TOOLS = [
    {"type": "function", "name": "check_fit", "strict": True,
     "description": "Score one named thing (or, with kind 'tag', a kind of thing such as "
                    "'synthwave' or 'food truck') for the current audience with Qloo.",
     "parameters": {"type": "object", "additionalProperties": False,
                    "required": ["name", "kind"],
                    "properties": {"name": {"type": "string"},
                                   "kind": {"type": "string", "enum": KINDS}}}},
    {"type": "function", "name": "explore", "strict": True,
     "description": "What the current audience likes most in a category, optionally kept to "
                    "a style or genre keyword ('' for none). Ranked by Qloo affinity.",
     "parameters": {"type": "object", "additionalProperties": False,
                    "required": ["kind", "keyword"],
                    "properties": {"kind": {"type": "string", "enum": KINDS[:-1]},
                                   "keyword": {"type": "string"}}}},
    {"type": "function", "name": "what_if", "strict": True,
     "description": "Re-score every cue of the video for a different audience.",
     "parameters": {"type": "object", "additionalProperties": False,
                    "required": ["age", "gender"],
                    "properties": {"age": {"type": "string", "enum": AGES},
                                   "gender": {"type": "string", "enum": [*GENDERS, "any"]}}}},
    {"type": "function", "name": "find_moment", "strict": True,
     "description": "Find the shots of the video where something is seen or said.",
     "parameters": {"type": "object", "additionalProperties": False, "required": ["query"],
                    "properties": {"query": {"type": "string"}}}},
    {"type": "function", "name": "cue_detail", "strict": True,
     "description": "Everything held about one cue: its Qloo match, audience profile by age "
                    "and gender, and swaps.",
     "parameters": {"type": "object", "additionalProperties": False, "required": ["cue_id"],
                    "properties": {"cue_id": {"type": "string"}}}},
]


def _context(report: dict[str, Any], view: dict[str, Any]) -> str:
    cues = []
    for c in view["cues"]:
        cues.append({"id": c["id"], "label": c["label"], "kind": c["kind"],
                     "shots": c["shots"], "qloo": c["qloo"]["name"] if c.get("qloo") else None,
                     "fit": c.get("fit"),
                     "peak": fitting.AGE_LABELS[fitting.best_age(c["profile"])]
                     if c.get("profile") else None})
    shots = [{"shot": s["shot"], "t": f"{s['start']:.1f}-{s['end']:.1f}s",
              "summary": (s.get("seen") or {}).get("summary", "")[:200]} for s in report["shots"]]
    return json.dumps({
        "audience": view["label"], "cue_average": view["overall"],
        "appeal_by_age": {fitting.AGE_LABELS[a]: g["appeal"]
                          for a, g in (report.get("appeal") or {}).get("by_age", {}).items()},
        "appeal_here": view.get("appeal"), "read": report["read"],
        "cast": report["cast"], "shots": shots, "cues": cues,
        "swaps": {k: [f"{s['name']} ({s['fit']})" for s in v] for k, v in view["swaps"].items()},
        "brief": {"headline": view["brief"]["headline"], "summary": view["brief"]["summary"]},
    }, ensure_ascii=False)


def _profile_line(p: dict[str, Any]) -> dict[str, Any]:
    return {"by_age": {fitting.AGE_LABELS[a]: round(v, 2) for a, v in p["age"].items()},
            "gender": {g: round(v, 2) for g, v in (p.get("gender") or {}).items()}}


class Tools:
    def __init__(self, q: Qloo, report: dict[str, Any], view: dict[str, Any]):
        self.q, self.report, self.view = q, report, view
        self.aud = view["audience"]

    async def check_fit(self, name: str, kind: str) -> dict[str, Any]:
        if kind == "tag":
            found = await self.q.tags(name, take=8)
            ids = [t["id"] for t in found if t["id"]]
            prof = await self.q.demographics(ids) if ids else {}
            hit = next((t for t in found if t["id"] in prof), None)
            if not hit:
                return {"found": False, "note": f"Qloo holds no audience for {name!r}"}
            matched, pid = hit["name"], hit["id"]
        else:
            hits = await self.q.search(name, [kind], take=3)
            if not hits:
                return {"found": False, "note": f"no {kind} called {name!r} in Qloo"}
            matched, pid = hits[0].get("name"), entity_id(hits[0])
            prof = await self.q.demographics([pid])
        p = prof.get(pid)
        if not p:
            return {"found": True, "matched": matched, "note": "no audience data in Qloo"}
        score = fitting.score(p, self.aud)
        return {"found": True, "matched": matched, "fit": score,
                "verdict": fitting.verdict(score),
                "peak": fitting.AGE_LABELS[fitting.best_age(p)], **_profile_line(p)}

    async def explore(self, kind: str, keyword: str) -> dict[str, Any]:
        params: dict[str, Any] = {"signal.demographics.age": self.aud["age"], "take": 8}
        if self.aud.get("gender"):
            params["signal.demographics.gender"] = self.aud["gender"]
        if self.aud.get("location"):
            params["filter.location.query" if kind == "place"
                   else "signal.location.query"] = self.aud["location"]
        within = None
        if keyword.strip():
            tags = await self.q.tags(keyword, take=3, parent=kind)
            if tags:
                within = tags[0]["name"]
                params["filter.tags"] = [tags[0]["id"]]
        got = await self.q.insights(kind, params)
        return {"within": within, "for": fitting.describe(self.aud),
                "results": [{"name": e.get("name"), "affinity": round(affinity(e) or 0, 3)}
                            for e in got]}

    async def what_if(self, age: str, gender: str) -> dict[str, Any]:
        aud = fitting.audience(age, None if gender == "any" else gender)
        cues = [dict(c) for c in self.view["cues"]]
        overall = fitting.rate(cues, aud)
        judged = (self.report.get("appeal") or {}).get("by_age", {}).get(age)
        return {"audience": fitting.describe(aud), "overall": overall,
                "appeal": judged,
                "cues": [{"label": c["label"], "fit": c["fit"]} for c in cues
                         if c["fit"] is not None]}

    async def find_moment(self, query: str) -> dict[str, Any]:
        from vidra.shared.storage.folder import Folder
        from vidra.video_rag import search

        from .models import models

        moments, _ = await asyncio.to_thread(
            search, query, video_id=self.report["id"], moments=3,
            database=Folder(settings().out), models=models())
        shots = {s["shot"]: s for s in self.report["shots"]}
        return {"moments": [{"shot": m.chunk_id, "start": round(m.start_ts, 1),
                             "end": round(m.end_ts, 1),
                             "summary": ((shots.get(m.chunk_id) or {}).get("seen") or {})
                             .get("summary", "")[:240]} for m in moments]}

    async def cue_detail(self, cue_id: str) -> dict[str, Any]:
        cue = next((c for c in self.view["cues"] if c["id"] == cue_id), None)
        if cue is None:
            return {"error": f"no cue {cue_id}"}
        return {"label": cue["label"], "why": cue["why"], "shots": cue["shots"],
                "qloo": cue.get("qloo"), "fit": cue.get("fit"), "local": cue.get("local"),
                "profile": _profile_line(cue["profile"]) if cue.get("profile") else None,
                "swaps": [{"name": s["name"], "fit": s["fit"], "how": s.get("how")}
                          for s in self.view["swaps"].get(cue_id, [])]}


def _summary(name: str, args: dict[str, Any], result: dict[str, Any]) -> str:
    """One line for the page: what was asked, and the headline of the answer."""
    if name == "check_fit":
        if result.get("fit") is None:
            return f"Qloo: {args['name']} - {result.get('note', 'no data')}"
        return f"Qloo: {result['matched']} - fit {result['fit']:+.2f}, peaks {result['peak']}"
    if name == "explore":
        top = ", ".join(r["name"] for r in result.get("results", [])[:3])
        within = f" ({result['within']})" if result.get("within") else ""
        return f"Qloo: top {args['kind']}{within} for {result.get('for')}: {top}"
    if name == "what_if":
        judged = (result.get("appeal") or {}).get("appeal")
        return (f"Re-scored for {result['audience']}: appeal {judged}, "
                f"cue average {result['overall']['fit']}")
    if name == "find_moment":
        return "Searched the video: shots " + ", ".join(
            str(m["shot"]) for m in result.get("moments", []))
    return f"Looked up {args.get('cue_id')}"


async def chat(report: dict[str, Any], view: dict[str, Any],
               messages: list[dict[str, str]]) -> dict[str, Any]:
    """{"text": the answer, "steps": [{tool, args, summary}]}"""
    from openai import AsyncOpenAI

    client = AsyncOpenAI()
    model = settings().llm or "gpt-5.4-mini"
    convo: list[Any] = [{"role": m["role"], "content": m["content"]}
                        for m in messages[-12:] if m.get("role") in ("user", "assistant")]
    steps: list[dict[str, Any]] = []
    async with Qloo() as q:
        tools = Tools(q, report, view)
        for _ in range(ROUNDS):
            r = await client.responses.create(
                model=model, instructions=SYSTEM.format(report=_context(report, view)),
                input=convo, tools=TOOLS, max_output_tokens=4000)
            called = [o for o in r.output if o.type == "function_call"]
            if not called:
                return {"text": r.output_text, "steps": steps}
            convo.extend(r.output)
            for call in called:
                args = json.loads(call.arguments or "{}")
                try:
                    result = await getattr(tools, call.name)(**args)
                except (QlooError, ValueError, KeyError) as exc:
                    result = {"error": str(exc)[:300]}
                if "error" not in result:
                    steps.append({"tool": call.name, "args": args,
                                  "summary": _summary(call.name, args, result)})
                convo.append({"type": "function_call_output", "call_id": call.call_id,
                              "output": json.dumps(result, ensure_ascii=False)})
    return {"text": "I could not finish that within the steps I'm allowed; try a narrower "
                    "question.", "steps": steps}
