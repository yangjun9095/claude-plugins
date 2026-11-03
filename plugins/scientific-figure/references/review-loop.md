# The Claude–Codex review loop

Claude reviewing a figure Claude drew confirms its own blind spots. A second model, given the
rendered image and no memory of the design discussion, is in the condition a referee is in.

## Running it

    ./codex_review.sh <panel.png> <brief.txt> [extra instruction]

Returns one JSON object: `score` 0-100, `verdict` (the single worst thing), `issues`
(severity, what_i_see, fix), `works` (what must not be lost).

`codex exec` needs the prompt on **stdin** and the image via `-i`. It echoes the session
header, the prompt and the reply, and prints the reply twice, so parse the LAST balanced JSON
object containing a `score` key.

Run at `model_reasoning_effort="high"`. At the `max` default one review ran past ten minutes;
at high it is about 90 seconds with no loss of bite.

## What it is good at

Finding specific, located defects that a figure's own authors have stopped seeing. Two
examples from one session, both missed by fourteen rounds of same-model critique:

- a solid revise lane landing on a downstream box read as a forward shortcut skipping the
  box between
- a panel printing the words "6 ranked rows" beside rows deliberately **not** in rank order

## What it is bad at, and how to compensate

**Its diagnoses are frequently wrong even when its findings are right.** Three times in one
session it named a real defect and misattributed the cause. The second example above: it
reported the plot as *mis-sorted*, when the plot was correctly *grouped* and merely
*mislabelled*. Re-sorting would have broken it.

> Fix what it SAW. Argue with WHY it thinks that happened. Tell the builder to do the same.

**The score is noise-dominated at this resolution.** Measured: three renders differing only
by a two-pixel dilation of one arrow scored **82, 79, 76**. A full ten-round trajectory ran
64, 74, 76, 76, 76, 74, 73, 82, 79, 76 while the panel improved monotonically.

> Treat the band, not the number. **Never set a numeric pass threshold**, and never let a
> round be spent chasing points. Stop when the findings stop being real.

**It contradicts itself across rounds.** Asked for motif rows to be "visibly continuous"; the
result was called "folded DNA with loop anchors". Then asked for "one straight strip"; that
glyph came out 90% paper. Four forms were drawn before the first was reinstated.

> When two rounds disagree about the same element, stop and decide it yourself.

**It argues from priors about convention.** It held that a revise lane must point back to the
coordinator, in a system that genuinely re-dispatches forward.

> A disagreement that survives two rounds with no new evidence is a difference of opinion.
> Record it and move on.

**If it flags a contradiction with the brief, suspect the brief first.** One low score traced
entirely to an ambiguous denominator in the brief: six rows against five distinct molecules,
with the brief naming neither.

## Loop shape

    for round in 1..N:
        build agent  (gets: mandate + last verdict + the `works` list)
        codex review (a thin courier agent; returns the JSON verbatim, unedited)

The courier must be told: *do not edit, soften or re-rank it. You are a courier.* A builder
allowed to summarise its own review will soften it.

Always pass the `works` list forward. Without it, round N+1 destroys what round N fixed.
