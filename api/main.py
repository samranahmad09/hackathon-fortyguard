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


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC / "index.html")


if STATIC.exists():
    app.mount("/static", StaticFiles(directory=STATIC), name="static")
