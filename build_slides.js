/**
 * Thesis defense deck for the AIUB Voronoi utility-services study.
 * Run:  NODE_PATH="$(npm root -g)" node build_slides.js
 */
const pptxgen = require("pptxgenjs");

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE"; // 13.33 x 7.5 in
pres.author = "Minhazul Abedin";
pres.title = "Providing Utility Services using Voronoi Diagrams";

const FIG = "outputs/figures/";
const OUT = "outputs/Dhaka_Voronoi_Defense.pptx";

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

function framedImage(slide, path, x, y, w, h) {
  slide.addShape(pres.ShapeType.roundRect, {
    x: x - 0.05, y: y - 0.05, w: w + 0.1, h: h + 0.1,
    fill: { color: WHITE }, line: { color: LINE, width: 1 }, rectRadius: 0.06,
    shadow: { type: "outer", color: "8B99A6", blur: 8, offset: 2, angle: 90, opacity: 0.5 },
  });
  slide.addImage({ path, x, y, w, h, sizing: { type: "contain", w, h } });
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

// ------------------------------------------------------------------ 1. title
let s = pres.addSlide();
s.background = { color: NAVY };
s.addImage({ path: "data/templates/aiub_logo.png", x: 6.17, y: 0.35, w: 1.0, h: 1.0 });
s.addText("AMERICAN INTERNATIONAL UNIVERSITY-BANGLADESH", {
  x: 0.5, y: 1.45, w: 12.3, h: 0.3, align: "center", fontFace: BF, fontSize: 12,
  bold: true, color: "8FB3D9", charSpacing: 1.5, margin: 0 });
s.addText("Faculty of Science and Technology  ·  Department of Computer Science", {
  x: 0.5, y: 1.78, w: 12.3, h: 0.3, align: "center", fontFace: BF, fontSize: 12,
  color: "AEC4DD", margin: 0 });
s.addText("Providing Utility Services using Voronoi Diagrams", {
  x: 0.6, y: 2.35, w: 12.1, h: 0.7, align: "center", fontFace: HF, fontSize: 32,
  bold: true, color: WHITE, margin: 0 });
s.addText("Some Analyses, Recommendations, along with a Case Study for Dhaka City", {
  x: 0.8, y: 3.1, w: 11.7, h: 0.5, align: "center", fontFace: BF, fontSize: 16,
  italic: true, color: "CADCFC", margin: 0 });
const team = [
  "Minhazul Abedin (21-44625-1)", "Zarin Tasnim Rayta (21-45742-3)",
  "Abdullah Al Noman (21-45825-3)", "Mehedi Hasan Aziz (19-40060-1)",
];
team.forEach((t, i) => {
  s.addShape(pres.ShapeType.roundRect, {
    x: 0.75 + i * 3.05, y: 4.05, w: 2.85, h: 0.55,
    fill: { color: "16385C" }, line: { color: "2C5680", width: 1 }, rectRadius: 0.08 });
  s.addText(t, { x: 0.75 + i * 3.05, y: 4.05, w: 2.85, h: 0.55, align: "center",
    valign: "middle", fontFace: BF, fontSize: 12, color: "CADCFC", margin: 0 });
});
s.addText("Supervised by", { x: 0.5, y: 4.95, w: 12.3, h: 0.3, align: "center",
  fontFace: BF, fontSize: 12, color: "8FB3D9", margin: 0 });
s.addText("Dr. Md. Manzurul Hasan", { x: 0.5, y: 5.25, w: 12.3, h: 0.4, align: "center",
  fontFace: HF, fontSize: 20, bold: true, color: WHITE, margin: 0 });
s.addText("Associate Professor, Department of Computer Science", {
  x: 0.5, y: 5.68, w: 12.3, h: 0.3, align: "center", fontFace: BF, fontSize: 12,
  color: "AEC4DD", margin: 0 });
s.addText("Fall 2025-2026  ·  Defense: 06.07.2026", { x: 0.5, y: 6.5, w: 12.3, h: 0.3,
  align: "center", fontFace: BF, fontSize: 12, italic: true, color: "8FB3D9", margin: 0 });
s.addNotes("Assalamu Alaikum. We are presenting our thesis on providing utility services using Voronoi diagrams, with a case study of Dhaka City.");

// ------------------------------------------------------------------ 2. outline
s = newSlide("Overview", "What we will cover");
const agenda = [
  ["01", "Problem & Objectives", "Why utility access in Dhaka needs measuring"],
  ["02", "Literature & Gap", "What exists, and what is missing"],
  ["03", "Proposed Model", "Voronoi partitioning and the benefit index"],
  ["04", "Data", "901 real facilities, 10.7M residents"],
  ["05", "Results", "Coverage, sections, recommendations"],
  ["06", "Validation", "2SFCA, exact optimum, road network"],
];
agenda.forEach((a, i) => {
  const x = 0.7 + (i % 2) * 6.2, y = 1.85 + Math.floor(i / 2) * 1.55;
  s.addShape(pres.ShapeType.roundRect, { x, y, w: 5.9, h: 1.25,
    fill: { color: TINT }, line: { color: LINE, width: 1 }, rectRadius: 0.08 });
  s.addText(a[0], { x: x + 0.25, y: y + 0.2, w: 0.8, h: 0.8, fontFace: HF,
    fontSize: 26, bold: true, color: TEAL, margin: 0 });
  s.addText(a[1], { x: x + 1.15, y: y + 0.22, w: 4.5, h: 0.4, fontFace: BF,
    fontSize: 17, bold: true, color: INK, margin: 0 });
  s.addText(a[2], { x: x + 1.15, y: y + 0.68, w: 4.6, h: 0.4, fontFace: BF,
    fontSize: 12, color: MUTED, margin: 0 });
});
s.addNotes("Six parts: the problem, the literature gap, our model, the data, the results, and how we validated them.");

// ------------------------------------------------------------------ 3. problem
s = newSlide("The problem", "Dhaka grew faster than its utilities");
bullets(s, [
  "One of the world's densest cities, expanded largely unplanned.",
  "Transport, health, water, fuel and emergency networks lag behind.",
  "No consolidated official registry of facility locations exists.",
  "Result: some neighbourhoods are well served, others are not — and nobody has measured it across services.",
], 0.7, 1.75, 6.6, 16);
s.addShape(pres.ShapeType.roundRect, { x: 0.7, y: 4.6, w: 6.6, h: 1.75,
  fill: { color: "FBEEE9" }, line: { color: AMBER, width: 1.5 }, rectRadius: 0.08 });
s.addText("Research problem", { x: 0.95, y: 4.78, w: 6, h: 0.35, fontFace: BF,
  fontSize: 14, bold: true, color: AMBER, margin: 0 });
s.addText("Existing Dhaka studies examine one service at a time and weight coverage by land area, not by the people actually affected.",
  { x: 0.95, y: 5.15, w: 6.1, h: 1.0, fontFace: BF, fontSize: 14, color: INK, margin: 0 });
framedImage(s, FIG + "sections_only.png", 7.9, 1.7, 4.8, 4.9);
s.addNotes("Dhaka's utilities have not kept pace with its growth. Prior studies look at a single service and measure over area rather than population.");

// ------------------------------------------------------------------ 4. objectives
s = newSlide("Aim", "Objectives and research questions");
s.addText("Research Objectives", { x: 0.7, y: 1.7, w: 5.8, h: 0.35, fontFace: BF,
  fontSize: 16, bold: true, color: DEEP, margin: 0 });
["Partition Dhaka into Voronoi service areas for six utilities.",
 "Quantify coverage and find underserved areas, weighted by population.",
 "Rank the city's areas by how well residents are served.",
 "Recommend new facility locations that most improve access.",
 "Validate against established methods and release reproducible software.",
].forEach((t, i) => {
  s.addText(["i", "ii", "iii", "iv", "v"][i] + ".", { x: 0.7, y: 2.15 + i * 0.62,
    w: 0.45, h: 0.4, fontFace: BF, fontSize: 14, bold: true, color: TEAL, margin: 0 });
  s.addText(t, { x: 1.15, y: 2.15 + i * 0.62, w: 5.3, h: 0.55, fontFace: BF,
    fontSize: 13.5, color: INK, margin: 0 });
});
s.addShape(pres.ShapeType.roundRect, { x: 7.1, y: 1.65, w: 5.6, h: 4.6,
  fill: { color: TINT }, line: { color: LINE, width: 1 }, rectRadius: 0.08 });
s.addText("Research Questions", { x: 7.4, y: 1.85, w: 5, h: 0.35, fontFace: BF,
  fontSize: 16, bold: true, color: DEEP, margin: 0 });
["How well do the six utilities cover Dhaka, and where are the gaps?",
 "Which areas benefit most once population is taken into account?",
 "Where should new facilities go to help the most people?",
 "Do the results agree with established methods, and how much does road distance change them?",
].forEach((t, i) => {
  s.addText(["i", "ii", "iii", "iv"][i] + ".", { x: 7.4, y: 2.35 + i * 0.95,
    w: 0.4, h: 0.4, fontFace: BF, fontSize: 14, bold: true, color: AMBER, margin: 0 });
  s.addText(t, { x: 7.8, y: 2.35 + i * 0.95, w: 4.7, h: 0.85, fontFace: BF,
    fontSize: 13.5, color: INK, margin: 0 });
});
s.addNotes("Five objectives and four questions; the questions map one-to-one onto the results section.");

// ------------------------------------------------------------------ 5. literature
s = newSlide("Chapter 2", "Literature and the research gap");
const litRows = [
  ["Okabe et al. [16]", "2000", "Voronoi tessellations", "Foundational theory"],
  ["Church & ReVelle [6]", "1974", "Maximal covering (MCLP)", "Siting under a threshold"],
  ["Luo & Wang [14]", "2003", "2SFCA", "Single service; no siting"],
  ["Ahmed et al. [1]", "2019", "2SFCA + traffic, Dhaka", "Emergency care only"],
  ["Alam et al. [2]", "2025", "Accessibility index, Dhaka", "Open space only"],
  ["This study", "2026", "Voronoi + pop-weighting + MCLP", "Six utilities, reproducible"],
];
s.addTable(
  [["Study", "Year", "Method", "Scope / limitation"].map((h) => ({
    text: h, options: { bold: true, color: WHITE, fill: { color: DEEP }, fontSize: 12 } }))].concat(
    litRows.map((r, i) => r.map((c) => ({
      text: c,
      options: { fontSize: 11.5, color: INK,
        fill: { color: i === litRows.length - 1 ? "E6EFE6" : (i % 2 ? TINT : WHITE) },
        bold: i === litRows.length - 1 } })))),
  { x: 0.7, y: 1.8, w: 12, colW: [2.7, 1.0, 4.0, 4.3], border: { pt: 0.5, color: LINE },
    fontFace: BF, rowH: 0.42, valign: "middle" }
);
s.addShape(pres.ShapeType.roundRect, { x: 0.7, y: 5.15, w: 12, h: 1.2,
  fill: { color: "FBEEE9" }, line: { color: AMBER, width: 1.5 }, rectRadius: 0.08 });
s.addText("Research gap", { x: 0.95, y: 5.3, w: 4, h: 0.3, fontFace: BF, fontSize: 13,
  bold: true, color: AMBER, margin: 0 });
s.addText("No integrated, multi-utility, population-weighted and reproducible accessibility study of Dhaka that also recommends where to invest.",
  { x: 0.95, y: 5.62, w: 11.4, h: 0.6, fontFace: BF, fontSize: 14, color: INK, margin: 0 });
s.addNotes("The literature gives us the method and the data, but every Dhaka study is single-service. That gap is what we fill.");

// ------------------------------------------------------------------ 6. method
s = newSlide("Chapter 3", "The proposed model");
const stages = [
  ["1", "Collect", "Six services from OpenStreetMap; population from WorldPop", DEEP],
  ["2", "Partition", "Exact Voronoi cells from perpendicular bisectors", TEAL],
  ["3", "Measure", "Nearest-facility distance on a 250 m grid (k-d tree)", AMBER],
  ["4", "Score", "Population- and criticality-weighted benefit index", GREEN],
  ["5", "Recommend", "Greedy maximal covering on underserved population", RED],
];
stages.forEach((st, i) => {
  const x = 0.7 + i * 2.48;
  s.addShape(pres.ShapeType.roundRect, { x, y: 1.9, w: 2.25, h: 2.5,
    fill: { color: TINT }, line: { color: LINE, width: 1 }, rectRadius: 0.08 });
  s.addShape(pres.ShapeType.ellipse, { x: x + 0.85, y: 2.12, w: 0.55, h: 0.55,
    fill: { color: st[3] } });
  s.addText(st[0], { x: x + 0.85, y: 2.12, w: 0.55, h: 0.55, align: "center",
    valign: "middle", fontFace: HF, fontSize: 18, bold: true, color: WHITE, margin: 0 });
  s.addText(st[1], { x: x + 0.15, y: 2.82, w: 1.95, h: 0.35, align: "center",
    fontFace: BF, fontSize: 15, bold: true, color: INK, margin: 0 });
  s.addText(st[2], { x: x + 0.15, y: 3.2, w: 1.95, h: 1.05, align: "center",
    fontFace: BF, fontSize: 11, color: MUTED, margin: 0 });
  if (i < stages.length - 1) {
    s.addText("→", { x: x + 2.2, y: 2.9, w: 0.3, h: 0.4, fontFace: BF, fontSize: 18,
      color: MUTED, margin: 0 });
  }
});
s.addText("V(p)  =  B  ∩  ⋂  H(p,q),   q ∈ N(p)          H(p,q) = { x : |x−p| ≤ |x−q| }", {
  x: 0.7, y: 4.8, w: 12, h: 0.5, align: "center", fontFace: HF, fontSize: 17,
  italic: true, color: INK, margin: 0 });
s.addText("Each cell is an intersection of half-planes, so every interior edge is a true perpendicular bisector and exactly three cells meet at each vertex — verified by 29 automated tests.",
  { x: 1.3, y: 5.45, w: 10.8, h: 0.8, align: "center", fontFace: BF, fontSize: 13,
    color: MUTED, margin: 0 });
s.addNotes("Five stages. The key property is that cells are half-plane intersections, which guarantees exact bisector edges — and we test that automatically.");

// ------------------------------------------------------------------ 7. correctness
s = newSlide("Verification", "The geometry is provably correct");
framedImage(s, FIG + "textbook_all.png", 0.7, 1.7, 6.5, 4.9);
bullets(s, [
  "Seeds in general position — no three collinear, no four cocircular.",
  "Every edge is a straight perpendicular bisector.",
  "Exactly three cells meet at each vertex (red circles).",
  "Cells tile the region exactly — no gaps, no overlaps.",
], 7.7, 2.0, 5.0, 15);
s.addShape(pres.ShapeType.roundRect, { x: 7.7, y: 4.85, w: 5.0, h: 1.4,
  fill: { color: "E6EFE6" }, line: { color: GREEN, width: 1.5 }, rectRadius: 0.08 });
s.addText("29 automated tests pass", { x: 7.95, y: 5.05, w: 4.5, h: 0.35, fontFace: BF,
  fontSize: 15, bold: true, color: GREEN, margin: 0 });
s.addText("Geometry, coverage metrics and the recommender are all under test.",
  { x: 7.95, y: 5.42, w: 4.6, h: 0.7, fontFace: BF, fontSize: 12.5, color: INK, margin: 0 });
s.addNotes("Before touching Dhaka we proved the construction on three textbook cases from the course, and locked it with a test suite.");

// ------------------------------------------------------------------ 8. data
s = newSlide("Chapter 4", "Authentic open data");
statCard(s, 0.7, 1.75, 2.9, 1.5, "901", "facilities mapped", DEEP);
statCard(s, 3.85, 1.75, 2.9, 1.5, "6", "utility services", TEAL);
statCard(s, 7.0, 1.75, 2.9, 1.5, "10.7M", "residents covered", AMBER);
statCard(s, 10.15, 1.75, 2.55, 1.5, "8", "named sections", GREEN);
const dataRows = [
  ["Metro station", "railway=station | halt", "36", "26"],
  ["Hospital", "amenity=hospital", "451", "286"],
  ["Water pump / source", "man_made=water_well …", "487", "118"],
  ["Fuel station", "amenity=fuel", "219", "135"],
  ["Bus stop", "highway=bus_stop", "559", "314"],
  ["Fire station", "amenity=fire_station", "29", "22"],
];
s.addTable(
  [["Service", "OpenStreetMap tag", "Raw", "Cleaned"].map((h) => ({
    text: h, options: { bold: true, color: WHITE, fill: { color: DEEP }, fontSize: 12 } }))].concat(
    dataRows.map((r, i) => r.map((c) => ({
      text: c, options: { fontSize: 12, color: INK, fill: { color: i % 2 ? TINT : WHITE } } })))),
  { x: 0.7, y: 3.55, w: 7.6, colW: [2.3, 3.0, 1.15, 1.15], border: { pt: 0.5, color: LINE },
    fontFace: BF, rowH: 0.38, valign: "middle" }
);
bullets(s, [
  "Live OpenStreetMap query via OSMnx — no synthetic points needed.",
  "Polygons reduced to interior points; duplicates within 150 m removed.",
  "Clipped to the OSM administrative boundary of Dhaka.",
  "Population from the WorldPop 1 km UN-adjusted raster (2020).",
], 8.6, 3.6, 4.1, 12.5);
s.addNotes("All data is real and openly licensed. The raw-to-cleaned drop is duplicate mapping and out-of-boundary features, not data loss.");

// ------------------------------------------------------------------ 9. coverage
s = newSlide("Results", "Coverage differs sharply by service");
s.addText("Share of the study area beyond each service's distance threshold", {
  x: 0.7, y: 1.62, w: 8, h: 0.35, fontFace: BF, fontSize: 14, color: MUTED, margin: 0 });
s.addChart(pres.ChartType.bar, [{
  name: "% underserved",
  labels: ["Water", "Metro", "Bus", "Fuel", "Fire", "Hospital"],
  values: [73, 67, 57, 47, 41, 33],
}], {
  x: 0.4, y: 2.05, w: 8.2, h: 4.5, barDir: "col", barGapWidthPct: 45,
  showTitle: false, showLegend: false, showValue: true, dataLabelPosition: "outEnd",
  dataLabelColor: INK, dataLabelFontFace: BF, dataLabelFontSize: 13, dataLabelFontBold: true,
  dataLabelFormatCode: '0"%"',
  chartColors: [RED, "CB5A2A", AMBER, TEAL, "3C8DBC", GREEN],
  catAxisLabelColor: INK, catAxisLabelFontFace: BF, catAxisLabelFontSize: 14,
  valAxisHidden: true, valGridLine: { style: "none" }, catGridLine: { style: "none" },
  valAxisMaxVal: 85, valAxisMinVal: 0,
});
[["Water & metro", "widest gaps — metro follows only the MRT-6 corridor", RED],
 ["Hospitals", "best area coverage, but see the population view next", GREEN],
].forEach((c, i) => {
  const y = 2.3 + i * 2.15;
  s.addShape(pres.ShapeType.roundRect, { x: 9.0, y, w: 3.7, h: 1.85,
    fill: { color: TINT }, line: { color: LINE, width: 1 }, rectRadius: 0.08 });
  s.addText(c[0], { x: 9.25, y: y + 0.22, w: 3.2, h: 0.4, fontFace: BF, fontSize: 16,
    bold: true, color: c[2], margin: 0 });
  s.addText(c[1], { x: 9.25, y: y + 0.72, w: 3.25, h: 0.95, fontFace: BF, fontSize: 12.5,
    color: MUTED, margin: 0 });
});
s.addNotes("Water and metro have the widest gaps by area. Hospitals look best here — but that changes once we weight by population.");

// ------------------------------------------------------------------ 10. sections
s = newSlide("Results", "Dhaka in eight coloured sections");
framedImage(s, FIG + "sections_only.png", 0.7, 1.7, 4.9, 5.0);
s.addText("Every facility seeds a Voronoi cell; each cell takes the colour of the named area its seed falls in. Dashed lines are the coarse eight-section partition.",
  { x: 6.0, y: 1.85, w: 6.6, h: 1.0, fontFace: BF, fontSize: 15, color: INK, margin: 0 });
const secs = [["Uttara", "e6194B"], ["Mirpur", "f58231"], ["Bashundhara", "911eb4"],
  ["Banani", "4363d8"], ["Gulshan", "3cb44b"], ["Dhanmondi", "42d4f4"],
  ["Khilgaon", "f032e6"], ["Motijheel", "ffe119"]];
secs.forEach((z, i) => {
  const x = 6.0 + (i % 2) * 3.35, y = 3.15 + Math.floor(i / 2) * 0.62;
  s.addShape(pres.ShapeType.ellipse, { x, y: y + 0.04, w: 0.26, h: 0.26, fill: { color: z[1] } });
  s.addText(z[0], { x: x + 0.36, y, w: 2.8, h: 0.34, fontFace: BF, fontSize: 15,
    bold: true, color: INK, margin: 0 });
});
s.addShape(pres.ShapeType.roundRect, { x: 6.0, y: 5.85, w: 6.6, h: 0.85,
  fill: { color: TINT }, line: { color: LINE, width: 1 }, rectRadius: 0.08 });
s.addText("A genuine Voronoi diagram that is also a legible map of the city.",
  { x: 6.0, y: 5.85, w: 6.6, h: 0.85, align: "center", valign: "middle", fontFace: BF,
    fontSize: 14, italic: true, color: MUTED, margin: 0 });
s.addNotes("This is the flagship figure: a mathematically exact Voronoi diagram that still reads as a recognisable map of Dhaka.");

// ------------------------------------------------------------------ 11. benefit
s = newSlide("Key finding", "Which areas benefit most");
framedImage(s, FIG + "section_benefit.png", 0.7, 1.7, 5.3, 5.0);
s.addText("Population- and emergency-weighted benefit score (% of people well served)", {
  x: 6.4, y: 1.78, w: 6.3, h: 0.6, fontFace: BF, fontSize: 14, color: INK, margin: 0 });
const rank = [["Mirpur", 92, GREEN], ["Banani", 90, GREEN], ["Dhanmondi", 85, GREEN],
  ["Gulshan", 81, "5DA130"], ["Khilgaon", 68, AMBER], ["Motijheel", 68, AMBER],
  ["Uttara", 61, "D35400"], ["Bashundhara", 55, RED]];
rank.forEach((r, i) => {
  const y = 2.38 + i * 0.455;
  s.addText(r[0], { x: 6.4, y, w: 2.4, h: 0.4, fontFace: BF, fontSize: 14, bold: true,
    color: INK, margin: 0 });
  s.addShape(pres.ShapeType.roundRect, { x: 8.8, y: y + 0.06, w: (r[1] / 100) * 3.3,
    h: 0.28, fill: { color: r[2] }, rectRadius: 0.04 });
  s.addText(String(r[1]), { x: 12.2, y, w: 0.6, h: 0.4, fontFace: BF, fontSize: 13,
    bold: true, color: r[2], margin: 0 });
});
s.addShape(pres.ShapeType.roundRect, { x: 6.4, y: 6.05, w: 6.3, h: 0.7,
  fill: { color: "FBEEE9" }, line: { color: AMBER, width: 1.5 }, rectRadius: 0.08 });
s.addText("Motijheel: 3.1M residents — most populous, yet only 68", {
  x: 6.4, y: 6.05, w: 6.3, h: 0.7, align: "center", valign: "middle", fontFace: BF,
  fontSize: 14, bold: true, color: AMBER, margin: 0 });
s.addNotes("Weighting by people changes the story. The central belt is best served. Motijheel is the most populous section but only moderately served — that makes it the highest-impact target.");

// ------------------------------------------------------------------ 12. recommendations
s = newSlide("Results", "Where new facilities should go");
framedImage(s, FIG + "recommendations_all_services.png", 0.6, 1.65, 6.8, 5.3);
s.addText("Greedy placement adds each facility at the most-populated location that is still underserved.",
  { x: 7.6, y: 1.8, w: 5.2, h: 0.6, fontFace: BF, fontSize: 13.5, color: INK, margin: 0 });
const recRows = [["Fire station", "1.67M", "0.74M"], ["Hospital", "1.07M", "0.61M"],
  ["Fuel station", "1.94M", "1.42M"], ["Metro station", "5.0M", "3.9M"],
  ["Bus stop", "3.0M", "2.8M"], ["Water pump", "4.7M", "4.3M"]];
s.addTable(
  [["Service", "Underserved before", "After 3 new sites"].map((h) => ({
    text: h, options: { bold: true, color: WHITE, fill: { color: DEEP }, fontSize: 12 } }))].concat(
    recRows.map((r, i) => [
      { text: r[0], options: { fontSize: 13, bold: true, color: INK, fill: { color: i % 2 ? TINT : WHITE } } },
      { text: r[1], options: { fontSize: 13, color: MUTED, align: "center", fill: { color: i % 2 ? TINT : WHITE } } },
      { text: r[2], options: { fontSize: 13, bold: true, color: GREEN, align: "center", fill: { color: i % 2 ? TINT : WHITE } } },
    ])),
  { x: 7.6, y: 2.6, w: 5.2, colW: [2.0, 1.6, 1.6], border: { pt: 0.5, color: LINE },
    fontFace: BF, rowH: 0.44, valign: "middle" }
);
s.addShape(pres.ShapeType.roundRect, { x: 7.6, y: 5.95, w: 5.2, h: 0.75,
  fill: { color: "E6EFE6" }, line: { color: GREEN, width: 1.5 }, rectRadius: 0.08 });
s.addText("Three fire stations alone bring 930,000 people back within reach.", {
  x: 7.6, y: 5.95, w: 5.2, h: 0.75, align: "center", valign: "middle", fontFace: BF,
  fontSize: 14, bold: true, color: GREEN, margin: 0 });
s.addNotes("Because placement targets population, the proposed sites land in dense underserved areas rather than empty land.");

// ------------------------------------------------------------------ 13. validation
s = newSlide("Validation", "Three independent checks");
const checks = [
  ["2SFCA", "Compared against the standard supply–demand method", "ρ = 0.93 for metro and water; 0.71 hospitals", TEAL],
  ["Exact optimum", "Greedy vs exhaustive maximal covering", "Greedy recovers ~100% of optimal coverage", GREEN],
  ["Road network", "Shortest paths on 43k-node Dhaka graph", "Median detour ×1.5 — underserved share doubles", RED],
];
checks.forEach((c, i) => {
  const x = 0.7 + i * 4.15;
  s.addShape(pres.ShapeType.roundRect, { x, y: 1.8, w: 3.85, h: 2.6,
    fill: { color: TINT }, line: { color: LINE, width: 1 }, rectRadius: 0.08 });
  s.addText(c[0], { x: x + 0.25, y: 2.0, w: 3.4, h: 0.4, fontFace: BF, fontSize: 18,
    bold: true, color: c[3], margin: 0 });
  s.addText(c[1], { x: x + 0.25, y: 2.5, w: 3.4, h: 0.7, fontFace: BF, fontSize: 12.5,
    color: MUTED, margin: 0 });
  s.addText(c[2], { x: x + 0.25, y: 3.3, w: 3.4, h: 0.9, fontFace: BF, fontSize: 13.5,
    bold: true, color: INK, margin: 0 });
});
framedImage(s, FIG + "network_vs_euclid.png", 2.6, 4.6, 8.2, 2.1);
s.addNotes("Three checks: agreement with 2SFCA for scarce services, near-optimal greedy placement, and the honest finding that straight-line distance understates the gap.");

// ------------------------------------------------------------------ 14. equity
s = newSlide("Analysis", "Access is unequal — and clustered");
framedImage(s, FIG + "lorenz_access.png", 1.1, 1.75, 4.4, 4.6);
statCard(s, 6.3, 1.9, 3.0, 1.7, "0.165", "Gini coefficient of access", DEEP);
statCard(s, 9.6, 1.9, 3.1, 1.7, "0.99", "Moran's I (p = 0.005)", TEAL);
bullets(s, [
  "Moderate inequality: the Lorenz curve sits below the equality line.",
  "Very strong spatial clustering — well- and poorly-served areas form contiguous regions, not a random scatter.",
  "This is what justifies treating the city as eight coherent sections.",
  "Ranking is robust: ±25% thresholds or equal weights leave it unchanged (ρ ≈ 0.98).",
], 6.3, 3.9, 6.4, 14);
s.addNotes("Two numbers summarise equity: a Gini of 0.165 and a Moran's I of 0.99, meaning inequality is real and geographically organised.");

// ------------------------------------------------------------------ 15. limitations
s = newSlide("Chapter 6", "Limitations and future work");
s.addText("Limitations", { x: 0.7, y: 1.7, w: 5.6, h: 0.4, fontFace: BF, fontSize: 18,
  bold: true, color: RED, margin: 0 });
bullets(s, [
  "Straight-line distance in the core analysis, not travel time.",
  "OpenStreetMap completeness varies — counts are a lower bound.",
  "Facility capacity is not modelled (no reliable open data).",
  "Sections are analytical zones, not official ward boundaries.",
  "Population is a modelled 1 km raster from 2020.",
], 0.7, 2.2, 5.6, 13.5);
s.addText("Future Work Scopes", { x: 6.9, y: 1.7, w: 5.8, h: 0.4, fontFace: BF,
  fontSize: 18, bold: true, color: GREEN, margin: 0 });
bullets(s, [
  "Travel time under realistic traffic conditions.",
  "Capacity-weighted Voronoi diagrams using official registries.",
  "Finer 100 m population and official thana boundaries.",
  "Socio-economic weighting — income, vehicle ownership.",
  "Machine-learning prediction of emerging service gaps.",
  "Transfer the framework to Chattogram, Khulna and Sylhet.",
], 6.9, 2.2, 5.8, 13.5);
s.addNotes("We are explicit about what the model does not do, and each limitation maps onto a concrete next step.");

// ------------------------------------------------------------------ 16. conclusion
s = newSlide("Conclusion", "What the study delivers", { dark: true });
const take = [
  ["Central belt is best served", "Mirpur, Banani and Dhanmondi sit inside the dense facility cluster."],
  ["Motijheel is the highest-impact fix", "Most populous section, only moderately served — priority for hospitals and fire stations."],
  ["Water and metro are the widest gaps", "Metro reaches only the MRT-6 corridor; water sources are thin city-wide."],
  ["Straight-line analysis understates the gap", "Road-network distance roughly doubles the underserved share."],
];
take.forEach((t, i) => {
  const y = 1.85 + i * 1.15;
  s.addShape(pres.ShapeType.ellipse, { x: 0.7, y, w: 0.5, h: 0.5, fill: { color: TEAL } });
  s.addText(String(i + 1), { x: 0.7, y, w: 0.5, h: 0.5, align: "center", valign: "middle",
    fontFace: HF, fontSize: 17, bold: true, color: WHITE, margin: 0 });
  s.addText(t[0], { x: 1.45, y: y - 0.02, w: 11, h: 0.42, fontFace: BF, fontSize: 18,
    bold: true, color: WHITE, margin: 0 });
  s.addText(t[1], { x: 1.45, y: y + 0.42, w: 11.2, h: 0.5, fontFace: BF, fontSize: 13,
    color: "AEC4DD", margin: 0 });
});
s.addText("Fully reproducible:  python voronoi_dhaka.py   ·   29 tests   ·   interactive maps + 55-page report", {
  x: 0.7, y: 6.6, w: 12, h: 0.4, fontFace: BF, fontSize: 13, italic: true,
  color: "8FB3D9", margin: 0 });
s.addNotes("Four findings, and everything regenerates from a single command.");

// ------------------------------------------------------------------ 17. thanks
s = pres.addSlide();
s.background = { color: NAVY };
s.addImage({ path: "data/templates/aiub_logo.png", x: 6.17, y: 1.5, w: 1.0, h: 1.0 });
s.addText("Thank You", { x: 0.5, y: 2.9, w: 12.3, h: 0.9, align: "center", fontFace: HF,
  fontSize: 44, bold: true, color: WHITE, margin: 0 });
s.addText("Questions?", { x: 0.5, y: 3.85, w: 12.3, h: 0.5, align: "center", fontFace: BF,
  fontSize: 20, italic: true, color: "CADCFC", margin: 0 });
s.addText("Minhazul Abedin  ·  Zarin Tasnim Rayta  ·  Abdullah Al Noman  ·  Mehedi Hasan Aziz", {
  x: 0.5, y: 5.0, w: 12.3, h: 0.35, align: "center", fontFace: BF, fontSize: 13,
  color: "AEC4DD", margin: 0 });
s.addText("Supervised by Dr. Md. Manzurul Hasan, Associate Professor, Department of Computer Science", {
  x: 0.5, y: 5.4, w: 12.3, h: 0.35, align: "center", fontFace: BF, fontSize: 12,
  color: "8FB3D9", margin: 0 });
s.addNotes("Thank you. We are happy to take questions.");

pres.writeFile({ fileName: OUT }).then((f) => console.log("saved", f));
