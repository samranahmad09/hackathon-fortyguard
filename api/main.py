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

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from respite.vulnerability import LABELS as VULN_LABELS

ROOT = Path(__file__).resolve().parent.parent
LAYER = ROOT / "data" / "processed" / "tracts_recovery.geojson"
STATIC = Path(__file__).resolve().parent / "static"

app = FastAPI(
    title="Respite",
    description="Which blocks never cool down, and who sleeps in them.",
    version="0.1.0",
)

_layer_cache: dict | None = None


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
    """Headline numbers, so the front end never recomputes them."""
    feats = [f for f in layer()["features"] if f["properties"].get("ok")]
    vals = sorted(f["properties"]["value"] for f in feats)
    if not vals:
        raise HTTPException(status_code=503, detail="No tracts pass the coverage filter.")
    hottest = max(feats, key=lambda f: f["properties"]["value"])["properties"]
    coolest = min(feats, key=lambda f: f["properties"]["value"])["properties"]
    no_relief = [f for f in feats if f["properties"].get("no_relief")]
    return {
        "tracts": len(vals),
        "night_window": "00:00-06:00 local",
        "threshold_c": 28.0,
        "window_hours": 6.0,
        "min_hours": round(vals[0], 2),
        "max_hours": round(vals[-1], 2),
        "spread_hours": round(vals[-1] - vals[0], 2),
        # The headline: tracts that never drop below the threshold all night.
        "tracts_with_no_relief": len(no_relief),
        "max_relief_hours": round(6.0 - vals[0], 2),
        "hottest": {"name": hottest["name"], "geoid": hottest["geoid"],
                    "hours": round(hottest["value"], 2)},
        "coolest": {"name": coolest["name"], "geoid": coolest["geoid"],
                    "hours": round(coolest["value"], 2)},
    }


@app.get("/api/divergence")
def divergence() -> dict:
    """Where measured exposure disagrees with the vulnerability index.

    In this study area the two are uncorrelated (r = 0.004, n = 132), so an
    index-led programme mis-targets in both directions. This endpoint quantifies
    both errors rather than blending them into one score, because the
    disagreement is the finding.
    """
    feats = [f for f in layer()["features"] if f["properties"].get("ok")]
    buckets: dict[str, dict] = {}
    for f in feats:
        p = f["properties"]
        q = p.get("quadrant", "unknown")
        b = buckets.setdefault(q, {"tracts": 0, "population": 0.0, "over_65": 0.0,
                                   "label": VULN_LABELS.get(q, q)})
        b["tracts"] += 1
        b["population"] += p.get("population") or 0.0
        b["over_65"] += p.get("over_65") or 0.0

    for b in buckets.values():
        b["population"] = round(b["population"])
        b["over_65"] = round(b["over_65"])

    severe = buckets.get("confirmed", {}).get("tracts", 0) +              buckets.get("blind_spot", {}).get("tracts", 0)
    bs = buckets.get("blind_spot", {})
    return {
        "correlation_gap_vs_svi": 0.004,
        "note": ("Measured overnight exposure and social vulnerability are "
                 "uncorrelated here, so neither can substitute for the other."),
        "quadrants": buckets,
        "severe_tracts": severe,
        "blind_spot_share_of_severe": (
            round(bs.get("tracts", 0) / severe, 3) if severe else None
        ),
    }


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


@app.post("/api/agent")
def agent(payload: dict) -> dict:
    """Ask the agent a question. Returns its answer plus the full audit trail.

    POST {"question": "..."}

    The audit trail is part of the response rather than a log line: a
    recommendation about where a city spends money should be traceable to the
    measurement behind it.
    """
    question = (payload or {}).get("question", "").strip()
    if not question:
        raise HTTPException(status_code=422, detail="Provide a 'question' field.")

    if not os.getenv("OPENAI_API_KEY"):
        raise HTTPException(
            status_code=503,
            detail=("No OPENAI_API_KEY configured on the server. The map and all "
                    "measurement endpoints work without it; only the agent needs it."),
        )

    from respite.agent import openai_model, run

    try:
        brief = run(question, openai_model())
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
