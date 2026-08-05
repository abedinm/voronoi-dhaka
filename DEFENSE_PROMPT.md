# Defense-day prompt

On the Windows laptop, open Claude Code in this folder and paste everything
between the lines below as your first message. `CLAUDE.md` in this repository
loads automatically, so Claude already has the project context — this prompt
tells it what you need it to *do*.

---

I am about to defend my undergraduate thesis and you are helping me prepare and
get through it. Read CLAUDE.md in this repository first — it has the project
context, the finding, the file layout, and the rules.

**My situation.** I am on a Windows laptop, in or near the defense room. The
build pipeline will not run here and I do not need it to. I need you to help me
*understand, rehearse and defend* the work, not rebuild it.

**What I have with me.** DEFENSE_KIT.zip in this repository, containing:

- `1_Presentation.pptx` — 13 slides, what I present (`1_Presentation_BACKUP.pdf`
  if PowerPoint fails)
- `2_Poster.pdf` — the poster
- `3_Cheat_Sheet.pdf` — talk on the left, poster on the right
- `4_How_This_Thesis_Was_Done.pdf` — the method as a one-page argument
- `5_Card_Thesis_Detail.pdf` — the statistics I deliberately cut from the slides
  (2SFCA, Gini, Moran's I, Spearman)
- `6_Full_QA_Cheat_Sheet.pdf` — longer Q&A preparation
- `7_Thesis.pdf`, `8_IEEE_Paper.pdf` — the submitted documents
- `10_Interactive_Map.html` — open this in a browser before I start

**How I want you to work with me.**

1. **Answer from the repository, not from memory.** If I ask what a number is,
   find it in `voronoi_dhaka.py` or the built documents and tell me where it came
   from. Never invent a figure — if you cannot find it, say so.

2. **Be direct about weaknesses.** If a question would expose a real limitation,
   tell me plainly rather than reassuring me. I would rather hear it from you
   than from the panel.

3. **When I say "quiz me", act as a hostile examiner.** Ask the hardest question
   you can from the thesis, let me answer, then tell me where my answer would not
   survive a follow-up. The questions most likely to hurt: why the fire-station
   2SFCA correlation is only 0.12; whether straight-line distance is meaningful
   in Dhaka traffic; why the eight areas are not official wards; and what is
   actually new when Voronoi diagrams date from 1908.

4. **Keep answers short.** I am reading you between other things. Lead with the
   answer, then the reasoning if it matters.

5. **Do not change any file unless I ask.** Especially never touch the
   iThenticate reports.

**Start by** confirming you have read CLAUDE.md, then give me the single
strongest sentence I can say if the panel asks "what is new here?"

---

## Getting the repository onto the Windows laptop

The full history is large. **Do not do a plain `git clone`** — use a shallow one:

```bash
git clone --depth 1 https://github.com/abedinm/voronoi-dhaka.git
```

If you only want the defense files and not the code, download `DEFENSE_KIT.zip`
straight from the GitHub web interface — it is 66 MB and needs no git at all.

Whichever you do, also put `DEFENSE_KIT.zip` on a USB stick and email it to
yourself. Do not let a network be the only thing standing between you and your
slides.
