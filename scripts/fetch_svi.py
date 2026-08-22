"""Download CDC/ATSDR SVI for Arizona and keep only the tracts in our study set.

No API key: SVI is a plain CSV. The full Arizona file is ~1.3 MB across 1,765
tracts; we keep the 134 we actually measured, which is small enough to commit so
the deployed box needs no network at all.

SVI encodes missing values as -999, which will silently poison any average that
does not filter it out.
"""
from __future__ import annotations

import csv
import io
import json
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
SVI_URL = "https://svi.cdc.gov/Documents/Data/2022/csv/states/Arizona.csv"
TRACTS = ROOT / "data" / "tracts.geojson"
OUT = ROOT / "data" / "svi_tracts.csv"

MISSING = -999.0

# Everything we need for the vulnerability layer, plus the join key.
KEEP = [
    "FIPS",
    "LOCATION",
    "E_TOTPOP",      # total population
    "E_AGE65",       # count 65+
    "EP_AGE65",      # % 65+
    "EP_POV150",     # % below 150% of poverty
    "EP_NOVEH",      # % no vehicle
    "EP_DISABL",     # % with a disability
    "EP_UNINSUR",    # % uninsured
    "EP_MOBILE",     # % mobile homes
    "EP_MUNIT",      # % in multi-unit structures
    "EP_AGE17",      # % under 18
    "RPL_THEMES",    # overall SVI percentile rank, 0-1
]


def main() -> int:
    if not TRACTS.exists():
        print(f"missing {TRACTS}")
        return 1

    wanted = {
        f["properties"]["GEOID"]
        for f in json.loads(TRACTS.read_text(encoding="utf-8"))["features"]
    }
    print(f"study tracts: {len(wanted)}")

    print(f"downloading {SVI_URL}")
    r = requests.get(SVI_URL, timeout=180)
    r.raise_for_status()
    text = r.content.decode("utf-8-sig", errors="replace")
    print(f"  {len(r.content):,} bytes")

    rows = list(csv.DictReader(io.StringIO(text)))
    print(f"  {len(rows):,} Arizona tracts")

    missing_cols = [c for c in KEEP if c not in rows[0]]
    if missing_cols:
        print(f"  ABORT: columns absent from the file: {missing_cols}")
        return 1

    kept, flagged = [], []
    for row in rows:
        fips = (row.get("FIPS") or "").strip()
        if fips not in wanted:
            continue
        rec = {k: (row.get(k) or "").strip() for k in KEEP}
        # count how many of our numeric fields are suppressed for this tract
        bad = [
            k for k in KEEP[2:]
            if _num(rec[k]) is None or _num(rec[k]) == MISSING
        ]
        if bad:
            flagged.append((fips, bad))
        kept.append(rec)

    found = {r["FIPS"] for r in kept}
    print(f"  matched {len(kept)} of {len(wanted)} study tracts")
    absent = wanted - found
    if absent:
        print(f"  NOT IN SVI ({len(absent)}): {sorted(absent)[:6]}")

    if flagged:
        print(f"  tracts with suppressed (-999) values: {len(flagged)}")
        for fips, bad in flagged[:5]:
            print(f"     {fips}: {bad}")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with io.open(OUT, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=KEEP)
        w.writeheader()
        w.writerows(kept)
    print(f"  wrote {OUT} ({OUT.stat().st_size:,} bytes)")
    return 0


def _num(v: str) -> float | None:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


if __name__ == "__main__":
    raise SystemExit(main())
