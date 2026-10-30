# Brief: principles file

The orchestrator writes `profiles/principles.md` from the seven profiles. It is at most 1,200 words.

## Shape

The file starts with `# Principles` and has two headings:

1. `## Shared moves`: each closed answer that is present in at least half of the papers of at least 5 people. For each move, give one sentence that names the move, then the count for each person as "N of M papers".
2. `## Distinctive moves`: for each person, the two or three items where the person's share differs most from the median share of the other six. Name the item and give both counts.

## Rules

The rules of the card brief apply: counts from the profile data, no percentages, quotes only from the profile quotes as `"text" (doi:10.xxxx/yyyy)`, at most 2 quotes from one paper and 20 quotes in the file, no ranking and no praise. Skip any item whose `stability` says `"stable": false`.

Run `python3 lab/style_lab.py check-card principles` and fix every failure before the commit.
