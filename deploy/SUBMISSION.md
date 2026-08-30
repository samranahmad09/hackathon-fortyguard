# Submission answers

For the official form: <https://forms.gle/jLgBzVTG1NhJ3gNe6>

**Deadline 30 August 2026, 23:59 GST. One submission per team, the team leader submits.**
The form can be resubmitted any number of times before then and the latest entry is kept, so
submit a complete draft early and refine it rather than leaving it to the last hour.

**The FortyGuard API key goes in the form and nowhere else.** Not in this file, not in the
repo, not in the video. It is requested by the form itself, which is the only place it belongs.

---

## Project title

Respite

## One-line pitch

Respite finds the neighbourhoods that never cool down overnight, and shows that the index
cities use to target heat help does not find them.

## Primary track

Track 06, Agentic AI.

Secondary tags: Track 04, Government and Environment.

## Problem and user

Heat response programmes are aimed using a social vulnerability index, on the assumption that
the most vulnerable places are also the hottest. In central Phoenix that assumption does not
hold: measured overnight exposure and the CDC/ATSDR index are uncorrelated at r = 0.004 across
132 tracts. Fifteen neighbourhoods, 52,091 people and 6,293 residents over 65, are severely
exposed overnight while sitting outside the band such a programme would target.

The user is whoever decides where a finite number of welfare checks go tonight, and which
cooling centres stay open past the evening. That is a city heat officer, an emergency
management team, or a public health department. The tool narrows a citywide problem to a list
of places. It does not claim to prove that any particular intervention works, and refuses to
when asked.

## Location and time period

Central Phoenix, Arizona. 134 census tracts across a 21.5 by 22.5 km area of interest.
One night: 15 August 2026, 00:00 to 06:00 local.

## How we used the Temperature API

One `POST /v1/heatmap` request with `analytic_type: "exceedance"`, `threshold: 28.0`,
`direction: "above"` and `filter_type: 2` over a 00:00 to 06:00 window, at 100 m granularity.
That returns 47,944 tiles, each carrying hours spent above 28 °C during the night.

Those tiles are joined to census tract polygons by an area-weighted overlap, which is the step
that turns a raster into something a city can act on. We tested that this aggregation does not
destroy the signal before relying on it: the ICC is 0.855, so 86% of the variance is between
tracts rather than within them, and the tract spread of 3.18 h retains most of the 3.70 h tile
spread.

Also used: `satellite` segmentation across 50 sampled tracts to test whether surface
composition explains overnight exposure. It does not, once position is controlled for, and that
negative result is reported rather than buried.

The processed layer is committed to the repo, so no page load calls the API. That is
deliberate: the API returned errors on three separate days during the sprint, and a demo whose
uptime depends on a vendor is a demo that fails during judging.

## AI tools disclosed

Claude (Opus 5, via Claude Code) wrote most of the code and most of the prose in the
repository, including the README, working from direction given in conversation. It also ran the
analysis scripts. The framing of the product around the divergence finding came out of that
conversation rather than from either party alone.

The humans chose the problem and the track, set the constraint that the tool must refuse
unsupported claims, ran the user testing that caused the interface to be rebuilt around the
agent, deployed and verified it, and rejected work that was wrong. Several errors were caught
by a human noticing something looked off, including a basemap that shipped with an
"API KEY REQUIRED" watermark across every tile, a chart whose top row disagreed with the
headline number, and an interface where two of five testers never found the agent at all.

OpenAI GPT-5.5 is the model the deployed agent runs on, with GPT-5-mini as a judge in the eval
suite.

No measurement is AI-generated. Every figure comes from the FortyGuard Temperature API, the
CDC/ATSDR SVI, or the US Census, and the figures quoted in the README were re-verified against
the raw API responses before publication.

## Code repo

<https://github.com/samranahmad09/hackathon-fortyguard>

Public, so no collaborator is strictly required, but `hackathon@fortyguard.com` is added
anyway. The README covers how to run it, what does not work yet, and a real API request with
its response. No key has ever been committed: `.env` is gitignored and a pre-commit hook blocks
key-shaped strings.

## Live demo URL

<https://respite.samtechpk.com>

No login, nothing to install, opens in a private window. Stays up through judging on a Hetzner
box behind Caddy, running as a scheduled task that restarts on boot.

## Demo video

Unlisted YouTube or Loom link, under three minutes, human voiceover over the live site.
Script and shot list: [`VIDEO.md`](VIDEO.md) and
[`Respite-video-script.pdf`](Respite-video-script.pdf).

---

## Before submitting, check

- [ ] `hackathon@fortyguard.com` added as a repo collaborator
- [ ] Live URL opens in a genuine private window, no login, map and charts render
- [ ] The agent answers a question there, and the tool list appears under the answer
- [ ] Video is **under 3:00**, has a voiceover, and shows the project actually working
- [ ] Video link is set to unlisted rather than private, and opens for a signed-out viewer
- [ ] `/health` shows `llm_key_configured: true` and the agent budget is not near its cap
- [ ] The OpenAI key has enough credit for two weeks of judging, 1 to 15 September
- [ ] No API key anywhere in the repo, the video, or this file

## After submitting

Judging runs 1 to 15 September, so the site has to survive two weeks unattended. Worth doing
once, deliberately: reboot the box and confirm `respite.samtechpk.com/health` comes back on its
own. That proves the scheduled task's `-AtStartup` trigger, which is otherwise untested until
the moment it matters.
