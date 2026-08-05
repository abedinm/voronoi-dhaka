#!/usr/bin/env python3
"""Two one-page documents for the defense, written to be read by a panel.

  outputs/kit/How_This_Thesis_Was_Done.pdf   the method as a short argument
  outputs/kit/Cheat_Sheet_Talk_and_Poster.pdf  what to say, both settings

Deliberately one page each. A note that runs to three pages is not a note, and
a cheat sheet you have to turn over is useless while you are standing up.

Run:  python build_defense_kit.py
"""

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (BaseDocTemplate, Frame, FrameBreak, KeepTogether,
                                PageTemplate, Paragraph, Spacer, Table, TableStyle)

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "outputs" / "kit"
OUT.mkdir(parents=True, exist_ok=True)


def _fonts() -> str:
    """Embed DejaVu; the base-14 faces are not embedded and lose bold in some
    viewers, which would silently flatten every emphasis in these documents."""
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
RULE = colors.HexColor("#C6D3DC")

ss = getSampleStyleSheet()
SCALE = 1.0
TITLE = ParagraphStyle("T", parent=ss["Heading1"], fontName=F + "-B", fontSize=15,
                       leading=17.5, textColor=NAVY, spaceAfter=1)
SUB = ParagraphStyle("S", parent=ss["BodyText"], fontName=F, fontSize=7.6,
                     leading=9.5, textColor=MUTED, spaceAfter=6)
H = ParagraphStyle("H", parent=ss["Heading2"], fontName=F + "-B", fontSize=9.5,
                   leading=11.5, textColor=TEAL, spaceBefore=7, spaceAfter=3)
B = ParagraphStyle("B", parent=ss["BodyText"], fontName=F, fontSize=8.4,
                   leading=11.6, textColor=INK, spaceAfter=4, alignment=TA_JUSTIFY)
SMALL = ParagraphStyle("SM", parent=B, fontSize=7.7, leading=10.2)
_ALL = (TITLE, SUB, H, B, SMALL)
_BASE = {s.name: (s.fontSize, s.leading, s.spaceBefore, s.spaceAfter) for s in _ALL}


def set_scale(f):
    global SCALE
    SCALE = f
    for s in _ALL:
        fs, ld, sb, sa = _BASE[s.name]
        s.fontSize, s.leading, s.spaceBefore, s.spaceAfter = fs * f, ld * f, sb * f, sa * f


def rule(w):
    t = Table([[""]], colWidths=[w], rowHeights=[0.5])
    t.setStyle(TableStyle([("LINEABOVE", (0, 0), (-1, -1), 1.1, NAVY)]))
    return t


def kv(rows, w, klabel=3.0, fs=7.7):
    fs *= SCALE
    ks = ParagraphStyle("k", parent=SMALL, fontSize=fs, leading=fs + 2.0,
                        textColor=NAVY, alignment=0)
    vs = ParagraphStyle("v", parent=SMALL, fontSize=fs, leading=fs + 2.0, alignment=0)
    t = Table([[Paragraph("<b>%s</b>" % a, ks), Paragraph(b, vs)] for a, b in rows],
              colWidths=[klabel * cm, w - klabel * cm])
    t.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.white, TINT]),
        ("LINEBELOW", (0, 0), (-1, -2), 0.25, RULE),
        ("LEFTPADDING", (0, 0), (-1, -1), 3), ("RIGHTPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING", (0, 0), (-1, -1), 2.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5)]))
    return t


def box(text, w, color=TEAL, fill=TINT, fs=8.0):
    fs *= SCALE
    t = Table([[Paragraph(text, ParagraphStyle("bx", parent=SMALL, fontSize=fs,
                                               leading=fs + 2.6, alignment=0))]],
              colWidths=[w])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), fill),
        ("BOX", (0, 0), (-1, -1), 0.9, color),
        ("LEFTPADDING", (0, 0), (-1, -1), 7), ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]))
    return KeepTogether([t, Spacer(1, 0.18 * cm)])


def bul(items):
    return [Paragraph("•&nbsp; " + i, SMALL) for i in items]


def page(name, title, subtitle, build):
    """One A4 page, shrinking type until it fits rather than guessing sizes."""
    path = OUT / name
    for sc in (1.0, 0.97, 0.94, 0.91, 0.88, 0.85, 0.82, 0.79, 0.76):
        set_scale(sc)
        left, right = build()
        doc = BaseDocTemplate(str(path), pagesize=A4,
                              leftMargin=1.2 * cm, rightMargin=1.2 * cm,
                              topMargin=1.1 * cm, bottomMargin=1.0 * cm,
                              title=title, author="Minhazul Abedin")
        W = doc.width
        head = [Paragraph(title, TITLE), Paragraph(subtitle, SUB), rule(W)]
        pad = dict(leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
        if right is None:
            frames = [Frame(doc.leftMargin, doc.bottomMargin, W, doc.height, id="o", **pad)]
            story = head + left
        else:
            gap, hh = 0.6 * cm, 1.7 * cm
            cw = (W - gap) / 2
            frames = [
                Frame(doc.leftMargin, doc.bottomMargin + doc.height - hh, W, hh, id="h", **pad),
                Frame(doc.leftMargin, doc.bottomMargin, cw, doc.height - hh, id="l", **pad),
                Frame(doc.leftMargin + cw + gap, doc.bottomMargin, cw, doc.height - hh,
                      id="r", **pad)]
            story = head + [FrameBreak()] + left + [FrameBreak()] + right
        doc.addPageTemplates([PageTemplate(id="p", frames=frames)])
        doc.build(story)
        if doc.page == 1:
            print(f"  {name}  1 page  (scale {sc:.2f})")
            return path
    raise SystemExit(f"{name}: does not fit on one page — cut content")


CW = (A4[0] - 2.4 * cm - 0.6 * cm) / 2
FW = A4[0] - 2.4 * cm
SUB_LINE = ("Providing Utility Services using Voronoi Diagrams — A Case Study for Dhaka "
            "City &nbsp;·&nbsp; Abedin · Rayta · Noman · Aziz &nbsp;·&nbsp; AIUB, "
            "Department of Computer Science")


# ═══════════════════════════════════════════ 1. how the thesis was done
def note():
    left = [
        Paragraph("The question", H),
        Paragraph(
            "Dhaka has grown far faster than the services its residents depend on, and no "
            "public study had measured how unevenly. We asked two things: <b>which parts "
            "of the city are worse served</b>, and <b>where should new facilities go</b> — "
            "across six services at once, not one at a time.", B),

        Paragraph("The data", H),
        Paragraph(
            "901 real facilities — hospitals, fire stations, water points, metro stations, "
            "bus stops, fuel stations — taken live from OpenStreetMap. Population from "
            "WorldPop's 1 km grid: 10.7 million residents. Nothing is synthetic. Duplicates "
            "within 150 m were removed and everything clipped to the city boundary; the "
            "drop from raw to cleaned counts is de-duplication, not data loss.", B),

        Paragraph("The method", H),
        Paragraph(
            "For each service, every point in Dhaka is assigned to its nearest facility. "
            "The result is an exact Voronoi partition: each border is the perpendicular "
            "bisector between two facilities, so the city is covered with no gaps and no "
            "overlaps. Distance is then measured from every point on a 250 m grid against "
            "a per-service threshold taken from planning practice — 2 km to a hospital, "
            "800 m to a bus stop, a four-minute fire response. All geometry is computed in "
            "metres, not degrees.", B),

        Paragraph("The decision that changed the result", H),
        box("Coverage was first measured by <b>land area</b>. That made the empty eastern "
            "fringe look worst — but almost nobody lives there. Re-measured by "
            "<b>population</b>, the finding reversed: dense Motijheel, 3.1 million "
            "residents, became the highest-impact target. Empty land does not need a "
            "hospital; crowded neighbourhoods do. This is the contribution.", CW, AMBER,
            colors.HexColor("#FBF1E6")),
    ]

    right = [
        Paragraph("Where new facilities should go", H),
        Paragraph(
            "Each proposed site is placed where it brings the most underserved people back "
            "within reach, then the calculation repeats. Candidate locations are screened "
            "first: water bodies, wetlands, rivers, canals and drains, reservoirs, "
            "landfills, cemeteries, military land and airport surfaces are excluded — about "
            "a fifth of the city — so no proposal lands somewhere nothing can be built.", B),

        Paragraph("Why the result can be trusted", H),
        kv([
            ("Against the standard method",
             "Our ranking agrees with 2SFCA, the measure the literature uses, most strongly "
             "where services are scarce. Where it differs we say so, and why."),
            ("Against the exact answer",
             "Our fast placement recovers essentially 100% of the exhaustive optimum, so the "
             "shortcut costs nothing."),
            ("Against real roads",
             "On Dhaka's 43,000-junction road network journeys run about 1.5× longer and the "
             "underserved share roughly doubles. We report this rather than hide it: our "
             "headline figures are optimistic."),
            ("Against our own choices",
             "Changing every distance threshold by ±25%, or weighting all six services "
             "equally, leaves the ranking of areas essentially unchanged."),
        ], CW, klabel=2.9),

        Paragraph("What is new", H),
        Paragraph(
            "The geometry is classical — Voronoi diagrams date from 1908. The contribution "
            "is the combination: six utilities assessed together rather than one; weighted "
            "by real population rather than land area; validated four independent ways; and "
            "released as software that rebuilds every figure, table and document from a "
            "single command. Every prior Dhaka study we found examines one service, "
            "measured by area.", B),

        box("<b>Everything here is reproducible.</b> One command regenerates the entire "
            "study from public data. Nothing in this thesis rests on a number that cannot "
            "be recomputed.", CW, GREEN, colors.HexColor("#EAF3ED")),
    ]
    return left, right


# ═══════════════════════════════════════════ 2. cheat sheet, talk and poster
def cheat():
    left = [
        Paragraph("THE TALK — 13 slides, one line each", H),
        kv([
            ("1 Title", "Assalamu alaikum. Topic, team. 15 s."),
            ("2 Problem", "Dhaka grew faster than its utilities. Nobody measured it."),
            ("3 Objectives", "Four objectives, four questions. Point, do not read."),
            ("4 Gap", "All prior work: one service, measured by land."),
            ("5 Data", "901 facilities · 10.7 M people · eight areas · all public."),
            ("6 How it works", "Nearest facility wins. Divide → measure → score → recommend."),
            ("7 Where services sit", "110 groups. Metro and fire sit furthest off-centre."),
            ("8 What each covers", "Six maps. Water 73% too far; hospitals 33%."),
            ("9 <b>Benefit ranking</b>", "<b>THE slide.</b> Land vs people flips it to Motijheel."),
            ("10 Recommendations", "3 fire stations → 946,000 people back in reach."),
            ("11 Three checks", "Usual method · exact answer · real roads."),
            ("12 Limitations", "Say them yourself, before you are asked."),
            ("13 Conclusion", "Contribution, software, one line of future work."),
        ], CW, klabel=2.75, fs=7.4),

        Paragraph("Pacing", H),
        kv([("15 min", "≈60 s a slide. Give 9 and 10 two minutes between them."),
            ("Cut to 10", "Compress 3, 4, 7. Move fast through 5. Never rush 9."),
            ("Running late", "Jump to 9, then 13. Those two carry the thesis.")],
           CW, klabel=2.2),

        Paragraph("Three rules", H),
        *bul([
            "<b>Never read a slide.</b> Say the one line, then stop.",
            "<b>Hand over by name</b> — &ldquo;Noman will cover the data.&rdquo;",
            "<b>Point at the figure.</b> A pause while pointing reads as confidence.",
        ]),
    ]

    right = [
        Paragraph("THE POSTER — 60 seconds, said standing", H),
        box("&ldquo;Dhaka has grown much faster than its utilities, and nobody had measured "
            "how unevenly. We took 901 real facilities across six services and worked out "
            "which part of the city is nearest to each one. Then we counted how many "
            "<b>people</b> — not how much land — fall outside a reasonable distance. That "
            "word is the point: measured by land, empty fields look like the crisis; "
            "measured by people, it is dense Motijheel, 3.1 million residents. Finally we "
            "computed where new facilities should go — three fire stations alone bring "
            "946,000 people back within reach.&rdquo;", CW, NAVY),

        Paragraph("Ten-second version", H),
        Paragraph(
            "&ldquo;We mapped which parts of Dhaka are too far from a hospital, fire station "
            "or water point — counted by <b>people</b>, not area — and worked out where to "
            "put new ones.&rdquo;", SMALL),

        Paragraph("The six questions you will actually get", H),
        kv([
            ("Why Voronoi, not circles?",
             "Circles overlap and leave gaps, and the radius is arbitrary. These cover the "
             "city exactly and need no radius."),
            ("Is volunteered map data reliable?",
             "It is a lower bound, and we say so. No public official registry exists for "
             "Dhaka — validating against one is our future work."),
            ("Motijheel has the most facilities. Why target it?",
             "It also has the most people: 3.1 M. What matters is facilities per person."),
            ("Straight lines, in Dhaka traffic?",
             "We measured it. On real roads journeys run ≈1.5× longer and the underserved "
             "share roughly doubles. Our figures are optimistic and we say so."),
            ("What is new? Voronoi is from 1908.",
             "The geometry is classical. New is the combination: six services, population "
             "weights, four checks, reproducible software."),
            ("Could you do another city?",
             "Yes — the pipeline takes a bounding box. Chattogram and Khulna are in our "
             "future work."),
        ], CW, klabel=3.4, fs=7.3),

        box("<b>If you do not know:</b> &ldquo;We did not test that — it is outside our "
            "scope. The way we would approach it is…&rdquo;  Never invent a number. Offer "
            "the table or the code instead of arguing from memory.", CW, GREEN,
            colors.HexColor("#EAF3ED")),
    ]
    return left, right


if __name__ == "__main__":
    print("defense kit ->", OUT)
    page("How_This_Thesis_Was_Done.pdf", "How This Thesis Was Done", SUB_LINE, note)
    page("Cheat_Sheet_Talk_and_Poster.pdf", "Cheat Sheet — The Talk and The Poster",
         SUB_LINE, cheat)
