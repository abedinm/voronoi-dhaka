"""Fill the official AIUB FST poster template with our thesis content."""
from pptx import Presentation
from pptx.util import Inches, Pt

TPL = "data/templates/AIUB_FST_Poster_Template.pptx"
OUT = "outputs/Dhaka_Voronoi_Poster_AIUB.pptx"
FIG = "outputs/figures/"

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
                 "Abdullah Al Noman (21-45825-3)   ·   Mehedi Hasan Aziz (19-40060-1)\n"
                 "Supervisor: Dr. Md. Manzurul Hasan, Associate Professor, "
                 "Department of Computer Science"],
     keep_first=False, size=17)

# ---------------- column 1 ----------------
fill(by_idx[7], [
    "Dhaka has grown far faster than its utilities, leaving uneven access. We analyse six "
    "services — metro, hospitals, water, fuel, bus stops and fire stations (901 OSM "
    "facilities) — with exact Voronoi diagrams and WorldPop population (~10.7M people): "
    "which areas benefit most, and where should new facilities go?"])
fill(by_idx[9], [
    "Every facility seeds an exact Voronoi cell (perpendicular-bisector edges, verified by "
    "29 automated tests). Nearest-facility distance is computed on a 250 m grid (k-d tree) "
    "against per-service thresholds.",
    "POPULATION-WEIGHTED BENEFIT",
    "Eight named sections are scored by the share of their residents within reach of each "
    "service, weighting hospitals, fire and water higher (WorldPop).",
    "Access is validated against the 2SFCA method and road-network distance.",
    "GREEDY MAXIMAL COVERING",
    "New sites are placed at the most-populated underserved locations "
    "(Church & ReVelle, 1974) and recover ~100% of the exact optimum."])
delete(by_idx[11])          # chart has its own title; caption would clash
fill(by_idx[12], [
    "Combined access across all six utilities is moderately unequal (Gini = 0.165) and "
    "strongly clustered (Moran's I = 0.99, p = 0.005): well- and poorly-served locations "
    "form contiguous regions.",
    "Section ranking is robust: ±25% thresholds or equal weights leave it almost "
    "unchanged (Spearman ρ ≈ 0.98).",
    "2SFCA agrees with the Voronoi ranking for scarce services (metro, water, hospital).",
    "The Lorenz curve below summarises the equity of access."])

# picture placeholder in column 1 -> network comparison chart
by_idx[10].insert_picture(FIG + "network_vs_euclid.png")

# dummy donut chart -> Lorenz curve
delete(by_idx[13])
slide.shapes.add_picture(FIG + "lorenz_access.png", Inches(3.4), Inches(34.1),
                         width=Inches(3.9))

# ---------------- Limitations & Future Work (column 1) ----------------
from pptx.util import Pt as _Pt
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
    "OSM completeness varies — counts are a lower bound.",
    "Capacity not modelled; sections are analytical zones.",
], _RGB(0xC0, 0x39, 0x2B))

_list_block(5.6, 39.5, 4.4, "FUTURE WORK", [
    "Traffic-aware travel time on the road network.",
    "Capacity-weighted Voronoi from official registries.",
    "Finer population grid; transfer to other cities.",
], _RGB(0x2E, 0x8B, 0x57))

# ---------------- column 2 ----------------
for i in (15, 16, 17, 20, 21, 22, 23):          # dummy table, footnote, chart, pyramid, labels
    delete(by_idx[i])
slide.shapes.add_picture(FIG + "zones_dhaka_flagship.png", Inches(10.7), Inches(4.5),
                         width=Inches(9.0))     # -> ~14.3 in tall
fill(by_idx[19], [
    "The central belt is best served — Mirpur (92), Banani (90), Dhanmondi (85) — while "
    "Bashundhara (55) and Uttara (61) lag. Motijheel, the most populous section at 3.1M "
    "residents, scores only 68, making it the highest-impact investment target.",
    "Water sources (73% of area) and metro (67%) show the widest gaps; hospitals the "
    "narrowest (33%). Three targeted sites per service cut the underserved population "
    "sharply — fire 1.67M → 0.74M, hospitals 1.07M → 0.61M."], size=17)
slide.shapes.add_picture(FIG + "section_benefit.png", Inches(11.6), Inches(25.2),
                         width=Inches(7.4))     # -> ~9.5 in tall
fill(by_idx[24], [
    "A reproducible, open-data Voronoi framework showing where Dhaka's utilities serve "
    "people well and where to add capacity.",
    "The centre is well served and the periphery lags; dense old Dhaka is the top "
    "priority for hospitals and fire stations; straight-line analysis understates the "
    "true gap.",
    "Fully reproducible: python voronoi_dhaka.py"], size=17)

# ---------------- column 3 ----------------
fill(by_idx[26], [
    "Okabe, A. et al. (2000). Spatial Tessellations. Wiley.",
    "Church, R. & ReVelle, C. (1974). The maximal covering location problem. Papers Reg. Sci.",
    "Luo, W. & Wang, F. (2003). Measures of spatial accessibility. EPB, 30(6).",
    "Ahmed, S. et al. (2019). Emergency healthcare access in Dhaka. PLOS ONE 14(9).",
    "Tatem, A. (2017). WorldPop, open data for spatial demography. Sci. Data 4.",
    "Boeing, G. (2017). OSMnx. CEUS 65.",
    "Alam, I. et al. (2025). Public open space access in Dhaka. Comput. Urban Sci. 5."])
fill(by_idx[27], [
    "We thank our supervisor, Dr. Md. Manzurul Hasan, Associate Professor, Department of Computer Science, AIUB, "
    "for continuous guidance, and the Faculty of Science and Technology for its support. "
    "Facility data © OpenStreetMap contributors; population from WorldPop; basemaps © "
    "CARTO and Google."])
slide.shapes.add_picture(FIG + "recommendations_fire_station.png", Inches(20.6), Inches(16.6),
                         width=Inches(8.9))     # aspect 1.62 -> ~14.4 in tall
slide.shapes.add_picture(FIG + "voronoi_hospital.png", Inches(20.6), Inches(31.6),
                         width=Inches(8.9))     # aspect 1.37 -> ~12.2 in tall

prs.save(OUT)
print("saved", OUT)
