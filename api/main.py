"""Respite API.

The one rule this service exists to enforce: the FortyGuard key never leaves the
server. The repo is public and the demo URL is public, so nothing in the browser
may hold a credential or call the Temperature API directly.

The second rule follows from the API going down three times in four days: no
request path touches FortyGuard. Everything user-facing is served from the
precomputed layer committed under ``data/processed``. Rebuilding that layer is a
deliberate offline step (``scripts/build_layer.py``), never a page load.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from api import limits
from respite import tools as rtools
from respite.vulnerability import LABELS as VULN_LABELS

ROOT = Path(__file__).resolve().parent.parent
LAYER = ROOT / "data" / "processed" / "tracts_recovery.geojson"
CURVES = ROOT / "data" / "processed" / "night_curves.json"
STATIC = Path(__file__).resolve().parent / "static"

# The scripts each call load_dotenv themselves; the server did not, so a key sat
# in .env while /api/agent reported none configured. Real environment variables
# still win, which is what a host like systemd or a scheduled task will set.
load_dotenv(ROOT / ".env", override=False)

app = FastAPI(
    title="Respite",
    description="Which blocks never cool down, and who sleeps in them.",
    version="0.1.0",
)

_layer_cache: dict | None = None
_briefing_cache: dict | None = None
_tract_cache: dict[str, dict] = {}


def layer() -> dict:
    global _layer_cache
    if _layer_cache is None:
        if not LAYER.exists():
            raise HTTPException(
                status_code=503,
                detail="Tract layer not built. Run scripts/build_layer.py.",
            )
        _layer_cache = json.loads(LAYER.read_text(encoding="utf-8"))
    return _layer_cache


@app.get("/health")
def health() -> dict:
    """Cheap liveness check that also reports whether the data layer is present."""
    present = LAYER.exists()
    n = len(layer()["features"]) if present else 0
    return {
        "status": "ok",
        "layer_present": present,
        "tracts": n,
        # Presence only. Never the value.
        "fortyguard_key_configured": bool(os.getenv("FORTYGUARD_API_KEY")),
        "llm_key_configured": bool(os.getenv("OPENAI_API_KEY")),
        **limits.state(),
    }


@app.get("/api/tracts")
def tracts(min_coverage: float = 0.90) -> JSONResponse:
    """Tract polygons with the overnight recovery gap.

    ``value`` is hours spent above the night threshold within the 00:00-06:00
    window, area-weighted across every tile overlapping the tract.
    ``relief_hours`` is the remainder of the six-hour night.
    """
    feats = [
        f for f in layer()["features"]
        if f["properties"].get("coverage", 0) >= min_coverage
    ]
    return JSONResponse({"type": "FeatureCollection", "features": feats})


@app.get("/api/summary")
def summary() -> dict:
    """Headline numbers.

    Delegates to :func:`respite.tools.exposure_overview` so the page and the agent
    cannot disagree. Two separate implementations drifted once already.
    """
    feats = [f for f in layer()["features"] if f["properties"].get("ok")]
    if not feats:
        raise HTTPException(status_code=503, detail="No tracts pass the coverage filter.")
    out = dict(rtools.exposure_overview())

    hottest = max(feats, key=lambda f: f["properties"]["value"])["properties"]
    coolest = min(feats, key=lambda f: f["properties"]["value"])["properties"]
    out["min_hours"] = out["hours_above_threshold_min"]
    out["max_hours"] = out["hours_above_threshold_max"]
    out["max_relief_hours"] = round(out["window_hours"] - out["hours_above_threshold_min"], 2)
    out["hottest"] = {"name": hottest["name"], "geoid": hottest["geoid"],
                      "hours": round(hottest["value"], 2)}
    out["coolest"] = {"name": coolest["name"], "geoid": coolest["geoid"],
                      "hours": round(coolest["value"], 2)}
    return out


@app.get("/api/divergence")
def divergence() -> dict:
    """Where measured exposure disagrees with the vulnerability index.

    In this study area the two are uncorrelated (r = 0.004, n = 132), so an
    index-led programme mis-targets in both directions. This endpoint quantifies
    both errors rather than blending them into one score, because the
    disagreement is the finding.
    """
    out = dict(rtools.divergence_summary())
    for q, b in out.get("quadrants", {}).items():
        b["label"] = VULN_LABELS.get(q, q)
    severe = out.get("severe_tracts") or 0
    bs = out.get("quadrants", {}).get("blind_spot", {})
    out["blind_spot_share_of_severe"] = (
        round(bs.get("tracts", 0) / severe, 3) if severe else None
    )
    return out


@app.get("/api/blindspot")
def blindspot() -> dict:
    """The tracts a vulnerability-led programme would miss, worst first."""
    feats = [
        f["properties"] for f in layer()["features"]
        if f["properties"].get("ok") and f["properties"].get("quadrant") == "blind_spot"
    ]
    feats.sort(key=lambda p: (-p["value"], p.get("svi") or 0))
    return {
        "count": len(feats),
        "population": round(sum(p.get("population") or 0 for p in feats)),
        "over_65": round(sum(p.get("over_65") or 0 for p in feats)),
        "tracts": [
            {
                "name": p["name"], "geoid": p["geoid"],
                "hours_above_threshold": round(p["value"], 2),
                "relief_hours": p["relief_hours"],
                "svi_percentile": p.get("svi"),
                "population": p.get("population"),
                "over_65": p.get("over_65"),
                "pct_mobile_homes": p.get("pct_mobile_homes"),
            }
            for p in feats
        ],
    }


@app.get("/api/curves")
def curves(pair: bool = True) -> dict:
    """Hourly temperature through the night.

    ``pair=True`` returns just two contrasting tracts, which is what the chart
    needs: one that cools and one that does not. The full set is available for
    anyone who wants to check that the pair was not cherry-picked.
    """
    if not CURVES.exists():
        raise HTTPException(
            status_code=503,
            detail="Night curves not built. Run scripts/night_curve.py.",
        )
    data = json.loads(CURVES.read_text(encoding="utf-8"))
    if not pair:
        return data

    tracts = [
        {"geoid": g, **t} for g, t in data["tracts"].items()
        if t.get("hours_above_threshold") is not None and t.get("svi") is not None
    ]
    if not tracts:
        raise HTTPException(status_code=503, detail="No tracts with a full curve.")

    # Selected on the overnight *minimum*, not the size of the drop. The metric
    # this page reports is time spent above the threshold, so the pair that
    # illustrates it is the tract whose night never gets under the line against
    # the one that gets furthest under it. Ranking by drop picked a pair that both
    # crossed the threshold, which showed nothing.
    thr = data["threshold_c"]
    tracts.sort(key=lambda t: t["min_c"])
    cools, flat = tracts[0], tracts[-1]
    below = sum(1 for v in cools["series"] if v < thr)
    return {
        "date": data["date"],
        "hours": data["hours"],
        "threshold_c": thr,
        "flat": flat,
        "cools": cools,
        "cools_hours_below": below,
        "min_gap_c": round(flat["min_c"] - cools["min_c"], 2),
        "n_tracts_measured": len(tracts),
        "selection": (
            "The highest and lowest overnight minimum across every measured tract, "
            "picked by the data rather than by hand."
        ),
    }


def _agent_or_503(request: Request | None = None):
    """Shared guard so every agent-backed endpoint fails the same way.

    Also enforces the spend ceiling, because these endpoints cost money per call
    and the app is meant to be shareable over a tunnel.
    """
    if request is not None:
        try:
            limits.check(request)
        except limits.RateLimited as exc:
            raise HTTPException(status_code=429, detail=str(exc)) from exc
    if not os.getenv("OPENAI_API_KEY"):
        raise HTTPException(
            status_code=503,
            detail=("No OPENAI_API_KEY configured on the server. The map, the charts and "
                    "every measurement endpoint work without it; only the agent needs it."),
        )
    from respite.agent import openai_model, run
    return run, openai_model()


BRIEFING_PROMPT = (
    "Brief a city official who has never seen this data and has two minutes. "
    "Cover, in this order and in plain language: what was measured and what the "
    "numbers mean, why overnight heat is the thing to care about, the single most "
    "important finding, and what it implies for how heat response is targeted. "
    "Explain any term a non-specialist would not know. Be specific with tract "
    "numbers and figures. Do not exceed roughly 300 words."
)


@app.get("/api/briefing")
def briefing(request: Request, refresh: bool = False) -> dict:
    """A standing briefing the agent writes without being asked.

    Generated on first request and cached, so repeated visits cost nothing and
    the wording stays stable between them. ``refresh=1`` forces a rewrite.
    """
    global _briefing_cache
    # The cached briefing is free to serve, so it is not counted against the
    # allowance. Only a real generation spends anything.
    if _briefing_cache is not None and not refresh:
        return {**_briefing_cache, "cached": True}

    run, model = _agent_or_503(request)
    try:
        brief = run(BRIEFING_PROMPT, model)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Model call failed: {exc}") from exc

    _briefing_cache = {
        **brief.to_dict(),
        "prompt": BRIEFING_PROMPT,
        "unprompted": True,
    }
    return {**_briefing_cache, "cached": False}


@app.get("/api/explain/{geoid}")
def explain(geoid: str, request: Request) -> dict:
    """Explain one tract in plain language, triggered by a click rather than a question."""
    if geoid in _tract_cache:
        return {**_tract_cache[geoid], "cached": True}

    check = rtools.tract_detail(geoid)
    if check.get("error"):
        raise HTTPException(status_code=404, detail=check["error"])

    run, model = _agent_or_503(request)
    prompt = (
        f"Explain tract {geoid} to someone with no background in this data. Say how its "
        "night compared with the rest of the city, who lives there, whether a "
        "vulnerability-led programme would reach it, and what that means in practice. "
        "Four short paragraphs at most, plain language, no jargon left unexplained."
    )
    try:
        brief = run(prompt, model)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Model call failed: {exc}") from exc

    _tract_cache[geoid] = {**brief.to_dict(), "geoid": geoid,
                           "name": check.get("name")}
    return {**_tract_cache[geoid], "cached": False}


@app.post("/api/agent")
def agent(payload: dict, request: Request) -> dict:
    """Ask the agent a question. Returns its answer plus the full audit trail.

    POST {"question": "..."}

    The audit trail is part of the response rather than a log line: a
    recommendation about where a city spends money should be traceable to the
    measurement behind it.
    """
    question = (payload or {}).get("question", "").strip()
    if not question:
        raise HTTPException(status_code=422, detail="Provide a 'question' field.")

    run, model = _agent_or_503(request)
    try:
        brief = run(question, model)
    except Exception as exc:  # noqa: BLE001 - surface provider failures as 502
        raise HTTPException(status_code=502, detail=f"Model call failed: {exc}") from exc
    return brief.to_dict()


@app.get("/api/agent/tools")
def agent_tools() -> dict:
    """What the agent can read. Exposed so the demo can show its working."""
    from respite.agent import tool_schemas

    return {
        "tools": [
            {"name": t["function"]["name"], "description": t["function"]["description"]}
            for t in tool_schemas()
        ],
        "note": ("analysis_limits is a tool rather than a prompt instruction so the "
                 "agent cannot drift away from the claims the data will not support."),
    }


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC / "index.html")


if STATIC.exists():
    app.mount("/static", StaticFiles(directory=STATIC), name="static")


if __name__ == "__main__":
    # Convenience entry point so the box can run `python -m api.main` without
    # remembering uvicorn flags. Defaults to loopback: in production Caddy is
    # the only thing that should reach this process.
    import uvicorn

    uvicorn.run(
        "api.main:app",
        host=os.getenv("RESPITE_HOST", "127.0.0.1"),
        port=int(os.getenv("RESPITE_PORT", "8020")),
        reload=os.getenv("RESPITE_RELOAD") == "1",
    )
