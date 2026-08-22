"""Sample land cover across the recovery-gap range, for the dose-response fit.

Why sample rather than measure everything: satellite segmentation costs 14,400
credits per call against 4,220 for a whole citywide heatmap, so covering 134
tracts would cost 1.9M. Fifty tracts stratified evenly across the *gap* range
buys the leverage that matters for a regression while leaving budget spare.

Sampling is stratified by rank on the recovery gap, not geographically. The point
of the exercise is to explain variation in overnight exposure, so the sample must
span that variation rather than the map.

Each tract is probed at an interior representative point. That is defensible here
only because we measured tracts to be internally homogeneous on this metric
(ICC 0.855, median within-tract sd 0.071 h) -- in a city where tracts were
heterogeneous, a single point could not stand in for the tract.

Run from the repo root:  .venv/Scripts/python scripts/sample_landcover.py
"""
from __future__ import annotations

import csv
import json
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

from shapely.geometry import shape

from respite import client as fg
from respite.retry import with_retry

LAYER = ROOT / "data" / "processed" / "tracts_recovery.geojson"
OUT = ROOT / "data" / "landcover_sample.csv"

N_SAMPLE = 50
STUDY_DATE = "2026-08-15"
GRANULARITY = 100
WORKERS = 4          # the docs suggest parallel is fine with polite backoff

FIELDS = [
    "geoid", "name", "lat", "lon", "recovery_gap_h", "relief_h", "svi",
    "population", "built_share", "veg_share", "bare_share", "classified",
    "usable", "built", "vegetation", "bare", "water", "transient",
    "unclassified", "unmapped",
]


def pick(features: list[dict]) -> list[dict]:
    """Evenly spaced by rank across the recovery-gap distribution."""
    usable = [f for f in features if f["properties"].get("ok")]
    usable.sort(key=lambda f: f["properties"]["value"])
    if len(usable) <= N_SAMPLE:
        return usable
    step = (len(usable) - 1) / (N_SAMPLE - 1)
    idx = sorted({round(i * step) for i in range(N_SAMPLE)})
    return [usable[i] for i in idx]


def probe(feat: dict) -> dict | None:
    p = feat["properties"]
    geom = shape(feat["geometry"])
    pt = geom.representative_point()
    if not geom.contains(pt):
        pt = geom.centroid
    lat, lon = round(pt.y, 6), round(pt.x, 6)

    try:
        res = with_retry(
            lambda: fg.satellite(
                latitude=lat, longitude=lon, start_date=STUDY_DATE,
                filter_type=3, granularity=GRANULARITY,
            ),
            label=f"tract {p['name']}",
        )
    except Exception as exc:  # noqa: BLE001
        print(f"  {p['name']:>9}  FAILED: {str(exc)[:90]}", flush=True)
        return None

    lc = fg.land_cover(res)
    row = {
        "geoid": p["geoid"], "name": p["name"], "lat": lat, "lon": lon,
        "recovery_gap_h": round(p["value"], 4),
        "relief_h": p.get("relief_hours"),
        "svi": p.get("svi"), "population": p.get("population"),
        "built_share": lc["built_share"], "veg_share": lc["veg_share"],
        "bare_share": lc["bare_share"], "classified": lc["classified"],
        "usable": lc["usable"],
        "built": round(lc["built"], 4),
        "vegetation": round(lc["vegetation"], 4),
        "bare": round(lc["bare"], 4),
        "water": round(lc["water"], 4),
        "transient": round(lc["transient"], 4),
        "unclassified": round(lc["unclassified"], 4),
        "unmapped": "|".join(lc["unmapped"]),
    }
    flag = "" if lc["usable"] else "   <-- UNUSABLE, only %.0f%% classified" % (lc["classified"] * 100)
    bs = lc["built_share"]
    bs_txt = "  n/a" if bs is None else format(bs, ".1%")
    print(f"  {p['name']:>9}  gap {row['recovery_gap_h']:>5.2f}  "
          f"built_share {bs_txt:>6}  classified {lc['classified']:>5.1%}{flag}"
          + (f"  UNMAPPED: {row['unmapped']}" if lc["unmapped"] else ""), flush=True)
    return row


def main() -> int:
    feats = json.loads(LAYER.read_text(encoding="utf-8"))["features"]
    chosen = pick(feats)
    gaps = [f["properties"]["value"] for f in chosen]
    print(f"sampling {len(chosen)} tracts, gap {min(gaps):.2f} .. {max(gaps):.2f} h", flush=True)

    before = with_retry(fg.credits, label="credits")["total_credits_used"]
    print(f"credits used before: {before:,}\n", flush=True)

    rows: list[dict] = []
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        futures = {pool.submit(probe, f): f for f in chosen}
        for fut in as_completed(futures):
            r = fut.result()
            if r:
                rows.append(r)

    rows.sort(key=lambda r: r["recovery_gap_h"])
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)

    after = with_retry(fg.credits, label="credits")
    print(f"\n{len(rows)} of {len(chosen)} probed successfully")
    print(f"credits spent: {after['total_credits_used'] - before:,}")
    print(f"credits left : {after['total_remaining_credits']:,}")
    print(f"wrote {OUT}")

    unmapped = sorted({u for r in rows for u in r["unmapped"].split("|") if u})
    if unmapped:
        print(f"\nUNMAPPED land-cover classes seen: {unmapped}")
        print("Add them to the vocabulary in respite/client.py before trusting `built`.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
