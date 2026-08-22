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
JOB_TIMEOUT = 1800.0

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
