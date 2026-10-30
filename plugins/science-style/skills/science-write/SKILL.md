---
name: science-write
description: Use when drafting or revising a manuscript section, an abstract, a blog post or grant text and the author asks to follow the writing habits of a scientist that the science-style lab profiled (Garcia, Royer, Shendure, Trapnell, Pinello, Zou, Rives), or the principles they share.
---

# Science write (prototype)

This skill is a prototype. It reads the style cards that the lab wrote on 2026-10-30, and the author has not reviewed those cards yet.

`<plugin>` below means the folder two levels above this SKILL.md.

## Before you write

1. Get three facts from the request, or ask for them in one question: the genre (manuscript section, abstract, blog post or grant aim), the section, and the card (a person id from `<plugin>/data/people.json`, or `principles`).
2. Read `<plugin>/profiles/principles.md`. For a person, also read `<plugin>/profiles/<id>.md`. Read `<plugin>/profiles/<id>.json` only to check a count.
3. List the card moves that fit the genre and the section. Examples: the order of introduction roles, a gap sentence before a here-we sentence, results subheadings as full-sentence claims, how a results section opens, where the figure reference stands, where limits stand and how specific they are, the order of discussion moves, sentence length, hedges and connectives.
4. Leave out every move that the card says the checklist could not measure reliably.

## Write

- Apply the moves to the author's content. Never invent a result, a number or a citation. Mark a missing fact as `[TODO: ...]`.
- Use the habits of the card, not its quotes. Copy at most a few words of a quote. Never present text as written by the profiled person.
- For a blog post or grant text, use the essay counts of the card and the shared principles. No card holds a blog post or a grant.
- Treat the measures as a range. Aim near the median sentence length of the card, not at its exact value.

## Check

1. When the plain-prose plugin is installed, run its lint on the draft and fix every flagged pattern.
2. Report a short table: each move you applied, where it stands in the draft, and the card line it comes from. Name the moves you left out, with the reason.

## Limits

- A card describes the papers of a person's group. Trainees draft most senior-author papers.
- A profile holds 10 to 14 papers, so its counts are small.
- A card describes the moves and habits of the papers. The draft keeps the author's own voice.
