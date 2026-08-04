#!/usr/bin/env python3
"""Three single-page quick-reference cards.

Run:  python build_quick_cards.py
  ->  outputs/Card_1_Thesis_Report.pdf     (the report, one page)
      outputs/Card_2_Presentation.pdf      (slide-by-slide, shorter)
      outputs/Card_3_Poster.pdf            (standing at the poster)

Each card must land on exactly one A4 page. Rather than hand-tuning font sizes
against the content, `card()` rebuilds at progressively smaller scales until the
page count is 1, and raises if even the smallest scale overflows.
"""

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (BaseDocTemplate, Frame, FrameBreak, KeepTogether,
                                PageTemplate, Paragraph, Spacer, Table, TableStyle)

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "outputs"


def _register_fonts() -> str:
    """Embed a real font family.

    The base-14 Helvetica is not embedded, so viewers that substitute it (poppler,
    some print drivers) collapse Bold and Oblique onto the regular face and <b>/<i>
    silently vanish. DejaVu also covers the glyphs we use (arrows, rho, circled
    digits, curly quotes) that WinAnsi cannot encode."""
    import matplotlib
    from reportlab.lib.fonts import addMapping
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    d = Path(matplotlib.get_data_path()) / "fonts" / "ttf"
    for name, fn in {"DJV": "DejaVuSans.ttf", "DJV-B": "DejaVuSans-Bold.ttf",
                     "DJV-I": "DejaVuSans-Oblique.ttf",
                     "DJV-BI": "DejaVuSans-BoldOblique.ttf"}.items():
        pdfmetrics.registerFont(TTFont(name, str(d / fn)))
    for bold, italic, name in [(0, 0, "DJV"), (1, 0, "DJV-B"),
                               (0, 1, "DJV-I"), (1, 1, "DJV-BI")]:
        addMapping("DJV", bold, italic, name)
    return "DJV"


FONT = _register_fonts()

NAVY = colors.HexColor("#0E2A47")
TEAL = colors.HexColor("#1C7293")
AMBER = colors.HexColor("#B4650F")
GREEN = colors.HexColor("#2E6B45")
INK = colors.HexColor("#1C2B39")
MUTED = colors.HexColor("#5B6B7A")
TINT = colors.HexColor("#EDF3F7")
RULE = colors.HexColor("#C6D3DC")
CREAM = colors.HexColor("#FBF1E6")
MINT = colors.HexColor("#EAF3ED")

ss = getSampleStyleSheet()
SCALE = 1.0                      # set by the auto-fit loop in card()

TITLE = ParagraphStyle("T", parent=ss["Heading1"], fontName=FONT + "-B", fontSize=14,
                       leading=16.5, textColor=NAVY, spaceAfter=1)
SUB = ParagraphStyle("S", parent=ss["BodyText"], fontName=FONT, fontSize=7.2,
                     leading=9, textColor=MUTED, spaceAfter=5)
H = ParagraphStyle("H", parent=ss["Heading2"], fontName=FONT + "-B", fontSize=9,
                   leading=11, textColor=TEAL, spaceBefore=6, spaceAfter=2.5)
B = ParagraphStyle("B", parent=ss["BodyText"], fontName=FONT, fontSize=7.6,
                   leading=10.2, textColor=INK, spaceAfter=3)
SMALL = ParagraphStyle("SM", parent=B, fontSize=7.1, leading=9.4)
LEAD = ParagraphStyle("L", parent=B, fontSize=8.4, leading=11.4, textColor=NAVY)

_STYLES = (TITLE, SUB, H, B, SMALL, LEAD)
_BASE = {s.name: (s.fontSize, s.leading, s.spaceBefore, s.spaceAfter) for s in _STYLES}


def set_scale(f: float) -> None:
    global SCALE
    SCALE = f
    for s in _STYLES:
        fs, ld, sb, sa = _BASE[s.name]
        s.fontSize, s.leading = fs * f, ld * f
        s.spaceBefore, s.spaceAfter = sb * f, sa * f


# ─────────────────────────────────────────────────────────────── components
def hrule(width, color=NAVY, thick=1.1):
    t = Table([[""]], colWidths=[width], rowHeights=[0.5])
    t.setStyle(TableStyle([("LINEABOVE", (0, 0), (-1, -1), thick, color)]))
    return t


def kv(rows, w, klabel=2.9, fs=7.4):
    """Two-column key/value table."""
    fs *= SCALE
    ks = ParagraphStyle("k", parent=SMALL, fontSize=fs, leading=fs + 1.9, textColor=NAVY)
    vs = ParagraphStyle("v", parent=SMALL, fontSize=fs, leading=fs + 1.9)
    t = Table([[Paragraph("<b>%s</b>" % a, ks), Paragraph(b, vs)] for a, b in rows],
              colWidths=[klabel * cm, w - klabel * cm])
    t.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.white, TINT]),
        ("LINEBELOW", (0, 0), (-1, -2), 0.25, RULE),
        ("LEFTPADDING", (0, 0), (-1, -1), 3), ("RIGHTPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2)]))
    return t


def box(text, w, color=TEAL, fill=TINT, fs=7.6):
    fs *= SCALE
    t = Table([[Paragraph(text, ParagraphStyle("bx", parent=SMALL, fontSize=fs,
                                               leading=fs + 2.3))]], colWidths=[w])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), fill),
        ("BOX", (0, 0), (-1, -1), 0.9, color),
        ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]))
    return KeepTogether([t, Spacer(1, 0.16 * cm)])


def bul(items):
    return [Paragraph("•&nbsp; " + i, SMALL) for i in items]


def card(name, title, subtitle, build):
    """Render one A4 page, shrinking the type until the content fits.

    `build` returns either (left, right) for a two-column card or (body, None)
    for a single wide column."""
    path = OUT / name
    for scale in (1.0, 0.97, 0.94, 0.91, 0.88, 0.85, 0.82, 0.79, 0.76):
        set_scale(scale)
        left, right = build()
        doc = BaseDocTemplate(str(path), pagesize=A4,
                              leftMargin=1.1 * cm, rightMargin=1.1 * cm,
                              topMargin=1.0 * cm, bottomMargin=0.9 * cm,
                              title=title, author="Minhazul Abedin")
        W = doc.width
        head = [Paragraph(title, TITLE), Paragraph(subtitle, SUB), hrule(W)]
        pad = dict(leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)

        if right is None:
            frames = [Frame(doc.leftMargin, doc.bottomMargin, W, doc.height,
                            id="one", **pad)]
            story = head + left
        else:
            gap, hh = 0.55 * cm, 1.55 * cm
            cw = (W - gap) / 2
            frames = [                       # header spans both columns
                Frame(doc.leftMargin, doc.bottomMargin + doc.height - hh, W, hh,
                      id="hd", **pad),
                Frame(doc.leftMargin, doc.bottomMargin, cw, doc.height - hh,
                      id="l", **pad),
                Frame(doc.leftMargin + cw + gap, doc.bottomMargin, cw,
                      doc.height - hh, id="r", **pad),
            ]
            story = head + [FrameBreak()] + left + [FrameBreak()] + right

        doc.addPageTemplates([PageTemplate(id="p", frames=frames)])
        doc.build(story)
        if doc.page == 1:
            print(f"  {name}  1 page  (scale {scale:.2f})")
            return path
    raise SystemExit(f"{name}: still overflows at the smallest scale — cut content")


CW = (A4[0] - 2.2 * cm - 0.55 * cm) / 2      # column width for 2-col cards
FW = A4[0] - 2.2 * cm                        # full width

SUBTITLE = ("Providing Utility Services using Voronoi Diagrams — Case Study for Dhaka "
            "City &nbsp;·&nbsp; Abedin · Rayta · Noman · Aziz &nbsp;·&nbsp; "
            "Supervisor: Dr. Md. Manzurul Hasan")


# ══════════════════════════════════════════════════ CARD 1 — the thesis report
def card1():
    left = [
        Paragraph("The whole thesis in one sentence", H),
        Paragraph(
            "We mapped which part of Dhaka is nearest to each hospital, bus stop, metro "
            "station, fuel pump, water source and fire station; counted how many "
            "<b>people</b> — not how much land — falls outside a reasonable distance; "
            "and computed where new facilities would help the most people.", LEAD),

        Paragraph("Chapter map — what is where", H),
        kv([
            ("Ch. 1 Introduction", "Problem, 4 objectives, 4 research questions (Roman "
             "numerals), scope, contribution."),
            ("Ch. 2 Literature", "Accessibility methods, Dhaka studies, comparison "
             "table 2.1, the research gap."),
            ("Ch. 3 Proposed Model", "Feasibility, requirements, methodology, "
             "architecture, tools, validation design."),
            ("Ch. 4 Implementation", "Data collection, system build, testing, and "
             "<b>all results</b> (§4.6.1–4.6.6)."),
            ("Ch. 5 Standards", "Ethics, sustainability, societal impact, constraints, "
             "budget, Gantt chart."),
            ("Ch. 6 Conclusion", "Contributions, limitations, future work."),
            ("Appendix A–C", "Reproducibility, data provenance, thresholds &amp; weights."),
        ], CW, klabel=2.55),

        Paragraph("The one idea that changed the answer", H),
        box("<b>Area weighting → population weighting.</b> Measured by land area, the "
            "empty eastern fringe (Bashundhara) looked worst — but almost nobody lives "
            "there. Measured by <b>population</b>, dense Motijheel (3.1 M residents, "
            "score 68) becomes the real priority. Empty land does not need a hospital; "
            "crowded neighbourhoods do. <i>This is the contribution — lead with it.</i>",
            CW, AMBER, CREAM),

        Paragraph("Method in five steps", H),
        Paragraph(
            "<b>1 Collect</b> 901 facilities (OpenStreetMap) + 10.7 M residents "
            "(WorldPop 1 km). <b>2 Partition</b> an exact Voronoi diagram per service. "
            "<b>3 Measure</b> distance to the nearest facility on a 250 m grid; beyond "
            "the threshold = underserved. <b>4 Score</b> each of 8 sections out of 100, "
            "weighting emergency services double. <b>5 Recommend</b> — greedily place "
            "the facility that recovers the most underserved people, three times per "
            "service.", SMALL),

        Paragraph("The proof, if they push", H),
        Paragraph(
            "The set of points at least as close to facility <i>p</i> as to <i>q</i> is "
            "the half-plane { x : |x−p| ≤ |x−q| }. Its boundary is by definition "
            "equidistant from both — the <b>perpendicular bisector</b> of segment "
            "<i>pq</i>. A Voronoi cell is the intersection of those half-planes over all "
            "neighbours, so every interior edge is a bisector automatically. Three cells "
            "meet at a vertex because a vertex is equidistant from three facilities; "
            "four would need four points on one circle, which &lsquo;general "
            "position&rsquo; excludes — and we assert it in code. <i>Be ready to draw "
            "two dots and the line between them.</i>", SMALL),
    ]

    right = [
        Paragraph("Numbers you must know cold", H),
        kv([
            ("Facilities", "901 across 6 services, de-duplicated within 150 m"),
            ("Population", "10.7 million (WorldPop 2020, UN-adjusted)"),
            ("Grid", "250 m demand points; CRS EPSG:32646 (UTM 46N)"),
            ("Best served", "Mirpur 92 · Banani 90 · Dhanmondi 85 · Gulshan 81"),
            ("Worst served", "Bashundhara 55 · Uttara 61"),
            ("Top target", "<b>Motijheel</b> — 3.1 M people, scores only 68"),
            ("Weakest service", "Water 73% of area too far · metro 67%"),
            ("Strongest", "Hospitals — only 33% too far"),
            ("Equity", "Gini 0.165 (moderately unequal)"),
            ("Clustering", "Moran's I 0.99 → contiguous zones, not random"),
            ("Payoff", "3 new fire stations → 930,000 people back in reach"),
            ("Sensitivity", "±25% on every threshold → ranking holds, ρ ≈ 0.98"),
        ], CW, klabel=2.35),

        Paragraph("Three ways we checked ourselves", H),
        Paragraph(
            "<b>1 · Against 2SFCA</b> — the standard method [14]. Strong agreement for "
            "scarce services (ρ 0.71–0.93), weak for dense ones (fire 0.12) because "
            "2SFCA also penalises clustering. We report the disagreement honestly.", SMALL),
        Paragraph(
            "<b>2 · Against the exact optimum</b> — our greedy placement reaches "
            "essentially 100% of the brute-force MCLP optimum, so the shortcut is safe.",
            SMALL),
        Paragraph(
            "<b>3 · Against real roads</b> — rebuilt on Dhaka's 43,000-junction drive "
            "network. Journeys run ≈1.5× longer and the underserved share roughly "
            "<b>doubles</b>. Our headline figures are therefore optimistic, and we say "
            "so.", SMALL),

        Paragraph("Why these thresholds, why these weights", H),
        Paragraph(
            "Thresholds come from planning practice, not from us — El-Geneidy et al. [9] "
            "measured ≈524 m 85th-percentile walking distance to bus; NFPA 1710 [15] "
            "frames fire cover around a four-minute response. Doubling the weight on "
            "hospitals, fire and water is a stated value judgement. <b>Both were "
            "tested:</b> ±25% on every threshold, and equal weights throughout, each "
            "leave the ranking essentially unchanged (ρ ≈ 0.98).", SMALL),

        Paragraph("Limitations — admit these before you are asked", H),
        *bul([
            "Straight-line distance, not travel time or traffic.",
            "OpenStreetMap completeness is unknown; counts are a lower bound.",
            "Facility <b>capacity</b> is ignored — a clinic counts like a 500-bed hospital.",
            "The 8 sections are analytical zones, not official thana boundaries.",
            "Population is a 2020 gridded estimate, not a 2026 census.",
        ]),

        Paragraph("What is actually new (the contribution)", H),
        Paragraph(
            "The geometry is from 1908 — say so first, then: our contribution is the "
            "<b>combination</b>. Six utilities together rather than one; weighted by real "
            "population rather than land area; validated three independent ways; released "
            "as reproducible open software. Every prior Dhaka study we found does one "
            "service, area-based — Ahmed [1] emergency care, Rahman [17] transit, Bhuiya "
            "[4] evacuation, Alam [2] open space.", SMALL),

        box("<b>If you do not know:</b> &ldquo;We did not test that — it is outside our "
            "scope. The way we would approach it is…&rdquo; &nbsp;Never invent a number. "
            "Offer to show the table or re-run the code.", CW, GREEN, MINT),
    ]
    return left, right


# ══════════════════════════════════════════════════ CARD 2 — the presentation
SLIDES = [
    ("1", "Title", "Assalamu alaikum. Name the topic, the team, the supervisor. 15 s."),
    ("2", "Outline", "&ldquo;Eight parts.&rdquo; Read the headings, do not explain them. 10 s."),
    ("3", "Introduction", "Dhaka grew faster than its utilities; access is uneven and unmeasured."),
    ("4", "Objectives &amp; RQs", "Four objectives (i–iv), four questions. Point, do not read all."),
    ("5", "Literature", "Prior Dhaka work: emergency care, transit, evacuation, open space."),
    ("6", "Research gap", "<b>All single-service and area-based.</b> We do six, weighted by people."),
    ("7", "Data", "901 facilities, 10.7 M residents, all open licence. Name the sources."),
    ("8", "Study area", "The eight sections. Say they are analytical zones, not wards."),
    ("9", "Method", "The five stages: collect → partition → measure → score → recommend."),
    ("10", "Mathematics", "Cell = intersection of half-planes ⇒ perpendicular-bisector edges."),
    ("11", "Coverage", "Water and metro are weakest; hospitals strongest. One number each."),
    ("12", "Benefit ranking", "<b>The key slide.</b> Area vs population flips the answer to Motijheel."),
    ("13", "Recommendations", "Where new facilities go. 3 fire stations → 930,000 people."),
    ("14", "Validation &amp; equity", "2SFCA, exact optimum, road network. Gini 0.165, Moran 0.99."),
    ("15", "Limitations", "Say them yourself, plainly. It buys credibility for the Q&amp;A."),
    ("16", "Conclusion", "Contribution + reproducible software + one line of future work."),
]


def card2():
    fs = 7.6 * SCALE
    cell = ParagraphStyle("c", parent=SMALL, fontSize=fs, leading=fs + 2)
    num = ParagraphStyle("n", parent=cell, textColor=TEAL)
    ttl = ParagraphStyle("t", parent=cell, textColor=NAVY)
    rows = [[Paragraph("<b>%s</b>" % n, num), Paragraph("<b>%s</b>" % t, ttl),
             Paragraph(s, cell)] for n, t, s in SLIDES]
    tbl = Table(rows, colWidths=[0.75 * cm, 3.3 * cm, FW - 4.05 * cm])
    tbl.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.white, TINT]),
        ("LINEBELOW", (0, 0), (-1, -2), 0.25, RULE),
        ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 2.6), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.6)]))

    body = [
        box("<b>Open:</b> &ldquo;Assalamu alaikum. We are presenting our thesis on "
            "providing utility services using Voronoi diagrams, with a case study of "
            "Dhaka City.&rdquo; &nbsp;&nbsp;<b>Close:</b> &ldquo;That concludes our "
            "presentation. Thank you — we are happy to take your questions.&rdquo;",
            FW, NAVY),
        Paragraph("One line per slide — say this, then move", H),
        tbl,
        Spacer(1, 0.18 * cm),
        Paragraph("Pacing", H),
        kv([
            ("15 minutes", "≈50 s per slide. Slides 12–13 get 90 s each; take it from "
             "4, 5 and 8."),
            ("If cut to 10", "Drop 5 and 8, compress 9 + 10 into one breath. Never drop 12."),
            ("Running late", "Skip to slide 12, then 16. Those two carry the thesis."),
        ], FW, klabel=2.6),

        Paragraph("Quick-fire answers — the six you will actually get", H),
        kv([
            ("Why Voronoi, not buffers?",
             "Circles overlap and leave gaps, and the radius is arbitrary. Voronoi cells "
             "tile the city exactly, never overlap, and need no radius."),
            ("Is OpenStreetMap trustworthy?",
             "Volunteer data, so our counts are an explicit lower bound [11]. No public "
             "official registry of Dhaka facilities exists — validating against one is "
             "future work."),
            ("Motijheel has the most facilities — why is it the target?",
             "Because it has the most people: 3.1 M. What matters is facilities per "
             "person, not the raw count. That is the point of population weighting."),
            ("Moran's I of 0.99 is impossibly high.",
             "It is over a fine 250 m grid where neighbouring points share a nearest "
             "facility, so it is expected. We use it to show under-service is "
             "contiguous, not as a precision claim."),
            ("Straight lines in Dhaka traffic?",
             "We measured it rather than assumed — on the road network journeys run "
             "≈1.5× longer and the underserved share roughly doubles. Our figures are "
             "optimistic and we say so."),
            ("What is new? Voronoi is from 1908.",
             "The geometry is classical. New is the combination: six utilities, "
             "population weights, three validations, reproducible open software."),
        ], FW, klabel=4.4),

        Paragraph("Three rules", H),
        *bul([
            "<b>Never read a slide.</b> The examiners can read. Say the one line, then stop.",
            "<b>Hand over cleanly</b> — name the next speaker: &ldquo;Noman will cover "
            "the data.&rdquo;",
            "<b>Point at the figure</b> you are describing. A pause while pointing looks "
            "confident.",
        ]),
        box("<b>Carry:</b> laptop + USB + the deck emailed to yourself + a printed PDF. "
            "Have the interactive map open in a browser tab — panning to an area an "
            "examiner names is the single most convincing thing you can do. "
            "&nbsp;<b>Golden rule:</b> if you do not know, say &ldquo;we did not test "
            "that&rdquo; and describe how you would. Never invent a number.",
            FW, AMBER, CREAM),
    ]
    return body, None


# ══════════════════════════════════════════════════ CARD 3 — the poster
def card3():
    left = [
        Paragraph("The 60-second pitch — say this when someone stops", H),
        box("&ldquo;Dhaka has grown much faster than its utilities, and nobody has "
            "measured how unevenly. We took 901 real facilities across six services — "
            "hospitals, fire stations, water, metro, buses, fuel — and built a Voronoi "
            "diagram for each, so every point in the city knows its nearest facility. "
            "Then we laid a 250-metre grid over the city and counted how many "
            "<b>people</b> fall outside a reasonable distance. That last word is the "
            "point: earlier studies weight by land area, which makes empty fields look "
            "like the crisis. Weighted by population, the real priority is dense "
            "Motijheel — 3.1 million people. Finally we compute where new facilities "
            "should go: three fire stations alone bring 930,000 people back within "
            "reach.&rdquo;", CW, NAVY),

        Paragraph("Panel map — walk them in this order", H),
        kv([
            ("1 Introduction", "The problem: uneven, unmeasured access."),
            ("2 Methods", "Voronoi + 250 m grid + population weighting."),
            ("3 Data Analysis", "Gini 0.165, Moran's I 0.99 — unequal and clustered."),
            ("4 Results", "Mirpur 92 → Bashundhara 55. Motijheel is the opportunity."),
            ("5 Limitations &amp; Future Work", "Own it before they ask."),
            ("6 Conclusion", "Reproducible, open-data, six services at once."),
            ("7 References", "Okabe 2000, Church &amp; ReVelle 1974, Luo &amp; Wang 2003."),
        ], CW, klabel=3.1),

        Paragraph("The two figures do the work", H),
        Paragraph(
            "<b>Population-weighted benefit map</b> — point here for &ldquo;which area "
            "is better off?&rdquo; <b>Greedy maximal covering</b> — point here for "
            "&ldquo;so what do we do about it?&rdquo; Almost every question lands on one "
            "of these two. Learn where they sit on the board so you can turn and point "
            "without hunting.", SMALL),

        Paragraph("The 10-second version — for people walking past", H),
        box("&ldquo;We mapped which parts of Dhaka are too far from a hospital, fire "
            "station or water source — counted by <b>people</b>, not by area — and "
            "worked out where to put new ones.&rdquo;", CW, TEAL),

        Paragraph("Numbers to have on your tongue", H),
        kv([
            ("901", "facilities, six services, de-duplicated"),
            ("10.7 M", "residents in the study area (WorldPop)"),
            ("250 m", "demand grid; UTM 46N for true metres"),
            ("92 → 55", "Mirpur best, Bashundhara worst (score /100)"),
            ("3.1 M", "people in Motijheel — the top target"),
            ("930,000", "people recovered by 3 new fire stations"),
            ("0.165", "Gini — moderately unequal access"),
            ("×1.5", "road-network detour vs straight line"),
        ], CW, klabel=2.0),
    ]

    right = [
        Paragraph("Questions you will get standing there", H),
        kv([
            ("&ldquo;Why Voronoi and not circles?&rdquo;",
             "Circles overlap and leave gaps, and the radius is arbitrary. Voronoi cells "
             "tile the city exactly and need no radius."),
            ("&ldquo;Is OSM data reliable?&rdquo;",
             "It is volunteer data, so our counts are a lower bound — we state that. "
             "There is no public official registry for Dhaka."),
            ("&ldquo;Motijheel has the most facilities — why is it the target?&rdquo;",
             "Because it also has the most people: 3.1 M. What matters is facilities per "
             "person, not the raw count."),
            ("&ldquo;Straight lines in Dhaka traffic?&rdquo;",
             "We measured it — on the real road network journeys are ≈1.5× longer and "
             "the underserved share roughly doubles."),
            ("&ldquo;What is new? Voronoi is from 1908.&rdquo;",
             "The geometry is classical. New is the combination: six utilities, real "
             "population weights, three validations, released as open software."),
            ("&ldquo;Could you do this for another city?&rdquo;",
             "Yes — the pipeline takes a bounding box and tag filters. Chattogram and "
             "Khulna are in our future work."),
        ], CW, klabel=3.35, fs=7.2),

        Paragraph("Own the limitations before they find them", H),
        Paragraph(
            "Volunteering a weakness reads as command of the work; being caught by one "
            "reads as a gap. Say plainly: <b>straight-line distance, not travel time</b>; "
            "<b>OpenStreetMap completeness unknown</b>, so counts are a lower bound; "
            "<b>capacity ignored</b> — a clinic counts like a 500-bed hospital; the eight "
            "sections are <b>analytical zones, not official thanas</b>. Then pivot "
            "straight to future work: traffic-aware travel time, capacity weighting, "
            "official boundaries, other cities.", SMALL),

        Paragraph("Poster-session craft", H),
        *bul([
            "<b>Stand beside the poster, not in front of it.</b> Never block a figure.",
            "Open with one sentence, then <b>ask</b>: &ldquo;Would you like the short or "
            "the long version?&rdquo; It hands them control and they stay.",
            "Match their level — a visitor gets the pizza-shop analogy, an examiner gets "
            "half-plane intersection.",
            "Have the printed thesis and a phone with the interactive map within reach.",
            "Agree in advance who speaks first; the others fill gaps rather than interrupt.",
            "If a number is challenged, offer the table — do not argue from memory.",
        ]),

        box("<b>The pizza-shop line</b> (for anyone non-technical): &ldquo;Three pizza "
            "shops in a town — everyone orders from the nearest one. Colour each house by "
            "its shop and the town splits into three regions. That is a Voronoi diagram. "
            "We did it for Dhaka's hospitals and fire stations instead of pizza.&rdquo;",
            CW, GREEN, MINT),
    ]
    return left, right


if __name__ == "__main__":
    card("Card_1_Thesis_Report.pdf", "Thesis Report — One-Page Master Card",
         SUBTITLE, card1)
    card("Card_2_Presentation.pdf", "Defense Presentation — Slide-by-Slide Card",
         "16 slides &nbsp;·&nbsp; " + SUBTITLE, card2)
    card("Card_3_Poster.pdf", "Poster Session — Standing Card", SUBTITLE, card3)
