"""Tools the agent may call.

Deliberately pure functions over the committed layer: no network, no LLM, no
FortyGuard calls on this path. That makes every one of them testable on its own,
which matters because the agent's output is only as trustworthy as these are.

The unusual one is :func:`analysis_limits`. Most of the work on this project went
into finding out what the data will *not* support, and an agent that cannot see
those limits will confidently assert the things we disproved. So the limits are a
tool it can read rather than a paragraph in a prompt it might drift away from.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
LAYER = ROOT / "data" / "processed" / "tracts_recovery.geojson"
SAMPLE = ROOT / "data" / "landcover_sample.csv"

WINDOW_HOURS = 6.0
THRESHOLD_C = 28.0


@lru_cache(maxsize=1)
def _tracts() -> list[dict]:
    data = json.loads(LAYER.read_text(encoding="utf-8"))
    return [f["properties"] for f in data["features"] if f["properties"].get("ok")]


@lru_cache(maxsize=1)
def _land_cover() -> dict[str, dict]:
    if not SAMPLE.exists():
        return {}
    import csv
    import io

    out: dict[str, dict] = {}
    with io.open(SAMPLE, encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            out[row["geoid"]] = row
    return out


def _f(v: Any) -> float | None:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


# ----------------------------------------------------------------- tools

# Seconds of relief still counted as "no relief". Zero is the strict reading and
# is what the headline uses. The rest are here because the strict reading turns on
# a tolerance nobody chose on physical grounds.
RELIEF_TOLERANCES_S = (0, 60, 300, 900, 1800)


def relief_sensitivity() -> list[dict]:
    """How the no-relief count moves with the tolerance applied to it.

    ``TractStat.no_relief`` tests ``value >= WINDOW_HOURS - 1e-6``. That 1e-6 is a
    floating-point equality guard, 3.6 milliseconds, and it ended up acting as a
    physical threshold. Tracts credited with relief include several whose
    area-weighted mean dipped below the line for under a second, which is
    interpolation noise rather than a recovery window.

    It matters because the count nearly doubles: 18 tracts at exactly zero relief,
    32 once a single minute counts as none. So the honest object is this curve, the
    same way the vulnerability cut is reported as a curve rather than one number.
    """
    t = _tracts()
    out = []
    for secs in RELIEF_TOLERANCES_S:
        sel = [p for p in t if (WINDOW_HOURS - p["value"]) * 3600.0 <= secs + 1e-9]
        out.append({
            "relief_under_seconds": secs,
            "tracts": len(sel),
            "population": round(sum(p.get("population") or 0 for p in sel)),
        })
    return out


def exposure_overview() -> dict:
    """Headline numbers for the study area."""
    t = _tracts()
    vals = sorted(p["value"] for p in t)
    no_relief = [p for p in t if p.get("no_relief")]
    return {
        "city": "Phoenix, Arizona",
        "study_date": "2026-08-15",
        "night_window": "00:00-06:00 local",
        "threshold_c": THRESHOLD_C,
        "window_hours": WINDOW_HOURS,
        "tracts": len(t),
        "hours_above_threshold_min": round(vals[0], 2),
        "hours_above_threshold_max": round(vals[-1], 2),
        "spread_hours": round(vals[-1] - vals[0], 2),
        "tracts_with_no_relief": len(no_relief),
        "population_with_no_relief": round(sum(p.get("population") or 0 for p in no_relief)),
        # Reported alongside the count, never separately, because the count is the
        # strictest point on this curve rather than a robust figure.
        "no_relief_tolerance_sensitivity": relief_sensitivity(),
        "metric_meaning": (
            "Hours spent above the threshold during the night window, area-weighted "
            "from 100 m tiles. At the window maximum the tract never dropped below "
            "the threshold at any point in the night."
        ),
        "counting_caveat": (
            "The no-relief count uses exact equality with the window. Several further "
            "tracts dipped below the threshold for under a second, which is not a "
            "recovery window, so the count rises from 18 to 32 if a minute of relief "
            "still counts as none. Quote the sensitivity, not the bare 18."
        ),
    }


def divergence_summary() -> dict:
    """How measured exposure compares with the vulnerability index."""
    t = _tracts()
    buckets: dict[str, dict] = {}
    for p in t:
        q = p.get("quadrant", "unknown")
        b = buckets.setdefault(q, {"tracts": 0, "population": 0.0, "over_65": 0.0})
        b["tracts"] += 1
        b["population"] += p.get("population") or 0.0
        b["over_65"] += p.get("over_65") or 0.0
    for b in buckets.values():
        b["population"] = round(b["population"])
        b["over_65"] = round(b["over_65"])
    severe = buckets.get("confirmed", {}).get("tracts", 0) + buckets.get("blind_spot", {}).get("tracts", 0)

    from .vulnerability import sensitivity
    gaps = sorted(p["value"] for p in t)
    gap_cutoff = gaps[int(len(gaps) * 0.75)]
    curve = sensitivity(
        [(p["value"], p.get("svi"), p.get("population") or 0.0, p.get("over_65") or 0.0) for p in t],
        gap_cutoff,
    )

    return {
        "correlation_exposure_vs_svi": 0.004,
        "correlation_n": 132,
        "interpretation": (
            "Measured overnight exposure and CDC social vulnerability are uncorrelated "
            "in this study area, so neither can be used as a proxy for the other."
        ),
        "quadrants": buckets,
        "severe_tracts": severe,
        "svi_threshold_used": 0.75,
        "threshold_caveat": (
            "0.75 is the top-quartile convention, not a fact. The count of missed "
            "tracts depends on it: see threshold_sensitivity. Describe these tracts as "
            "outside the targeted band, never as ones the index 'ranks low' -- the "
            "median missed tract sits at the 68th percentile."
        ),
        "threshold_sensitivity": curve,
        "quadrant_meanings": {
            "confirmed": "severe exposure, inside the top-quartile vulnerability band",
            "blind_spot": "severe exposure, outside the band a programme would target",
            "over_targeted": "inside the targeted band, but the night is survivable",
            "low_priority": "neither severe exposure nor inside the targeted band",
        },
    }


def list_tracts(quadrant: str | None = None, order: str = "exposure", limit: int = 10) -> dict:
    """Tracts, optionally filtered by quadrant.

    ``order``: ``exposure`` (most exposed first), ``relief`` (most relief first),
    ``population`` (largest first), or ``over_65``.
    """
    t = _tracts()
    if quadrant:
        t = [p for p in t if p.get("quadrant") == quadrant]
    keys = {
        "exposure": lambda p: -p["value"],
        "relief": lambda p: p["value"],
        "population": lambda p: -(p.get("population") or 0),
        "over_65": lambda p: -(p.get("over_65") or 0),
    }
    t = sorted(t, key=keys.get(order, keys["exposure"]))[: max(1, min(limit, 50))]
    return {
        "count": len(t),
        "order": order,
        "quadrant": quadrant,
        "tracts": [
            {
                "name": p["name"], "geoid": p["geoid"],
                "hours_above_threshold": round(p["value"], 2),
                "relief_hours": p.get("relief_hours"),
                "svi_percentile": p.get("svi"),
                "quadrant": p.get("quadrant"),
                "population": p.get("population"),
                "over_65": p.get("over_65"),
            }
            for p in t
        ],
    }


def tract_detail(geoid: str) -> dict:
    """Everything measured about one tract, including whether land cover was sampled."""
    match = next((p for p in _tracts() if p["geoid"] == geoid or p["name"] == geoid), None)
    if match is None:
        return {"error": f"no tract matching {geoid!r} in the study set"}

    out = {
        "name": match["name"], "geoid": match["geoid"],
        "hours_above_threshold": round(match["value"], 2),
        "relief_hours": match.get("relief_hours"),
        "no_relief": match.get("no_relief"),
        "quadrant": match.get("quadrant"),
        "svi_percentile": match.get("svi"),
        "population": match.get("population"),
        "over_65": match.get("over_65"),
        "pct_over_65": match.get("pct_over_65"),
        "pct_poverty": match.get("pct_poverty"),
        "pct_mobile_homes": match.get("pct_mobile_homes"),
        "pct_no_vehicle": match.get("pct_no_vehicle"),
        "measurement_coverage": round(match.get("coverage", 0), 3),
        "tiles_measured": match.get("n_tiles"),
    }

    lc = _land_cover().get(match["geoid"])
    if lc is None:
        out["land_cover"] = None
        out["land_cover_note"] = (
            "This tract was not in the 50-tract land-cover sample. Land cover was not "
            "measured here."
        )
    elif (lc.get("usable") or "").lower() != "true":
        out["land_cover"] = None
        out["land_cover_note"] = (
            f"Land cover unusable: only {_f(lc.get('classified')) or 0:.0%} of the image "
            "was classified, so composition here would be an artifact."
        )
    else:
        out["land_cover"] = {
            "built_share": _f(lc.get("built_share")),
            "vegetation_share": _f(lc.get("veg_share")),
            "bare_share": _f(lc.get("bare_share")),
            "classified": _f(lc.get("classified")),
        }
        out["land_cover_note"] = (
            "Sampled at one interior point. Note that land cover was NOT found to "
            "predict exposure independently of position; see analysis_limits."
        )
    return out


def analysis_limits() -> dict:
    """What this analysis does not support. Read before making any recommendation."""
    return {
        "no_intervention_effect_sizes": {
            "finding": (
                "Land cover does not predict overnight exposure once position is "
                "controlled for. Built share gives t = +0.24 with latitude in the model; "
                "vegetation gives t = -1.46. Latitude and longitude alone reach R2 0.70."
            ),
            "consequence": (
                "Do not state or imply how many hours any intervention would save. No "
                "effect size was measurable, so cost-per-hour claims are unsupported."
            ),
        },
        "exposure_is_censored": {
            "finding": (
                f"The metric caps at {WINDOW_HOURS} h. Tracts at the cap were above the "
                "threshold for the entire night; how far above cannot be distinguished."
            ),
            "consequence": "Do not rank tracts against each other at the cap.",
        },
        "vulnerability_is_not_exposure": {
            "finding": "Exposure and the vulnerability index are uncorrelated (r = 0.004).",
            "consequence": (
                "Do not blend them into a single score. Report them as separate axes and "
                "say where they disagree."
            ),
        },
        "blind_spot_depends_on_an_arbitrary_threshold": {
            "finding": (
                "The count of severely exposed tracts outside the targeted vulnerability "
                "band falls from 15 at SVI < 0.75 to 4 at SVI < 0.50. The median such "
                "tract sits at the 68th percentile."
            ),
            "consequence": (
                "Quote the sensitivity curve, not a single count. Do not say the index "
                "'ranks these low'; say they fall outside the band a programme targets."
            ),
        },
        "no_relief_count_depends_on_a_tolerance": {
            "finding": (
                "The no-relief count tests exact equality with the 6 h window. Tracts "
                "just under it dipped below the threshold for as little as a tenth of a "
                "second, which is interpolation noise, not recovery. The count is 18 at "
                "exactly zero relief, 32 at under a minute, 34 at under fifteen minutes."
            ),
            "consequence": (
                "Do not present 18 as a robust count. Say it is the strictest reading and "
                "give the curve, the same way the vulnerability threshold is handled."
            ),
        },
        "single_night_single_city": {
            "finding": "One night, 2026-08-15, 134 tracts in central Phoenix.",
            "consequence": "Do not generalise to other cities, seasons, or dates.",
        },
        "geography_is_the_strongest_predictor": {
            "finding": "Position explains most of the variance; the cause behind it is not identified.",
            "consequence": (
                "Attribute the pattern to position, not to a mechanism. Candidate "
                "explanations such as elevation or distance from open desert were not tested."
            ),
        },
    }


from . import context as _ctx

# Measurement tools and context tools are registered together so the agent can
# reach both, but they carry different provenance and the prompt requires the
# agent to keep that visible. Measurements come from this study; context comes
# from the literature and is never tract-specific.
REGISTRY = {
    "exposure_overview": exposure_overview,
    "divergence_summary": divergence_summary,
    "list_tracts": list_tracts,
    "tract_detail": tract_detail,
    "analysis_limits": analysis_limits,
    "why_night_heat_matters": _ctx.why_night_heat_matters,
    "what_cities_do": _ctx.what_cities_do,
    "glossary": _ctx.glossary,
}
