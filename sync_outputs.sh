#!/bin/bash
# Distribute built artifacts to the folders on the Desktop and in Downloads.
#
# Thesis_Final holds only what gets presented: the deck and the poster.
# Thesis_Documents holds everything that gets read: thesis, paper, iThenticate
# reports, cheat sheets. The split is deliberate — copying documents back into
# Thesis_Final would undo it on every rebuild.
#
# Downloads keeps the complete set, as it always has.
set -euo pipefail
cd "$(dirname "$0")"
OUT=outputs
FINAL=~/Desktop/Thesis_Final
DOCS=~/Desktop/Thesis_Documents
DL=~/Downloads/Voronoi_Dhaka_Thesis

PRESENTED=(Dhaka_Voronoi_Defense_16.pptx Dhaka_Voronoi_Defense_16.pdf
           Dhaka_Voronoi_Poster_AIUB.pptx Dhaka_Voronoi_Poster_AIUB.pdf)
READ=(Dhaka_Voronoi_AIUB_Thesis.docx Dhaka_Voronoi_AIUB_Thesis.pdf
      Dhaka_Voronoi_IEEE_Paper.docx Dhaka_Voronoi_IEEE_Paper.pdf
      Card_1_Thesis_Report.pdf Card_2_Presentation.pdf Card_3_Poster.pdf
      Defense_Cheat_Sheet.pdf)

mkdir -p "$FINAL" "$DOCS" "$DL"
for f in "${PRESENTED[@]}"; do
  [ -f "$OUT/$f" ] && cp "$OUT/$f" "$FINAL/" && cp "$OUT/$f" "$DL/"
done
for f in "${READ[@]}"; do
  [ -f "$OUT/$f" ] && cp "$OUT/$f" "$DOCS/" && cp "$OUT/$f" "$DL/"
done
# the iThenticate reports are official records; they are never regenerated, only
# carried along if they are already present
for f in Dhaka_Voronoi_AIUB_Thesis_Similarity.pdf Dhaka_Voronoi_AIUB_Thesis_AI.pdf; do
  [ -f "$DOCS/$f" ] || { [ -f "$DL/$f" ] && cp "$DL/$f" "$DOCS/"; }
done
echo "Thesis_Final     : $(/bin/ls -1 "$FINAL" | wc -l | tr -d ' ') files (presented)"
echo "Thesis_Documents : $(/bin/ls -1 "$DOCS" | wc -l | tr -d ' ') files (read)"
echo "Downloads        : $(/bin/ls -1 "$DL" | wc -l | tr -d ' ') files (everything)"
