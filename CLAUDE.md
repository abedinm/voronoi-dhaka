# Voronoi Dhaka — thesis project context

Claude Code loads this file automatically. It is the standing brief for this
repository.

**Read `PROJECT_STATE.md` next.** It records what has already been decided, what
the supervisor has already asked for, and what was tried and rejected — so
nothing settled gets reopened. `DEFENSE_PROMPT.md` holds two prompts: one for
defense day, one for editing the slides and poster.

## What this is

An undergraduate thesis, **"Providing Utility Services using Voronoi Diagrams,
Some Analyses, Recommendations, along with a Case Study for Dhaka City"**.

- **Authors** — Minhazul Abedin (21-44625-1), Zarin Tasnim Rayta (21-45742-3),
  Abdullah Al Noman (21-45825-3), Mehedi Hasan Aziz (19-40060-1)
- **Supervisor** — Dr. Md. Manzurul Hasan, Associate Professor
- **Institution** — American International University-Bangladesh, Department of
  Computer Science. Fall 2025-2026.

## The finding, in one paragraph

Six utility services in Dhaka — hospitals, fire stations, water points, metro
stations, bus stops, fuel stations — 901 real facilities from OpenStreetMap,
against 10.7 M residents from WorldPop. For each service, every point in the city
is assigned to its nearest facility (an exact Voronoi partition), and distance is
measured on a 250 m grid against per-service thresholds.

**The pivotal result:** coverage measured by *land area* made the empty eastern
fringe look worst. Re-measured by *population*, the finding reversed — dense
Motijheel (3.1 M residents) is the real priority. Empty land does not need a
hospital. That reversal is the contribution; everything else supports it.

Key numbers: Mirpur 92 (best) → Bashundhara 55 (worst); Motijheel scores 68 with
3.1 M people; three new fire stations recover 946,000 people; on the real road
network the underserved share roughly doubles.

## Repository layout

| Path | What it is |
|---|---|
| `voronoi_dhaka.py` | The whole pipeline — data, geometry, analysis, thesis `.docx`, IEEE paper. ~4,500 lines. |
| `build_slides_16.js` | The 13-slide defense deck (the filename is historical). |
| `fill_poster.py` | Fills the official AIUB poster template. |
| `build_plain_figures.py` | Plain-language figure captions for the talk and poster. |
| `build_quick_cards.py` | Three one-page cards. |
| `build_cheatsheet.py` | The long Q&A cheat sheet. |
| `build_defense_kit.py` | The method note and the combined cheat sheet. |
| `sync_outputs.sh` | Copies built files to the Desktop/Downloads folders. |
| `outputs/` | Every built artifact. |
| `outputs/figures/` | Technical captions — used by the thesis. |
| `outputs/figures/plain/` | Plain captions — used by the deck and poster. |
| `tests/` | 29 tests, mostly geometric correctness. |
| `DEFENSE_KIT.zip` | Everything needed on defense day. |

## Standing rules — do not break these

- **Never modify the iThenticate reports.** `*_Similarity.pdf` and `*_AI.pdf` are
  official records with a submission ID. They are carried, never regenerated.
- **Never help evade plagiarism or AI detection.** This has been asked and
  declined; the answer does not change.
- **No `Co-Authored-By: Claude`** in commit messages. Academic integrity.
- **The thesis stays technical; the deck and poster stay plain.** A thesis that
  talks like a poster reads as thin. Do not "simplify" the thesis.
- **Do not simplify the deck further.** An 11-slide version was tried and
  rejected as too thin for a graduate defense. The problem was never too much
  content — it was maps being too small.

## Hard-won details that are easy to get wrong

- **Figure numbers in the thesis are hard-coded.** Inserting one means
  renumbering. Always renumber highest-first, then fix range endpoints by hand
  (`Figures 4.8–4.9` — the regex only catches the first number), then audit for
  gaps and duplicates.
- **Declared box geometry is not where the ink is.** Text boxes in the poster
  overflow their stated height by an inch or more. Position against the render,
  never against the coordinates.
- **`alpha` in geopandas fades edges as well as fills.** Draw the fill and the
  boundary separately or the tessellation washes out.
- **Base-14 fonts are not embedded**, so `<b>`/`<i>` vanish in some viewers. The
  card scripts embed DejaVu for this reason.
- **LibreOffice drops hidden slides from PDF export.** Backup slides are
  deliberately not marked hidden.
- **Numbers are hard-coded in seven places** — four deck scripts, the poster, the
  cheat sheet, the cards. Changing a result means chasing all of them.

## Running things

Built on macOS with Python 3, LibreOffice (for PDF export) and Node (for the
decks). **On Windows most of this will not run** without significant setup —
geopandas, osmnx and rasterio are the hard parts. On a Windows machine, treat
this repository as read-only reference material.

```bash
python voronoi_dhaka.py          # full pipeline — slow, needs network
python build_plain_figures.py    # plain-caption figures
NODE_PATH="$(npm root -g)" node build_slides_16.js
python fill_poster.py
python build_quick_cards.py && python build_defense_kit.py
python -m pytest -q              # 29 tests
./sync_outputs.sh                # distribute to Desktop/Downloads
```
