# Brief: principles file

The orchestrator writes `profiles/principles.md` from the 7 profiles. It is at most 1,200 words.

## Shape

The file starts with `# Principles` and has these headings, in this order:

1. `## Shared moves`: each closed answer that at least 5 people give in N of M papers, with N at least M divided by 2. For each move, give one sentence that names the move, then the count for each person as "N of M papers".
2. `## Distinctive moves`: for each person, the 2 or 3 items where the person's share differs most from the median share of the 6 others. Name the item and give both counts.

## Rules

The rules of the card brief apply. Take every count from the profile data. Quote only from the profile quotes, as `"text" (doi:10.xxxx/yyyy)`. Use at most 2 quotes from one paper and 20 quotes in the file. Do not rank anyone and do not praise. Skip any item whose `stability` says `"stable": false` or `"stable": null`.

Every card rule on numbers applies. Write every number as digits. Use no number word, no "-fold" form and no percentage.

Run `python3 -I lab/style_lab.py check-card principles` and fix every failure before the commit.
