"""Aggregate tile-level values onto census tracts, area-weighted.

Centroid-in-polygon assignment is fine for a variance test but wrong for
published numbers: a tile straddling a boundary gets given entirely to one
side, which is why our first pass reported tracts at up to 120% apparent
coverage. Here every tile contributes to each tract in proportion to the
overlapping area, and each tract reports how much of itself was actually
measured so a thinly-covered unit can be excluded rather than trusted.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Iterable

from shapely.geometry import shape
from shapely.strtree import STRtree

MIN_COVERAGE = 0.90

# The exceedance layer caps at the window length: a 1 h window maxes at exactly
# 1.000 and a 3 h window at exactly 3.000 (measured). Over a 6 h window, ~10% of
# tiles come back marginally above 6.0 -- up to 14 minutes over, median 24
# seconds -- which is boundary interpolation overshoot, not extra exposure. Any
# value at or above the window means the cell never dropped below the threshold
# all night, so clamp rather than carry an impossible number into the pitch.
WINDOW_HOURS = 6.0


@dataclass
class TractStat:
    geoid: str
    name: str
    value: float          # area-weighted mean, clamped to the window
    coverage: float       # fraction of the tract's area actually measured
    n_tiles: int
    vmin: float
    vmax: float

    @property
    def ok(self) -> bool:
        return self.coverage >= MIN_COVERAGE

    @property
    def relief_hours(self) -> float:
        """Hours of the night the tract spent below the threshold. Never negative."""
        return max(0.0, WINDOW_HOURS - self.value)

    @property
    def no_relief(self) -> bool:
        """Above the threshold for the whole window -- no recovery at all."""
        return self.value >= WINDOW_HOURS - 1e-6


def load_tracts(geojson: dict) -> tuple[list, list[str], list[str]]:
    polys, gids, names = [], [], []
    for feat in geojson["features"]:
        geom = shape(feat["geometry"])
        if geom.is_empty or not geom.is_valid:
            continue
        props = feat.get("properties", {})
        polys.append(geom)
        gids.append(props.get("GEOID", ""))
        names.append(props.get("BASENAME", ""))
    return polys, gids, names


def aggregate(
    tiles: Iterable[tuple],           # (shapely geometry, value)
    polys: list,
    gids: list[str],
    names: list[str],
) -> list[TractStat]:
    """Area-weighted mean of the tile metric per tract."""
    tiles = list(tiles)
    tree = STRtree([g for g, _ in tiles])

    out: list[TractStat] = []
    for poly, gid, name in zip(polys, gids, names):
        num = 0.0     # sum(value * overlap area)
        den = 0.0     # sum(overlap area)
        seen = 0
        lo, hi = None, None

        for idx in tree.query(poly):
            tgeom, val = tiles[idx]
            if val is None:
                continue
            inter = poly.intersection(tgeom)
            if inter.is_empty:
                continue
            a = inter.area
            if a <= 0:
                continue
            num += val * a
            den += a
            seen += 1
            lo = val if lo is None else min(lo, val)
            hi = val if hi is None else max(hi, val)

        if den <= 0 or poly.area <= 0:
            continue
        out.append(
            TractStat(
                geoid=gid,
                name=name,
                value=min(num / den, WINDOW_HOURS),
                coverage=den / poly.area,
                n_tiles=seen,
                vmin=lo,
                vmax=hi,
            )
        )
    return out


def to_geojson(stats: list[TractStat], polys: list, gids: list[str], metric: str) -> dict:
    """Tract polygons carrying the aggregated metric, ready to serve to a map."""
    by_gid = {g: p for g, p in zip(gids, polys)}
    feats = []
    for s in stats:
        geom = by_gid.get(s.geoid)
        if geom is None:
            continue
        props = asdict(s)
        props["metric"] = metric
        props["ok"] = s.ok
        props["relief_hours"] = round(s.relief_hours, 3)
        props["no_relief"] = s.no_relief
        props["window_hours"] = WINDOW_HOURS
        feats.append(
            {"type": "Feature", "geometry": geom.__geo_interface__, "properties": props}
        )
    return {"type": "FeatureCollection", "features": feats}
