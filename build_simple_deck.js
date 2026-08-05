/**
 * Dhaka_Voronoi_Defense_Simple.pptx — the stripped-back defense deck.
 *
 * One idea per slide. A headline you could read aloud, one picture, and almost
 * no body text. Nothing here is a summary of the 19-slide deck; it is the
 * argument reduced to the eleven things that actually have to land.
 *
 * The full deck is untouched. Run:
 *   NODE_PATH="$(npm root -g)" node build_simple_deck.js
 */
const pptxgen = require("pptxgenjs");

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE";                    // 13.33 x 7.5 in
pres.author = "Minhazul Abedin";
pres.title = "Providing Utility Services using Voronoi Diagrams";

const FIG = "outputs/figures/plain/";
const OUT = "outputs/Dhaka_Voronoi_Defense_Simple.pptx";

const NAVY = "0E2A47", DEEP = "0B5394", TEAL = "1C7293", AMBER = "D2691E";
const GREEN = "2E8B57", RED = "C0392B", WHITE = "FFFFFF", INK = "1C2B39";
const MUTED = "5B6B7A", TINT = "EDF3F7", LINE = "D6E0E7";
const HF = "Cambria", BF = "Calibri";

let n = 0;

/** Headline slide: one big sentence, nothing else competing with it. */
function slide(headline, opts = {}) {
  const s = pres.addSlide();
  s.background = { color: opts.dark ? NAVY : WHITE };
  if (headline) {
    s.addText(headline, {
      x: 0.7, y: 0.5, w: 11.9, h: 1.15, fontFace: HF, fontSize: opts.small ? 30 : 34,
      bold: true, color: opts.dark ? WHITE : INK, margin: 0, valign: "middle",
    });
  }
  n += 1;
  if (!opts.noNumber) {
    s.addText(String(n), { x: 12.6, y: 6.95, w: 0.4, h: 0.3, fontFace: BF,
      fontSize: 11, color: opts.dark ? "8FB3D9" : MUTED, align: "right", margin: 0 });
  }
  return s;
}

/** A single line of plain explanation under the headline. */
function line(s, text, y, opts = {}) {
  s.addText(text, {
    x: opts.x || 0.7, y, w: opts.w || 11.9, h: opts.h || 0.9, fontFace: BF,
    fontSize: opts.size || 21, color: opts.color || MUTED, margin: 0,
  });
}

function picture(s, file, x, y, w, h) {
  s.addImage({ path: FIG + file, x, y, w, h, sizing: { type: "contain", w, h } });
}

/** One oversized number with a short label — readable from the back row. */
function bigNumber(s, x, y, w, value, label, color) {
  s.addText(value, { x, y, w, h: 1.1, align: "center", fontFace: HF, fontSize: 54,
    bold: true, color, margin: 0 });
  s.addText(label, { x, y: y + 1.15, w, h: 0.6, align: "center", fontFace: BF,
    fontSize: 17, color: MUTED, margin: 0 });
}

// ══════════════════════════════════════════════════════════════ 1. title
let s = pres.addSlide();
s.background = { color: NAVY };
s.addImage({ path: "data/templates/aiub_logo.png", x: 6.17, y: 1.0, w: 1.0, h: 1.0 });
s.addText("Providing Utility Services using Voronoi Diagrams", {
  x: 0.8, y: 2.35, w: 11.7, h: 1.0, align: "center", fontFace: HF, fontSize: 34,
  bold: true, color: WHITE, margin: 0 });
s.addText("A Case Study for Dhaka City", {
  x: 0.8, y: 3.35, w: 11.7, h: 0.5, align: "center", fontFace: BF, fontSize: 20,
  italic: true, color: "CADCFC", margin: 0 });
s.addText("Minhazul Abedin  ·  Zarin Tasnim Rayta  ·  Abdullah Al Noman  ·  Mehedi Hasan Aziz", {
  x: 0.8, y: 4.5, w: 11.7, h: 0.4, align: "center", fontFace: BF, fontSize: 15,
  color: "AEC4DD", margin: 0 });
s.addText("American International University-Bangladesh  ·  Fall 2025-2026", {
  x: 0.8, y: 5.15, w: 11.7, h: 0.4, align: "center", fontFace: BF, fontSize: 13,
  color: "8FB3D9", margin: 0 });
s.addNotes("Assalamu alaikum. We are presenting our thesis on providing utility services using Voronoi diagrams, with a case study of Dhaka City.");
n = 1;

// ══════════════════════════════════════════════════ 2. the problem
s = slide("Dhaka grew. Its services did not keep up.");
line(s, "Hospitals, fire stations and water points are packed into the centre and thin out at the edges. Nobody had measured how uneven it actually is.", 1.75, { w: 5.9, h: 1.9, size: 20, color: INK });
s.addShape(pres.ShapeType.roundRect, { x: 0.7, y: 4.1, w: 5.9, h: 1.5,
  fill: { color: "FBEEE9" }, line: { color: AMBER, width: 1.5 }, rectRadius: 0.08 });
s.addText("So: which areas are worse off, and where should new ones go?", {
  x: 0.95, y: 4.1, w: 5.4, h: 1.5, valign: "middle", fontFace: BF, fontSize: 19,
  bold: true, color: INK, margin: 0 });
picture(s, "all_facilities.png", 7.0, 1.6, 5.6, 5.3);
s.addNotes("901 facilities on this map. Point at the dense centre, then at the empty east.");

// ══════════════════════════════════════════════════ 3. the idea
s = slide("Everyone goes to the nearest one.");
picture(s, "simple_idea.png", 0.7, 1.7, 6.4, 5.1);
line(s, "Five hospitals. Colour every house by the one closest to it, and the city splits into five areas.", 1.8, { x: 7.6, w: 5.1, h: 2.0, size: 21, color: INK });
s.addShape(pres.ShapeType.roundRect, { x: 7.6, y: 4.15, w: 5.1, h: 1.9,
  fill: { color: TINT }, line: { color: LINE, width: 1.5 }, rectRadius: 0.08 });
s.addText("Every border sits exactly halfway between two facilities.\n\nThat is the whole method.", {
  x: 7.9, y: 4.15, w: 4.6, h: 1.9, valign: "middle", fontFace: BF, fontSize: 19,
  bold: true, color: DEEP, margin: 0 });
s.addNotes("The one picture that has to land. Point at one dot, then trace its area. Borders are halfway lines. If asked for the formal name — Voronoi diagram.");

// ══════════════════════════════════════════════════ 4. what we studied
s = slide("We did this for all of Dhaka, six services at once.");
[["901", "real facilities", DEEP], ["6", "services", TEAL],
 ["10.7M", "people", GREEN], ["8", "areas compared", AMBER],
].forEach((b, i) => bigNumber(s, 0.7 + i * 3.05, 1.9, 2.85, b[0], b[1], b[2]));
line(s, "Hospitals · fire stations · water points · metro stations · bus stops · fuel stations", 3.9, { size: 19, color: INK });
picture(s, "sections_only.png", 4.3, 4.4, 4.7, 2.7);
s.addNotes("All free public data — OpenStreetMap for the facilities, WorldPop for where people live.");

// ══════════════════════════════════════════════════ 5. the gap
s = slide("What was missing");
[["Everyone else looked at one service", "Emergency care. Or buses. Or parks. Never all of them together.", RED],
 ["And they measured empty land", "An empty field counts the same as a crowded neighbourhood.", RED],
 ["We do six services, counted by people", "That one change flips the answer — as you will see.", GREEN],
].forEach((c, i) => {
  const y = 1.85 + i * 1.65;
  s.addShape(pres.ShapeType.roundRect, { x: 0.7, y, w: 11.9, h: 1.4,
    fill: { color: i === 2 ? "E6EFE6" : TINT },
    line: { color: i === 2 ? GREEN : LINE, width: i === 2 ? 2 : 1 }, rectRadius: 0.08 });
  s.addText(c[0], { x: 1.05, y: y + 0.18, w: 5.4, h: 0.5, fontFace: BF, fontSize: 21,
    bold: true, color: c[2], margin: 0 });
  s.addText(c[1], { x: 1.05, y: y + 0.72, w: 10.9, h: 0.5, fontFace: BF, fontSize: 18,
    color: INK, margin: 0 });
});
s.addNotes("Three lines. Do not elaborate — the third one is the contribution and slide 8 proves it.");

// ══════════════════════════════════════════════════ 6. how we measured
s = slide("How we measured it — three steps");
[["1", "Divide", "Every point in Dhaka belongs to its nearest facility", DEEP],
 ["2", "Measure", "How far is that? Too far, or close enough?", TEAL],
 ["3", "Score", "Give each area a mark out of 100, based on its people", GREEN],
].forEach((st, i) => {
  const x = 0.7 + i * 4.05;
  s.addShape(pres.ShapeType.roundRect, { x, y: 2.0, w: 3.8, h: 3.6,
    fill: { color: TINT }, line: { color: LINE, width: 1 }, rectRadius: 0.1 });
  s.addShape(pres.ShapeType.ellipse, { x: x + 1.5, y: 2.35, w: 0.8, h: 0.8,
    fill: { color: st[3] } });
  s.addText(st[0], { x: x + 1.5, y: 2.35, w: 0.8, h: 0.8, align: "center",
    valign: "middle", fontFace: HF, fontSize: 26, bold: true, color: WHITE, margin: 0 });
  s.addText(st[1], { x: x + 0.2, y: 3.35, w: 3.4, h: 0.5, align: "center",
    fontFace: BF, fontSize: 24, bold: true, color: INK, margin: 0 });
  s.addText(st[2], { x: x + 0.35, y: 3.95, w: 3.1, h: 1.4, align: "center",
    fontFace: BF, fontSize: 17, color: MUTED, margin: 0 });
});
line(s, "Then: put a new facility where it helps the most people. Repeat.", 5.9, { size: 20, color: INK });
s.addNotes("Divide, measure, score, then recommend. Do not go deeper unless asked.");

// ══════════════════════════════════════════════════ 7. what we found
s = slide("Some services cover the city. Some barely do.");
picture(s, "voronoi_all_services.png", 0.7, 1.6, 7.9, 5.3);
[["Water points", "73% of the city too far", RED],
 ["Metro stations", "67% too far", RED],
 ["Hospitals", "33% too far — the best", GREEN],
].forEach((c, i) => {
  const y = 2.0 + i * 1.6;
  s.addShape(pres.ShapeType.roundRect, { x: 8.9, y, w: 3.7, h: 1.35,
    fill: { color: TINT }, line: { color: LINE, width: 1 }, rectRadius: 0.08 });
  s.addText(c[0], { x: 9.15, y: y + 0.15, w: 3.2, h: 0.45, fontFace: BF,
    fontSize: 19, bold: true, color: INK, margin: 0 });
  s.addText(c[1], { x: 9.15, y: y + 0.65, w: 3.3, h: 0.5, fontFace: BF,
    fontSize: 17, color: c[2], margin: 0 });
});
s.addNotes("Six maps, one per service. The contrast between bus stops and fire stations is the thing to point at.");

// ══════════════════════════════════════════ 8. THE KEY INSIGHT
s = slide("The one thing that changed our answer", { dark: true });
s.addText("Count people, not land.", {
  x: 0.7, y: 1.6, w: 6.2, h: 0.8, fontFace: HF, fontSize: 32, bold: true,
  color: "FFD166", margin: 0 });
s.addText("Measured by land, the empty eastern edge looked worst — but almost nobody lives there.", {
  x: 0.7, y: 2.55, w: 6.2, h: 1.3, fontFace: BF, fontSize: 20, color: "CADCFC", margin: 0 });
s.addText("Measured by people, the real problem is crowded old Dhaka.", {
  x: 0.7, y: 3.85, w: 6.2, h: 1.0, fontFace: BF, fontSize: 20, color: WHITE, margin: 0 });
s.addShape(pres.ShapeType.roundRect, { x: 0.7, y: 5.0, w: 6.2, h: 1.6,
  fill: { color: "16385C" }, line: { color: "FFD166", width: 2 }, rectRadius: 0.1 });
s.addText("Motijheel — 3.1 million people, and only a middling score.\nOur top priority.", {
  x: 1.0, y: 5.0, w: 5.6, h: 1.6, valign: "middle", fontFace: BF, fontSize: 19,
  bold: true, color: "FFD166", margin: 0 });
picture(s, "section_benefit.png", 7.3, 1.5, 5.3, 5.4);
s.addNotes("This is the contribution. Say it slowly. Empty land does not need a hospital; crowded neighbourhoods do.");

// ══════════════════════════════════════════════════ 9. recommendations
s = slide("So where should new ones go?");
picture(s, "recommendations_all_services.png", 0.7, 1.55, 7.9, 5.4);
line(s, "We put each new facility where it brings the most people back within reach — and never on water or a drain.", 1.75, { x: 8.8, w: 3.85, h: 2.2, size: 19, color: INK });
s.addShape(pres.ShapeType.roundRect, { x: 8.8, y: 4.1, w: 3.85, h: 2.4,
  fill: { color: "E6EFE6" }, line: { color: GREEN, width: 2 }, rectRadius: 0.1 });
s.addText("946,000", { x: 8.8, y: 4.35, w: 3.85, h: 0.9, align: "center",
  fontFace: HF, fontSize: 42, bold: true, color: GREEN, margin: 0 });
s.addText("people brought back within reach\nby just 3 new fire stations", {
  x: 9.0, y: 5.3, w: 3.45, h: 1.0, align: "center", fontFace: BF, fontSize: 17,
  color: INK, margin: 0 });
s.addNotes("Red stars are the proposed sites. The 946,000 is the number to leave them with.");

// ══════════════════════════════════════════════════ 10. limitations
s = slide("What we cannot do yet");
[["We measured straight lines", "Real journeys follow roads, so the true problem is about twice as big. We checked, and we say so."],
 ["Our map data is volunteered", "So our counts are a minimum, not a complete list."],
 ["We did not count size", "A small clinic counts the same as a large hospital."],
].forEach((c, i) => {
  const y = 1.9 + i * 1.6;
  s.addShape(pres.ShapeType.roundRect, { x: 0.7, y, w: 11.9, h: 1.35,
    fill: { color: TINT }, line: { color: LINE, width: 1 }, rectRadius: 0.08 });
  s.addText(c[0], { x: 1.05, y: y + 0.15, w: 4.3, h: 0.5, fontFace: BF, fontSize: 20,
    bold: true, color: RED, margin: 0 });
  s.addText(c[1], { x: 5.4, y: y + 0.15, w: 7.0, h: 1.05, fontFace: BF, fontSize: 17,
    color: INK, margin: 0 });
});
line(s, "Next: real travel time on the road network, and the size of each facility.", 6.75, { size: 19, color: MUTED });
s.addNotes("Say these yourself before anyone asks. Volunteering a weakness reads as command of the work.");

// ══════════════════════════════════════════════════ 11. close
s = slide("", { dark: true, noNumber: true });
s.addText("What we built", { x: 0.8, y: 0.9, w: 11.7, h: 0.7, align: "center",
  fontFace: HF, fontSize: 30, bold: true, color: WHITE, margin: 0 });
[["A map of who is served", "and who is not, for six services at once"],
 ["A ranking by people", "not by empty land — the first for Dhaka"],
 ["A list of where to build", "with the number of people each site helps"],
].forEach((c, i) => {
  const y = 2.1 + i * 1.3;
  s.addShape(pres.ShapeType.roundRect, { x: 2.0, y, w: 9.3, h: 1.1,
    fill: { color: "16385C" }, line: { color: "2C5680", width: 1 }, rectRadius: 0.08 });
  s.addText(c[0], { x: 2.4, y: y + 0.1, w: 4.3, h: 0.9, valign: "middle",
    fontFace: BF, fontSize: 20, bold: true, color: "FFD166", margin: 0 });
  s.addText(c[1], { x: 6.6, y: y + 0.1, w: 4.5, h: 0.9, valign: "middle",
    fontFace: BF, fontSize: 18, color: "CADCFC", margin: 0 });
});
s.addText("Thank you  —  Questions?", { x: 0.8, y: 6.1, w: 11.7, h: 0.8,
  align: "center", fontFace: HF, fontSize: 26, bold: true, color: WHITE, margin: 0 });
s.addNotes("Three things. Then stop and invite questions.");

pres.writeFile({ fileName: OUT }).then((f) => console.log("saved", f));
