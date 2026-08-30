# Respite

**Which blocks never cool down, and who sleeps in them.**

**Live: [respite.samtechpk.com](https://respite.samtechpk.com)**

An entry for [FortyGuard Hackathon'26](https://www.fortyguard.com/hackathon26), built on the
FortyGuard Temperature API®. Tracks 06 (Agentic AI) and 04 (Government & Environment).

Ask the agent a question about overnight heat in Phoenix and it answers from measurements,
tells you when the data cannot support what you asked, and shows every source it read.

No login, nothing to install. It opens in a private window and every measurement on the page
works whether or not the agent is reachable.

**Provenance.** This repository is a fork of FortyGuard's own
[temperature-api-quickstart](https://github.com/FortyGuard-Tech/temperature-api-quickstart), so
its history contains FortyGuard's commits from April and May 2026. That inherited boilerplate
is the `fortyguard/` client package and `notebooks/00`-`05`, MIT licensed, listed under
[Attribution](#attribution). Everything of ours begins on 21 August 2026, after the kickoff.

---

## The finding

Heat programmes are usually aimed with a social vulnerability index, on the assumption that
the most vulnerable places are also the hottest. In this study area that assumption does not
hold. Measured overnight exposure and the CDC/ATSDR index are **uncorrelated**:

```
r = 0.004   (n = 132 tracts)
```

That is the product. Respite does not blend exposure and vulnerability into a priority score,
because averaging two uncorrelated variables destroys the only interesting thing about them.
It reports where they **disagree**:

| | Tracts | People | Over 65 |
|---|---|---|---|
| Severely exposed, outside the targeted band | **15** | 52,091 | 6,293 |
| Severely exposed, already targeted | 18 | 61,999 | 4,209 |
| Targeted, not severely exposed overnight | 53 | 212,101 | 19,242 |
| Neither | 46 | 175,167 | 28,246 |

We checked the obvious explanations for a null result before building on it. It is not range
restriction (sd ratio 0.85) and not a ceiling effect: excluding the capped tracts still gives
r = -0.070, and the mid-range gives r = -0.272.

The 15 depends on where the targeting line is drawn, so the tool reports the curve, never the
bare count:

| Vulnerability cut | Missed tracts | People |
|---|---|---|
| SVI < 0.90 | 24 | 80,645 |
| **SVI < 0.75** | **15** | **52,091** |
| SVI < 0.60 | 7 | 26,668 |
| SVI < 0.50 | 4 | 16,262 |
| SVI < 0.40 | 2 | 7,278 |

The median missed tract sits at the 68th percentile of vulnerability. These are not places the
index ranks as safe; they are places that fall outside the band a programme would target.

## Why overnight

Overnight minimum temperature predicts heat mortality better than daytime maximum. The body
sheds accumulated heat when air is cooler than skin, so a night that never drops removes the
recovery window and the previous day's strain carries into the next.

That matters only if overnight heat varies at block scale. It does. Central Phoenix,
2026-08-15, hours spent above 28 °C between midnight and 06:00, from the `exceedance` layer at
100 m granularity:

| | Hours above 28 °C, of a 6-hour night |
|---|---|
| Coolest tile | 2.53 |
| Hottest tile | 6.23 |
| **Spread** | **3.70** |

The 16:00 afternoon peak spreads only 1.57 °C across the same area. The city looks uniform by
day and is not uniform at night.

The signal survives aggregation to administrative units, which is what makes it usable by
anyone. Measured across an AOI wide enough to fully contain every tract in the study set
(21.5 × 22.5 km, all 134 tracts at ≥88.7% coverage):

| Geography | Units | Spread of unit means | Retained | ICC |
|---|---|---|---|---|
| Tiles (100 m) | 47,944 | 3.70 h | n/a | n/a |
| **Census tracts** | 134 | 3.18 h | 86% | **0.855** |
| Block groups | 333 | 3.28 h | 89% | 0.901 |

An ICC of 0.855 means 86% of the variance is *between* tracts rather than within them; median
within-tract spread is 0.071 h. Tracts are internally coherent on this metric, so tract-level
reporting is not an averaging artefact. Block groups are marginally better and triple the unit
count, which is why the shipped layer uses tracts.

## What it does

The deployed app is an agent with tools over a precomputed measurement layer.

1. **Writes an opening briefing unprompted.** Nobody asked it anything; it reads the
   measurements and the public health literature and decides what matters.
2. **Answers questions** from the same measurements, separating what was measured here from
   what is general literature, and listing every tool call it made.
3. **Explains any tract** when you click it on the map.
4. **Refuses what the data will not support**, which is the part we spent the most effort on.

The agent reads the study's own limitations as a *tool* (`analysis_limits`) rather than as
prompt text, so a prompt edit cannot quietly remove them. Asked for a cool-pavement effect
size, it declines and says why. Asked to rank the tracts that are pinned at the measurement
ceiling, it says they cannot be ranked. Asked to blend exposure and vulnerability into one
score, it keeps them apart.

## What we tested and could not support

These are here because a tool that only reports what it found is harder to trust than one that
says where it stops.

- **No intervention effect sizes.** We sampled surface composition at 50 tracts to test whether
  pavement and canopy explain overnight heat. Once position is controlled for they do not:
  built share gives t = +0.24, vegetation t = -1.46, while latitude and longitude alone reach
  R² 0.70. So the tool never estimates how much cooling anything would buy.
- **Position, not mechanism.** Something about where a tract sits drives this and we did not
  test what. Elevation, drainage and distance from open desert are untested candidates.
- **A ceiling on the metric.** The measure caps at six hours. Tracts at the cap were above
  28 °C for the whole window and cannot be ranked against each other.
- **The no-relief count turns on a tolerance.** A tract counts as having no relief only if its
  hours above 28 °C exactly equal the window. Several tracts dipped below the line for under a
  second, which is interpolation noise rather than recovery. The count is **18** at exactly
  zero relief, 32 at under a minute, 34 at under fifteen minutes. The page quotes 18 because it
  is the claim that cannot be argued down, not because it is the robust one, and the agent
  gives the whole curve when asked.
- **One night, one city.** 2026-08-15, 134 tracts in central Phoenix. Nothing here generalises
  to another city, season or date, and the agent says so when asked.

## How it is built

```
respite/client.py       guarded FortyGuard wrapper: timeouts, empty-result detection
respite/aggregate.py    area-weighted tile to tract join, no geopandas
respite/vulnerability.py SVI join and the divergence classification
respite/tools.py        the agent's tools, pure functions over the committed layer
respite/context.py      public health literature, kept separate from measurements
respite/agent.py        tool-calling loop
api/main.py             FastAPI, serves the app and proxies the agent
api/limits.py           spend ceilings on the model-backed endpoints
api/static/index.html   the whole front end
evals/                  16 regression cases, half of them bait
```

**The processed layer is committed**, so no page load calls the Temperature API. That is
deliberate: the API returned errors on three separate days during the sprint, and a demo that
depends on a vendor being up is a demo that fails when it matters. Rebuilds are an offline
script.

**Guardrails are tested, not asserted.** `evals/` holds 16 cases, roughly half designed to bait
the agent into an unsupported claim, checked with a mix of structural patterns and a model
judge. Current state on the production model: **16 clean, 0 flaky, 0 failing.** The suite
defaults to whatever model the app runs, because a suite that tests a different model says
nothing about shipped behaviour.

**The API key never reaches the browser.** `.env` is gitignored, a pre-commit hook blocks
key-shaped strings, and the agent is proxied server-side. `/health` reports only whether a key
is *present*.

**Spend is bounded.** 25 agent questions per caller per hour and 300 across all callers per
24 hours, checked before the model is reached so a blocked request costs nothing. Both are
rolling windows, so the agent cannot be left permanently refusing. Running out is not a broken
page: every measurement, the map and both charts are independent of it.

## A real Temperature API request and response

This is the call that builds the whole study layer, from
[`scripts/build_layer.py`](scripts/build_layer.py). One heatmap request covers the entire area
at 100 m granularity; there is no per-tract looping.

**Request.** `POST https://api.fortyguard.com/v1/heatmap`, with the key in an `api-key` header
(never in the body, the URL, or this file):

```json
{
  "polygon_aoi": {
    "type": "FeatureCollection",
    "features": [{
      "type": "Feature", "properties": {},
      "geometry": {"type": "Polygon", "coordinates": [[
        [-112.1923, 33.3919], [-111.9610, 33.3919],
        [-111.9610, 33.5959], [-112.1923, 33.5959], [-112.1923, 33.3919]
      ]]}
    }]
  },
  "start_date": "2026-08-15",
  "filter_type": 2,
  "start_time": "00:00",
  "end_time": "06:00",
  "granularity": 100,
  "analytic_type": "exceedance",
  "threshold": 28.0,
  "direction": "above"
}
```

The endpoint is asynchronous: it returns an `activity_id`, which is polled at
`GET /v1/status/{activity_id}` until the result is ready.

**Response**, abridged. `stats_data` verbatim; `map_data.features` is 47,944 entries and one is
shown:

```json
{
  "activity_id": "9c898f97-f1ae-42a4-8b94-c0662dd661ab",
  "result": {
    "stats_data": {
      "activity_id": "9c898f97-f1ae-42a4-8b94-c0662dd661ab",
      "analytic_type": "exceedance",
      "units": "hour",
      "n_cells": 47944,
      "min": 2.5344,
      "max": 6.2346,
      "mean": 4.6997108021858836
    },
    "map_data": {
      "type": "FeatureCollection",
      "features": [
        {
          "id": "0",
          "type": "Feature",
          "properties": {"tile_id": 0, "value": 5.9928},
          "geometry": {"type": "Polygon", "coordinates": [[
            [-112.06814774987384, 33.39145271087759],
            [-112.06707311253570, 33.39146190000000],
            "... 3 more vertices ..."
          ]]}
        }
      ]
    }
  }
}
```

`value` is hours above 28 °C within the requested window. Note `max: 6.2346` against a
six-hour window: 10.2% of tiles overshoot the ceiling, by 23 seconds at the median and 14.1
minutes at the worst, which is why the aggregation clamps to the window.

## What does not work yet

- **One night, one city.** 2026-08-15, 134 tracts in central Phoenix. There is no city picker.
  Pointing it elsewhere means editing the AOI in `scripts/build_layer.py` and rebuilding, which
  costs FortyGuard credits and takes a few minutes; nothing about the code is Phoenix-specific,
  but nothing is parameterised in the UI either.
- **The layer is precomputed, not live.** The site never calls the Temperature API at request
  time. That is a deliberate trade for reliability during judging, but it does mean the page
  cannot answer questions about tonight.
- **No forecast.** The API's forward windows return `n_cells: 0` and still bill, so the tool is
  retrospective only.
- **The agent has no memory between questions.** Each one is answered from scratch. Follow-ups
  that say "and what about that one" will not resolve.
- **Tracts at the six-hour ceiling cannot be ranked** against each other, so the tool refuses
  to order them. That is correct behaviour rather than a bug, but it does surprise people.
- **No authentication, no per-user state.** It is a public read-only demo, with a spend cap on
  the agent endpoints.

## Measured constraints worth knowing

Findings from live API calls, several of which contradict the published docs.

- **Tiles are °C, not °F**, despite the client docstring. The threshold is also °C, so no
  conversion is needed.
- **Forward or current-day windows return `n_cells: 0` and still bill 4,220 credits.** Assert
  `n_cells > 0` before consuming a response, and never retry an empty window.
- **Credits are flat per call**: 4,220 for a heatmap regardless of area or granularity, 14,400
  for satellite segmentation.
- **Thresholds saturate silently.** `persistence` above 30 °C returned a flat 8.00 across all
  23,167 tiles. A flat map means a bad threshold, not absent signal.
- **Never use `heat_index` overnight.** `env_params` holds temperature fixed and varies only
  humidity, so heat index peaks overnight as an artefact.
- **`env_params` cannot separate blocks**: its grid is coarser than 1.36 km.
- **10.2% of tiles overshoot the requested window.** 4,870 of 47,944 exceeded 6.0 h, median by
  23 seconds and at most by 14.1 minutes, so the aggregation clamps to the window. This is why
  the tract spread the app reports (3.11 h) is slightly narrower than the unclamped 3.18 h.
- **Land cover at a point does not predict tract exposure.** Across 50 sampled tracts vegetation
  runs 0 to 55.7% (mean 12.7%) and built share 0 to 100% (mean 74.6%), but neither survives
  controlling for position. An earlier two-point sample suggested Phoenix had almost no canopy
  anywhere; the wider sample showed that was unrepresentative.
- **"others" is the segmentation model's unclassified bucket, not a land-cover class.** One
  sampled tract returned `{"others": 100.0}`. Counting that as 0% built would feed a fabricated
  zero into a regression, so composition is expressed as a share of *classified* surface and
  thinly classified tracts are excluded.

## How to run it

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt
cp .env.example .env    # then add your keys
git config core.hooksPath .githooks
```

That last line matters: `core.hooksPath` is local config and does not survive a clone, so every
teammate must run it once to enable the key guard.

Run it:

```bash
.venv/Scripts/python -m uvicorn api.main:app --host 127.0.0.1 --port 8020
```

Only `OPENAI_API_KEY` is needed to serve the app. `FORTYGUARD_API_KEY` is needed only to rebuild
the layer, from the [Temperature Dashboard](https://dashboard.fortyguard.com) under Profile.
Each team member should generate their own: separate credit pools, no waiting on each other.

Deployment runbook: [`deploy/README.md`](deploy/README.md). Eval suite: [`evals/README.md`](evals/README.md).

## AI tool usage

Disclosed in full, as the rules require.

**Claude (Opus 5, via Claude Code) wrote most of the code and most of the prose in this
repository**, including this README, working from direction given in conversation. It also ran
the analysis scripts, and the framing of the product around the divergence finding came out of
that conversation rather than from either party alone.

What the humans did: chose the problem and the track, set the constraint that the tool must
refuse unsupported claims, ran the user testing that caused the interface to be rebuilt around
the agent, deployed and verified it, and rejected work that was wrong. Several errors in this
project were caught by a human noticing something looked off, including a basemap that shipped
with an "API KEY REQUIRED" watermark across every tile, a chart whose top row disagreed with
the headline number, and an interface where two of five testers never found the agent at all.

The measurements are not AI-generated. Every figure in this README comes from the FortyGuard
Temperature API, the CDC/ATSDR SVI, or the US Census, and the ones quoted here were re-verified
against the raw API responses before publication.

## Attribution

Forked from [FortyGuard-Tech/temperature-api-quickstart](https://github.com/FortyGuard-Tech/temperature-api-quickstart)
and stripped back to the client and setup notebooks. The `fortyguard/` package and
`notebooks/00`–`05` are FortyGuard's work, MIT licensed (see [LICENSE](LICENSE)). Everything
else here is ours.

Vulnerability data from the CDC/ATSDR Social Vulnerability Index 2022. Tract boundaries from the
US Census TIGERweb. Basemap from [OpenFreeMap](https://openfreemap.org) and OpenStreetMap
contributors.
