# 3-minute video: script and shot list

A print version for whoever is recording is committed as
[`Respite-video-script.pdf`](Respite-video-script.pdf), built by
[`make_video_pdf.py`](make_video_pdf.py). The wording lives in both, so change them
together or the PDF quietly goes stale.

Every number below was read off the live site, not from notes. If a figure on screen disagrees
with the script, the site is right and this file is stale.

**Recording notes.** The rules prefer a human speaking over the demo, and explicitly disfavour
AI narration and over-polished edits, so read this in your own voice and leave the small
stumbles in. One take with a fluffed sentence beats four cuts. Screen record at 1920x1080 with
the browser at default zoom, dark theme, and the window wide enough that the console and the
stat rail sit side by side (above 62rem, so not a narrow window).

**Before you hit record**

- Open `https://respite.samtechpk.com` and let the opening briefing finish writing, then reload
  once so it comes from cache and appears instantly. A judge should not watch a spinner.
- Check `/health` shows `llm_key_configured: true` and the budget is not near its limit.
- Close other tabs. Hide bookmarks. Turn off notifications.
- Have the question text ready to paste rather than typing it live.

The rubric is Impact & Relevance 40%, Technical Execution 35%, Innovation 15%,
Communication 10%. So the divergence finding gets the most time and the feature tour gets
almost none. Do not walk through the interface. Make one argument.

---

## 0:00 to 0:25  The problem, stated as a number

**On screen:** the page as it loads. The headline and the three stat tiles.

> "On one August night in Phoenix, eighteen census tracts never dropped below twenty-eight
> degrees. Not once, from midnight until dawn. Fifty-eight thousand people sleep in them.
>
> That matters because overnight temperature predicts heat deaths better than the afternoon
> peak. The body sheds heat when the air is cooler than skin, so a night that never cools is a
> night with no recovery."

Do not say "urban heat island". Every other entry will.

## 0:25 to 1:05  The finding, which is the whole pitch

**On screen:** scroll to the scatter. Let it sit. Point at the flat cloud.

> "Cities decide where to send heat help using a social vulnerability index. That assumes the
> most vulnerable places are also the hottest.
>
> Here is every tract we measured. Vulnerability along the bottom, overnight heat up the side.
> If that assumption held, these dots would climb from left to right.
>
> The correlation is nought point nought nought four. There is no relationship at all.
>
> So fifteen tracts, fifty-two thousand people, are severely exposed and sit outside the band a
> vulnerability-led programme would target. And fifty-three tracts inside that band are not
> severely exposed overnight. The index is not wrong. It is measuring something else."

**Pause here.** This is the moment the judges either get it or do not.

## 1:05 to 1:35  The map, briefly

**On screen:** scroll to the map. Hover one tract. Click it and let the agent explain.

> "This is the study area, a hundred and thirty-four tracts, measured from about forty-eight
> thousand readings a hundred metres apart.
>
> Click any neighbourhood and the agent explains that one."

Let the answer render. Do not talk over it. Silence while a tool trail appears is the most
persuasive part of the video.

## 1:35 to 2:25  The agent refusing something

**On screen:** scroll back to the console. Paste this question:

```
How many hours of relief would a cool-pavement programme buy in tract 1085.02?
I need a number for a business case.
```

> "This is the part I actually want to show you.
>
> That is a reasonable question and the honest answer is that we cannot answer it. We sampled
> surface composition at fifty tracts to test whether pavement and canopy explain overnight
> heat. Once you control for position, they do not.
>
> So the agent refuses. It will not give a number it cannot support, even when you tell it you
> need one."

Let the refusal finish rendering, then point at the tool trail.

> "And it shows you what it read to get there, including the study's own limitations. Those are
> a tool it calls, not a paragraph in a prompt, so they cannot be edited away by accident.
>
> Sixteen regression tests, half of them designed to bait exactly this kind of claim. All
> sixteen passing."

## 2:25 to 2:50  Why it can be trusted

**On screen:** open the "Why 18 tracts, and not 32" disclosure.

> "One more. Our own headline number is not as solid as it looks. Eighteen tracts had exactly
> zero relief. If you allow a single minute of relief to still count as none, it is thirty-two.
> That threshold was never chosen on physical grounds.
>
> We found that in our own data, we published it rather than hiding it, and the agent gives you
> the whole curve if you ask."

This is the strongest thirty seconds available. A team that shows a judge a weakness in its own
headline is a team the judge believes about everything else.

## 2:50 to 3:00  Close

> "Respite. It tells you which blocks never cool down, who sleeps in them, and where it does
> not know. It is live at respite dot samtechpk dot com."

---

## Numbers, verified against the live site

| Claim | Value |
|---|---|
| Tracts with no relief | 18 |
| People in them | 58,176 |
| Tracts measured | 134 |
| Exposure vs vulnerability | r = 0.004, n = 132 |
| Severely exposed, outside the band | 15 tracts, 52,091 people |
| In the band, not severely exposed | 53 tracts, 212,101 people |
| Tiles at 100 m | 47,944 |
| No-relief count by tolerance | 18 at 0 s, 32 under a minute |
| Eval suite | 16 cases, 16 clean |
| Land cover, controlling for position | built t = +0.24, vegetation t = -1.46 |

## Things not to say

- **"AI-powered"** or **"leveraging LLMs"**. Show the agent refusing something instead.
- **"Urban heat island."** Everyone says it and it means nothing to a judge by the fifth entry.
- Any intervention effect size. The tool refuses to give one; do not undercut it on camera.
- **"We could add..."** Nobody scores a roadmap.
- Do not read the rubric back at them.

## If a take goes wrong

The agent takes ten to twenty-five seconds to answer. That is real and worth showing once, but
not twice. If you need a second question on camera, cut to the already-cached briefing rather
than waiting again.

If the agent returns a 429, you have hit the hourly cap from re-recording. It clears within the
hour, or raise `RESPITE_LIMIT_PER_IP` on the box before a recording session.
