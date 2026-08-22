"""Build the committed tract layer: fetch the night exceedance heatmap, aggregate
area-weighted onto census tracts, write GeoJSON for the API to serve.

Run from the repo root:  .venv/Scripts/python scripts/build_layer.py
"""
from __future__ import annotations
import json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

from shapely.geometry import shape
from respite import client as fg
from respite.aggregate import load_tracts, aggregate, to_geojson, MIN_COVERAGE

# Phoenix study area, wide enough to fully contain every tract in the set.
AOI = {"type": "FeatureCollection", "features": [{"type": "Feature", "properties": {},
    "geometry": {"type": "Polygon", "coordinates": [[
        [-112.1923, 33.3919], [-111.9610, 33.3919],
        [-111.9610, 33.5959], [-112.1923, 33.5959], [-112.1923, 33.3919]]]}}]}

STUDY_DATE = "2026-08-15"     # historical: forward windows return empty and still bill
NIGHT_START, NIGHT_END = "00:00", "06:00"
THRESHOLD_C = 28.0            # calibrated: 30 C saturates the layer flat in Phoenix
GRANULARITY = 100

TRACTS = ROOT / "data" / "tracts.geojson"
OUT = ROOT / "data" / "processed" / "tracts_recovery.geojson"


def main() -> int:
    if not TRACTS.exists():
        print(f"missing {TRACTS} -- run scripts/fetch_tracts.py first")
        return 1

    print(f"night exceedance > {THRESHOLD_C} C, {NIGHT_START}-{NIGHT_END} on {STUDY_DATE}")
    hm = fg.heatmap(
        polygon_aoi=AOI, start_date=STUDY_DATE, filter_type=2,
        start_time=NIGHT_START, end_time=NIGHT_END,
        granularity=GRANULARITY, analytic_type="exceedance",
        threshold=THRESHOLD_C, direction="above",
    )
    feats = fg.tiles(hm)
    tiles = [(shape(f["geometry"]), fg.tile_value(f)) for f in feats]
    print(f"  {len(tiles):,} tiles")

    polys, gids, names = load_tracts(json.loads(TRACTS.read_text(encoding="utf-8")))
    print(f"  {len(polys)} tracts; aggregating area-weighted ...")
    stats = aggregate(tiles, polys, gids, names)

    good = [s for s in stats if s.ok]
    vals = sorted(s.value for s in good)
    print(f"  {len(good)} of {len(stats)} tracts at >= {MIN_COVERAGE:.0%} coverage")
    print(f"  recovery gap {vals[0]:.2f} .. {vals[-1]:.2f} h   spread {vals[-1]-vals[0]:.2f} h")
    cov = sorted(s.coverage for s in stats)
    print(f"  coverage min {cov[0]:.1%}  median {cov[len(cov)//2]:.1%}  max {cov[-1]:.1%}")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(to_geojson(stats, polys, gids, "recovery_gap_hours")),
                   encoding="utf-8")
    print(f"  wrote {OUT} ({OUT.stat().st_size:,} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
