# Brief: profile card

You write the card of one person from the profile data and the digest. The dispatch gives the path of the profile data (`<id>.json`), the path of the digest, and the output path (`<id>.md`). Read only those files. Do not use the web. Do not dispatch other agents.

## Shape

The card starts with `# <name>` and has these headings, in this order:

1. `## Sample`: the number of papers, the years, the split by group and tier, and the text versions.
2. `## Storyline`: the moves of the abstract and the arc from the first question to the last result. Use `abstract_moves`, `results_openings` and the storyline lines of the digest.
3. `## Introduction`: the roles of the paragraphs, where the gap and the here-we sentences stand, and how titles read.
4. `## Results`: the form of subheadings, how sections open, and how the text refers to figures.
5. `## Excitement`: where and how the papers say a result matters, and how the strongest claim is hedged.
6. `## Limitations`: where the limits stand and how specific they are.
7. `## Discussion`: the moves of the discussion, in their usual order.
8. `## Sentences and words`: the surface measures and the distinctive words.
9. `## Signature moves`: the habits that recur in this person's papers, each with one quote.
10. `## Caveats`: the text versions used, the papers left out, and this sentence or one like it: trainees draft most senior-author papers, so the card describes the papers of the person's group.

## Rules

1. Take every count from the profile data, as "N of M papers". M is the `n` of the field, the `n_by_group` or `n_by_tier` value for one group or tier, or `n_papers` for the Sample split.
2. Use only numbers that appear in the profile data. The numbers 100 and 1,000 are allowed in "per 100" and "per 1,000". Write every number as digits. Do not write number words such as two, half, quarter or twice, and do not use percentages.
3. Quote only from the `quotes` list of the profile data. A quote may be the whole entry or a contiguous part of it, 25 words or fewer. Write each quote as `"text" (doi:10.xxxx/yyyy)` with the DOI of that entry. Use double quotes for nothing else.
4. Write each quote on one line. A DOI that contains a parenthesis cannot be quoted. Choose a quote from another paper.
5. Use at most 2 quotes from one paper and at most 20 quotes in the card.
6. Keep the card to at most 900 words.
7. When the `stability` of an item says `"stable": false`, state no pattern from that item. Say that the checklist could not measure it reliably.
8. When `distinctive_note` is not empty, say in `## Sentences and words` that the distinctive words could not be computed, and why.
9. Describe what the papers do. Do not rank the person, praise the writing, or compare its quality with other people.
10. Write plain English: short sentences, the active voice, one name for each thing. Start each section with its main point.

## Report

When you finish, reply with the output path and the word count. A script then checks the card. A card that fails goes to a fresh writer with the list of failures.
