"""Fit the dose-response: how much overnight exposure comes with built surface?

Three things make this harder than a one-line regression, and all three are
reported rather than hidden.

1. **Censoring.** About a quarter of tracts sit pinned at the 6 h ceiling -- they
   are above the threshold for the entire night, and we cannot tell "just barely"
   from "by ten degrees". OLS on a censored outcome flattens the slope, so every
   fit is reported twice: on all tracts, and on the uncensored subset only.

2. **A geographic confound.** Recovery gap correlates -0.66 with latitude in this
   study area: the north is cooler and also greener and higher. Built surface may
   be doing nothing except standing in for "south". A multiple regression with
   latitude alongside built surface separates them.

3. **Point-for-tract substitution.** Land cover is measured at one interior point
   per tract. Defensible only because tracts are internally homogeneous on this
   metric (ICC 0.855), and stated as an assumption rather than assumed silently.

Run from the repo root:  .venv/Scripts/python scripts/dose_response.py
"""
from __future__ import annotations

import csv
import io
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
SAMPLE = ROOT / "data" / "landcover_sample.csv"
CEILING = 6.0


def num(v: str) -> float | None:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def ols(y: np.ndarray, X: np.ndarray, names: list[str]) -> dict:
    """Least squares with an intercept, returning coefficients and t-stats."""
    n, k = X.shape
    A = np.column_stack([np.ones(n), X])
    beta, *_ = np.linalg.lstsq(A, y, rcond=None)
    resid = y - A @ beta
    dof = n - A.shape[1]
    if dof <= 0:
        return {"n": n, "r2": float("nan"), "coef": {}, "t": {}}
    s2 = float(resid @ resid) / dof
    cov = s2 * np.linalg.pinv(A.T @ A)
    se = np.sqrt(np.diag(cov))
    ss_tot = float(((y - y.mean()) ** 2).sum())
    r2 = 1.0 - float(resid @ resid) / ss_tot if ss_tot else float("nan")
    labels = ["intercept"] + names
    return {
        "n": n,
        "r2": r2,
        "adj_r2": 1 - (1 - r2) * (n - 1) / dof if dof else float("nan"),
        "coef": {l: float(b) for l, b in zip(labels, beta)},
        "t": {l: float(b / s) if s else float("inf") for l, b, s in zip(labels, beta, se)},
    }


def main() -> int:
    if not SAMPLE.exists():
        print(f"missing {SAMPLE} -- run scripts/sample_landcover.py first")
        return 1

    rows, dropped = [], []
    with io.open(SAMPLE, encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            gap = num(r["recovery_gap_h"])
            built = num(r["built_share"])
            usable = (r.get("usable") or "").strip().lower() == "true"
            if gap is None:
                continue
            if built is None or not usable:
                dropped.append((r["name"], num(r["classified"])))
                continue
            rows.append({
                "name": r["name"], "gap": gap, "built": built,
                "veg": num(r["veg_share"]) or 0.0,
                "bare": num(r["bare_share"]) or 0.0,
                "lat": num(r["lat"]) or 0.0,
            })

    if dropped:
        print("dropped for insufficient classified surface "
              "(a low built share there would be an artifact, not a measurement):")
        for name, cl in dropped:
            print(f"   tract {name:>9}  only {0 if cl is None else cl:.0%} classified")
        print()

    n_all = len(rows)
    uncens = [r for r in rows if r["gap"] < CEILING - 1e-6]
    print(f"sampled tracts: {n_all}")
    print(f"  at the {CEILING:.0f} h ceiling (censored): {n_all - len(uncens)}")
    print(f"  uncensored:                        {len(uncens)}")

    b = np.array([r["built"] for r in rows])
    print(f"\nbuilt surface across the sample: {b.min():.1%} .. {b.max():.1%}  "
          f"(mean {b.mean():.1%}, sd {b.std(ddof=1):.1%})")
    v = np.array([r["veg"] for r in rows])
    print(f"vegetation:                     {v.min():.1%} .. {v.max():.1%}  (mean {v.mean():.1%})")

    for label, data in (("ALL TRACTS (outcome censored at 6 h)", rows),
                        ("UNCENSORED ONLY", uncens)):
        if len(data) < 8:
            print(f"\n{label}: only {len(data)} rows, skipping")
            continue
        y = np.array([r["gap"] for r in data])
        print(f"\n{'=' * 68}\n{label}   n={len(data)}\n{'=' * 68}")

        for pred in ("built", "veg", "bare"):
            x = np.array([r[pred] for r in data])
            if x.std() < 1e-9:
                print(f"  gap ~ {pred:6}  no variance in predictor, skipped")
                continue
            m = ols(y, x.reshape(-1, 1), [pred])
            per10 = m["coef"][pred] * 0.10
            print(f"  gap ~ {pred:6}  slope {m['coef'][pred]:+.3f} h per unit  "
                  f"({per10:+.3f} h per 10pp)  R2 {m['r2']:.3f}  t {m['t'][pred]:+.2f}")

        # does built survive controlling for the north-south gradient?
        x2 = np.column_stack([[r["built"] for r in data], [r["lat"] for r in data]])
        m2 = ols(y, x2, ["built", "lat"])
        print(f"\n  controlling for latitude:  R2 {m2['r2']:.3f} (adj {m2['adj_r2']:.3f})")
        print(f"    built  {m2['coef']['built']:+.3f} h per unit "
              f"({m2['coef']['built'] * 0.10:+.3f} per 10pp)  t {m2['t']['built']:+.2f}")
        print(f"    lat    {m2['coef']['lat']:+.3f} h per degree            t {m2['t']['lat']:+.2f}")

    print(f"\n{'=' * 68}")
    print("Read the uncensored fit as the honest one; the censored fit is attenuated.")
    print("A |t| below about 2 means the predictor is not doing distinguishable work.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
