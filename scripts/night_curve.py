"""Fetch hourly temperature through the night, so the metric can be shown as a curve.

"6.0 hours above 28 C" means nothing to a non-technical reader. Two lines, one
falling and one flat, mean everything. This pulls a single-hour snapshot for each
hour of the night window; each call covers the whole AOI, so seven calls give an
hourly curve for every tract at once.

Consistent with the exposure metric on purpose: same date, same 00:00-06:00 local
window, same AOI, so the curve and the headline number describe the same night.

Run from the repo root:  .venv/Scripts/python scripts/night_curve.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

from shapely.geometry import shape
from shapely.strtree import STRtree

from respite import client as fg
from respite.retry import with_retry

AOI = {"type": "FeatureCollection", "features": [{"type": "Feature", "properties": {},
    "geometry": {"type": "Polygon", "coordinates": [[
        [-112.1923, 33.3919], [-111.9610, 33.3919],
        [-111.9610, 33.5959], [-112.1923, 33.5959], [-112.1923, 33.3919]]]}}]}

STUDY_DATE = "2026-08-15"
HOURS = ["00:00", "01:00", "02:00", "03:00", "04:00", "05:00", "06:00"]
GRANULARITY = 100

TRACTS = ROOT / "data" / "tracts.geojson"
LAYER = ROOT / "data" / "processed" / "tracts_recovery.geojson"
OUT = ROOT / "data" / "processed" / "night_curves.json"


def main() -> int:
    tract_geo = json.loads(TRACTS.read_text(encoding="utf-8"))
    polys, gids, names = [], [], []
    for f in tract_geo["features"]:
        g = shape(f["geometry"])
        if g.is_valid and not g.is_empty:
            polys.append(g)
            gids.append(f["properties"]["GEOID"])
            names.append(f["properties"]["BASENAME"])
    tree = STRtree(polys)

    before = with_retry(fg.credits, label="credits")["total_credits_used"]
    print(f"credits used before: {before:,}")

    # hour -> geoid -> mean temperature.
    # One 504 on the status poll must not throw away the hours that did land, so a
    # failed hour is skipped and reported. A curve with a gap is still a curve; an
    # aborted run is nothing. This API produced four disruptions in five days.
    curves: dict[str, dict[str, float]] = {}
    failed: list[str] = []
    for hh in HOURS:
        try:
            res = with_retry(
                lambda hh=hh: fg.heatmap(
                    polygon_aoi=AOI, start_date=STUDY_DATE, filter_type=1,
                    start_time=hh, granularity=GRANULARITY, analytic_type="tcm",
                ),
                label=f"hour {hh}", attempts=6, base_delay=5.0,
            )
        except Exception as exc:  # noqa: BLE001
            print(f"  {hh}  SKIPPED after retries: {str(exc)[-90:]}", flush=True)
            failed.append(hh)
            continue
        feats = fg.tiles(res)
        sums: dict[str, list[float]] = {}
        for feat in feats:
            v = fg.tile_value(feat)
            if v is None:
                continue
            pt = shape(feat["geometry"]).centroid
            for idx in tree.query(pt):
                if polys[idx].contains(pt):
                    sums.setdefault(gids[idx], []).append(v)
                    break
        curves[hh] = {g: round(sum(vs) / len(vs), 3) for g, vs in sums.items() if vs}
        temps = list(curves[hh].values())
        print(f"  {hh}  {len(feats):>6,} tiles  {len(temps):>3} tracts  "
              f"mean {sum(temps)/len(temps):.2f} C  range {min(temps):.2f}..{max(temps):.2f}")

    # reshape to per-tract series and attach the exposure metric
    layer = {f["properties"]["geoid"]: f["properties"]
             for f in json.loads(LAYER.read_text(encoding="utf-8"))["features"]}

    got = [h for h in HOURS if h in curves]
    if len(got) < 4:
        print(f"Only {len(got)} of {len(HOURS)} hours retrieved; not enough for a curve")
        return 1
    if failed:
        print(f"Hours missing from the curve: {failed}")

    out = {"date": STUDY_DATE, "hours": got, "hours_requested": HOURS,
           "hours_failed": failed, "threshold_c": 28.0, "tracts": {}}
    name_by_gid = dict(zip(gids, names))
    for gid in sorted({g for h in curves.values() for g in h}):
        series = [curves[hh].get(gid) for hh in got]
        if any(v is None for v in series):
            continue
        p = layer.get(gid, {})
        out["tracts"][gid] = {
            "name": name_by_gid.get(gid, gid),
            "series": series,
            "min_c": min(series),
            "max_c": max(series),
            "drop_c": round(max(series) - min(series), 2),
            "hours_above_threshold": p.get("value"),
            "svi": p.get("svi"),
            "quadrant": p.get("quadrant"),
            "population": p.get("population"),
        }

    OUT.write_text(json.dumps(out), encoding="utf-8")
    after = with_retry(fg.credits, label="credits")
    print(f"\n{len(out['tracts'])} tracts with a full 7-point curve")
    print(f"credits spent: {after['total_credits_used'] - before:,}")
    print(f"credits left : {after['total_remaining_credits']:,}")
    print(f"wrote {OUT} ({OUT.stat().st_size:,} bytes)")

    # the pair that tells the story: biggest drop vs smallest, both well covered
    ts = [t for t in out["tracts"].values() if t["hours_above_threshold"] is not None]
    ts.sort(key=lambda t: t["drop_c"])
    print("\nflattest nights (never cool down):")
    for t in ts[:4]:
        print(f"   tract {t['name']:>9}  drop {t['drop_c']:>4.2f} C  "
              f"{t['min_c']:.1f} to {t['max_c']:.1f} C  SVI {t['svi']}")
    print("coolest nights (real recovery):")
    for t in ts[-4:]:
        print(f"   tract {t['name']:>9}  drop {t['drop_c']:>4.2f} C  "
              f"{t['min_c']:.1f} to {t['max_c']:.1f} C  SVI {t['svi']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
