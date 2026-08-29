"""Single source for the video script, emitting both the markdown and the PDF.

The script text was previously written twice, once in VIDEO.md and once in a PDF
generator, and the pacing table was hand-written. All three drifted within an
hour: the table claimed 525 spoken words when the text held 648, which is the
difference between a video that fits the five-minute cap and one that does not.

So the wording lives here once, the timings are counted from it rather than
asserted, and the build fails if the total runs outside the allowed window.

    .venv/Scripts/python deploy/make_video_script.py
"""
from __future__ import annotations

import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
MD = os.path.join(HERE, "VIDEO.md")
PDF = os.path.join(HERE, "Respite-video-script.pdf")

URL = "respite.samtechpk.com"

# The rules allow 3 to 5 minutes. Aim near the middle so neither a slow nor a
# brisk delivery falls out of the window.
MIN_S, MAX_S = 180, 300
TARGET_S = 255
WPM = 150.0          # a normal explaining pace, not a rush
SLOW, FAST = 130.0, 170.0


class Beat:
    def __init__(self, title, screen, lines, watch=0, after=None, note=None, paste=None):
        self.title = title
        self.screen = screen
        self.lines = lines          # spoken, in order
        self.watch = watch          # seconds spent watching the agent work
        self.after = after          # direction between spoken blocks
        self.note = note            # direction after the beat
        self.paste = paste          # text to paste on camera

    @property
    def words(self):
        return sum(len(re.sub(r"\s+", " ", l).strip().split()) for l in self.lines)

    @property
    def speech(self):
        return self.words / (WPM / 60.0)


BEATS = [
    Beat(
        "The stake",
        "the page as it loads. The headline and the three figures.",
        [
            "Somewhere in Phoenix tonight, someone in their seventies is lying awake in a "
            "bedroom that will not drop below twenty-eight degrees before dawn. No heatwave "
            "headline. Just a house that never cools.",

            "On the night we measured, eighteen neighbourhoods never dropped below that line. "
            "Not once, midnight to six. Fifty-eight thousand people live in them.",

            "No cool window, no recovery. That is why epidemiologists watch the overnight "
            "minimum, not the afternoon peak.",
        ],
        note='Do not say "urban heat island". Every other entry will.',
    ),
    Beat(
        "What we measured",
        "scroll to the map. Let the streets and place names show. Hover one tract.",
        [
            "Central Phoenix. A hundred and thirty-four neighbourhoods, from nearly "
            "forty-eight thousand readings a hundred metres apart, on the FortyGuard API.",

            "Coolest block to hottest is three hours and forty minutes of difference in one "
            "night. By day the same city varies by a degree and a half. Uniform in the "
            "afternoon, not after dark.",

            "And eighty-six percent of that variation is between neighbourhoods, not within "
            "them.",
        ],
    ),
    Beat(
        "The finding",
        "scroll to the scatter chart. Let it sit a second before speaking. Point at the flat "
        "cloud of dots.",
        [
            "Now the part that surprised us. Cities send heat help using a social "
            "vulnerability index, which assumes the most vulnerable places are also the "
            "hottest. Nobody checks it.",

            "Here is every tract. Vulnerability along the bottom, overnight heat up the side. "
            "If that held, these dots would climb left to right.",

            "The correlation is nought point nought nought four. No relationship at all, and "
            "we tried hard to break that result.",

            "So fifteen neighbourhoods, fifty-two thousand people, six thousand over "
            "sixty-five, are severely exposed and outside the band a vulnerability-led "
            "programme targets.",
        ],
        note="**Pause.** This is the moment the judges either get it or do not.",
    ),
    Beat(
        "What a city does on Monday",
        "scroll up to the console and paste the question below.",
        [
            "This is an agent, not a dashboard. Watch what it reads: the divergence, the "
            "tract list, the public health playbook, and its own limitations.",

            # Read off the screen, so single quotes inside the spoken double ones.
            # Nesting curly doubles inside curly doubles renders as a doubled
            # quote mark and reads like a typo.
            "\u2018Put crews and overnight cooling access in the severely exposed tracts, not "
            "only the high-vulnerability ones. SVI alone is the wrong dispatch map.\u2019",

            "Most cooling centres close in the evening, before the risk period even begins. So "
            "the output is not a heat map. It is which neighbourhoods to keep one open in "
            "tonight, and where to send a finite number of welfare checks.",
        ],
        watch=25,
        paste="What should the city actually do tonight, and in which neighbourhoods?",
        after="Say the first line while the tool list appears. Then stop talking, let the "
              "answer land, and read its opening sentence off the screen.",
    ),
    Beat(
        "What it refuses to do",
        "paste the second question.",
        [
            "Here is the part I most want you to see. Reasonable question, and we cannot "
            "answer it. We sampled fifty tracts to test whether pavement and canopy explain "
            "overnight heat. Control for where a tract sits, and they do not.",

            "So it refuses, even when you tell it you need a number for a business case.",

            "A model that invents a plausible figure under pressure is worse than no model, "
            "because someone will spend against it. Our limits are a tool the agent calls, not "
            "a line in a prompt, so they cannot be edited away. Sixteen tests, half written to "
            "bait exactly this. All sixteen passing.",
        ],
        watch=20,
        paste="How many hours of relief would a cool-pavement programme buy in\n"
              "tract 1085.02? I need a number for a business case.",
        after="Let the refusal render, then point at the list of sources underneath it.",
    ),
    Beat(
        "Our own number is soft",
        'open the disclosure titled "Why 18 tracts, and not 32".',
        [
            "One last thing, and it is what I would want to know if I were judging this. "
            "Eighteen is the strictest possible reading. Some tracts dipped below the line for "
            "a tenth of a second. Allow a minute of relief to still count as none, and it is "
            "thirty-two.",

            "We found that in our own data, published it rather than hiding it, and the agent "
            "hands you the whole curve if you ask.",
        ],
    ),
    Beat(
        "Close",
        "back to the top of the page.",
        [
            "Respite. Which blocks never cool down, who sleeps in them, what to do about it "
            "tonight, and where it does not know.",

            "Live now at respite dot samtechpk dot com. Ask it something hard.",
        ],
    ),
]

WORDS = sum(b.words for b in BEATS)
WATCH = sum(b.watch for b in BEATS)
SPEECH = WORDS / (WPM / 60.0)
TOTAL = SPEECH + WATCH


def mmss(s):
    s = int(round(s))
    return "%d:%02d" % (s // 60, s % 60)


def check():
    """Refuse to emit a script that breaks the rules it is written against."""
    problems = []
    for rate, label in ((SLOW, "slow"), (WPM, "normal"), (FAST, "brisk")):
        t = WORDS / (rate / 60.0) + WATCH
        if not (MIN_S <= t <= MAX_S):
            problems.append("at a %s pace (%g wpm) it runs %s, outside %s to %s"
                            % (label, rate, mmss(t), mmss(MIN_S), mmss(MAX_S)))
    return problems


NUMBERS = [
    ("Tracts with no relief", "18"),
    ("People in them", "58,176"),
    ("Tracts measured", "134"),
    ("Readings, at 100 m spacing", "47,944"),
    ("Spread, coolest to hottest block", "3.70 h in one night"),
    ("Afternoon spread, same area", "1.57 °C"),
    ("Variance between tracts (ICC)", "0.855, so 86%"),
    ("Exposure vs vulnerability", "r = 0.004, n = 132"),
    ("Severely exposed, outside the band", "15 tracts, 52,091 people, 6,293 over 65"),
    ("In the band, not severely exposed", "53 tracts, 212,101 people"),
    ("No-relief count by tolerance", "18 at zero, 32 under a minute"),
    ("Eval suite", "16 cases, 16 clean"),
    ("Land cover, controlling for position", "built t = +0.24, vegetation t = -1.46"),
]

AVOID = [
    ('**"AI-powered"** or **"leveraging LLMs"**. Show the agent refusing something instead.'),
    ('**"Urban heat island."** Everyone says it, and it means nothing to a judge by the fifth '
     'entry.'),
    ("Any intervention effect size. The tool refuses to give one; do not undercut it on camera."),
    ('**"We could add..."** Nobody scores a roadmap.'),
    ("Do not claim the cooling-centre and welfare-check actions are things *we* measured. They "
     "are the standard public health playbook, and the agent labels them that way on screen. "
     "Saying otherwise contradicts your own demo."),
    ("Do not read the judging criteria back at them."),
]

PREP = [
    "Open `https://%s` and let the opening briefing finish writing, then reload once so it "
    "comes from cache and appears instantly. A judge should not watch a spinner." % URL,
    "Check `/health` shows `llm_key_configured: true` and the budget is not near its limit.",
    "Close other tabs. Hide bookmarks. Turn off notifications.",
    "Have both questions copied somewhere you can paste from. Do not type them live.",
]


def build_markdown():
    o = []
    w = o.append
    w("# Video script and shot list\n")
    w("**Generated by [`make_video_script.py`](make_video_script.py). Edit the script there, "
      "not here, then re-run it.** It also builds "
      "[`Respite-video-script.pdf`](Respite-video-script.pdf), and it refuses to emit either "
      "if the running time falls outside the allowed window.\n")
    w("Every number below was read off the live site. If a figure on screen disagrees with "
      "this script, the site is right and this file is stale.\n")
    w("**Target %s.** The rules allow 3 to 5 minutes. This is %d spoken words, %s of speech at "
      "a normal pace, plus %d seconds watching the agent work. That watching is not dead air: "
      "it is the part that proves the thing is real.\n"
      % (mmss(TOTAL), WORDS, mmss(SPEECH), WATCH))
    w("**Recording notes.** The rules prefer a human speaking over the demo and explicitly "
      "disfavour AI narration and over-polished edits, so read this in your own voice and "
      "leave the small stumbles in. One take with a fluffed sentence beats four cuts. Screen "
      "record at 1920x1080, browser at default zoom, dark theme, window wide enough that the "
      "console and the three figures sit side by side.\n")
    w("**Before you hit record**\n")
    for p in PREP:
        w("- %s" % p)
    w("")
    w("The rubric is Impact and Relevance 40%, Technical Execution 35%, Innovation 15%, "
      "Communication 10%. So the finding and what a city does with it get the most time, and "
      "the interface tour gets almost none. Do not walk through features. Make one argument.\n")
    w("---\n")

    t = 0.0
    for b in BEATS:
        start = t
        t += b.speech + b.watch
        w("## %s to %s  %s\n" % (mmss(start), mmss(t), b.title))
        w("**On screen:** %s\n" % b.screen)
        if b.paste:
            w("```")
            w(b.paste)
            w("```\n")
        if b.after:
            w("%s\n" % b.after)
        for line in b.lines:
            w("> “%s”\n" % re.sub(r"\s+", " ", line).strip())
        if b.note:
            w("%s\n" % b.note)

    w("---\n")
    w("## Pacing\n")
    w("Counted from the script text, not estimated. Speech assumes %g words a minute.\n" % WPM)
    w("| Beat | Words | Speech | Watching | Ends at |")
    w("|---|---|---|---|---|")
    t = 0.0
    for b in BEATS:
        t += b.speech + b.watch
        w("| %s | %d | %s | %s | %s |"
          % (b.title, b.words, mmss(b.speech), mmss(b.watch) if b.watch else "", mmss(t)))
    w("| **Total** | **%d** | **%s** | **%s** | **%s** |\n"
      % (WORDS, mmss(SPEECH), mmss(WATCH), mmss(TOTAL)))
    w("At a slow %g words a minute this runs %s. At a brisk %g it runs %s. Both are inside the "
      "three to five minute window, so pace is not something to worry about on the day.\n"
      % (SLOW, mmss(WORDS / (SLOW / 60.0) + WATCH), FAST, mmss(WORDS / (FAST / 60.0) + WATCH)))
    w("**Running short?** Slow down rather than adding material. Most people read a script "
      "faster than they think, and the two waits while the agent works are easy to "
      "underestimate.\n")
    w("**Running long?** Cut the eighty-six percent line and the second half of the stake. Do "
      "not cut the refusal or the self-criticism: those are the two beats that separate this "
      "from every other entry.\n")

    w("## Numbers, verified against the live site\n")
    w("| Claim | Value |")
    w("|---|---|")
    for k, v in NUMBERS:
        w("| %s | %s |" % (k, v))
    w("")
    w("## Things not to say\n")
    for a in AVOID:
        w("- %s" % a)
    w("")
    w("## If a take goes wrong\n")
    w("The agent takes ten to twenty-five seconds, and the “what should the city do” "
      "answer is long. Let it run once. If you need to redo a later beat, cut back to the "
      "briefing already on screen rather than sitting through another full answer.\n")
    w("If the agent says you have used your allowance, you have hit the hourly cap from "
      "re-recording. It clears within the hour, or raise `RESPITE_LIMIT_PER_IP` on the box "
      "before a session.")
    return "\n".join(o) + "\n"


def build_pdf():
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_LEFT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import (BaseDocTemplate, Frame, KeepTogether, PageBreak,
                                    PageTemplate, Paragraph, Spacer, Table, TableStyle)

    INK = colors.HexColor("#14140f")
    INK2 = colors.HexColor("#52514e")
    INK3 = colors.HexColor("#77756d")
    UI = colors.HexColor("#0d7d8a")
    RULE = colors.HexColor("#dcdad4")
    BAND = colors.HexColor("#f2f1ec")
    ss = getSampleStyleSheet()

    def S(n, **kw):
        kw.setdefault("fontName", "Helvetica")
        kw.setdefault("textColor", INK2)
        kw.setdefault("alignment", TA_LEFT)
        return ParagraphStyle(n, parent=ss["Normal"], **kw)

    title = S("t", fontName="Helvetica-Bold", fontSize=21, leading=24, textColor=INK, spaceAfter=3)
    sub = S("s", fontSize=10.5, leading=14.5, spaceAfter=2)
    h2 = S("h", fontName="Helvetica-Bold", fontSize=13, leading=16, textColor=INK,
           spaceBefore=13, spaceAfter=5)
    timing = S("ti", fontName="Helvetica-Bold", fontSize=8.5, leading=11, textColor=UI,
               spaceBefore=15, spaceAfter=1)
    beat = S("b", fontName="Helvetica-Bold", fontSize=14.5, leading=18, textColor=INK, spaceAfter=6)
    say = S("y", fontSize=12.5, leading=18.5, textColor=INK, leftIndent=9, spaceAfter=9)
    direct = S("d", fontSize=9.3, leading=13.5, textColor=INK3, spaceAfter=7)
    note = S("n", fontSize=9.3, leading=13.5, spaceAfter=6)
    mono = S("m", fontName="Courier-Bold", fontSize=10, leading=14.5, textColor=INK,
             leftIndent=7, rightIndent=7)
    bullet = S("bu", fontSize=9.6, leading=13.8, leftIndent=11, bulletIndent=2, spaceAfter=3.5)
    cell = S("c", fontSize=9, leading=12)
    cellb = S("cb", fontName="Helvetica-Bold", fontSize=9, leading=12, textColor=INK)

    story = []
    W = 152 * mm

    def spoken(text):
        t = Table([[Paragraph(text, say)]], colWidths=[W])
        t.setStyle(TableStyle([("LINEBEFORE", (0, 0), (0, -1), 2.2, UI),
                               ("LEFTPADDING", (0, 0), (-1, -1), 9),
                               ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                               ("TOPPADDING", (0, 0), (-1, -1), 2),
                               ("BOTTOMPADDING", (0, 0), (-1, -1), 2)]))
        story.append(t)
        story.append(Spacer(1, 7))

    def box(text, style=mono):
        t = Table([[Paragraph(text, style)]], colWidths=[W])
        t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), BAND),
                               ("BOX", (0, 0), (-1, -1), 0.7, RULE),
                               ("LEFTPADDING", (0, 0), (-1, -1), 9),
                               ("RIGHTPADDING", (0, 0), (-1, -1), 9),
                               ("TOPPADDING", (0, 0), (-1, -1), 7),
                               ("BOTTOMPADDING", (0, 0), (-1, -1), 7)]))
        story.append(t)
        story.append(Spacer(1, 8))

    def table(rows, widths):
        body = [[Paragraph(str(c), cellb if i == 0 else cell) for c in r]
                for i, r in enumerate(rows)]
        t = Table(body, colWidths=widths, hAlign="LEFT")
        t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"),
                               ("LINEBELOW", (0, 0), (-1, -2), 0.5, RULE),
                               ("LINEBELOW", (0, 0), (-1, 0), 1.1, INK),
                               ("TOPPADDING", (0, 0), (-1, -1), 5),
                               ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                               ("LEFTPADDING", (0, 0), (-1, -1), 0),
                               ("RIGHTPADDING", (0, 0), (-1, -1), 8)]))
        story.append(t)
        story.append(Spacer(1, 9))

    story.append(Paragraph("Respite: video script", title))
    story.append(Paragraph(
        "FortyGuard Hackathon'26 &nbsp;&middot;&nbsp; live at %s &nbsp;&middot;&nbsp; "
        "target %s of a 3 to 5 minute window" % (URL, mmss(TOTAL)), sub))
    story.append(Paragraph(
        "Read the ruled lines aloud. Everything else is direction and is not spoken.", sub))
    story.append(Spacer(1, 10))

    story.append(Paragraph("Read this first", h2))
    story.append(Paragraph(
        "The rules prefer a human speaking over the demo and explicitly disfavour AI narration "
        "and over-polished edits. Read it in your own voice and leave the small stumbles in. "
        "One take with a fluffed sentence beats four cuts.", note))
    story.append(Paragraph(
        "This is %d spoken words, about %s of speech, plus %d seconds watching the agent work. "
        "That waiting is not dead air. It is the part that proves the thing is real."
        % (WORDS, mmss(SPEECH), WATCH), note))

    story.append(Paragraph("Before you hit record", h2))
    for p in PREP:
        story.append(Paragraph(re.sub(r"[`*]", "", p), bullet, bulletText="•"))

    story.append(Paragraph("What the video is for", h2))
    story.append(Paragraph(
        "Judging is Impact and Relevance 40%, Technical Execution 35%, Innovation 15%, "
        "Communication 10%. The finding and what a city does with it get the most time; the "
        "interface tour gets almost none. <b>Do not walk through features. Make one "
        "argument.</b>", note))
    story.append(PageBreak())

    # No hard page breaks between beats. An earlier version put them at fixed
    # indexes, which stopped matching the moment the script was shortened and
    # left two pages almost empty. Each beat is kept whole instead, so a beat
    # never splits across a page turn while someone is reading it aloud, and the
    # pages fill themselves.
    t = 0.0
    for b in BEATS:
        start = t
        t += b.speech + b.watch
        block = [Paragraph("%s to %s" % (mmss(start), mmss(t)), timing),
                 Paragraph(b.title, beat),
                 Paragraph("On screen: %s" % b.screen, direct)]
        story.append(KeepTogether(block))
        if b.paste:
            box(b.paste.replace("\n", "<br/>"))
        if b.after:
            story.append(Paragraph(b.after, direct))
        for line in b.lines:
            spoken(re.sub(r"\s+", " ", line).strip())
        if b.note:
            story.append(Paragraph(re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", b.note), direct))

    story.append(PageBreak())
    story.append(Paragraph("Reference", title))
    story.append(Paragraph(
        "Every figure was read off the live site. If something on screen disagrees with this "
        "page, the site is right and this page is stale.", sub))
    story.append(Spacer(1, 12))

    story.append(Paragraph("Pacing", h2))
    rows = [["Beat", "Words", "Speech", "Watching", "Ends at"]]
    tt = 0.0
    for b in BEATS:
        tt += b.speech + b.watch
        rows.append([b.title, str(b.words), mmss(b.speech),
                     mmss(b.watch) if b.watch else "", mmss(tt)])
    rows.append(["Total", str(WORDS), mmss(SPEECH), mmss(WATCH), mmss(TOTAL)])
    table(rows, [58 * mm, 18 * mm, 22 * mm, 26 * mm, 24 * mm])
    story.append(Paragraph(
        "At a slow %g words a minute this runs %s; at a brisk %g, %s. Both sit inside the three "
        "to five minute window, so pace is not something to worry about on the day. If you are "
        "short, slow down rather than adding material."
        % (SLOW, mmss(WORDS / (SLOW / 60.0) + WATCH), FAST, mmss(WORDS / (FAST / 60.0) + WATCH)),
        note))

    story.append(Paragraph("Numbers you may be asked about", h2))
    table([["Claim", "Value"]] + [list(r) for r in NUMBERS], [92 * mm, 60 * mm])

    story.append(Paragraph("Things not to say", h2))
    for a in AVOID:
        story.append(Paragraph(re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>",
                                      a.replace("*we*", "<i>we</i>")),
                               bullet, bulletText="•"))

    story.append(Paragraph("If a take goes wrong", h2))
    story.append(Paragraph(
        "The agent takes ten to twenty-five seconds, and the “what should the city "
        "do” answer is long. Let it run once. If you need to redo a later beat, cut back "
        "to the briefing already on screen rather than sitting through another full answer.",
        note))
    story.append(Paragraph(
        "If the agent says you have used your allowance, you have hit the hourly cap from "
        "re-recording. It clears within the hour, or Tehseen can raise it on the box before a "
        "session.", note))

    def furniture(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(INK3)
        canvas.drawString(24 * mm, 12 * mm, "Respite  ·  video script  ·  %s"
                          % mmss(TOTAL))
        canvas.drawRightString(186 * mm, 12 * mm, "Page %d" % doc.page)
        canvas.setStrokeColor(RULE)
        canvas.setLineWidth(0.5)
        canvas.line(24 * mm, 15.5 * mm, 186 * mm, 15.5 * mm)
        canvas.restoreState()

    doc = BaseDocTemplate(PDF, pagesize=A4, leftMargin=24 * mm, rightMargin=24 * mm,
                          topMargin=20 * mm, bottomMargin=20 * mm,
                          title="Respite: video script",
                          author="Respite, FortyGuard Hackathon'26",
                          subject="Script and shot list for the submission video")
    doc.addPageTemplates([PageTemplate(
        id="main",
        frames=[Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="body")],
        onPage=furniture)])
    doc.build(story)


if __name__ == "__main__":
    problems = check()
    print("  spoken words : %d" % WORDS)
    print("  speech       : %s at %g wpm" % (mmss(SPEECH), WPM))
    print("  watching     : %s" % mmss(WATCH))
    print("  total        : %s   (window %s to %s)" % (mmss(TOTAL), mmss(MIN_S), mmss(MAX_S)))
    for rate, label in ((SLOW, "slow"), (WPM, "normal"), (FAST, "brisk")):
        print("    %-6s %-7s %s" % (label, "%g wpm" % rate,
                                    mmss(WORDS / (rate / 60.0) + WATCH)))
    if problems:
        raise SystemExit("\n  REFUSING TO BUILD:\n    " + "\n    ".join(problems))
    open(MD, "w", encoding="utf-8", newline="\n").write(build_markdown())
    build_pdf()
    print("\n  wrote %s" % os.path.basename(MD))
    print("  wrote %s (%d bytes)" % (os.path.basename(PDF), os.path.getsize(PDF)))
