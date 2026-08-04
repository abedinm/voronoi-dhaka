#!/usr/bin/env python3
"""Defense cheat sheet: plain-English thesis explainer + likely Q&A.

Run:  python build_cheatsheet.py     ->  outputs/Defense_Cheat_Sheet.pdf
"""

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (KeepTogether, PageBreak, Paragraph,
                                SimpleDocTemplate, Spacer, Table, TableStyle)

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "outputs" / "Defense_Cheat_Sheet.pdf"

NAVY = colors.HexColor("#0E2A47")
TEAL = colors.HexColor("#1C7293")
AMBER = colors.HexColor("#B4650F")
GREEN = colors.HexColor("#2E6B45")
INK = colors.HexColor("#1C2B39")
MUTED = colors.HexColor("#5B6B7A")
TINT = colors.HexColor("#EDF3F7")

ss = getSampleStyleSheet()
H1 = ParagraphStyle("H1", parent=ss["Heading1"], fontSize=16, textColor=NAVY,
                    spaceBefore=10, spaceAfter=7)
H2 = ParagraphStyle("H2", parent=ss["Heading2"], fontSize=12, textColor=TEAL,
                    spaceBefore=9, spaceAfter=4)
BODY = ParagraphStyle("Body", parent=ss["BodyText"], fontSize=10, leading=14,
                      alignment=TA_JUSTIFY, textColor=INK, spaceAfter=6)
LEAD = ParagraphStyle("Lead", parent=BODY, fontSize=11, leading=15, textColor=NAVY)
Q = ParagraphStyle("Q", parent=BODY, fontSize=10, leading=13.5, textColor=NAVY,
                   spaceAfter=2)
A = ParagraphStyle("A", parent=BODY, fontSize=9.5, leading=13, spaceAfter=8,
                   leftIndent=10)
NOTE = ParagraphStyle("Note", parent=BODY, fontSize=9, leading=12.5, textColor=MUTED)

story = []


def qa(question, answer):
    story.append(KeepTogether([
        Paragraph("<b>Q. " + question + "</b>", Q),
        Paragraph("<b>A.</b> " + answer, A),
    ]))


def callout(title, text, color=TEAL):
    t = Table([[Paragraph("<b>" + title + "</b><br/>" + text,
                          ParagraphStyle("c", parent=BODY, fontSize=9.5, leading=13))]],
              colWidths=[16.4 * cm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), TINT),
        ("BOX", (0, 0), (-1, -1), 1, color),
        ("LEFTPADDING", (0, 0), (-1, -1), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
    story.extend([t, Spacer(1, 0.3 * cm)])


# ===================================================================== PART A
story.append(Paragraph("Thesis Defense Cheat Sheet", H1))
story.append(Paragraph(
    "Providing Utility Services using Voronoi Diagrams — Case Study for Dhaka City<br/>"
    "Minhazul Abedin · Zarin Tasnim Rayta · Abdullah Al Noman · Mehedi Hasan Aziz", NOTE))
story.append(Spacer(1, 0.3 * cm))

story.append(Paragraph("PART A — The whole thesis in plain English", H1))

story.append(Paragraph("The one-sentence version", H2))
story.append(Paragraph(
    "We drew a map of Dhaka showing which neighbourhood is closest to each hospital, bus "
    "stop, metro station, fuel pump, water source and fire station — then we counted how "
    "many <i>people</i> are too far from each one, and worked out where new facilities "
    "would help the most people.", LEAD))

story.append(Paragraph("1. What is a Voronoi diagram?", H2))
story.append(Paragraph(
    "Imagine three pizza shops in a town. Every house orders from whichever shop is "
    "nearest. If you colour each house by the shop it uses, the town splits into three "
    "regions. That picture is a <b>Voronoi diagram</b>: each shop gets the territory of "
    "everything closest to it.", BODY))
story.append(Paragraph(
    "The border between two shops is the line where you are <i>exactly equally far</i> "
    "from both. That line is always straight, always cuts the line joining the two shops "
    "in half, and always meets it at a right angle. Mathematicians call it the "
    "<b>perpendicular bisector</b>. Our whole map is built out of those lines.", BODY))
callout("If asked to prove it",
        "The cell of shop p is every point closer to p than to any other shop. "
        "For one rival q, that is the set { x : |x−p| ≤ |x−q| } — a half-plane whose edge "
        "is the perpendicular bisector. Intersect those half-planes over all rivals and "
        "you get the cell. Straight bisector edges therefore come out automatically.")

story.append(Paragraph("2. What we actually did — five steps", H2))
steps = [
    ("Collect", "We downloaded the real locations of six services in Dhaka from "
                "OpenStreetMap — 901 facilities in total. We also downloaded a population "
                "map (WorldPop) that tells us roughly how many people live in each "
                "1 km square: about 10.7 million people in our study area."),
    ("Partition", "For each service separately, we built the Voronoi diagram — so every "
                  "point in Dhaka knows which hospital, bus stop, etc. is its nearest."),
    ("Measure", "We laid an invisible grid over the city with a point every 250 m. At "
                "each grid point we measured the distance to the nearest facility. If that "
                "distance was bigger than a sensible limit (2 km for a hospital, 800 m for "
                "a bus stop, 3 km for a fire station), we marked that spot "
                "<b>underserved</b>."),
    ("Score", "We split Dhaka into eight familiar areas — Uttara, Mirpur, Bashundhara, "
              "Banani, Gulshan, Dhanmondi, Khilgaon, Motijheel — and gave each a score out "
              "of 100: what percentage of its <i>people</i> are within reach of the "
              "services, counting hospitals, fire stations and water as more important."),
    ("Recommend", "We asked the computer: where is the single most crowded place that is "
                  "still underserved? Put a new facility there. Then recalculate and "
                  "repeat. Three times per service."),
]
for i, (name, text) in enumerate(steps, 1):
    story.append(Paragraph(f"<b>Step {i} — {name}.</b> {text}", BODY))

story.append(Paragraph("3. The one idea that changed our answer", H2))
story.append(Paragraph(
    "At first we measured coverage by <b>land area</b>. That made the empty eastern edge "
    "of the city look like the worst problem — but hardly anyone lives there. So we "
    "switched to measuring by <b>population</b>. Suddenly the answer flipped: the real "
    "problem is dense old Dhaka (Motijheel), which has 3.1 million residents but only a "
    "moderate score. Empty land does not need a hospital; crowded neighbourhoods do.", BODY))
callout("This is the heart of the thesis",
        "Measuring by area tells you where the empty gaps are. Measuring by population "
        "tells you where the <i>people</i> are stuck. Ours is the first Dhaka study that "
        "does the second, across six services at once.", AMBER)

story.append(Paragraph("4. What we found", H2))
findings = [
    ["Best served", "Mirpur (92), Banani (90), Dhanmondi (85), Gulshan (81)"],
    ["Worst served", "Bashundhara (55), Uttara (61)"],
    ["Biggest opportunity", "Motijheel — 3.1M people, scores only 68"],
    ["Weakest services", "Water sources (73% of area too far), metro (67%)"],
    ["Strongest service", "Hospitals (only 33% of area too far)"],
    ["Fairness", "Gini = 0.165 → access is mildly unequal (0 = perfectly equal)"],
    ["Pattern", "Moran's I = 0.99 → good and bad areas form big clumps, not a random mix"],
    ["Fixing it", "3 new fire stations move 946,000 people back within reach"],
]
t = Table([[Paragraph("<b>" + a + "</b>", ParagraphStyle("k", parent=BODY, fontSize=9.5)),
            Paragraph(b, ParagraphStyle("v", parent=BODY, fontSize=9.5))] for a, b in findings],
          colWidths=[4.6 * cm, 11.8 * cm])
t.setStyle(TableStyle([
    ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.white, TINT]),
    ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#CCCCCC")),
    ("LEFTPADDING", (0, 0), (-1, -1), 6), ("TOPPADDING", (0, 0), (-1, -1), 4),
    ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]))
story.extend([t, Spacer(1, 0.35 * cm)])

story.append(Paragraph("5. How we checked we were not fooling ourselves", H2))
story.append(Paragraph(
    "<b>Check 1 — against the standard method.</b> Other researchers use a technique "
    "called 2SFCA. We ran it too. For scarce services (metro, water, hospitals) it "
    "agreed with us strongly. For crowded services it differed, because 2SFCA also "
    "penalises facilities being bunched together. So the two methods complement each "
    "other — we say so honestly.", BODY))
story.append(Paragraph(
    "<b>Check 2 — against the perfect answer.</b> Our placement method is a shortcut "
    "(&ldquo;greedy&rdquo;). We also computed the mathematically perfect placement by "
    "brute force. The shortcut got essentially 100% of the perfect result — so the "
    "shortcut is fine.", BODY))
story.append(Paragraph(
    "<b>Check 3 — real roads.</b> Straight-line distance ignores that you cannot walk "
    "through buildings and rivers. So we rebuilt everything using Dhaka's real road "
    "network (43,000 junctions). Real journeys are about 1.5× longer, and the number of "
    "underserved people roughly <b>doubles</b>. We report this openly — it means our "
    "main figures are optimistic.", BODY))

story.append(Paragraph("6. Why it matters", H2))
story.append(Paragraph(
    "Dhaka spends money on new facilities every year, but siting decisions are rarely "
    "backed by open evidence. Our framework turns an invisible problem into a map, a "
    "score and a list of coordinates — and anyone can re-run it with one command as the "
    "city changes. Everything uses free data and free software.", BODY))

# ===================================================================== PART B
story.append(PageBreak())
story.append(Paragraph("PART B — Questions you will be asked", H1))
story.append(Paragraph(
    "Golden rule: if you do not know, say <i>&ldquo;We did not test that — it is outside "
    "our scope, but the way we would approach it is…&rdquo;</i> Never invent a number.", NOTE))
story.append(Spacer(1, 0.25 * cm))

story.append(Paragraph("About the method", H2))
qa("Why Voronoi instead of simple circles or buffers around each facility?",
   "Circles overlap and leave gaps, and the radius is arbitrary. Voronoi cells never "
   "overlap, cover everything, and need no radius — each point simply belongs to its "
   "nearest facility. It is also provably correct, which we verify with automated tests.")
qa("Prove that your cell edges are perpendicular bisectors.",
   "The set of points at least as close to p as to q is the half-plane "
   "{ x : |x−p| ≤ |x−q| }. Its boundary is by definition equidistant from p and q, which "
   "is the perpendicular bisector of segment pq. A cell is the intersection of these "
   "half-planes over the facility's neighbours, so every interior edge is such a "
   "bisector. <i>Be ready to draw two dots and the line between them.</i>")
qa("Why do exactly three cells meet at each vertex?",
   "A Voronoi vertex is equidistant from three facilities. Four cells meeting would "
   "require four facilities on a common circle — a degenerate case excluded by 'general "
   "position', which we check for automatically.")
qa("What is the computational complexity?",
   "Building the Voronoi diagram is O(n log n). Each nearest-facility lookup on the grid "
   "is O(log n) using a k-d tree [Bentley, 1975]. The whole pipeline runs in minutes on "
   "an ordinary laptop.")
qa("Why UTM zone 46N and not latitude/longitude?",
   "Degrees are not a distance unit — a degree of longitude shrinks as you move from the "
   "equator, so areas and distances computed in lat/long are wrong. UTM 46N is the metric "
   "projection for Bangladesh, so all our distances are true metres.")

story.append(Paragraph("About the data", H2))
qa("OpenStreetMap is volunteer data. How can you trust it?",
   "We do not claim it is complete — we state explicitly that our counts are a lower "
   "bound, and cite Klinkhardt et al. (2023), who measured exactly this problem. We use "
   "it because no consolidated official registry of Dhaka facility locations is publicly "
   "available. Validating against official registries is our stated future work.")
qa("Why did 451 hospitals become 286 after cleaning?",
   "OpenStreetMap often maps one hospital several times — as a point, as a building "
   "outline, and as a relation. We removed duplicates within 150 m and clipped to the "
   "city boundary. It is de-duplication, not data loss. Table 4.1 shows every count.")
qa("Where did the population figure come from, and is it accurate?",
   "WorldPop's 1 km gridded estimate for 2020, which disaggregates census totals using "
   "satellite imagery. Our study-area total of about 10.7 million matches published "
   "Dhaka city estimates — that agreement is our sanity check that we sampled it "
   "correctly.")
qa("Your eight sections are not official wards. Why?",
   "Correct — they are analytical zones built as a coarse Voronoi of well-known area "
   "centres. We tried the OpenStreetMap administrative boundaries for Dhaka and found "
   "them inconsistent and incomplete. This is listed under Limitations, and replacing "
   "them with official thana boundaries is in Future Work.")

story.append(Paragraph("About the assumptions (expect these to be pressed)", H2))
qa("Why 2 km for a hospital? Why 800 m for a bus stop? These look arbitrary.",
   "They come from planning practice, not from us: El-Geneidy et al. (2014) measured an "
   "85th-percentile walking distance of about 524 m to bus service, and NFPA 1710 frames "
   "fire coverage around a four-minute response. More importantly, we <b>tested</b> the "
   "sensitivity: changing every threshold by ±25% leaves the section ranking essentially "
   "unchanged, Spearman ρ ≈ 0.98.")
qa("Why weight hospitals and fire stations double? That is a value judgement.",
   "It is, and we say so. It reflects that missing an emergency service is more serious "
   "than missing a fuel station. We also re-ran everything with all services weighted "
   "equally — the ranking barely moved (ρ ≈ 0.98). So our conclusions do not depend on "
   "that judgement.")

story.append(Paragraph("Challenge questions", H2))
qa("Motijheel has the most facilities of any section, yet scores only 68. Contradiction?",
   "No — it also has the most <b>people</b>: 3.1 million. What matters is facilities "
   "relative to population, not the raw count. This is precisely why population weighting "
   "changed our recommendations, and why Motijheel is our top investment target.")
qa("A Moran's I of 0.99 seems impossibly high.",
   "It is computed over a fine 250 m grid, where neighbouring points usually share the "
   "same nearest facility, so very strong autocorrelation is expected. We use it to "
   "confirm that under-service forms contiguous zones rather than a random scatter — it "
   "is not a precision claim about the magnitude.")
qa("Straight-line distance is meaningless in Dhaka traffic.",
   "We agree, and we measured it rather than assuming. Using the real road network the "
   "median journey is about 1.5× longer and the underserved share roughly doubles. We "
   "report this openly and state that our main figures are therefore optimistic. "
   "Traffic-aware travel time is our first future-work item.")
qa("Your recommendations could put a hospital in an empty field.",
   "That is exactly what the area-weighted version did, which is why we changed it. The "
   "final recommender maximises <i>underserved population</i>, so proposed sites land in "
   "dense neighbourhoods. Compare the before and after maps in Chapter 4.")
qa("What is actually new here? Voronoi diagrams are from 1908.",
   "The geometry is classical — our contribution is the combination: six utilities "
   "assessed together, weighted by real population, validated three ways, and released as "
   "reproducible software. No previous Dhaka study does any of those together; every one "
   "we found examines a single service.")
qa("How is this different from other accessibility studies of Dhaka?",
   "Ahmed et al. (2019) covered emergency healthcare only; Rahman et al. (2022) transit; "
   "Bhuiya et al. (2023) evacuation; Alam et al. (2025) open space. All single-service, "
   "and mostly area-based. Ours is multi-utility and population-weighted — and reassuringly, "
   "Alam et al. independently found the same centre-versus-periphery pattern we did.")
qa("Could you extend this to another city?",
   "Yes, with almost no changes — the pipeline takes a bounding box and tag filters. "
   "Chattogram, Khulna and Sylhet are named in our Future Work.")

story.append(Paragraph("Practical reminders", H2))
for r in [
    "Bring the deck on a laptop <b>and</b> a USB <b>and</b> email it to yourself; also carry the PDF.",
    "Have the interactive Google map open in a browser tab — panning to an area an examiner "
    "names is the most convincing thing you can do.",
    "Every member should be able to explain any paragraph of the document in their own words.",
    "Agree in advance who answers what — but anyone may help; silence looks worse than teamwork.",
    "If a number is challenged, offer to show the table or run the code rather than arguing.",
]:
    story.append(Paragraph("• " + r, BODY))

doc = SimpleDocTemplate(str(OUT), pagesize=A4, leftMargin=2.2 * cm, rightMargin=2.2 * cm,
                        topMargin=1.8 * cm, bottomMargin=1.8 * cm,
                        title="Thesis Defense Cheat Sheet", author="Minhazul Abedin")
doc.build(story)
print("saved", OUT)
