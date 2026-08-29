# Builds the video script as a PDF meant to be read while screen-recording, so
# the spoken lines have to be findable at a glance and clearly separable from the
# stage directions. Not a transcription of the markdown: the medium is different.
import io
import os

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    KeepTogether,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

OUT = r"C:\Users\samra\fortyguard-hackathon\deploy\Respite-video-script.pdf"

INK = colors.HexColor("#14140f")
INK2 = colors.HexColor("#52514e")
INK3 = colors.HexColor("#77756d")
UI = colors.HexColor("#0d7d8a")
ACCENT = colors.HexColor("#c2521f")
RULE = colors.HexColor("#dcdad4")
BAND = colors.HexColor("#f2f1ec")

ss = getSampleStyleSheet()


def S(name, **kw):
    kw.setdefault("fontName", "Helvetica")
    kw.setdefault("textColor", INK2)
    kw.setdefault("alignment", TA_LEFT)
    return ParagraphStyle(name, parent=ss["Normal"], **kw)


title = S("title", fontName="Helvetica-Bold", fontSize=21, leading=24,
          textColor=INK, spaceAfter=3)
sub = S("sub", fontSize=10.5, leading=14.5, textColor=INK2, spaceAfter=2)
h2 = S("h2", fontName="Helvetica-Bold", fontSize=13, leading=16,
       textColor=INK, spaceBefore=13, spaceAfter=5)
timing = S("timing", fontName="Helvetica-Bold", fontSize=8.5, leading=11,
           textColor=UI, spaceBefore=15, spaceAfter=1)
beat = S("beat", fontName="Helvetica-Bold", fontSize=14.5, leading=18,
         textColor=INK, spaceAfter=6)
# What he actually says. Bigger than everything else on purpose.
say = S("say", fontSize=12.5, leading=18.5, textColor=INK,
        leftIndent=9, spaceAfter=9)
# Stage directions, deliberately quieter than the lines.
direct = S("direct", fontSize=9.3, leading=13.5, textColor=INK3, spaceAfter=7)
note = S("note", fontSize=9.3, leading=13.5, textColor=INK2, spaceAfter=6)
mono = S("mono", fontName="Courier-Bold", fontSize=10, leading=14.5,
         textColor=INK, leftIndent=7, rightIndent=7, spaceBefore=3, spaceAfter=3)
bullet = S("bullet", fontSize=9.6, leading=13.8, textColor=INK2,
           leftIndent=11, bulletIndent=2, spaceAfter=3.5)
cell = S("cell", fontSize=9, leading=12, textColor=INK2)
cellb = S("cellb", fontName="Helvetica-Bold", fontSize=9, leading=12, textColor=INK)
foot = S("foot", fontSize=8, leading=10, textColor=INK3)

story = []


def spoken(text):
    """A line to read aloud, marked by a rule down its left edge."""
    t = Table([[Paragraph(text, say)]], colWidths=[152 * mm])
    t.setStyle(TableStyle([
        ("LINEBEFORE", (0, 0), (0, -1), 2.2, UI),
        ("LEFTPADDING", (0, 0), (-1, -1), 9),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    story.append(t)
    story.append(Spacer(1, 7))


def box(text, style=mono, fill=BAND, edge=RULE):
    t = Table([[Paragraph(text, style)]], colWidths=[152 * mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), fill),
        ("BOX", (0, 0), (-1, -1), 0.7, edge),
        ("LEFTPADDING", (0, 0), (-1, -1), 9),
        ("RIGHTPADDING", (0, 0), (-1, -1), 9),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))
    story.append(t)
    story.append(Spacer(1, 8))


def rows(data, widths, head=True):
    body = []
    for i, r in enumerate(data):
        st = cellb if (head and i == 0) else cell
        body.append([Paragraph(str(c), st) for c in r])
    t = Table(body, colWidths=widths, hAlign="LEFT")
    style = [
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LINEBELOW", (0, 0), (-1, -2), 0.5, RULE),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
    ]
    if head:
        style.append(("LINEBELOW", (0, 0), (-1, 0), 1.1, INK))
    t.setStyle(TableStyle(style))
    story.append(t)
    story.append(Spacer(1, 9))


# ------------------------------------------------------------------ page one
story.append(Paragraph("Respite: 3-minute video script", title))
story.append(Paragraph(
    "FortyGuard Hackathon'26 &nbsp;&middot;&nbsp; "
    "live at respite.samtechpk.com &nbsp;&middot;&nbsp; "
    "read the ruled lines aloud, everything else is direction", sub))
story.append(Spacer(1, 10))

story.append(Paragraph("Read this first", h2))
story.append(Paragraph(
    "The rules prefer a human speaking over the demo and explicitly disfavour AI narration and "
    "over-polished edits. Read it in your own voice and leave the small stumbles in. One take "
    "with a fluffed sentence beats four cuts.", note))

story.append(Paragraph("Before you hit record", h2))
for b in [
    "Open the site and let the opening briefing finish writing, then reload once so it comes "
    "from cache and appears instantly. A judge should not watch a spinner.",
    "Check respite.samtechpk.com/health shows <b>llm_key_configured: true</b> and the agent "
    "budget is not near its limit.",
    "Screen record at 1920x1080, browser at default zoom, dark theme, window wide enough that "
    "the console and the three numbers sit side by side.",
    "Close other tabs, hide bookmarks, turn off notifications.",
    "Have the question on page 3 copied ready to paste. Do not type it live.",
]:
    story.append(Paragraph(b, bullet, bulletText="\u2022"))

story.append(Spacer(1, 6))
story.append(Paragraph("What the video is for", h2))
story.append(Paragraph(
    "Judging is Impact and Relevance 40%, Technical Execution 35%, Innovation 15%, "
    "Communication 10%. So the finding gets the most time and the interface tour gets almost "
    "none. <b>Do not walk through the features. Make one argument.</b>", note))

story.append(PageBreak())

# ------------------------------------------------------------------ the beats
story.append(Paragraph("0:00 to 0:25", timing))
story.append(Paragraph("The problem, as a number", beat))
story.append(Paragraph("On screen: the page as it loads. The headline and the three figures.", direct))
spoken("On one August night in Phoenix, eighteen census tracts never dropped below "
       "twenty-eight degrees. Not once, from midnight until dawn. Fifty-eight thousand "
       "people sleep in them.")
spoken("That matters because overnight temperature predicts heat deaths better than the "
       "afternoon peak. The body sheds heat when the air is cooler than skin, so a night "
       "that never cools is a night with no recovery.")
story.append(Paragraph(
    "Do not say <b>urban heat island</b>. Every other entry will.", direct))

story.append(Paragraph("0:25 to 1:05", timing))
story.append(Paragraph("The finding. This is the pitch.", beat))
story.append(Paragraph("On screen: scroll to the scatter chart. Let it sit. Point at the flat cloud of dots.", direct))
spoken("Cities decide where to send heat help using a social vulnerability index. That "
       "assumes the most vulnerable places are also the hottest.")
spoken("Here is every tract we measured. Vulnerability along the bottom, overnight heat up "
       "the side. If that assumption held, these dots would climb from left to right.")
spoken("The correlation is nought point nought nought four. There is no relationship at all.")
spoken("So fifteen tracts, fifty-two thousand people, are severely exposed and sit outside "
       "the band a vulnerability-led programme would target. And fifty-three tracts inside "
       "that band are not severely exposed overnight. The index is not wrong. It is "
       "measuring something else.")
box("<font color='#c2521f'><b>Pause here.</b></font> This is the moment the judges either "
    "get it or they do not. Give it a beat before moving on.",
    style=S("pausebox", fontSize=9.6, leading=13.5, textColor=INK2))

story.append(PageBreak())

story.append(Paragraph("1:05 to 1:35", timing))
story.append(Paragraph("The map, briefly", beat))
story.append(Paragraph("On screen: scroll to the map. Hover one tract, then click it and let the agent explain.", direct))
spoken("This is the study area. A hundred and thirty-four tracts, measured from about "
       "forty-eight thousand readings a hundred metres apart.")
spoken("Click any neighbourhood and the agent explains that one.")
story.append(Paragraph(
    "Let the answer render. <b>Do not talk over it.</b> Silence while the list of sources "
    "appears is the most persuasive part of the video.", direct))

story.append(Paragraph("1:35 to 2:25", timing))
story.append(Paragraph("The agent refusing something", beat))
story.append(Paragraph("On screen: back to the console at the top. Paste this question:", direct))
box("How many hours of relief would a cool-pavement<br/>programme buy in tract 1085.02?<br/>"
    "I need a number for a business case.")
spoken("This is the part I actually want to show you.")
spoken("That is a reasonable question and the honest answer is that we cannot answer it. We "
       "sampled surface composition at fifty tracts to test whether pavement and canopy "
       "explain overnight heat. Once you control for position, they do not.")
spoken("So the agent refuses. It will not give a number it cannot support, even when you "
       "tell it you need one.")
story.append(Paragraph(
    "Let the refusal finish, then point at the list of sources underneath it.", direct))
spoken("And it shows you what it read to get there, including the study's own limitations. "
       "Those are a tool it calls, not a paragraph in a prompt, so they cannot be edited "
       "away by accident.")
spoken("Sixteen regression tests, half of them designed to bait exactly this kind of claim. "
       "All sixteen passing.")

story.append(PageBreak())

story.append(Paragraph("2:25 to 2:50", timing))
story.append(Paragraph("Why it can be trusted", beat))
story.append(Paragraph("On screen: open the disclosure titled \"Why 18 tracts, and not 32\".", direct))
spoken("One more. Our own headline number is not as solid as it looks. Eighteen tracts had "
       "exactly zero relief. If you allow a single minute of relief to still count as none, "
       "it is thirty-two. That threshold was never chosen on physical grounds.")
spoken("We found that in our own data, we published it rather than hiding it, and the agent "
       "gives you the whole curve if you ask.")
box("<font color='#c2521f'><b>This is the strongest thirty seconds available.</b></font> A "
    "team that shows a judge a weakness in its own headline is a team the judge believes "
    "about everything else. Do not cut this for time.",
    style=S("strongbox", fontSize=9.6, leading=13.5, textColor=INK2))

story.append(Paragraph("2:50 to 3:00", timing))
story.append(Paragraph("Close", beat))
spoken("Respite. It tells you which blocks never cool down, who sleeps in them, and where it "
       "does not know. It is live at respite dot samtechpk dot com.")

story.append(PageBreak())

# ------------------------------------------------------------------ reference
story.append(Paragraph("Reference", title))
story.append(Paragraph(
    "Every figure below was read off the live site. If something on screen disagrees with "
    "this page, the site is right and this page is stale.", sub))
story.append(Spacer(1, 12))

story.append(Paragraph("Numbers you may be asked about", h2))
rows([
    ["Claim", "Value"],
    ["Tracts with no relief", "18"],
    ["People living in them", "58,176"],
    ["Tracts measured", "134"],
    ["Exposure vs vulnerability", "r = 0.004, n = 132"],
    ["Severely exposed, outside the targeted band", "15 tracts, 52,091 people"],
    ["In the band, not severely exposed overnight", "53 tracts, 212,101 people"],
    ["Readings, at 100 m spacing", "47,944 tiles"],
    ["No-relief count by tolerance", "18 at zero, 32 under a minute"],
    ["Eval suite", "16 cases, 16 clean"],
    ["Land cover, controlling for position", "built t = +0.24, vegetation t = -1.46"],
], [92 * mm, 60 * mm])

story.append(Paragraph("Things not to say", h2))
for b in [
    "<b>AI-powered</b>, or <b>leveraging LLMs</b>. Show the agent refusing something instead.",
    "<b>Urban heat island.</b> Everyone says it, and it means nothing to a judge by the fifth entry.",
    "Any intervention effect size. The tool refuses to give one; do not undercut it on camera.",
    "<b>We could add...</b> Nobody scores a roadmap.",
    "Do not read the judging criteria back at them.",
]:
    story.append(Paragraph(b, bullet, bulletText="\u2022"))

story.append(Spacer(1, 6))
story.append(Paragraph("If a take goes wrong", h2))
story.append(Paragraph(
    "The agent takes ten to twenty-five seconds to answer. That is real and worth showing "
    "once, but not twice. If you need a second question on camera, cut to the briefing that "
    "is already on screen rather than waiting again.", note))
story.append(Paragraph(
    "If the agent says you have used your allowance, you have hit the hourly cap from "
    "re-recording. It clears within the hour. Tehseen can raise it on the server before a "
    "recording session.", note))


def furniture(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 7.5)
    canvas.setFillColor(INK3)
    canvas.drawString(24 * mm, 12 * mm, "Respite  \u00b7  3-minute video script")
    canvas.drawRightString(186 * mm, 12 * mm, "Page %d" % doc.page)
    canvas.setStrokeColor(RULE)
    canvas.setLineWidth(0.5)
    canvas.line(24 * mm, 15.5 * mm, 186 * mm, 15.5 * mm)
    canvas.restoreState()


doc = BaseDocTemplate(OUT, pagesize=A4,
                      leftMargin=24 * mm, rightMargin=24 * mm,
                      topMargin=20 * mm, bottomMargin=20 * mm,
                      title="Respite: 3-minute video script",
                      author="Respite, FortyGuard Hackathon'26",
                      subject="Script and shot list for the submission video")
frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="body")
doc.addPageTemplates([PageTemplate(id="main", frames=[frame], onPage=furniture)])
doc.build(story)

print("wrote", OUT, os.path.getsize(OUT), "bytes")
