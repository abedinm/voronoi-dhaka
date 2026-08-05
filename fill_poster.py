"""Fill the official AIUB FST poster template with our thesis content."""
from pptx import Presentation
from pptx.util import Inches, Pt

TPL = "data/templates/AIUB_FST_Poster_Template.pptx"
OUT = "outputs/Dhaka_Voronoi_Poster_AIUB.pptx"
FIG = "outputs/figures/plain/"   # plain-language captions

prs = Presentation(TPL)
slide = prs.slides[0]
shapes = list(slide.shapes)


def fill(shape, texts, keep_first=True, size=None):
    """Replace paragraph texts in a text frame, preserving each para's formatting.

    texts[i] goes to paragraph i (skipping the title para if keep_first)."""
    tf = shape.text_frame
    paras = list(tf.paragraphs)
    body = paras[1:] if keep_first else paras
    for i, p in enumerate(body):
        new = texts[i] if i < len(texts) else ""
        if i == len(body) - 1 and len(texts) > len(body):
            new = " ".join(texts[len(body) - 1:])
        if p.runs:
            p.runs[0].text = new
            if size:
                p.runs[0].font.size = Pt(size)
            for r in p.runs[1:]:
                r.text = ""
        elif new:
            r = p.add_run()
            r.text = new
            r.font.size = Pt(18)


def delete(shape):
    el = shape._element
    el.getparent().remove(el)


by_idx = {i: sh for i, sh in enumerate(shapes)}

# ---------------- header ----------------
fill(by_idx[1], ["Providing Utility Services using Voronoi Diagrams"], keep_first=False)
fill(by_idx[2], ["Some Analyses, Recommendations, along with a Case Study for Dhaka City"],
     keep_first=False, size=30)
by_idx[3].top = Inches(2.62)
by_idx[3].height = Inches(1.0)
by_idx[3].width = Inches(24.0)
fill(by_idx[3], ["Minhazul Abedin (21-44625-1)   ·   Zarin Tasnim Rayta (21-45742-3)   ·   "
                 "Abdullah Al Noman (21-45825-3)   ·   Mehedi Hasan Aziz (19-40060-1)"],
     keep_first=False, size=17)

# ---------------- column 1 ----------------
fill(by_idx[7], [
    "Dhaka has grown far faster than its utilities, leaving uneven access. We analyse six "
    "services — metro, hospitals, water, fuel, bus stops and fire stations (901 real "
    "locations) — against where its ~10.7M people actually live: which areas are "
    "better off, and where should new facilities go?"], size=28)
fill(by_idx[9], [
    "We split the city so every point belongs to its nearest facility. Borders fall "
    "exactly halfway between neighbours, checked automatically for gaps and overlaps. "
    "We then measure, every 250 m, how far it is to the nearest facility.",
    "SCORING EACH AREA BY ITS PEOPLE",
    "Each of the eight areas scores out of 100 on how many of its residents are within "
    "a sensible distance of each service, counting emergency services as more important.",
    "Checked against the method other researchers use, and against real road distances.",
    "WHERE NEW FACILITIES SHOULD GO",
    "Each new site goes where it brings the most people back within reach."], size=28)
delete(by_idx[11])          # chart has its own title; caption would clash
fill(by_idx[12], [
    "Access is uneven, and the gaps sit together: well- and badly-served places form "
    "solid blocks, not a random scatter.",
    "The ranking is stable — changing every distance limit by a quarter barely moves it.",
    "Where services are scarce, our ranking agrees with the method others use.",
    "Well-served and badly-served places form solid blocks on the map."], size=28)

# picture placeholder in column 1 -> network comparison chart.
# Removing the Lorenz curve freed ~5 in below Data Analysis, so this chart —
# which carries the strongest single finding, that the real gap is about twice
# what straight lines suggest — is enlarged into that space rather than leaving
# the column half empty.
delete(by_idx[10])
# The Methods text overflows its declared 19.5 in box by roughly 1.5 in, so the
# chart starts at 21.8 rather than butting up against the box height.
slide.shapes.add_picture(FIG + "network_vs_euclid.png", Inches(1.5), Inches(21.8),
                         width=Inches(8.0))     # aspect 1.62 -> 4.9 in tall, ends 26.7
                                                # Data Analysis starts 27.1

# The Lorenz curve is deliberately not on the poster. A Gini of 0.165 puts the
# curve almost on the diagonal, which reads at poster distance as "access is
# roughly equal" and argues against the finding it is meant to support. It needs
# a paragraph to interpret, which a poster cannot give it. It stays in the thesis,
# where that paragraph exists.
delete(by_idx[13])

# ---------------- Limitations & Future Work (column 1) ----------------
from pptx.util import Pt as _Pt
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN
from pptx.dml.color import RGBColor as _RGB

def _textbox(x, y, w, h):
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tb.text_frame.word_wrap = True
    return tb

_head = _textbox(1.0, 38.3, 9.0, 1.0)
_p = _head.text_frame.paragraphs[0]
_r = _p.add_run()
_r.text = "Limitations & Future Work"
_r.font.size = _Pt(40)
_r.font.bold = True
_r.font.color.rgb = _RGB(0x00, 0x5B, 0xBB)

def _list_block(x, y, w, title, items, title_colour):
    tb = _textbox(x, y, w, 3.1)
    tf = tb.text_frame
    p0 = tf.paragraphs[0]
    r0 = p0.add_run()
    r0.text = title
    r0.font.size = _Pt(26)
    r0.font.bold = True
    r0.font.color.rgb = title_colour
    for it in items:
        p = tf.add_paragraph()
        r = p.add_run()
        r.text = "•  " + it
        r.font.size = _Pt(22)
        r.font.color.rgb = _RGB(0x1C, 0x2B, 0x39)

_list_block(1.0, 39.5, 4.4, "LIMITATIONS", [
    "Straight-line distance, not travel time.",
    "Map data is volunteered, so our counts are a minimum.",
    "Facility size is not counted; the eight areas are our own.",
], _RGB(0xC0, 0x39, 0x2B))

_list_block(5.6, 39.5, 4.4, "FUTURE WORK", [
    "Traffic-aware travel time on the road network.",
    "Weight each facility by its size, using official records.",
    "Finer population grid; transfer to other cities.",
], _RGB(0x2E, 0x8B, 0x57))

# ---------------- Key numbers (column 1, where the Lorenz curve was) ----------
# A poster is read standing up and in a hurry. The gap left by the Lorenz curve
# is given to the six figures someone can absorb without reading a paragraph.
_kn_head = _textbox(1.0, 33.7, 9.0, 0.9)
_kr = _kn_head.text_frame.paragraphs[0].add_run()
_kr.text = "Key Numbers"
_kr.font.size = _Pt(34)
_kr.font.bold = True
_kr.font.color.rgb = _RGB(0x00, 0x5B, 0xBB)

_KEY_NUMBERS = [
    ("901",     "facilities, six services"),
    ("10.7M",   "residents in the study area"),
    ("8",       "areas compared"),
    ("92 → 55", "best to worst area score"),
    ("3.1M",    "people in Motijheel, our top target"),
    ("946,000", "people reached by 3 fire stations"),
]
for _i, (_big, _small) in enumerate(_KEY_NUMBERS):
    _x = 1.0 + (_i % 3) * 3.05
    _y = 34.8 + (_i // 3) * 1.75
    _tile = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE,
                                   Inches(_x), Inches(_y), Inches(2.85), Inches(1.55))
    _tile.fill.solid()
    _tile.fill.fore_color.rgb = _RGB(0xED, 0xF3, 0xF7)
    _tile.line.color.rgb = _RGB(0xC6, 0xD3, 0xDC)
    _tile.line.width = _Pt(1)
    _tile.shadow.inherit = False
    _tf = _tile.text_frame
    _tf.word_wrap = True
    _tf.margin_left = _tf.margin_right = Inches(0.08)
    _p1 = _tf.paragraphs[0]
    _p1.alignment = PP_ALIGN.CENTER
    _r1 = _p1.add_run()
    _r1.text = _big
    _r1.font.size = _Pt(40)
    _r1.font.bold = True
    _r1.font.color.rgb = _RGB(0x0E, 0x2A, 0x47)
    _p2 = _tf.add_paragraph()
    _p2.alignment = PP_ALIGN.CENTER
    _r2 = _p2.add_run()
    _r2.text = _small
    _r2.font.size = _Pt(15)
    _r2.font.color.rgb = _RGB(0x5B, 0x6B, 0x7A)

# ---------------- column 2 ----------------
for i in (15, 16, 17, 20, 21, 22, 23):          # dummy table, footnote, chart, pyramid, labels
    delete(by_idx[i])
# The eight-areas map defines the study area; it is setup, not a result, and had
# been sitting above the Results heading with no section of its own.
_heading2a = _textbox(10.6, 4.3, 9.0, 1.3)
_h2ar = _heading2a.text_frame.paragraphs[0].add_run()
_h2ar.text = "Study Area"
_h2ar.font.size = _Pt(40)
_h2ar.font.bold = True
_h2ar.font.color.rgb = _RGB(0x00, 0x5B, 0xBB)
# NOTE: the plain-caption version of this figure is aspect 0.625, not 0.707 —
# its title wraps to fewer lines. Size it by the height we need, not the width.
slide.shapes.add_picture(FIG + "sections_only.png", Inches(11.5), Inches(5.8),
                         width=Inches(7.4))     # 11.8 in tall, ends 17.6
fill(by_idx[19], [
    "The central belt is best served — Mirpur (92), Banani (90), Dhanmondi (85) — while "
    "Bashundhara (55) and Uttara (61) lag. Motijheel, the most populous section at 3.1M "
    "residents, scores only 68, making it the highest-impact investment target.",
    "Water sources (73% of area) and metro (67%) show the widest gaps; hospitals the "
    "narrowest (33%). Three targeted sites per service cut the underserved population "
    "sharply — fire 1.67M → 0.73M, hospitals 1.07M → 0.61M."], size=28)
slide.shapes.add_picture(FIG + "section_benefit.png", Inches(11.6), Inches(25.2),
                         width=Inches(7.4))     # -> ~9.5 in tall
fill(by_idx[24], [
    "A reproducible, open-data Voronoi framework showing where Dhaka's utilities serve "
    "people well and where to add capacity.",
    "The centre is well served and the periphery lags; dense old Dhaka is the top "
    "priority for hospitals and fire stations; straight-line analysis understates the "
    "true gap.",
    "Fully reproducible: python voronoi_dhaka.py"], size=28)

# ---------------- column 3 ----------------
fill(by_idx[26], [
    "Okabe, A. et al. (2000). Spatial Tessellations. Wiley.",
    "Church, R. & ReVelle, C. (1974). The maximal covering location problem. Papers Reg. Sci.",
    "Luo, W. & Wang, F. (2003). Measures of spatial accessibility. EPB, 30(6).",
    "Ahmed, S. et al. (2019). Emergency healthcare access in Dhaka. PLOS ONE 14(9).",
    "Tatem, A. (2017). WorldPop, open data for spatial demography. Sci. Data 4.",
    "Boeing, G. (2017). OSMnx. CEUS 65.",
    "Alam, I. et al. (2025). Public open space access in Dhaka. Comput. Urban Sci. 5."], size=28)
fill(by_idx[27], [
    "We thank the Department of Computer Science and the Faculty of Science and "
    "Technology, American International University-Bangladesh, for their guidance and "
    "support. Facility data © OpenStreetMap contributors; population from WorldPop; "
    "basemaps © CARTO and Google."], size=28)
# Column 3 runs figures first, then References and Acknowledgement last, so that
# reading down the column the closing sections come after the evidence rather
# than before it. The single-utility hospital map is dropped, and
# voronoi_all_services with it — cell_centroids already shows the same
# per-utility coloured cells and generators, plus the centre points.
# The three figures had no heading above them, so a reader could not tell which
# section they answered. They now sit under a heading of their own, each with a
# one-line caption, at the sizes used elsewhere on the poster: 40 pt headings,
# 17 pt body.
_c3 = _textbox(20.4, 4.4, 9.2, 1.3)
_c3r = _c3.text_frame.paragraphs[0].add_run()
_c3r.text = "Results in Detail"
_c3r.font.size = _Pt(40)
_c3r.font.bold = True
_c3r.font.color.rgb = _RGB(0x00, 0x5B, 0xBB)


def _figure_with_caption(png, y, height, caption, x=20.6, w=8.9):
    """Place a figure and say what it shows."""
    slide.shapes.add_picture(FIG + png, Inches(x), Inches(y), width=Inches(w))
    tb = _textbox(x, y + height + 0.05, w, 0.75)
    r = tb.text_frame.paragraphs[0].add_run()
    r.text = caption
    r.font.size = _Pt(17)
    r.font.color.rgb = _RGB(0x1C, 0x2B, 0x39)


_figure_with_caption("cell_centroids.png", 5.9, 7.4,
                     "Facilities sit off-centre in the areas they cover — worst for "
                     "metro and fire stations.")
_figure_with_caption("recommendations_all_services.png", 14.3, 8.1,
                     "Proposed new sites for every service, placed to reach the most "
                     "people.")
# The third figure moves to the foot of column 2. Column 3 has to end with
# References, Acknowledgement and then Conclusion, and all three plus three
# figures do not fit in one column.
_heading2b = _textbox(10.6, 35.4, 9.0, 1.3)
_h2br = _heading2b.text_frame.paragraphs[0].add_run()
_h2br.text = "Results in Detail (cont.)"
_h2br.font.size = _Pt(40)
_h2br.font.bold = True
_h2br.font.color.rgb = _RGB(0x00, 0x5B, 0xBB)
_figure_with_caption("cluster_centres.png", 36.9, 7.9,
                     "Where each service concentrates, area by area.",
                     x=11.1, w=8.0)

# Column 3 ends References -> Acknowledgement -> Conclusion, with nothing after.
by_idx[26].top = Inches(23.8)      # References — overflows its box by ~0.6 in
by_idx[27].top = Inches(31.0)      # Acknowledgement — References overruns its box
by_idx[24].left = Inches(20.4)     # Conclusion moves out of column 2
by_idx[24].top = Inches(35.8)
by_idx[24].width = Inches(9.2)
for _sh in slide.shapes:           # the thin rule that sat between them
    if (_sh.left is not None and 20.0 < _sh.left / 914400 < 21.5
            and abs(_sh.top / 914400 - 10.5) < 0.3 and _sh.height / 914400 < 1.0):
        _sh.top = Inches(30.3)

# Shrinking the map above Results freed space, but Results is a fixed-position
# placeholder and did not move into it. At 28 pt it needs the room.
by_idx[19].top = Inches(18.4)      # Results — map above now ends at 17.6
for _sh in slide.shapes:           # the rule that sat between the map and Results
    if (_sh.left is not None and 10.0 < _sh.left / 914400 < 19.4
            and abs(_sh.top / 914400 - 18.6) < 0.4 and _sh.height / 914400 < 1.0):
        _sh.top = Inches(17.9)

# fill() only resizes the first run of each paragraph, and several template
# paragraphs carry more than one run — the numbered reference entries in
# particular. Normalise every body run so no section is left at a stray size.
BODY_PT = 28
for _idx in (7, 9, 12, 19, 24, 26, 27):
    _tf = by_idx[_idx].text_frame
    for _pi, _para in enumerate(_tf.paragraphs):
        if _pi == 0 and _para.text.strip() in (
                "Introduction", "Methods", "Data Analysis", "Results",
                "Conclusion", "References", "Acknowledgement"):
            continue                      # leave the 40 pt section heading alone
        for _r in _para.runs:
            _r.font.size = _Pt(BODY_PT)

# The rule that sat under Conclusion in column 2 now falls inside the figure
# that replaced it, drawing a line across the middle of the map.
for _sh in slide.shapes:
    if (_sh.left is not None and 10.0 < _sh.left / 914400 < 19.4
            and abs(_sh.top / 914400 - 43.1) < 0.3 and _sh.height / 914400 < 1.0):
        _sh.top = Inches(45.9)

prs.save(OUT)
print("saved", OUT)
