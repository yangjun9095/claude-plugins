---
name: science-write
description: Use when drafting or revising a manuscript section, an abstract, a blog post or grant text and the author asks to follow the writing habits of a scientist that the science-style lab profiled (Garcia, Royer, Shendure, Trapnell, Pinello, Zou, Rives), or the principles they share.
---

# Science write (prototype)

This skill is a prototype. It reads the style cards that the lab wrote on 2026-10-30, and the author has not reviewed those cards yet.

`<plugin>` below means the plugin folder: the folder that holds `skills/`, `profiles/` and `prompts/`.

## Before you write

1. Get three facts from the request, or ask for them in one question: the genre (manuscript section, abstract, blog post or grant aim), the section, and the card (a person id or a team id from `<plugin>/data/people.json`, or `principles`). A team card describes the joint papers of its members.
2. Read `<plugin>/profiles/principles.md`. For a person or a team, also read `<plugin>/profiles/<id>.md`. Read `<plugin>/profiles/<id>.json` only to check a count.
3. Take the moves from the card sections that fit the text:

   | Text | Card sections |
   |---|---|
   | Abstract | Storyline (abstract moves), Introduction (gap and here-we sentences) |
   | Introduction | Introduction |
   | Results | Results, Signature moves |
   | Discussion | Discussion, Limitations, Excitement (strongest claim only) |
   | Blog post or grant aim | the essay counts of the card, and principles.md |
   | Any text | Sentences and words |

4. Leave out each item that the card names as not measured reliably. Other lines of the same card section stay usable.

## Write

- Apply the moves to the author's content. Never invent a result, a number or a citation.
- When the draft lacks a fact that a move needs, write the sentence and mark the fact as `[TODO: ...]`. A gap sentence with no gap in the draft is an example.
- Use the habits of the card, not its quotes. Copy at most a few words of a quote. Never present text as written by the profiled person.
- Treat the measures as a range. The author's house style, such as a sentence-length cap in CLAUDE.md, wins over a card measure.

## Check

1. Write the draft alone to a file. When the plain-prose plugin is installed, run its lint on that file: `python3 -B <plain-prose plugin>/scripts/prose_lint.py <file>`. Fix every flagged pattern.
2. Report a short table: each move you applied, where it stands in the draft, and the card line it comes from. Name the moves you left out, with the reason.

## Limits

- A card describes the papers of a person's group. Trainees draft most senior-author papers.
- A profile holds 10 to 14 papers, so its counts are small.
- A card describes the moves and habits of the papers. The draft keeps the author's own voice.
