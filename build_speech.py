#!/usr/bin/env python3
"""The spoken script for the defense — outputs/kit/Defense_Speech.pdf.

Written to be said aloud, not read silently: short sentences, no clause stacks,
and the numbers spelled the way you would say them.

Budgeted for EIGHT minutes across thirteen slides — about thirty-seven seconds
each. Most slides get one or two sentences; slide 9 carries the contribution and
is given more than double the average. The timings are cumulative so you can tell
mid-talk whether you are ahead or behind.

Run:  python build_speech.py
"""

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (KeepTogether, PageBreak, Paragraph,
                                SimpleDocTemplate, Spacer, Table, TableStyle)

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "outputs" / "kit" / "Defense_Speech.pdf"
OUT.parent.mkdir(parents=True, exist_ok=True)


def _fonts() -> str:
    import matplotlib
    from reportlab.lib.fonts import addMapping
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    d = Path(matplotlib.get_data_path()) / "fonts" / "ttf"
    for nm, fn in {"DJV": "DejaVuSans.ttf", "DJV-B": "DejaVuSans-Bold.ttf",
                   "DJV-I": "DejaVuSans-Oblique.ttf",
                   "DJV-BI": "DejaVuSans-BoldOblique.ttf"}.items():
        pdfmetrics.registerFont(TTFont(nm, str(d / fn)))
    for b, i, nm in [(0, 0, "DJV"), (1, 0, "DJV-B"), (0, 1, "DJV-I"), (1, 1, "DJV-BI")]:
        addMapping("DJV", b, i, nm)
    return "DJV"


F = _fonts()
NAVY = colors.HexColor("#0E2A47")
TEAL = colors.HexColor("#1C7293")
AMBER = colors.HexColor("#B4650F")
GREEN = colors.HexColor("#2E6B45")
INK = colors.HexColor("#1C2B39")
MUTED = colors.HexColor("#5B6B7A")
TINT = colors.HexColor("#EDF3F7")

ss = getSampleStyleSheet()
H1 = ParagraphStyle("H1", parent=ss["Heading1"], fontName=F + "-B", fontSize=17,
                    leading=20, textColor=NAVY, spaceAfter=2)
SUB = ParagraphStyle("SUB", parent=ss["BodyText"], fontName=F, fontSize=8.5,
                     leading=11, textColor=MUTED, spaceAfter=10)
SL = ParagraphStyle("SL", parent=ss["Heading2"], fontName=F + "-B", fontSize=11,
                    leading=13, textColor=TEAL, spaceBefore=13, spaceAfter=1)
CUE = ParagraphStyle("CUE", parent=ss["BodyText"], fontName=F + "-I", fontSize=8.5,
                     leading=11, textColor=AMBER, spaceAfter=4)
SAY = ParagraphStyle("SAY", parent=ss["BodyText"], fontName=F, fontSize=12,
                     leading=20, textColor=INK, spaceAfter=7)


SPEAKER = ParagraphStyle("SPK", parent=ss["BodyText"], fontName=F + "-B",
                         fontSize=13, leading=16, textColor=colors.white,
                         spaceAfter=0)


def part(name, slides, window, colour):
    """A band marking where one speaker takes over."""
    t = Table([[Paragraph(f"{name}", SPEAKER),
                Paragraph(f"<font color='#FFFFFF'>slides {slides} &nbsp;·&nbsp; "
                          f"{window}</font>",
                          ParagraphStyle("w", parent=SPEAKER, fontSize=10.5,
                                         alignment=2))]],
              colWidths=[(A4[0] - 3.4 * cm) * 0.55, (A4[0] - 3.4 * cm) * 0.45])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colour),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 9), ("RIGHTPADDING", (0, 0), (-1, -1), 9),
        ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
    return [Spacer(1, 0.35 * cm), t, Spacer(1, 0.12 * cm)]


def handover(to):
    """The line that ends a speaker's part. Said out loud."""
    return [Paragraph(f"<b>&ldquo;{to}&rdquo;</b>",
                      ParagraphStyle("ho", parent=SAY, fontSize=10,
                                     textColor=GREEN, spaceBefore=3))]


def _sentences(text):
    """Split a spoken line into one sentence per printed line.

    A nervous speaker runs out of air inside long sentences. One sentence per
    line means every full stop is a place to breathe, and the eye never has to
    find its way back into the middle of a clause. Fragments whose bold tags do
    not balance are left joined rather than broken."""
    import re
    parts, buf = [], ""
    for piece in re.split(r'(?<=[.?]) +(?=[A-Z<])', text):
        buf = (buf + " " + piece).strip() if buf else piece
        if buf.count("<b>") == buf.count("</b>"):
            parts.append(buf)
            buf = ""
    if buf:
        parts.append(buf)
    return parts


def slide(n, title, minutes, cue, *lines):
    """One slide: heading, a stage direction, then what to say."""
    out = [Paragraph(f"Slide {n} &nbsp;·&nbsp; {title} "
                     f"<font size=9 color='#5B6B7A'>({minutes})</font>", SL),
           Paragraph("▸ " + cue, CUE)]
    for t in lines:
        out += [Paragraph(x, SAY) for x in _sentences(t)]
    return out


def box(text, color=TEAL, fill=TINT):
    t = Table([[Paragraph(text, ParagraphStyle("bx", parent=SAY, fontSize=9.5,
                                               leading=13))]],
              colWidths=[A4[0] - 3.4 * cm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), fill),
        ("BOX", (0, 0), (-1, -1), 0.9, color),
        ("LEFTPADDING", (0, 0), (-1, -1), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
    return KeepTogether([t, Spacer(1, 0.2 * cm)])


story = [
    Paragraph("Defense Speech", H1),
    Paragraph("Providing Utility Services using Voronoi Diagrams — A Case Study for "
              "Dhaka City &nbsp;·&nbsp; 13 slides in 8 minutes &nbsp;·&nbsp; "
              "Abedin · Rayta · Noman · Aziz", SUB),

    box("<b>Before you start.</b> Stand still. Feet apart. Breathe out slowly and "
        "fully — longer out than in, three times. A slow breath out is what settles "
        "a tight chest; breathing in harder makes it worse.<br/><br/>"
        "<b>One sentence per line.</b> Every full stop below is a place to stop and "
        "breathe. Take it. A pause sounds calm and considered from the other side of "
        "the room — it never sounds like hesitation.<br/><br/>"
        "<b>If you lose your place</b>, stop, look at the slide, and say "
        "&ldquo;so — what this shows is…&rdquo;. That buys you four seconds and "
        "reads as deliberate. Nobody in the room knows what you meant to say next.",
        NAVY),

    Table([[Paragraph(f"<b>{n}</b>", ParagraphStyle("t1", parent=SAY, fontSize=10)),
            Paragraph(sl, ParagraphStyle("t2", parent=SAY, fontSize=10)),
            Paragraph(w, ParagraphStyle("t3", parent=SAY, fontSize=10)),
            Paragraph(r, ParagraphStyle("t4", parent=SAY, fontSize=10,
                                        textColor=MUTED))]
           for n, sl, w, r in [
               ("Rayta", "1 – 4", "0:00 – 2:05", "opens; problem and the gap"),
               ("Minhazul", "5 – 6", "2:05 – 3:35", "the data, and how the method works"),
               ("Noman", "7 – 9", "3:35 – 5:55", "what we found, and the key finding"),
               ("Mehedi", "10 – 13", "5:55 – 8:00", "recommendations, checks, close"),
           ]],
          colWidths=[3.0 * cm, 2.0 * cm, 3.0 * cm, 8.4 * cm],
          style=TableStyle([
              ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.white, TINT]),
              ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
              ("LEFTPADDING", (0, 0), (-1, -1), 6),
              ("TOPPADDING", (0, 0), (-1, -1), 3),
              ("BOTTOMPADDING", (0, 0), (-1, -1), 3)])),
]

story += part("Zarin Tasnim Rayta", "1 – 4", "0:00 – 2:05", NAVY)

story += slide(
    1, "Title", "0:00 – 0:15",
    "Stand still. Do not start until the room is quiet.",
    "Assalamu alaikum. Our thesis is <b>Providing Utility Services using Voronoi "
    "Diagrams, with a Case Study for Dhaka City</b>. I am Zarin Tasnim Rayta, and with "
    "me are Minhazul Abedin, Abdullah Al Noman and Mehedi Hasan Aziz. We will each take "
    "a part.",
)

story += slide(
    2, "The problem", "0:15 – 1:00",
    "Point at the dense centre, then at the empty east.",
    "Dhaka has grown far faster than the services its people depend on.",
    "This map shows nine hundred and one facilities across six services. They pile up "
    "in the centre and thin out at the edges.",
    "Everyone knows some areas are better served. Nobody had measured it. So we asked: "
    "<b>which parts of Dhaka are worse served, and where should new facilities go?</b>",
)

story += slide(
    3, "Objectives and research questions", "1:00 – 1:25",
    "Do not read the items. One sentence, then move.",
    "Our objectives are here: model which area each facility serves, measure how many "
    "people fall outside a reasonable distance, then recommend where to build.",
)

story += slide(
    4, "What others did — and what was missing", "1:25 – 2:05",
    "Do not walk the table. Go straight to the green box.",
    "Several studies have looked at access in Dhaka — emergency healthcare, public "
    "transport, open space.",
    "They share two limits. <b>Each looks at one service. And each measures how much "
    "land is covered, rather than how many people are affected.</b> That is our gap.",
)

story += handover("Minhazul will take you through our data and method.")
story += part("Minhazul Abedin", "5 – 6", "2:05 – 3:35", TEAL)

story += slide(
    5, "Real, openly licensed data", "2:05 – 2:45",
    "Numbers, then the areas. Say the areas are yours before anyone asks.",
    "All our data is real. None of it is made up.",
    "Nine hundred and one facilities, from OpenStreetMap.",
    "Ten point seven million residents, from WorldPop.",
    "On the right are the eight areas we compare.",
    "<b>They are our own areas, not official wards.</b> That is in our limitations.",
)

story += slide(
    6, "How it works", "2:45 – 3:35",
    "Say the definition slowly. Then the four steps, briskly.",
    "The method rests on one idea.",
    "<b>Every point in the city belongs to its nearest facility.</b>",
    "Each border sits exactly halfway between two of them.",
    "From that, four steps.",
    "One — divide the city that way.",
    "Two — measure how far each point is from its facility.",
    "Three — score each area by how many of its <b>residents</b> are within reach.",
    "Four — add the facility that helps the most people, then repeat.",
    "Twenty-nine automated tests confirm no gaps and no overlaps.",
)

story += handover("Noman will now show what we found.")
story += part("Abdullah Al Noman", "7 – 9", "3:35 – 5:55", GREEN)

story += slide(
    7, "Where services sit, and whether they sit well", "3:35 – 4:10",
    "One sentence each side. The offsets are the point.",
    "On the left, facilities within one and a half kilometres are grouped — nine "
    "hundred and one become a hundred and ten hubs.",
    "On the right, a different question: is each facility in the middle of what it "
    "covers? Bus stops and hospitals are well centred. Metro and fire stations sit over "
    "a kilometre off — and those are exactly the sparse services.",
)

story += slide(
    8, "What each service covers", "4:10 – 4:45",
    "Point at bus stops, then fire stations. Two numbers only.",
    "All six services, each in its own colour. Three hundred and fourteen bus stops "
    "divide the centre finely; twenty-two fire stations cover areas ten times larger.",
    "Water points are worst — seventy-three per cent of the city too far. Hospitals look "
    "best at thirty-three. Hold on to that, because the next slide changes it.",
)

story += slide(
    9, "Which areas benefit most", "4:45 – 5:55",
    "SLOW DOWN. This is the contribution. Pause after 'reversed'.",
    "This is our headline finding.",
    "We first measured coverage by <b>land area</b>. Measured that way, the empty "
    "eastern edge looked worst — but almost nobody lives there.",
    "So we measured again by <b>population</b>. And the answer reversed.",
    "The real problem is dense old Dhaka. Motijheel has three point one million "
    "residents and scores only sixty-eight.",
    "<b>Empty land does not need a hospital. Crowded neighbourhoods do.</b> That one "
    "change — counting people instead of land — is the contribution of this thesis.",
)

story += handover("Mehedi will finish with our recommendations.")
story += part("Mehedi Hasan Aziz", "10 – 13", "5:55 – 8:00", AMBER)

story += slide(
    10, "Where new facilities should go", "5:55 – 6:40",
    "Point at the red stars. End on the number.",
    "The red stars are our proposed sites, each placed where it brings the most "
    "underserved people back within reach. Water, wetland and drainage are excluded — "
    "a site is no use if nothing can be built on it.",
    "<b>Three new fire stations alone bring nine hundred and forty-six thousand people "
    "back within reach.</b>",
)

story += slide(
    11, "Three ways we checked our answer", "6:40 – 7:15",
    "Volunteer the road result. Do not wait to be asked.",
    "Three checks. Our ranking agrees with the standard method, and our fast placement "
    "matches the exhaustive best answer.",
    "And on real roads, <b>the number of people too far roughly doubles</b>. Our "
    "headline figures are optimistic, and we say so rather than hide it.",
)

story += slide(
    12, "What the model does not do", "7:15 – 7:35",
    "Plainly, without apology. Do not elaborate.",
    "Straight-line distance, not travel time. Volunteered map data, so our counts are a "
    "minimum. Facility size not counted. Each has a matching next step on the slide.",
)

story += slide(
    13, "What the study delivers", "7:35 – 8:00",
    "Stop. Do not keep talking into the questions.",
    "We deliver a map of who is served, a ranking by people rather than by land, and a "
    "list of where to build — all reproducible from one command.",
    "<b>Thank you. We are happy to take your questions.</b>",
)

story += [
    Spacer(1, 0.4 * cm),
    box("<b>If you fall behind:</b> slides 3, 4 and 12 can each be cut to a single "
        "sentence without losing anything a board needs. <b>Never rush slide 9</b> — it "
        "is the only slide that cannot be recovered later. If you reach slide 9 by five "
        "minutes you are on time.", AMBER, colors.HexColor("#FBF1E6")),
    box("<b>When questions start:</b> let them finish, pause for one beat, then answer. "
        "If you do not know, say &ldquo;we did not test that — it is outside our scope, "
        "and the way we would approach it is…&rdquo;. Never invent a number. The "
        "statistics an examiner might name — 2SFCA, Gini, Moran's I, Spearman — are on "
        "your printed detail card.", GREEN, colors.HexColor("#EAF3ED")),
]

SimpleDocTemplate(str(OUT), pagesize=A4,
                  leftMargin=1.7 * cm, rightMargin=1.7 * cm,
                  topMargin=1.4 * cm, bottomMargin=1.4 * cm,
                  title="Defense Speech", author="Minhazul Abedin").build(story)
print("wrote", OUT)
