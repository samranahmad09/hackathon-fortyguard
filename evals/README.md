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

## Flakiness

A case that passes sometimes is worse than one that fails, because it trains you
to shrug at red. Two cases have been rewritten for this reason rather than for
model behaviour:

- `bait_other_city` required a specific tool call and used a refusal regex that
  missed "I do not have data for Houston", so it failed a correct refusal.
- `overview` asked for "headline numbers in two sentences" and then required two
  specific figures, passing or failing depending on which the model chose to
  mention. It now asks for exactly what it checks.

The guardrail cases, the baits, have been stable across every run. Those are the
ones that matter; if one of them ever goes intermittent, treat it as a real
finding about the prompt rather than as noise to be smoothed over.

## Check the property, not the phrasing

Every eval failure on this suite so far has turned out to be a check matching the
words I expected rather than the behaviour I cared about:

| Case | What went wrong |
|---|---|
| `bait_other_city` | refusal regex missed "I do not have data for Houston" |
| `overview` | asked vaguely, then required two exact figures |
| `nonexistent_tract` | missed "I do not find tract 9999.99 in the study set" |
| `bait_rank_at_ceiling` | required "ceiling" when the model said "all tied" |
| `bait_causal_mechanism` | banned "caused by pavement" outright, so it fired on a correctly-labelled *general* statement about urban heat |

The last is the instructive one. Describing the general mechanism of urban heat is
useful and allowed; claiming it explains *our* tracts is not. A phrase ban cannot
tell those apart, so the case now requires the disclaimer instead. That is a
tighter test than the ban it replaced, not a looser one.

Loosening a check to turn a suite green is how a suite stops being worth running.
When a case fails, read the answer first and ask whether the behaviour was
actually wrong.
