"""A guarded wrapper around the FortyGuard client.

Every guard here exists because the underlying API bit us during the sprint:

* a forward or current-day window returns HTTP 200, ``status: "completed"`` and
  ``n_cells: 0`` -- and still bills 4,220 credits, so an empty result must be a
  hard error rather than an empty list flowing downstream;
* the vendor client's default 60 s HTTP timeout cannot download a citywide
  payload, and a read timeout bills in full;
* the service went down three times in four days, so anything we can cache we
  cache and never re-request.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

from fortyguard import FortyGuardClient

# The vendor default is 60 s. A citywide 60 m request is tens of megabytes.
HTTP_TIMEOUT = 900.0
JOB_TIMEOUT = 240.0

CACHE_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"


class EmptyResultError(RuntimeError):
    """The API reported success but returned no cells.

    Usually means the requested window is in the future or beyond the ingest
    boundary. The call was still billed.
    """


def _cache_path(kind: str, payload: dict) -> Path:
    blob = json.dumps(payload, sort_keys=True).encode()
    digest = hashlib.sha256(blob).hexdigest()[:16]
    return CACHE_DIR / f"{kind}_{digest}.json"


def _check(result: dict, what: str) -> dict:
    """Reject a successful-but-empty response before anything consumes it."""
    body = result.get("result", result)
    stats = body.get("stats_data") or {}
    cells = stats.get("n_cells")
    features = (body.get("map_data") or {}).get("features") or []
    if not features:
        raise EmptyResultError(
            f"{what}: API returned success with n_cells={cells} and no features. "
            "The window is probably in the future or past the ingest boundary. "
            "This call was billed."
        )
    if cells is not None and cells != len(features):
        # Not fatal, but worth surfacing: it has never happened in our runs.
        print(f"  warning: {what}: n_cells={cells} but {len(features)} features")
    return result


def client() -> FortyGuardClient:
    return FortyGuardClient(timeout=HTTP_TIMEOUT)


def heatmap(*, cache: bool = True, **kwargs: Any) -> dict:
    """``create_heatmap`` with an empty-result guard and an on-disk cache.

    Cache key is the full argument set, so changing any parameter re-requests
    and anything already fetched is free.
    """
    path = _cache_path("heatmap", kwargs)
    if cache and path.exists():
        return json.loads(path.read_text(encoding="utf-8"))

    result = client().create_heatmap(
        wait=True, timeout=JOB_TIMEOUT, verbose=True, **kwargs
    )
    _check(result, f"heatmap {kwargs.get('start_date')} {kwargs.get('analytic_type')}")

    if cache:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(result), encoding="utf-8")
    return result


# Land-cover classes the segmentation endpoint has been observed to return.
# Only classes present in an image appear in its `segments` dict, so the key set
# varies per call -- normalise on ingest and shout about anything unrecognised
# rather than letting it fall into "other" and quietly deflate the built share.
_BUILT = {
    "building", "skyscraper", "house", "road, route", "sidewalk, pavement",
    "bridge, span", "wall", "fence", "runway", "railing, rail", "rail", "path",
    "parking lot", "hovel, hut", "tower", "roof", "column, pillar",
}
_VEG = {"tree", "grass", "plant", "palm, palm tree", "field", "flower", "bush"}
_BARE = {
    "earth, ground", "sand", "dirt track", "rock, stone", "hill", "land",
    "mountain, mount",
}
_WATER = {"water", "sea", "river", "lake", "swimming pool", "pool"}

# Transient objects sitting on top of the surface. Classified, but they tell us
# nothing about what the ground is made of.
_TRANSIENT = {"car", "truck", "van", "person", "plane", "boat", "bus", "sky"}

# "others" is the model's own I-don't-know bucket, and it is not a land-cover
# class. One sampled tract came back {"others": 100.0} -- nothing was classified
# at all. Treating that as 0% built would feed a fabricated zero into the
# regression, so it is tracked separately and such tracts are excluded.
_UNCLASSIFIED = {"others", "other", "unknown"}


def satellite(*, cache: bool = True, **kwargs: Any) -> dict:
    """``satellite_segmentation`` with the same caching and guards.

    Costs 14,400 credits per call -- 3.4x a heatmap -- so the cache matters.
    """
    path = _cache_path("satellite", kwargs)
    if cache and path.exists():
        return json.loads(path.read_text(encoding="utf-8"))

    result = client().satellite_segmentation(
        wait=True, timeout=JOB_TIMEOUT, verbose=False, **kwargs
    )
    body = result.get("result", result)
    if not (body.get("segmentation") or {}).get("segments"):
        raise EmptyResultError(
            f"satellite at {kwargs.get('latitude')},{kwargs.get('longitude')}: "
            "no segments returned. This call was billed."
        )

    if cache:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(result), encoding="utf-8")
    return result


# Below this share of genuinely classified surface, a tract's composition is not
# a measurement and must not enter a regression.
MIN_CLASSIFIED = 0.50


def land_cover(result: dict) -> dict:
    """Normalise per-class percentages into a fixed schema.

    ``built_share`` is the headline: built surface as a fraction of *classified*
    area, so a tract where the model gave up on half the image is not silently
    recorded as half-unbuilt. ``usable`` says whether enough was classified to
    trust the composition at all, and ``unmapped`` lists any class outside the
    vocabulary so a silent misclassification cannot pass unnoticed.
    """
    segs = result["result"]["segmentation"]["segments"]
    out = {
        "built": 0.0, "vegetation": 0.0, "bare": 0.0, "water": 0.0,
        "transient": 0.0, "unclassified": 0.0,
    }
    unmapped: list[str] = []
    for name, pct in segs.items():
        key = name.strip().lower()
        frac = float(pct) / 100.0
        if key in _BUILT:
            out["built"] += frac
        elif key in _VEG:
            out["vegetation"] += frac
        elif key in _BARE:
            out["bare"] += frac
        elif key in _WATER:
            out["water"] += frac
        elif key in _TRANSIENT:
            out["transient"] += frac
        elif key in _UNCLASSIFIED:
            out["unclassified"] += frac
        else:
            out["unclassified"] += frac
            unmapped.append(name)

    surface = out["built"] + out["vegetation"] + out["bare"] + out["water"]
    out["classified"] = round(surface, 4)
    out["usable"] = surface >= MIN_CLASSIFIED
    out["built_share"] = round(out["built"] / surface, 4) if surface > 0 else None
    out["veg_share"] = round(out["vegetation"] / surface, 4) if surface > 0 else None
    out["bare_share"] = round(out["bare"] / surface, 4) if surface > 0 else None
    out["unmapped"] = unmapped
    return out


def credits() -> dict:
    return client().fetch_api_key_usage()["credit_summary"]


def tiles(result: dict) -> list[dict]:
    """The features array, whichever analytic type produced it."""
    return result["result"]["map_data"]["features"]


def tile_value(feature: dict) -> float | None:
    """Read the metric off a tile.

    ``tcm`` tiles carry ``average_temperature``; the analysis layers
    (``exceedance``, ``persistence``, ``time_of_measure``) carry ``value``.
    All of them are Celsius or hours -- never Fahrenheit, whatever the vendor
    docstring says.
    """
    props = feature.get("properties", {})
    for key in ("value", "average_temperature"):
        if props.get(key) is not None:
            return float(props[key])
    return None
