# Respite

**Which blocks never cool down, and who sleeps in them.**

An entry for [FortyGuard Hackathon'26](https://www.fortyguard.com/hackathon26), built on the
FortyGuard Temperature API®. Tracks 06 (Agentic AI) and 04 (Government & Environment).

> **Status: planning.** The analysis approach is settled and measured; the application is not
> built yet. This README describes the intended system, not a finished one.

## The premise

Overnight minimum temperature predicts heat mortality better than daytime maximum.
The body needs a cool window to shed accumulated heat load, and when the night never
drops, that recovery never happens.

That matters only if overnight heat varies at block scale. It does. Measured over central
Phoenix on a single night, hours spent above 28 °C between midnight and dawn:

| | Hours above 28 °C (of a 6-hour night) |
|---|---|
| Coolest block | 2.53 |
| Hottest block | 6.23 |
| **Spread** | **3.70** |

For comparison, the 16:00 afternoon peak spreads only 1.57 °C across the same area.

The signal survives aggregation to administrative units, which is what makes it actionable.
Measured over 47,944 tiles at 100 m granularity, across an AOI wide enough to fully contain
every tract in the study set (21.5 × 22.5 km, all 134 tracts at ≥88.7% coverage):

| Geography | Units | Spread of unit means | Retained | ICC |
|---|---|---|---|---|
| Tiles (100 m) | 47,944 | 3.70 h | n/a | n/a |
| **Census tracts** | 134 | **3.18 h** | **86%** | **0.855** |
| Block groups | 333 | 3.28 h | 89% | 0.901 |

An ICC of 0.855 means 86% of the variance is *between* tracts rather than within them.
Median within-tract spread is 0.071 h. Tracts are internally coherent on this metric, because overnight
heat retention is driven by neighbourhood-scale built form and tract boundaries tend to follow it.

An earlier pass used a narrower AOI that clipped 38 of the 134 tracts, the worst covering only
1.2% of its own area. Widening to full coverage moved the tract spread from 3.20 h to 3.18 h and
the ICC from 0.857 to 0.855. The conclusion is not sensitive to it, because a high ICC
means even a clipped sample comes from a fairly uniform tract. Clipping added noise, not bias.

Tract **1062** is a cool island at 2.89 h, and every tract it touches runs 1.7–2.0 h hotter
overnight, 1065.01 at 4.84 h, 1052 at 4.74 h, 1066 at 4.64 h, 1063 at 4.58 h. Three hours of
relief on one side of a boundary, a little over one hour on the other.

## What it does

Given a US city and a heat event, Respite:

1. Computes a **recovery gap** per block: hours above a calibrated night threshold within the
   local 00:00–06:00 window, from the heatmap `exceedance` layer.
2. Crosses that with **who lives there** (CDC/ATSDR SVI, Census ACS) to produce a triage ordering.
3. Uses **land-cover segmentation** to tag the cause, so the recommended intervention matches the
   actual problem rather than a default.
4. Reports where measured exposure **disagrees with the vulnerability index** a city would
   normally target by. The two are uncorrelated here (r = 0.004, n = 132), so 15 of the 33
   worst-exposed tracts sit below the threshold such a programme would use to find them.

We tested whether surface composition predicts overnight exposure and could not detect an
effect independent of position: built share gives t = +0.24 with latitude in the model, and
latitude plus longitude alone reach R2 0.70. So Respite does **not** claim intervention
effect sizes. At this scale, overnight retention looks like a regional gradient rather than a
local surface effect.

## Measured constraints worth knowing

Findings from ~25 live API calls, some of which contradict the published docs. Full notes live
in the team's build plan.

- **Tiles are °C, not °F**, despite the client docstring. Threshold is also °C, so no conversion.
- **Forward or current-day windows return `n_cells: 0` and still bill 4,220 credits.** Always
  assert `n_cells > 0` before consuming a response.
- **Credits are flat per call**: 4,220 for a heatmap regardless of area or granularity; 14,400
  for satellite segmentation.
- **Thresholds saturate silently.** `persistence` above 30 °C returned a flat 8.00 across all
  23,167 tiles. A flat map means a bad threshold, not absent signal.
- **Never use `heat_index` for anything overnight**: `env_params` holds temperature fixed and
  varies only humidity, so heat index peaks overnight as an artifact.
- **`env_params` cannot separate blocks**: its grid is coarser than 1.36 km.
- **Land cover at a point does not predict tract exposure.** Across 50 sampled tracts,
  vegetation runs 0 to 55.7% (mean 12.7%) and built share 0 to 100% (mean 74.6%), but neither
  survives controlling for position. An earlier two-point sample suggested Phoenix had almost
  no canopy anywhere; the wider sample shows that was unrepresentative.
- **"others" is the segmentation model's unclassified bucket, not a land-cover class.** One
  sampled tract returned `{"others": 100.0}`. Counting that as 0% built would feed a
  fabricated zero into any regression, so composition is expressed as a share of *classified*
  surface and thinly classified tracts are excluded.

## Setup

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt
cp .env.example .env    # then add your key
```

Generate a key from the [Temperature Dashboard](https://dashboard.fortyguard.com) under Profile.
Each team member should generate their own: separate credit pools, no waiting on each other.

After cloning, enable the safety hook (`core.hooksPath` is local config and does not travel with
a clone, so every teammate must run this once):

```bash
git config core.hooksPath .githooks
```

**The key never leaves the server.** `.env` is gitignored and a pre-commit hook blocks commits
containing key-shaped strings. This repo is public and the API key must stay server-side.

## Attribution

Forked from [FortyGuard-Tech/temperature-api-quickstart](https://github.com/FortyGuard-Tech/temperature-api-quickstart)
and stripped back to the client and setup notebooks. The `fortyguard/` package and `notebooks/00`–`05`
are FortyGuard's work, MIT licensed (see [LICENSE](LICENSE)). Everything else here is ours.

AI tool usage is disclosed in the hackathon submission, as required.
