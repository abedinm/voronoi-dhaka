#!/usr/bin/env python3
"""The spoken script for the defense — outputs/kit/Defense_Speech.pdf.

Written to be said aloud, not read silently: short sentences, no clause stacks,
and the numbers spelled the way you would say them. Roughly 15 minutes at a
normal speaking pace, with the timing marked so you can tell mid-talk whether
you are ahead or behind.

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
SAY = ParagraphStyle("SAY", parent=ss["BodyText"], fontName=F, fontSize=10.5,
                     leading=15.5, textColor=INK, spaceAfter=5)


def slide(n, title, minutes, cue, *lines):
    """One slide: heading, a stage direction, then what to say."""
    out = [Paragraph(f"Slide {n} &nbsp;·&nbsp; {title} "
                     f"<font size=9 color='#5B6B7A'>({minutes})</font>", SL),
           Paragraph("▸ " + cue, CUE)]
    out += [Paragraph(t, SAY) for t in lines]
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
              "Dhaka City &nbsp;·&nbsp; 13 slides, about 15 minutes &nbsp;·&nbsp; "
              "Abedin · Rayta · Noman · Aziz", SUB),

    box("<b>Read this out loud twice before the day.</b> It is written to be spoken, "
        "not recited — if a sentence feels wrong in your mouth, change it. The "
        "italic lines are stage directions, not speech.", NAVY),
]

story += slide(
    1, "Title", "0:00 – 0:20",
    "Stand still. Do not start until the room is quiet.",
    "Assalamu alaikum. Thank you for your time this morning.",
    "Our thesis is <b>Providing Utility Services using Voronoi Diagrams, with a Case "
    "Study for Dhaka City</b>. I am Minhazul Abedin, and with me are Zarin Tasnim "
    "Rayta, Abdullah Al Noman and Mehedi Hasan Aziz.",
)

story += slide(
    2, "The problem", "0:20 – 1:40",
    "Point at the dense centre of the map, then at the empty east.",
    "Dhaka has grown far faster than the services its people depend on.",
    "On this map you can see every hospital, fire station, water point, metro station, "
    "bus stop and fuel station we could find — nine hundred and one of them. Look at "
    "how they pile up in the centre, and how quickly they thin out toward the edges.",
    "Everyone in this city knows some areas are better served than others. But nobody "
    "had measured it. There is no public study that says which areas are worse off, or "
    "by how much.",
    "So we asked two questions. <b>Which parts of Dhaka are worse served — and where "
    "should new facilities go?</b>",
)

story += slide(
    3, "Objectives and research questions", "1:40 – 2:40",
    "Do not read all eight items. Point at the columns and say these three sentences.",
    "Our objectives and our research questions are on this slide.",
    "In short: build an exact model of which area each facility serves, measure how "
    "many people fall outside a reasonable distance, rank the areas, and recommend "
    "where to build.",
    "The four questions on the right map directly onto our results section, and I will "
    "answer each of them in turn.",
)

story += slide(
    4, "What others did — and what was missing", "2:40 – 4:00",
    "Walk the table quickly. Slow down on the green box — that is the whole slide.",
    "Voronoi diagrams themselves are old — Okabe's standard text is from 2000, and the "
    "placement problem we use goes back to Church and ReVelle in 1974.",
    "Closer to home, several studies have looked at access in Dhaka. Ahmed and "
    "colleagues studied emergency healthcare. Rahman and colleagues studied public "
    "transport. Alam and colleagues studied open space.",
    "Every one of them shares two limits. <b>Each looks at a single service. And each "
    "measures how much land is covered, rather than how many people are affected.</b>",
    "That is our gap. We assess six services together, and we weight them by "
    "population. As you will see on slide nine, that second change is what reverses "
    "the answer.",
)

story += slide(
    5, "Real, openly licensed data", "4:00 – 5:20",
    "Left side first, then the map. Say the areas are yours before anyone asks.",
    "All of our data is real and openly licensed. Nothing is simulated.",
    "The facilities come from OpenStreetMap — nine hundred and one of them after "
    "cleaning. The table shows what we searched for and what survived. Where the "
    "numbers drop, that is de-duplication: OpenStreetMap often maps one hospital three "
    "times, as a point, a building and a boundary. It is not data loss.",
    "Population comes from WorldPop, a free one-kilometre population map. Our study "
    "area holds about ten point seven million people.",
    "On the right are the eight areas we compare. I want to be clear that <b>these are "
    "our own analytical areas, not official wards</b> — we tried the official "
    "boundaries and found them incomplete. That is stated in our limitations.",
)

story += slide(
    6, "How it works", "5:20 – 7:00",
    "Say the top line slowly. Then the four steps. Point at the worked examples.",
    "Here is the method, and it rests on one idea.",
    "<b>A Voronoi cell is everywhere that is closer to one facility than to any "
    "other.</b> The border between two facilities is the line where you are exactly "
    "equally far from both.",
    "From that, four steps. First we divide — every point in Dhaka belongs to its "
    "nearest facility. Second we measure — from every point on a two hundred and fifty "
    "metre grid, how far is that facility? Third we score — each area gets a mark out "
    "of a hundred, based on how many of its <b>residents</b> are within reach. Fourth "
    "we recommend — we add the facility that helps the most people, and repeat.",
    "On the right are three worked examples we drew by hand first, to check the "
    "geometry. Twenty-nine automated tests confirm there are no gaps, no overlaps, and "
    "that every border sits exactly halfway between two facilities.",
)

story += slide(
    7, "Where services sit, and whether they sit well", "7:00 – 8:20",
    "Left map, then right panel. The offset numbers are the point.",
    "Two views of the same city.",
    "On the left, we grouped facilities that sit within one and a half kilometres of "
    "each other. Nine hundred and one facilities become a hundred and ten groups. The "
    "bigger the marker, the more facilities behind it — so you can see immediately "
    "where each service has real hubs.",
    "On the right, a different question: <b>is each facility in the middle of the area "
    "it covers?</b> The filled dot is the facility. The ring is the centre of its area. "
    "A long line between them means it serves its area from one edge.",
    "Bus stops and hospitals are well centred — about two hundred metres off. Metro "
    "stations and fire stations are not: one point six kilometres and one point three. "
    "Those are the sparse services, and that is a second piece of evidence pointing at "
    "the same conclusion.",
)

story += slide(
    8, "What each service covers", "8:20 – 9:40",
    "Point at bus stops, then at fire stations. The contrast does the work.",
    "Here are all six services, each in its own colour.",
    "Look at the difference in scale. Three hundred and fourteen bus stops divide the "
    "centre finely. Twenty-two fire stations cover areas ten times larger.",
    "The bars on the right show the share of the city that is too far from each "
    "service. Water points are worst at seventy-three per cent. Metro stations, "
    "sixty-seven. Hospitals look best, at thirty-three.",
    "Hold on to that last one, because the next slide changes it.",
)

story += slide(
    9, "Which areas benefit most", "9:40 – 11:20",
    "SLOW DOWN. This is the contribution. Pause after 'reversed'.",
    "This is our headline finding.",
    "We first measured coverage by <b>land area</b>. Measured that way, the empty "
    "eastern edge of the city looked worst. But almost nobody lives there.",
    "So we measured it again by <b>population</b>. And the answer reversed.",
    "Measured by people, the real problem is dense old Dhaka. Motijheel has three "
    "point one million residents and scores only sixty-eight. Mirpur, at ninety-two, "
    "is our best-served area; Bashundhara, at fifty-five, our worst.",
    "<b>Empty land does not need a hospital. Crowded neighbourhoods do.</b> That single "
    "change — counting people instead of land — is the contribution of this thesis, "
    "and it is why our recommendations differ from what a conventional analysis would "
    "produce.",
)

story += slide(
    10, "Where new facilities should go", "11:20 – 12:30",
    "Point at the red stars. End on the 946,000.",
    "So where should new facilities go?",
    "The red stars are our proposed sites. Each one is placed where it brings the most "
    "underserved people back within reach, and then the calculation repeats.",
    "We also screen the sites. Water bodies, wetlands, rivers, canals and drains, "
    "reservoirs, landfills, cemeteries, military land and airport surfaces are all "
    "excluded — about a fifth of the city. A site that scores well is no use if nothing "
    "can be built on it.",
    "The effect is concrete. <b>Three new fire stations alone bring nine hundred and "
    "forty-six thousand people back within reach.</b>",
)

story += slide(
    11, "Three ways we checked our answer", "12:30 – 13:40",
    "Volunteer the road-network result. Do not wait to be asked.",
    "We checked our answer three ways.",
    "First, against the method other researchers use. Our ranking broadly agrees with "
    "it, most strongly where services are scarce. Where it disagrees, we say so, and "
    "we explain why.",
    "Second, against the perfect answer. Our fast method for choosing sites finds "
    "essentially the same places as working through every possibility. So the shortcut "
    "costs us nothing.",
    "Third, against real roads. Straight lines ignore rivers and buildings. On Dhaka's "
    "real road network, journeys run about one and a half times longer, and <b>the "
    "number of people who are too far roughly doubles</b>. I want to be direct about "
    "that: it means our headline figures are optimistic, and we report it rather than "
    "hide it.",
)

story += slide(
    12, "What the model does not do", "13:40 – 14:30",
    "Say these plainly and without apology. Then pivot to future work.",
    "There are things this model does not do, and I would rather state them myself.",
    "We measured straight-line distance, not travel time. Our map data is volunteered, "
    "so our facility counts are a minimum, not a complete list. We did not count "
    "facility size — a small clinic counts the same as a large hospital. And our eight "
    "areas are our own, not official boundaries.",
    "Each of those has a matching next step: traffic-aware travel time on the road "
    "network, weighting each facility by its capacity using official records, and a "
    "finer population grid.",
)

story += slide(
    13, "What the study delivers", "14:30 – 15:00",
    "Stop. Do not keep talking into the questions.",
    "To close.",
    "We have produced a map of who is served and who is not, across six services at "
    "once. A ranking of areas by the people affected, not by empty land — the first "
    "for Dhaka that we know of. And a list of where to build, with the number of people "
    "each site would help.",
    "All of it is reproducible. One command rebuilds every figure, table and document "
    "in this thesis from public data.",
    "<b>That concludes our presentation. Thank you — we are happy to take your "
    "questions.</b>",
)

story += [
    Spacer(1, 0.4 * cm),
    box("<b>If you are running late:</b> the two slides that carry the thesis are "
        "<b>9</b> (people, not land) and <b>13</b> (what it delivers). Everything else "
        "can be compressed. Never rush slide 9.", AMBER, colors.HexColor("#FBF1E6")),
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
