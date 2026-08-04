/**
 * 16-slide defense deck with EMPTY image placeholders.
 * Same text and layout as build_slides_16.js — drop your own figures into the
 * dashed boxes (right-click the box > Change Picture, or just delete and insert).
 *
 * Structure:
 *   Intro · Literature review · Research gap · Data · Method ·
 *   Result analysis · Limitations · Conclusion
 * Run:  NODE_PATH="$(npm root -g)" node build_slides_16.js
 */
const pptxgen = require("pptxgenjs");

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE"; // 13.33 x 7.5 in
pres.author = "Minhazul Abedin";
pres.title = "Providing Utility Services using Voronoi Diagrams";

const FIG = "outputs/figures/";
const OUT = "outputs/Dhaka_Voronoi_Defense_16_BLANK.pptx";

// palette
const NAVY = "0E2A47", DEEP = "0B5394", TEAL = "1C7293", AMBER = "E8833A";
const GREEN = "2E8B57", RED = "C0392B", WHITE = "FFFFFF", INK = "1C2B39";
const MUTED = "5B6B7A", TINT = "EDF3F7", LINE = "D6E0E7";
const HF = "Cambria", BF = "Calibri";

let slideNo = 0;

function newSlide(kicker, title, opts = {}) {
  const s = pres.addSlide();
  s.background = { color: opts.dark ? NAVY : WHITE };
  if (kicker) {
    s.addText(kicker.toUpperCase(), {
      x: 0.6, y: 0.42, w: 9, h: 0.3, fontFace: BF, fontSize: 12, bold: true,
      color: opts.dark ? "8FB3D9" : TEAL, charSpacing: 2, margin: 0,
    });
  }
  if (title) {
    s.addText(title, {
      x: 0.56, y: 0.75, w: 12.2, h: 0.75, fontFace: HF, fontSize: 30, bold: true,
      color: opts.dark ? WHITE : INK, margin: 0,
    });
  }
  slideNo += 1;
  if (!opts.noNumber) {
    s.addText(String(slideNo), {
      x: 12.5, y: 6.95, w: 0.5, h: 0.3, fontFace: BF, fontSize: 10,
      color: opts.dark ? "8FB3D9" : MUTED, align: "right", margin: 0,
    });
  }
  return s;
}

// Empty, labelled slot where a figure should be dropped in.
const SLOT_LABELS = {
  "all_facilities.png": "All 901 facilities across Dhaka, coloured by utility — dense centre, sparse fringe",
  "voronoi_all_services.png": "Six Voronoi diagrams — one per utility, each in its own colour with generator points",
  "sections_only.png": "The eight study sections of Dhaka, with their centre points",
  "textbook_all.png": "Textbook Voronoi correctness proof (three diagrams)",
  "section_benefit.png": "Section benefit choropleth (green = well served, red = lagging)",
  "recommendations_all_services.png": "Proposed sites for all six utilities — existing in each utility's colour, proposed as red stars",
  "lorenz_access.png": "Lorenz curve of combined utility access",
};

function framedImage(slide, path, x, y, w, h) {
  const file = String(path).split("/").pop();
  const label = SLOT_LABELS[file] || file;
  slide.addShape(pres.ShapeType.roundRect, {
    x, y, w, h, fill: { color: "F7FAFC" },
    line: { color: TEAL, width: 1.5, dashType: "dash" }, rectRadius: 0.06,
  });
  slide.addText("IMAGE PLACEHOLDER", {
    x, y: y + h / 2 - 0.72, w, h: 0.32, align: "center", fontFace: BF, fontSize: 12,
    bold: true, color: TEAL, charSpacing: 1.5, margin: 0,
  });
  slide.addText(label, {
    x: x + 0.25, y: y + h / 2 - 0.32, w: w - 0.5, h: 0.75, align: "center",
    fontFace: BF, fontSize: 12, color: INK, margin: 0,
  });
  slide.addText(`suggested: ${file}   ·   ${w.toFixed(1)} × ${h.toFixed(1)} in`, {
    x: x + 0.2, y: y + h / 2 + 0.45, w: w - 0.4, h: 0.3, align: "center",
    fontFace: BF, fontSize: 9.5, italic: true, color: MUTED, margin: 0,
  });
}

function bullets(slide, items, x, y, w, size = 16) {
  slide.addText(
    items.map((t, i) => ({
      text: t,
      options: { bullet: { code: "2022" }, breakLine: i !== items.length - 1 },
    })),
    { x, y, w, h: 0.4 * items.length + 0.6, fontFace: BF, fontSize: size,
      color: INK, paraSpaceAfter: 10, margin: 0 }
  );
}

function statCard(slide, x, y, w, h, value, label, color) {
  slide.addShape(pres.ShapeType.roundRect, {
    x, y, w, h, fill: { color: TINT }, line: { color: LINE, width: 1 }, rectRadius: 0.08,
  });
  slide.addText(value, {
    x, y: y + 0.16, w, h: h * 0.5, align: "center", fontFace: HF,
    fontSize: 30, bold: true, color, margin: 0,
  });
  slide.addText(label, {
    x: x + 0.1, y: y + h * 0.62, w: w - 0.2, h: h * 0.34, align: "center",
    fontFace: BF, fontSize: 11, color: MUTED, margin: 0,
  });
}

// ================================================================ 1. TITLE
let s = pres.addSlide();
s.background = { color: NAVY };
s.addImage({ path: "data/templates/aiub_logo.png", x: 6.17, y: 0.3, w: 1.0, h: 1.0 });
s.addText("AMERICAN INTERNATIONAL UNIVERSITY-BANGLADESH", {
  x: 0.5, y: 1.4, w: 12.3, h: 0.3, align: "center", fontFace: BF, fontSize: 12,
  bold: true, color: "8FB3D9", charSpacing: 1.5, margin: 0 });
s.addText("Faculty of Science and Technology  ·  Department of Computer Science", {
  x: 0.5, y: 1.72, w: 12.3, h: 0.3, align: "center", fontFace: BF, fontSize: 12,
  color: "AEC4DD", margin: 0 });
s.addText("Providing Utility Services using Voronoi Diagrams", {
  x: 0.6, y: 2.28, w: 12.1, h: 0.7, align: "center", fontFace: HF, fontSize: 32,
  bold: true, color: WHITE, margin: 0 });
s.addText("Some Analyses, Recommendations, along with a Case Study for Dhaka City", {
  x: 0.8, y: 3.02, w: 11.7, h: 0.5, align: "center", fontFace: BF, fontSize: 16,
  italic: true, color: "CADCFC", margin: 0 });
[["Minhazul Abedin", "21-44625-1"], ["Zarin Tasnim Rayta", "21-45742-3"],
 ["Abdullah Al Noman", "21-45825-3"], ["Mehedi Hasan Aziz", "19-40060-1"],
].forEach((t, i) => {
  const x = 0.75 + i * 3.05;
  s.addShape(pres.ShapeType.roundRect, { x, y: 3.95, w: 2.85, h: 0.72,
    fill: { color: "16385C" }, line: { color: "2C5680", width: 1 }, rectRadius: 0.08 });
  s.addText(t[0], { x, y: 4.02, w: 2.85, h: 0.32, align: "center", fontFace: BF,
    fontSize: 13, bold: true, color: WHITE, margin: 0 });
  s.addText(t[1], { x, y: 4.33, w: 2.85, h: 0.28, align: "center", fontFace: BF,
    fontSize: 11, color: "8FB3D9", margin: 0 });
});
s.addText("Supervised by", { x: 0.5, y: 5.0, w: 12.3, h: 0.3, align: "center",
  fontFace: BF, fontSize: 12, color: "8FB3D9", margin: 0 });
s.addText("Dr. Md. Manzurul Hasan", { x: 0.5, y: 5.3, w: 12.3, h: 0.4, align: "center",
  fontFace: HF, fontSize: 20, bold: true, color: WHITE, margin: 0 });
s.addText("Associate Professor, Department of Computer Science", {
  x: 0.5, y: 5.73, w: 12.3, h: 0.3, align: "center", fontFace: BF, fontSize: 12,
  color: "AEC4DD", margin: 0 });
s.addText("Fall 2025-2026  ·  Defense: 06.07.2026", { x: 0.5, y: 6.55, w: 12.3, h: 0.3,
  align: "center", fontFace: BF, fontSize: 12, italic: true, color: "8FB3D9", margin: 0 });
s.addNotes("Assalamu Alaikum. We present our thesis on providing utility services using Voronoi diagrams, with a case study of Dhaka City.");

// ================================================================ 2. OUTLINE
s = newSlide("Outline", "How this presentation is organised");
[["01", "Introduction", "The problem, objectives and questions"],
 ["02", "Literature Review", "What has already been done"],
 ["03", "Research Gap", "What is missing — and what we add"],
 ["04", "Data", "Six services, 901 facilities, 10.7M people"],
 ["05", "Method", "Voronoi partitioning, scoring, siting"],
 ["06", "Result Analysis", "Coverage, benefit, recommendations, validation"],
 ["07", "Limitations", "What the model does not do"],
 ["08", "Conclusion", "Findings and contribution"],
].forEach((a, i) => {
  const x = 0.7 + (i % 2) * 6.2, y = 1.75 + Math.floor(i / 2) * 1.24;
  s.addShape(pres.ShapeType.roundRect, { x, y, w: 5.9, h: 1.0,
    fill: { color: TINT }, line: { color: LINE, width: 1 }, rectRadius: 0.07 });
  s.addText(a[0], { x: x + 0.22, y: y + 0.16, w: 0.75, h: 0.65, fontFace: HF,
    fontSize: 22, bold: true, color: TEAL, margin: 0 });
  s.addText(a[1], { x: x + 1.05, y: y + 0.14, w: 4.6, h: 0.36, fontFace: BF,
    fontSize: 16, bold: true, color: INK, margin: 0 });
  s.addText(a[2], { x: x + 1.05, y: y + 0.52, w: 4.7, h: 0.36, fontFace: BF,
    fontSize: 11.5, color: MUTED, margin: 0 });
});
s.addNotes("Eight parts, following the structure of the thesis document itself.");

// ================================================================ 3. INTRO
s = newSlide("01 · Introduction", "Dhaka grew faster than its utilities");
bullets(s, [
  "Among the world's densest cities, expanded largely unplanned.",
  "Transport, health, water, fuel and emergency networks lag behind.",
  "No consolidated official registry of facility locations exists.",
  "Some neighbourhoods are well served, others are not — and nobody has measured it across services.",
], 0.7, 1.75, 6.6, 16);
s.addShape(pres.ShapeType.roundRect, { x: 0.7, y: 4.55, w: 6.6, h: 1.8,
  fill: { color: "FBEEE9" }, line: { color: AMBER, width: 1.5 }, rectRadius: 0.08 });
s.addText("Problem statement", { x: 0.95, y: 4.73, w: 6, h: 0.35, fontFace: BF,
  fontSize: 14, bold: true, color: AMBER, margin: 0 });
s.addText("Planners lack a city-wide, evidence-based picture of which neighbourhoods are underserved across the utilities that matter to daily life and safety.",
  { x: 0.95, y: 5.1, w: 6.15, h: 1.1, fontFace: BF, fontSize: 14, color: INK, margin: 0 });
framedImage(s, FIG + "all_facilities.png", 7.9, 1.7, 4.8, 4.9);
s.addNotes("Dhaka's utilities have not kept pace with its growth, and no open evidence base exists for siting decisions.");

// ================================================================ 4. INTRO
s = newSlide("01 · Introduction", "Objectives and research questions");
s.addText("Research Objectives", { x: 0.7, y: 1.68, w: 5.8, h: 0.35, fontFace: BF,
  fontSize: 16, bold: true, color: DEEP, margin: 0 });
["Partition Dhaka into Voronoi service areas for six utilities.",
 "Quantify coverage and find underserved areas, weighted by population.",
 "Rank the city's areas by how well residents are served.",
 "Recommend new facility locations that most improve access.",
 "Validate against established methods; release reproducible software.",
].forEach((t, i) => {
  s.addText(["i", "ii", "iii", "iv", "v"][i] + ".", { x: 0.7, y: 2.12 + i * 0.62,
    w: 0.45, h: 0.4, fontFace: BF, fontSize: 14, bold: true, color: TEAL, margin: 0 });
  s.addText(t, { x: 1.15, y: 2.12 + i * 0.62, w: 5.3, h: 0.55, fontFace: BF,
    fontSize: 13.5, color: INK, margin: 0 });
});
s.addShape(pres.ShapeType.roundRect, { x: 7.1, y: 1.62, w: 5.6, h: 4.6,
  fill: { color: TINT }, line: { color: LINE, width: 1 }, rectRadius: 0.08 });
s.addText("Research Questions", { x: 7.4, y: 1.82, w: 5, h: 0.35, fontFace: BF,
  fontSize: 16, bold: true, color: DEEP, margin: 0 });
["How well do the six utilities cover Dhaka, and where are the gaps?",
 "Which areas benefit most once population is taken into account?",
 "Where should new facilities go to help the most people?",
 "Do results agree with established methods, and how much does road distance change them?",
].forEach((t, i) => {
  s.addText(["i", "ii", "iii", "iv"][i] + ".", { x: 7.4, y: 2.32 + i * 0.95,
    w: 0.4, h: 0.4, fontFace: BF, fontSize: 14, bold: true, color: AMBER, margin: 0 });
  s.addText(t, { x: 7.8, y: 2.32 + i * 0.95, w: 4.7, h: 0.85, fontFace: BF,
    fontSize: 13.5, color: INK, margin: 0 });
});
s.addNotes("Five objectives and four questions; the questions map directly onto the results section.");

// ================================================================ 5. LITERATURE
s = newSlide("02 · Literature Review", "What has already been done");
const lit = [
  ["Okabe et al. [16]", "2000", "Voronoi tessellations", "Foundational theory"],
  ["Church & ReVelle [6]", "1974", "Maximal covering (MCLP)", "Siting under a distance threshold"],
  ["Luo & Wang [14]", "2003", "Two-step floating catchment", "Standard accessibility measure"],
  ["Cui et al. [7]", "2021", "Dynamic Voronoi", "Adds facility capacity"],
  ["Ahmed et al. [1]", "2019", "2SFCA + traffic, Dhaka", "Emergency healthcare only"],
  ["Rahman et al. [17]", "2022", "Accessibility index, Dhaka", "Transit-oriented areas only"],
  ["Alam et al. [2]", "2025", "Accessibility index, Dhaka", "Public open space only"],
];
s.addTable(
  [["Study", "Year", "Method", "Scope"].map((h) => ({
    text: h, options: { bold: true, color: WHITE, fill: { color: DEEP }, fontSize: 12 } }))].concat(
    lit.map((r, i) => r.map((c) => ({
      text: c, options: { fontSize: 12, color: INK, fill: { color: i % 2 ? TINT : WHITE } } })))),
  { x: 0.7, y: 1.85, w: 12, colW: [2.8, 1.0, 3.9, 4.3], border: { pt: 0.5, color: LINE },
    fontFace: BF, rowH: 0.44, valign: "middle" });
s.addText("Foundations give us the geometry and the siting problem; the Dhaka studies give us context — but every one of them covers a single service.",
  { x: 0.7, y: 5.75, w: 12, h: 0.6, fontFace: BF, fontSize: 14, italic: true,
    color: MUTED, margin: 0 });
s.addNotes("The method literature is mature. The Dhaka literature is growing but strictly single-service.");

// ================================================================ 6. GAP
s = newSlide("03 · Research Gap", "What is missing — and what we add");
s.addText("Gaps in the existing work", { x: 0.7, y: 1.7, w: 5.8, h: 0.35, fontFace: BF,
  fontSize: 16, bold: true, color: RED, margin: 0 });
bullets(s, [
  "Every Dhaka study covers one service in isolation.",
  "Coverage is measured over land area, not over population.",
  "Facility siting is rarely recommended, only gaps described.",
  "Few studies release reproducible code or data.",
], 0.7, 2.15, 5.8, 14);
s.addText("What this thesis contributes", { x: 7.0, y: 1.7, w: 5.7, h: 0.35, fontFace: BF,
  fontSize: 16, bold: true, color: GREEN, margin: 0 });
bullets(s, [
  "Six utilities assessed together in one framework.",
  "Coverage weighted by WorldPop population and service criticality.",
  "Population-targeted siting via greedy maximal covering.",
  "Validated three ways and released as reproducible software.",
], 7.0, 2.15, 5.7, 14);
s.addShape(pres.ShapeType.roundRect, { x: 0.7, y: 4.75, w: 12, h: 1.5,
  fill: { color: "FBEEE9" }, line: { color: AMBER, width: 1.5 }, rectRadius: 0.08 });
s.addText("Research gap", { x: 1.0, y: 4.95, w: 4, h: 0.32, fontFace: BF, fontSize: 13,
  bold: true, color: AMBER, margin: 0 });
s.addText("No integrated, multi-utility, population-weighted and reproducible accessibility study of Dhaka exists that also recommends where to invest.",
  { x: 1.0, y: 5.3, w: 11.4, h: 0.8, fontFace: BF, fontSize: 16, color: INK, margin: 0 });
s.addNotes("This slide is the justification for the whole thesis: the gap is the combination, not any single ingredient.");

// ================================================================ 7. DATA
s = newSlide("04 · Data", "Real, openly licensed data");
statCard(s, 0.7, 1.72, 2.9, 1.45, "901", "facilities mapped", DEEP);
statCard(s, 3.85, 1.72, 2.9, 1.45, "6", "utility services", TEAL);
statCard(s, 7.0, 1.72, 2.9, 1.45, "10.7M", "residents covered", AMBER);
statCard(s, 10.15, 1.72, 2.55, 1.45, "8", "named sections", GREEN);
const dataRows = [
  ["Metro station", "railway = station | halt", "36", "26"],
  ["Hospital", "amenity = hospital", "451", "286"],
  ["Water pump / source", "man_made = water_well …", "487", "118"],
  ["Fuel station", "amenity = fuel", "219", "135"],
  ["Bus stop", "highway = bus_stop", "559", "314"],
  ["Fire station", "amenity = fire_station", "29", "22"],
];
s.addTable(
  [["Service", "OpenStreetMap tag", "Raw", "Cleaned"].map((h) => ({
    text: h, options: { bold: true, color: WHITE, fill: { color: DEEP }, fontSize: 12 } }))].concat(
    dataRows.map((r, i) => r.map((c) => ({
      text: c, options: { fontSize: 12, color: INK, fill: { color: i % 2 ? TINT : WHITE } } })))),
  { x: 0.7, y: 3.5, w: 7.5, colW: [2.3, 2.95, 1.1, 1.15], border: { pt: 0.5, color: LINE },
    fontFace: BF, rowH: 0.4, valign: "middle" });
bullets(s, [
  "Live OpenStreetMap query via OSMnx — no synthetic points.",
  "Polygons reduced to interior points; duplicates within 150 m removed.",
  "Clipped to the OSM administrative boundary of Dhaka.",
  "Population from the WorldPop 1 km UN-adjusted raster (2020).",
  "Raw → cleaned is de-duplication, not data loss.",
], 8.5, 3.55, 4.2, 12.5);
s.addNotes("All facility data is real and openly licensed. The raw-to-cleaned drop is duplicate mapping and out-of-boundary features.");

// ================================================================ 8. DATA
s = newSlide("04 · Data", "Study area and the eight sections");
framedImage(s, FIG + "sections_only.png", 0.7, 1.7, 4.9, 5.0);
s.addText("The study area is the Dhaka bounding box intersected with the OpenStreetMap administrative boundary. Within it we define eight familiar sections as a coarse Voronoi of well-known area centres.",
  { x: 6.0, y: 1.82, w: 6.6, h: 1.1, fontFace: BF, fontSize: 15, color: INK, margin: 0 });
[["Uttara", "e6194B"], ["Mirpur", "f58231"], ["Bashundhara", "911eb4"], ["Banani", "4363d8"],
 ["Gulshan", "3cb44b"], ["Dhanmondi", "42d4f4"], ["Khilgaon", "f032e6"], ["Motijheel", "ffe119"],
].forEach((z, i) => {
  const x = 6.0 + (i % 2) * 3.35, y = 3.15 + Math.floor(i / 2) * 0.6;
  s.addShape(pres.ShapeType.ellipse, { x, y: y + 0.04, w: 0.26, h: 0.26, fill: { color: z[1] } });
  s.addText(z[0], { x: x + 0.36, y, w: 2.8, h: 0.34, fontFace: BF, fontSize: 15,
    bold: true, color: INK, margin: 0 });
});
s.addShape(pres.ShapeType.roundRect, { x: 6.0, y: 5.85, w: 6.6, h: 0.85,
  fill: { color: TINT }, line: { color: LINE, width: 1 }, rectRadius: 0.08 });
s.addText("Analytical zones, not official wards — stated in our Limitations.",
  { x: 6.0, y: 5.85, w: 6.6, h: 0.85, align: "center", valign: "middle", fontFace: BF,
    fontSize: 14, italic: true, color: MUTED, margin: 0 });
s.addNotes("Each fine service cell takes the colour of the section its facility falls in. Be honest that these are analytical zones, not official wards.");

// ================================================================ 9. METHOD
s = newSlide("05 · Method", "A five-stage pipeline");
[["1", "Collect", "Six services from OSM; population from WorldPop", DEEP],
 ["2", "Partition", "Exact Voronoi cells from perpendicular bisectors", TEAL],
 ["3", "Measure", "Nearest-facility distance on a 250 m grid (k-d tree)", AMBER],
 ["4", "Score", "Population- and criticality-weighted benefit index", GREEN],
 ["5", "Recommend", "Greedy maximal covering on underserved population", RED],
].forEach((st, i) => {
  const x = 0.7 + i * 2.48;
  s.addShape(pres.ShapeType.roundRect, { x, y: 1.95, w: 2.25, h: 2.5,
    fill: { color: TINT }, line: { color: LINE, width: 1 }, rectRadius: 0.08 });
  s.addShape(pres.ShapeType.ellipse, { x: x + 0.85, y: 2.17, w: 0.55, h: 0.55,
    fill: { color: st[3] } });
  s.addText(st[0], { x: x + 0.85, y: 2.17, w: 0.55, h: 0.55, align: "center",
    valign: "middle", fontFace: HF, fontSize: 18, bold: true, color: WHITE, margin: 0 });
  s.addText(st[1], { x: x + 0.15, y: 2.87, w: 1.95, h: 0.35, align: "center",
    fontFace: BF, fontSize: 15, bold: true, color: INK, margin: 0 });
  s.addText(st[2], { x: x + 0.15, y: 3.25, w: 1.95, h: 1.05, align: "center",
    fontFace: BF, fontSize: 11, color: MUTED, margin: 0 });
  if (i < 4) s.addText("→", { x: x + 2.2, y: 2.95, w: 0.3, h: 0.4, fontFace: BF,
    fontSize: 18, color: MUTED, margin: 0 });
});
s.addShape(pres.ShapeType.roundRect, { x: 0.7, y: 4.85, w: 12, h: 1.5,
  fill: { color: TINT }, line: { color: LINE, width: 1 }, rectRadius: 0.08 });
s.addText("Everything runs in a metric projection (UTM 46N, EPSG:32646) so distances are true metres, and the whole pipeline regenerates from a single command.",
  { x: 1.0, y: 5.05, w: 11.4, h: 0.55, fontFace: BF, fontSize: 14, color: INK, margin: 0 });
s.addText("Tools:  Python · NumPy · SciPy · Shapely · GeoPandas · OSMnx · rasterio · Matplotlib · pytest",
  { x: 1.0, y: 5.62, w: 11.4, h: 0.5, fontFace: BF, fontSize: 12.5, italic: true,
    color: MUTED, margin: 0 });
s.addNotes("Five stages. Emphasise that all distance work happens in metres, not degrees.");

// ================================================================ 10. METHOD
s = newSlide("05 · Method", "The mathematics behind it");
framedImage(s, FIG + "textbook_all.png", 0.7, 1.7, 5.6, 4.9);
s.addText("Voronoi construction", { x: 6.7, y: 1.75, w: 6, h: 0.35, fontFace: BF,
  fontSize: 15, bold: true, color: DEEP, margin: 0 });
s.addText("H(p,q) = { x : |x−p| ≤ |x−q| }", { x: 6.7, y: 2.12, w: 6, h: 0.35,
  fontFace: HF, fontSize: 15, italic: true, color: INK, margin: 0 });
s.addText("V(p) = B ∩ ⋂ H(p,q),   q ∈ N(p)", { x: 6.7, y: 2.5, w: 6, h: 0.35,
  fontFace: HF, fontSize: 15, italic: true, color: INK, margin: 0 });
s.addText("Each cell is an intersection of half-planes, so every interior edge is a true perpendicular bisector and exactly three cells meet at each vertex.",
  { x: 6.7, y: 2.92, w: 6, h: 0.8, fontFace: BF, fontSize: 13, color: MUTED, margin: 0 });
s.addText("Benefit index", { x: 6.7, y: 3.82, w: 6, h: 0.35, fontFace: BF,
  fontSize: 15, bold: true, color: GREEN, margin: 0 });
s.addText("B_s = 100 · ( Σ w_j · f_{s,j} ) / ( Σ w_j )", { x: 6.7, y: 4.18, w: 6, h: 0.35,
  fontFace: HF, fontSize: 15, italic: true, color: INK, margin: 0 });
s.addText("f is the population-weighted fraction of section s within reach of service j; w weights hospitals and fire ×2, water ×1.5.",
  { x: 6.7, y: 4.58, w: 6, h: 0.75, fontFace: BF, fontSize: 13, color: MUTED, margin: 0 });
s.addShape(pres.ShapeType.roundRect, { x: 6.7, y: 5.45, w: 6.0, h: 1.15,
  fill: { color: "E6EFE6" }, line: { color: GREEN, width: 1.5 }, rectRadius: 0.08 });
s.addText("Verified by 29 automated tests", { x: 6.95, y: 5.6, w: 5.5, h: 0.32,
  fontFace: BF, fontSize: 14, bold: true, color: GREEN, margin: 0 });
s.addText("Degree-3 vertices, exact tiling and bisector midpoints all checked automatically.",
  { x: 6.95, y: 5.94, w: 5.6, h: 0.55, fontFace: BF, fontSize: 12, color: INK, margin: 0 });
s.addNotes("Left: the three textbook cases we verified before touching Dhaka. Right: the two equations that define the whole method.");

// ============================================================ 11. THE DIAGRAMS
s = newSlide("05 · Method", "The six Voronoi diagrams");
framedImage(s, FIG + "voronoi_all_services.png", 0.6, 1.65, 6.9, 5.4);
s.addText("One colour and one marker per utility", { x: 7.8, y: 1.75, w: 5, h: 0.35,
  fontFace: BF, fontSize: 15, bold: true, color: DEEP, margin: 0 });
s.addText("Every cell is the region whose nearest facility of that type is the point inside it. The generator points \u2014 the facilities themselves \u2014 are drawn on every panel.",
  { x: 7.8, y: 2.15, w: 5.0, h: 1.0, fontFace: BF, fontSize: 13, color: MUTED, margin: 0 });
[["Metro station", "26", RED], ["Hospital", "286", GREEN],
 ["Water pump / source", "118", "1F77B4"], ["Fuel station", "135", AMBER],
 ["Bus stop", "314", "9467BD"], ["Fire station", "22", "8C564B"],
].forEach((r, i) => {
  const y = 3.25 + i * 0.52;
  s.addShape(pres.ShapeType.ellipse, { x: 7.85, y: y + 0.09, w: 0.22, h: 0.22,
    fill: { color: r[2] } });
  s.addText(r[0], { x: 8.2, y, w: 3.1, h: 0.4, fontFace: BF, fontSize: 13,
    color: INK, margin: 0 });
  s.addText(r[1] + " points", { x: 11.2, y, w: 1.6, h: 0.4, fontFace: BF,
    fontSize: 13, bold: true, color: r[2], align: "right", margin: 0 });
});
s.addShape(pres.ShapeType.roundRect, { x: 7.8, y: 6.42, w: 5.0, h: 0.62,
  fill: { color: "FBEEE9" }, line: { color: AMBER, width: 1.2 }, rectRadius: 0.08 });
s.addText("314 bus stops tessellate the centre finely; 22 fire stations give cells an order of magnitude larger.",
  { x: 8.0, y: 6.5, w: 4.7, h: 0.5, fontFace: BF, fontSize: 11.5, color: INK, margin: 0 });
s.addNotes("Each utility has its own colour and marker, and the generator points are visible on every panel. Point at fire stations versus bus stops \u2014 the cell-size contrast is the whole story.");

// ================================================================ 11. RESULTS
s = newSlide("06 · Result Analysis", "Coverage differs sharply by service");
s.addText("Share of the study area beyond each service's distance threshold", {
  x: 0.7, y: 1.6, w: 8, h: 0.35, fontFace: BF, fontSize: 14, color: MUTED, margin: 0 });
s.addChart(pres.ChartType.bar, [{ name: "% underserved",
  labels: ["Water", "Metro", "Bus", "Fuel", "Fire", "Hospital"],
  values: [73, 67, 57, 47, 41, 33] }], {
  x: 0.4, y: 2.0, w: 8.2, h: 4.5, barDir: "col", barGapWidthPct: 45,
  showTitle: false, showLegend: false, showValue: true, dataLabelPosition: "outEnd",
  dataLabelColor: INK, dataLabelFontFace: BF, dataLabelFontSize: 13, dataLabelFontBold: true,
  dataLabelFormatCode: '0"%"',
  chartColors: [RED, "CB5A2A", AMBER, TEAL, "3C8DBC", GREEN],
  catAxisLabelColor: INK, catAxisLabelFontFace: BF, catAxisLabelFontSize: 14,
  valAxisHidden: true, valGridLine: { style: "none" }, catGridLine: { style: "none" },
  valAxisMaxVal: 85, valAxisMinVal: 0 });
[["Widest gaps", "Water sources and metro — the metro follows only the MRT-6 corridor", RED],
 ["Narrowest gap", "Hospitals, at 33% — but the population view changes this", GREEN],
].forEach((c, i) => {
  const y = 2.25 + i * 2.15;
  s.addShape(pres.ShapeType.roundRect, { x: 9.0, y, w: 3.7, h: 1.85,
    fill: { color: TINT }, line: { color: LINE, width: 1 }, rectRadius: 0.08 });
  s.addText(c[0], { x: 9.25, y: y + 0.2, w: 3.2, h: 0.4, fontFace: BF, fontSize: 16,
    bold: true, color: c[2], margin: 0 });
  s.addText(c[1], { x: 9.25, y: y + 0.7, w: 3.25, h: 1.0, fontFace: BF, fontSize: 12.5,
    color: MUTED, margin: 0 });
});
s.addNotes("Coverage by area. Water and metro are the widest gaps; hospitals look strongest here. "
  + "NOTE: this is a native PowerPoint chart, not an image — edit its data directly if needed.");

// ================================================================ 12. RESULTS
s = newSlide("06 · Result Analysis", "Which areas benefit most");
framedImage(s, FIG + "section_benefit.png", 0.7, 1.7, 5.3, 5.0);
s.addText("Population- and criticality-weighted benefit score (% of people well served)", {
  x: 6.4, y: 1.75, w: 6.3, h: 0.55, fontFace: BF, fontSize: 14, color: INK, margin: 0 });
[["Mirpur", 92, GREEN], ["Banani", 90, GREEN], ["Dhanmondi", 85, GREEN],
 ["Gulshan", 81, "5DA130"], ["Khilgaon", 68, AMBER], ["Motijheel", 68, AMBER],
 ["Uttara", 61, "D35400"], ["Bashundhara", 55, RED],
].forEach((r, i) => {
  const y = 2.38 + i * 0.455;
  s.addText(r[0], { x: 6.4, y, w: 2.4, h: 0.4, fontFace: BF, fontSize: 14, bold: true,
    color: INK, margin: 0 });
  s.addShape(pres.ShapeType.roundRect, { x: 8.8, y: y + 0.05, w: (r[1] / 100) * 3.3,
    h: 0.27, fill: { color: r[2] }, rectRadius: 0.04 });
  s.addText(String(r[1]), { x: 12.2, y, w: 0.6, h: 0.4, fontFace: BF, fontSize: 13,
    bold: true, color: r[2], margin: 0 });
});
s.addShape(pres.ShapeType.roundRect, { x: 6.4, y: 6.05, w: 6.3, h: 0.68,
  fill: { color: "FBEEE9" }, line: { color: AMBER, width: 1.5 }, rectRadius: 0.08 });
s.addText("Motijheel: 3.1M residents — most populous, yet scores only 68", {
  x: 6.4, y: 6.05, w: 6.3, h: 0.68, align: "center", valign: "middle", fontFace: BF,
  fontSize: 13.5, bold: true, color: AMBER, margin: 0 });
s.addNotes("This is our headline finding. Weighting by people, not land, moves the priority to dense old Dhaka.");

// ================================================================ 13. RESULTS
s = newSlide("06 · Result Analysis", "Where new facilities should go");
framedImage(s, FIG + "recommendations_all_services.png", 0.6, 1.65, 6.8, 5.3);
s.addText("Greedy placement adds each facility at the most-populated location that is still underserved.",
  { x: 7.6, y: 1.72, w: 5.2, h: 0.9, fontFace: BF, fontSize: 13.5, color: INK, margin: 0 });
s.addTable(
  [["Service", "Underserved before", "After 3 new sites"].map((h) => ({
    text: h, options: { bold: true, color: WHITE, fill: { color: DEEP }, fontSize: 12 } }))].concat(
    [["Fire station", "1.67M", "0.73M"], ["Hospital", "1.07M", "0.61M"],
     ["Fuel station", "1.94M", "1.43M"], ["Metro station", "5.0M", "3.9M"],
     ["Bus stop", "3.0M", "2.8M"], ["Water pump", "4.7M", "4.3M"]].map((r, i) => [
      { text: r[0], options: { fontSize: 13, bold: true, color: INK, fill: { color: i % 2 ? TINT : WHITE } } },
      { text: r[1], options: { fontSize: 13, color: MUTED, align: "center", fill: { color: i % 2 ? TINT : WHITE } } },
      { text: r[2], options: { fontSize: 13, bold: true, color: GREEN, align: "center", fill: { color: i % 2 ? TINT : WHITE } } },
    ])),
  { x: 7.6, y: 2.72, w: 5.2, colW: [2.0, 1.6, 1.6], border: { pt: 0.5, color: LINE },
    fontFace: BF, rowH: 0.42, valign: "middle" });
s.addShape(pres.ShapeType.roundRect, { x: 7.6, y: 5.95, w: 5.2, h: 0.95,
  fill: { color: "E6EFE6" }, line: { color: GREEN, width: 1.5 }, rectRadius: 0.08 });
s.addText("Three fire stations alone bring 946,000 people back within reach.", {
  x: 7.7, y: 5.95, w: 5.0, h: 0.95, align: "center", valign: "middle", fontFace: BF,
  fontSize: 13.5, bold: true, color: GREEN, margin: 0 });
s.addNotes("Because placement targets population, proposed sites land in dense underserved areas, not empty land.");

// ================================================================ 14. RESULTS
s = newSlide("06 · Result Analysis", "Validation and equity");
[["2SFCA", "Against the standard supply–demand method", "ρ = 0.93 metro & water; 0.71 hospitals", TEAL],
 ["Exact optimum", "Greedy vs exhaustive maximal covering", "Greedy recovers ~100% of optimal", GREEN],
 ["Road network", "Shortest paths on a 43k-node graph", "Detour ×1.5 — underserved doubles", RED],
].forEach((c, i) => {
  const x = 0.7 + i * 4.15;
  s.addShape(pres.ShapeType.roundRect, { x, y: 1.75, w: 3.85, h: 2.35,
    fill: { color: TINT }, line: { color: LINE, width: 1 }, rectRadius: 0.08 });
  s.addText(c[0], { x: x + 0.25, y: 1.93, w: 3.4, h: 0.4, fontFace: BF, fontSize: 17,
    bold: true, color: c[3], margin: 0 });
  s.addText(c[1], { x: x + 0.25, y: 2.4, w: 3.4, h: 0.65, fontFace: BF, fontSize: 12,
    color: MUTED, margin: 0 });
  s.addText(c[2], { x: x + 0.25, y: 3.1, w: 3.4, h: 0.85, fontFace: BF, fontSize: 13,
    bold: true, color: INK, margin: 0 });
});
framedImage(s, FIG + "lorenz_access.png", 1.1, 4.35, 3.3, 2.3);
statCard(s, 5.0, 4.6, 3.7, 1.75, "0.165", "Gini coefficient — mild inequality", DEEP);
statCard(s, 9.0, 4.6, 3.7, 1.75, "0.99", "Moran's I — strongly clustered (p = 0.005)", TEAL);
s.addNotes("Three checks plus the equity measures. Be upfront that road distance roughly doubles the underserved share.");

// ================================================================ 15. LIMITATIONS
s = newSlide("07 · Limitations", "What the model does not do");
s.addText("Limitations", { x: 0.7, y: 1.7, w: 5.6, h: 0.4, fontFace: BF, fontSize: 18,
  bold: true, color: RED, margin: 0 });
bullets(s, [
  "Straight-line distance in the core analysis, not travel time.",
  "OpenStreetMap completeness varies — counts are a lower bound.",
  "Facility capacity is not modelled (no reliable open data).",
  "Sections are analytical zones, not official ward boundaries.",
  "Population is a modelled 1 km raster from 2020.",
  "Thresholds and weights are planning conventions, not laws.",
], 0.7, 2.2, 5.6, 13.5);
s.addText("Future Work Scopes", { x: 6.9, y: 1.7, w: 5.8, h: 0.4, fontFace: BF,
  fontSize: 18, bold: true, color: GREEN, margin: 0 });
bullets(s, [
  "Travel time under realistic traffic conditions.",
  "Capacity-weighted Voronoi using official registries.",
  "Finer 100 m population and official thana boundaries.",
  "Socio-economic weighting — income, vehicle ownership.",
  "Machine-learning prediction of emerging service gaps.",
  "Transfer the framework to Chattogram, Khulna and Sylhet.",
], 6.9, 2.2, 5.8, 13.5);
s.addShape(pres.ShapeType.roundRect, { x: 0.7, y: 5.85, w: 12, h: 0.8,
  fill: { color: TINT }, line: { color: LINE, width: 1 }, rectRadius: 0.08 });
s.addText("Each limitation maps directly onto a concrete next step — and the sensitivity analysis shows our rankings hold under ±25% threshold changes (ρ ≈ 0.98).",
  { x: 0.7, y: 5.85, w: 12, h: 0.8, align: "center", valign: "middle", fontFace: BF,
    fontSize: 13.5, italic: true, color: MUTED, margin: 0 });
s.addNotes("Being explicit here is a strength, not a weakness. Every limitation has a matching future-work item.");

// ================================================================ 16. CONCLUSION
s = newSlide("08 · Conclusion", "What the study delivers", { dark: true });
[["Central belt is best served", "Mirpur, Banani and Dhanmondi sit inside the dense facility cluster."],
 ["Motijheel is the highest-impact fix", "Most populous section, only moderately served — priority for hospitals and fire stations."],
 ["Water and metro are the widest gaps", "Metro reaches only the MRT-6 corridor; water sources are thin city-wide."],
 ["Straight-line analysis understates the gap", "Road-network distance roughly doubles the underserved share."],
].forEach((t, i) => {
  const y = 1.8 + i * 1.1;
  s.addShape(pres.ShapeType.ellipse, { x: 0.7, y, w: 0.5, h: 0.5, fill: { color: TEAL } });
  s.addText(String(i + 1), { x: 0.7, y, w: 0.5, h: 0.5, align: "center", valign: "middle",
    fontFace: HF, fontSize: 17, bold: true, color: WHITE, margin: 0 });
  s.addText(t[0], { x: 1.45, y: y - 0.02, w: 11, h: 0.4, fontFace: BF, fontSize: 17,
    bold: true, color: WHITE, margin: 0 });
  s.addText(t[1], { x: 1.45, y: y + 0.38, w: 11.2, h: 0.5, fontFace: BF, fontSize: 12.5,
    color: "AEC4DD", margin: 0 });
});
s.addShape(pres.ShapeType.roundRect, { x: 0.7, y: 6.3, w: 5.9, h: 0.8,
  fill: { color: "16385C" }, line: { color: "2C5680", width: 1 }, rectRadius: 0.07 });
s.addText("Reproducible:  python voronoi_dhaka.py  ·  29 tests", { x: 0.85, y: 6.3,
  w: 5.6, h: 0.8, valign: "middle", fontFace: BF, fontSize: 12, color: "AEC4DD", margin: 0 });
s.addShape(pres.ShapeType.roundRect, { x: 6.8, y: 6.3, w: 5.9, h: 0.8,
  fill: { color: TEAL }, line: { color: TEAL, width: 1 }, rectRadius: 0.07 });
s.addText("Thank you  —  Questions?", { x: 6.8, y: 6.3, w: 5.9, h: 0.8, align: "center",
  valign: "middle", fontFace: HF, fontSize: 20, bold: true, color: WHITE, margin: 0 });
s.addNotes("Four findings; everything regenerates from one command. Thank you — we are happy to take questions.");

pres.writeFile({ fileName: OUT }).then((f) => console.log("saved", f));
