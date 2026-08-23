"""The Respite agent.

An LLM loop over the tools in :mod:`respite.tools`. Two design choices are worth
stating, because they are the difference between an agent and a chat box wrapped
round a dataset.

**The limits are a tool, not a prompt.** Most of the work behind this project
went into establishing what the data does not support: land cover does not
predict exposure once position is controlled for, the metric is censored at the
window length, and exposure is uncorrelated with the vulnerability index. An
agent told those things once in a system prompt will drift away from them over a
long answer. Making ``analysis_limits`` a tool it must call before recommending
anything keeps them in front of it.

**Every tool call is logged and returned.** The transcript is the product, not
debug output: a recommendation about where a city should spend money has to be
auditable back to the measurement that produced it.

Model access is injected, so the loop is testable without a key. See
:class:`ScriptedModel`.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any, Callable, Protocol

from . import tools as T

# gpt-5.5 by eval, not by preference for the newer number. On the 16-case suite
# gpt-4.1 scored 12 and gpt-5.5 scored 16. The gap that decided it: asked to
# explain the physical mechanism behind the pattern, gpt-4.1 answered from its
# own priors with zero tool calls and asserted that surface materials and
# vegetation cause the difference, which is precisely the claim this project
# measured and could not support. gpt-5.5 answered "we cannot identify the
# physical mechanism from this dataset" and cited the regression instead.
# It costs roughly 10 s per question against 2 s, which is fine for a briefing.
MODEL = os.getenv("RESPITE_MODEL", "gpt-5.5")
MAX_STEPS = 12

SYSTEM = """You are Respite, an analyst working for a city heat-response office.

You have measurements of overnight heat exposure for census tracts in Phoenix,
plus the CDC social vulnerability index, and tools to read them.

The single most important fact about this dataset: measured exposure and the
vulnerability index are uncorrelated. A programme that allocates by vulnerability
index alone therefore misses genuinely exposed places and prioritises places
where the night is already survivable. Your job is to surface that disagreement,
not to smooth it over.

Rules you must follow:

1. Call analysis_limits before you make any recommendation, and obey what it
   says. It lists claims this data cannot support.
2. Never state or imply how many hours an intervention would save. No effect size
   was measurable.
3. Never combine exposure and vulnerability into a single score or ranking.
4. Cite the tract and the number behind every claim.
5. Where you are uncertain, say so plainly. A short accurate answer beats a long
   confident one.

Write for a busy official: plain sentences, concrete numbers, no throat-clearing.

Style: never use em dashes. Use commas, colons, or separate sentences instead.
Round numbers sensibly and always name the tract behind a figure.
"""


class Model(Protocol):
    def __call__(self, messages: list[dict], tools: list[dict]) -> dict: ...


def tool_schemas() -> list[dict]:
    """OpenAI-style function schemas for the registry."""
    return [
        {
            "type": "function",
            "function": {
                "name": "exposure_overview",
                "description": "Headline overnight-exposure numbers for the study area.",
                "parameters": {"type": "object", "properties": {}},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "divergence_summary",
                "description": (
                    "How measured exposure compares with the vulnerability index, "
                    "including the four quadrants and their populations."
                ),
                "parameters": {"type": "object", "properties": {}},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "list_tracts",
                "description": "List tracts, optionally filtered to one quadrant.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "quadrant": {
                            "type": "string",
                            "enum": ["confirmed", "blind_spot", "over_targeted", "low_priority"],
                        },
                        "order": {
                            "type": "string",
                            "enum": ["exposure", "relief", "population", "over_65"],
                        },
                        "limit": {"type": "integer", "minimum": 1, "maximum": 50},
                    },
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "tract_detail",
                "description": "Everything measured about one tract, by GEOID or tract name.",
                "parameters": {
                    "type": "object",
                    "properties": {"geoid": {"type": "string"}},
                    "required": ["geoid"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "analysis_limits",
                "description": (
                    "What this analysis does not support. Call before recommending anything."
                ),
                "parameters": {"type": "object", "properties": {}},
            },
        },
    ]


@dataclass
class Step:
    tool: str
    args: dict
    ok: bool
    result: Any


@dataclass
class Brief:
    answer: str
    steps: list[Step] = field(default_factory=list)
    consulted_limits: bool = False
    truncated: bool = False

    def to_dict(self) -> dict:
        return {
            "answer": self.answer,
            "consulted_limits": self.consulted_limits,
            "truncated": self.truncated,
            "audit_trail": [
                {"tool": s.tool, "args": s.args, "ok": s.ok, "result": s.result}
                for s in self.steps
            ],
        }


def run(question: str, model: Model, *, max_steps: int = MAX_STEPS) -> Brief:
    """Drive the tool-calling loop until the model produces an answer."""
    messages: list[dict] = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": question},
    ]
    brief = Brief(answer="")

    for _ in range(max_steps):
        reply = model(messages, tool_schemas())
        calls = reply.get("tool_calls") or []

        if not calls:
            brief.answer = (reply.get("content") or "").strip()
            return brief

        messages.append({"role": "assistant", "content": reply.get("content"), "tool_calls": calls})

        for call in calls:
            name = call["function"]["name"]
            raw = call["function"].get("arguments") or "{}"
            try:
                args = json.loads(raw) if isinstance(raw, str) else dict(raw)
            except json.JSONDecodeError:
                args = {}

            fn: Callable | None = T.REGISTRY.get(name)
            if fn is None:
                payload, ok = {"error": f"unknown tool {name!r}"}, False
            else:
                try:
                    payload, ok = fn(**args), True
                except TypeError as exc:
                    payload, ok = {"error": f"bad arguments for {name}: {exc}"}, False

            if name == "analysis_limits" and ok:
                brief.consulted_limits = True

            brief.steps.append(Step(tool=name, args=args, ok=ok, result=payload))
            messages.append({
                "role": "tool",
                "tool_call_id": call["id"],
                "content": json.dumps(payload, default=str),
            })

    brief.truncated = True
    brief.answer = (
        "Stopped after the step limit without reaching an answer. The audit trail "
        "below shows what was gathered."
    )
    return brief


# --------------------------------------------------------------- models

def openai_model(api_key: str | None = None, model: str = MODEL) -> Model:
    """Live model. Requires OPENAI_API_KEY."""
    from openai import OpenAI

    client = OpenAI(api_key=api_key or os.getenv("OPENAI_API_KEY"))

    # Newer reasoning models reject a non-default temperature outright, so rather
    # than keeping a list of which ones, drop any parameter the API rejects and
    # remember that for the rest of the session.
    unsupported: set[str] = set()

    def call(messages: list[dict], tools: list[dict]) -> dict:
        for attempt in range(3):
            kwargs: dict[str, Any] = {"model": model, "messages": messages, "tools": tools}
            if "temperature" not in unsupported:
                kwargs["temperature"] = 0.2
            try:
                resp = client.chat.completions.create(**kwargs)
                break
            except Exception as exc:  # noqa: BLE001
                text = str(exc)
                dropped = next(
                    (p for p in ("temperature", "top_p") if p in text and p not in unsupported),
                    None,
                )
                if dropped is None or attempt == 2:
                    raise
                unsupported.add(dropped)
        msg = resp.choices[0].message
        return {
            "content": msg.content,
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                }
                for tc in (msg.tool_calls or [])
            ],
        }

    return call


class ScriptedModel:
    """A model that replays a fixed sequence, so the loop can be tested with no key.

    Each entry is either a list of ``(tool_name, args)`` to call, or a string to
    return as the final answer.
    """

    def __init__(self, script: list[Any]) -> None:
        self.script = list(script)
        self.seen: list[list[dict]] = []

    def __call__(self, messages: list[dict], tools: list[dict]) -> dict:
        self.seen.append(messages)
        if not self.script:
            return {"content": "(script exhausted)", "tool_calls": []}
        step = self.script.pop(0)
        if isinstance(step, str):
            return {"content": step, "tool_calls": []}
        return {
            "content": None,
            "tool_calls": [
                {
                    "id": f"call_{i}",
                    "type": "function",
                    "function": {"name": name, "arguments": json.dumps(args)},
                }
                for i, (name, args) in enumerate(step)
            ],
        }
