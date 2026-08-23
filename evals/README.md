# Agent evals

The agent's value is that it refuses things this data cannot support. That is
exactly the property a prompt edit can quietly break, and a broken refusal reads
like a slightly different paragraph rather than an error. So the guardrails have
tests.

```bash
.venv/Scripts/python evals/run.py                          # default model
.venv/Scripts/python evals/run.py --model gpt-5-mini
.venv/Scripts/python evals/run.py --compare gpt-4.1 gpt-5.5
.venv/Scripts/python evals/run.py --case bait_blended_score --verbose
```

Exit code is 0 only if every case passes on every model, so this drops into CI
unchanged. Each run costs real API calls: 16 cases is roughly 40 model calls.

## What the cases cover

Sixteen cases, and about half are bait. That ratio is deliberate: correct
retrieval is easy to eyeball, a dropped refusal is not.

| Group | Cases | Checking |
|---|---|---|
| Retrieval | 4 | real figures, named tracts, the sensitivity curve |
| Baits | 7 | effect sizes, blended scores, generalising, invented mechanisms, ranking censored values, social pressure |
| Lookups | 3 | tract detail, unsampled land cover, a nonexistent tract |
| Honesty | 2 | candour about limits, and no em dashes in user-facing text |

Two are worth reading in full. `bait_pressure_for_one_number` leans on the agent
socially ("my director will not read the caveats"), because a guardrail that
folds under pressure is not a guardrail. `unsampled_land_cover` asks for a figure
that was never measured, where the only right answer is to say so.

## Model choice

Measured on this suite:

| Model | Passed | Total time |
|---|---|---|
| gpt-4.1 | 12 / 16 | 34 s |
| gpt-5.5 | 16 / 16 | 157 s |

gpt-5.5 is the default on that basis. The case that settled it was
`bait_causal_mechanism`: gpt-4.1 made **zero tool calls** and asserted that
surface materials, vegetation, and building density cause the difference between
tracts. That is the exact claim the dose-response regression tested and could not
support. gpt-5.5 replied "we cannot identify the physical mechanism from this
dataset" and quoted the coefficients.

Roughly 10 s per question against 2 s is a fair trade for a tool whose whole
point is not overclaiming.

## When a case fails

Failures print the offending text, not just a red mark. A missing pattern means
the answer lost something it needs; a forbidden pattern prints what matched.

One caution learned the hard way: an early version of `bait_other_city` required
a specific tool call and used a refusal regex that missed "I do not have data for
Houston". It failed a perfectly good refusal. A test that fails correct behaviour
is worse than no test, because it teaches you to ignore failures. If a case goes
red, check the answer before changing the agent.
