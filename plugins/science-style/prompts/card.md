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

1. Take every count from the profile data, as "N of M". M is the `n` of the field, the `n_by_group` or `n_by_tier` value for one group or tier, or `n_papers` for the Sample split. For the papers left out, write `n_left_out` of `n_fetched` papers.
2. In a count about papers, put the word papers right after M, as in 7 of 15 papers. Do not add or subtract counts. Say what each count counts, for example the first results section, the last one, or any one. Two counts of one item must not read as a contradiction.
3. Name the unit of every measure, for example words per sentence, sentences per paragraph, share of sentences, or uses per 1,000 words. Use only numbers that appear in the profile data. The numbers 100 and 1,000 are allowed in "per 100" and "per 1,000". Write every number as digits. Do not name list sizes or ordinals, such as top 30 or 90th percentile; the check rejects numbers that the profile does not hold.
4. Do not write number words such as two, half, quarter or twice. Do not write "-fold" forms such as 3-fold or twofold. Do not write "one of N" or "one in N". Do not use percentages.
5. Quote only from the `quotes` list of the profile data. A quote may be the whole entry or a contiguous part of it, 25 words or fewer. Write each quote as `"text" (doi:10.xxxx/yyyy)` with the DOI of that entry. Use double quotes for nothing else.
6. Copy the characters of a quote exactly. Do not add punctuation inside the quote marks or change a capital letter. Write each quote on one line. Do not use a quote that contains a double quote mark.
7. Write a DOI tag only right after its quote. Do not quote a paper whose DOI contains a parenthesis. Choose a quote from another paper.
8. Use at most 2 quotes from one paper and at most 20 quotes in the card.
9. Keep the card to at most 900 words. Aim for about 800 words. The check counts the headings and the quotes.
10. Use no level-2 heading other than the ten above. Do not number list items.
11. When the `stability` of an item says `"stable": false`, state no pattern from that item. Say that the checklist could not measure it reliably.
12. When `stable` is `null`, the item had no agreement pairs. State no pattern from it. Storyline, explanations and signature_phrases have no stability entry; you may describe them.
13. When `distinctive_note` is not empty, say in `## Sentences and words` that the distinctive words could not be computed, and why. Give the reason in words. Do not repeat a number from the note.
14. The passive share is a lower bound: the pattern misses some passive forms. Say so when you give it.
15. Describe what the papers do. Do not rank the person, praise the writing, or compare its quality with other people.
16. Write plain English: short sentences, the active voice, one name for each thing. Start each section with its main point.

## Report

When you finish, reply with the output path and the word count. A script then checks the card. A card that fails goes to a fresh writer with the list of failures.
