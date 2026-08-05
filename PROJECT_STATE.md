# Where this project stands

Read this after `CLAUDE.md`. That file says what the project *is*; this one says
what has already been decided, so nothing settled gets reopened.

Last updated: 5 August 2026, end of the macOS working session.

## Current state of each deliverable

| Deliverable | State |
|---|---|
| **Thesis** | 59 pages, AIUB template, Figures 4.1–4.18 and Tables 2.1–4.11 numbered and audited. All seven supervisor corrections applied. |
| **Defense deck** | 13 slides, `build_slides_16.js` (filename is historical — it is not 16 slides). Plain language, no statistics jargon on screen. |
| **Poster** | 30×48 in, official AIUB template, one page. |
| **IEEE paper** | Complete, ready to submit. Venue not yet chosen. |
| **Cheat sheets** | Four one-page cards plus a long Q&A sheet, plus the method note. All match the 13-slide deck. |
| **Defense kit** | `DEFENSE_KIT.zip`, 66 MB, everything needed on the day. |
| **Tests** | 29, all passing. |

## Supervisor feedback, and how each point was handled

1. **"The Voronoi map doesn't show each utility with different colours and centre
   points."** Per-service maps were being tinted by *section*, so all six looked
   identical apart from a 16-pixel dot. Now each map is tinted in its utility's
   own colour with prominent generator markers, and a six-panel figure shows all
   utilities together.
2. **"Why only bus stops?"** The study-area map was built by colouring one
   service's cells by section, and the code picked whichever service had the most
   facilities — bus stops. Replaced with a map of the eight sections drawn from
   their own centres, independent of any utility.
3. **"Why only one utility?"** The recommendations slide showed fire stations
   only. Now a six-panel figure covers every service.
4. **"Need centre point of every cluster in each section."** Two readings were
   built and both kept: cluster centres per section, and each facility against
   the centroid of the cell it generates.
5. **"Proposed facilities must not be on ponds or drainage."** Candidate sites are
   now screened against water, wetland, rivers, canals, drains, reservoirs,
   quarries, landfills, cemeteries, military land and airport surfaces — about a
   fifth of the grid.

## Decisions already made — do not reopen

- **An 11-slide "simple" deck was built and rejected** as too thin for a graduate
  defense. The problem was never too much content; it was maps being too small.
  Do not propose cutting the deck down again.
- **The thesis stays technical. The deck and poster stay plain.** Statistics
  names — 2SFCA, Gini, Moran's I, Spearman — were deliberately removed from the
  slides and poster and live on the printed cards instead, so they can be
  answered but do not invite questions.
- **The Lorenz curve is off the poster and deck**, kept in the thesis. A Gini of
  0.165 puts the curve almost on the diagonal, which at poster distance reads as
  "access is roughly equal" and argues against the finding it supports.
- **"Mildly unequal", not "moderately unequal"** — 0.165 is a low Gini and the
  stronger adjective overstated it.
- **Backup slides are not marked hidden** — LibreOffice drops hidden slides from
  the PDF export, and the printed PDF is the fallback if the laptop dies.
- **The supervisor credit is off the deck title slide and the poster header**, at
  the author's request. The poster's Acknowledgement still thanks him.
- **Figure captions are plain in `outputs/figures/plain/` and technical in
  `outputs/figures/`.** The deck and poster use the former, the thesis the latter.

## Refusals that stand

- **The iThenticate reports are never modified.** Editing them, or changing the
  submitter's name, was requested and declined. They are official records with
  submission ID `trn:oid:::3618:146514131`.
- **No help evading plagiarism or AI detection.** Asked and declined.
- **No `Co-Authored-By: Claude`** in commits.

## Open items

- **The IEEE paper has no venue chosen.** It is written and formatted but not
  submitted anywhere.
- **The thesis is still open in Word on the Mac** — check for unsaved edits
  before regenerating it, since the pipeline overwrites the `.docx`.
- **Two working copies exist on the Mac**: `~/Desktop/voronoi-dhaka` (original,
  full history) and `~/voronoi-dhaka` (a `--depth 1` clone). Whichever machine is
  in use, commit and push before switching.
- **Poster wording has not been read at full size by a human.** Plain English
  runs longer than jargon and overflowed the layout once already; it was fixed
  and verified in the render, but a human eye on the Methods and Data Analysis
  panels is still worth having before printing at 30×48 in.

## The one number to protect

The population-weighted reversal is the contribution. If anything in the pipeline
changes, check that this still holds and still reads clearly everywhere:

> Measured by land area the empty eastern fringe looked worst. Measured by
> population, dense Motijheel — 3.1 million residents — is the real priority.
