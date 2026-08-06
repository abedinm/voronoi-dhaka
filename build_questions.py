#!/usr/bin/env python3
"""Likely questions with answers you can actually say.

  outputs/kit/Questions_And_Answers.pdf

Answers are written in the first person, in the words a nervous student would
use standing up — not the words the thesis uses. Every one is short enough to
finish on a single breath, because the ones that run long are the ones that
turn into mumbling.

Run:  python build_questions.py
"""

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (KeepTogether, Paragraph, SimpleDocTemplate,
                                Spacer, Table, TableStyle)

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "outputs" / "kit" / "Questions_And_Answers.pdf"
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
                     leading=11, textColor=MUTED, spaceAfter=9)
SEC = ParagraphStyle("SEC", parent=ss["Heading2"], fontName=F + "-B", fontSize=12,
                     leading=14, textColor=TEAL, spaceBefore=13, spaceAfter=4)
Q = ParagraphStyle("Q", parent=ss["BodyText"], fontName=F + "-B", fontSize=10.5,
                   leading=14, textColor=NAVY, spaceBefore=7, spaceAfter=2)
A = ParagraphStyle("A", parent=ss["BodyText"], fontName=F, fontSize=10.5,
                   leading=15.5, textColor=INK, spaceAfter=2, leftIndent=12)
NOTE = ParagraphStyle("N", parent=A, fontName=F + "-I", fontSize=9.5, leading=13,
                      textColor=MUTED, spaceAfter=4)


def qa(question, answer, note=None):
    out = [Paragraph(question, Q), Paragraph("&ldquo;" + answer + "&rdquo;", A)]
    if note:
        out.append(Paragraph(note, NOTE))
    return KeepTogether(out)


def box(text, color=TEAL, fill=TINT):
    t = Table([[Paragraph(text, ParagraphStyle("bx", parent=A, fontSize=10,
                                               leading=14, leftIndent=0))]],
              colWidths=[A4[0] - 3.4 * cm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), fill),
        ("BOX", (0, 0), (-1, -1), 0.9, color),
        ("LEFTPADDING", (0, 0), (-1, -1), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
    return KeepTogether([t, Spacer(1, 0.2 * cm)])


story = [
    Paragraph("Questions You Might Get — and What to Say", H1),
    Paragraph("Providing Utility Services using Voronoi Diagrams — A Case Study for "
              "Dhaka City &nbsp;·&nbsp; Abedin · Rayta · Noman · Aziz &nbsp;·&nbsp; "
              "AIUB, Department of Computer Science", SUB),

    box("<b>Every answer here is short on purpose.</b> Say it, then stop. A short "
        "answer that lands beats a long one that wanders, and stopping invites them to "
        "move on rather than dig.<br/><br/>"
        "<b>If you do not know:</b> &ldquo;We did not test that — it is outside our "
        "scope. The way we would approach it is…&rdquo;  <b>Never invent a number.</b>",
        NAVY),

    Paragraph("The basics", SEC),
    qa("What is a Voronoi diagram?",
       "Everyone goes to their nearest facility. Colour each spot by the one it would "
       "use, and the city splits into regions. That is it.",
       "If they want more: the border between two facilities is the line where you are "
       "equally far from both."),
    qa("Why Voronoi, and not circles around each facility?",
       "Circles overlap and leave gaps, and you have to pick a radius out of thin air. "
       "Voronoi regions cover everything exactly and need no radius."),
    qa("Why is the border exactly halfway?",
       "Because that is the line where you are equally far from both. Either side of "
       "it, one facility is closer."),
    qa("What does one cell on your map mean?",
       "Everyone inside it is closer to that facility than to any other one."),

    Paragraph("The data", SEC),
    qa("Where did your data come from?",
       "OpenStreetMap for the facilities, WorldPop for where people live. Both free "
       "and public. Nothing is made up."),
    qa("OpenStreetMap is volunteer data. Can you trust it?",
       "It is a minimum, not a complete list, and we say that in our limitations. "
       "There is no public official registry for Dhaka — checking against one is our "
       "future work."),
    qa("Why did your facility counts drop after cleaning?",
       "The same hospital is often on the map three times — as a point, a building and "
       "a boundary. We removed the copies. It is de-duplication, not lost data."),
    qa("Why these six services?",
       "They are the ones people need regularly, and the ones with usable open data — "
       "health, emergency, water, and three kinds of transport."),
    qa("How many facilities, and how many people?",
       "Nine hundred and one facilities. Ten point seven million residents."),

    Paragraph("The method", SEC),
    qa("What is the 250 metre grid for?",
       "It is how we measure. At every point on that grid we check the distance to the "
       "nearest facility."),
    qa("Where did your distance limits come from?",
       "Planning practice, not from us. Two kilometres to a hospital, eight hundred "
       "metres to a bus stop, and a four-minute fire response."),
    qa("Why do hospitals and fire stations count double?",
       "Because missing an emergency service is more serious than missing a fuel "
       "station. It is a judgement and we say so. We also re-ran it with everything "
       "equal, and the ranking barely moved."),
    qa("Why are your eight areas not official wards?",
       "We tried the official boundaries and they were incomplete. So we built our own "
       "around eight well-known centres. That is in our limitations."),
    qa("How do you choose where a new facility goes?",
       "We put it where it brings the most people back within reach. Then we work out "
       "the next one, and so on."),
    qa("Could a proposed site land somewhere nothing can be built?",
       "No. We rule out rivers, ponds, wetland, drains, landfills, cemeteries, "
       "military land and airports first — about a fifth of the city."),

    Paragraph("The findings", SEC),
    qa("What did you actually find?",
       "Measured by land, the empty east looked worst. Measured by people, it flipped. "
       "Crowded old Dhaka is the real problem — Motijheel has three point one million "
       "people and scores only sixty-eight.",
       "This is the answer to know best. It is the whole thesis in three sentences."),
    qa("Which areas are best and worst?",
       "Mirpur is best at ninety-two. Bashundhara is worst at fifty-five."),
    qa("Motijheel has the most facilities. Why is it your priority?",
       "Because it has the most people. What matters is facilities per person, not the "
       "raw count."),
    qa("How much do your recommendations help?",
       "Three new fire stations bring nine hundred and forty-six thousand people back "
       "within reach."),
    qa("Which service is worst served?",
       "Water points. Seventy-three per cent of the city is too far from one. "
       "Hospitals are the best at thirty-three per cent."),

    Paragraph("The hard ones", SEC),
    qa("Straight-line distance, in Dhaka traffic? Surely that is meaningless.",
       "We agree, so we measured it instead of assuming. On real roads journeys are "
       "about one and a half times longer, and twice as many people turn out to be too "
       "far. Our figures are optimistic and we say so.",
       "Your strongest answer. You already checked and published the bad news — there "
       "is nothing left to attack."),
    qa("How do you know your answer is right?",
       "Four checks. Against the method other researchers use. Against the perfect "
       "answer worked out the slow way. Against real roads. And against our own "
       "assumptions."),
    qa("What is new? Voronoi diagrams are from 1908.",
       "The maths is old, and we say so. What is new is doing six services at once, "
       "counting people instead of land, checking it four ways, and releasing it so "
       "anyone can re-run it."),
    qa("What can your model not do?",
       "Straight lines, not travel time. Volunteer map data. And facility size is not "
       "counted — a small clinic counts the same as a big hospital."),
    qa("What would you do next?",
       "Real travel time on the road network. Weight each facility by its size. And a "
       "finer population map."),
    qa("Could this work for another city?",
       "Yes. The program takes a map boundary and a list of what to search for. "
       "Chattogram and Khulna are in our future work."),

    Paragraph("About you", SEC),
    qa("What was your part in this?",
       "I worked on the data and the method — collecting the facilities, cleaning "
       "them, and building the model that splits the city.",
       "Answer for yourself, not the group. Panels ask this to find out who did what."),
    qa("What was the hardest part?",
       "Realising that measuring by land area was giving us the wrong answer, and "
       "redoing the whole thing by population.",
       "A good answer. It shows judgement rather than effort."),
    qa("What did you learn?",
       "That how you measure something decides what you find. We nearly recommended "
       "building hospitals where almost nobody lives."),

    Spacer(1, 0.3 * cm),
    box("<b>If your mind goes blank:</b> look at the slide and say &ldquo;so — what "
        "this shows is…&rdquo;. That buys four seconds and sounds deliberate.<br/><br/>"
        "<b>If a number is challenged:</b> offer the table rather than arguing from "
        "memory. &ldquo;That is in Chapter 4 — I can show you.&rdquo;", GREEN,
        colors.HexColor("#EAF3ED")),
]

SimpleDocTemplate(str(OUT), pagesize=A4,
                  leftMargin=1.7 * cm, rightMargin=1.7 * cm,
                  topMargin=1.3 * cm, bottomMargin=1.3 * cm,
                  title="Questions and Answers", author="Minhazul Abedin").build(story)
print("wrote", OUT)
