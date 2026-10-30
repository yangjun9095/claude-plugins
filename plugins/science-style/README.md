# science-style

The style lab finds open-access papers of chosen scientists and extracts how each person writes. It publishes one checked profile per person and a file of principles that the people share. A writing skill that uses the profiles comes in a later version.

## What it extracts

- Logic and storyline: how a paper moves from its question to its answer.
- How a paper states excitement and limitations.
- Sentence structure and word choice.

## Data directory

Set `STYLE_LAB_DATA` to a scratch folder outside the repository before any step. Every downloaded full text, paper file and extraction stays in that folder. The scripts refuse a folder inside the git worktree.

## Run the lab

In Claude Code, run `/style-lab <person ids> --pilot` for a pilot, then `/style-lab all`. The command runs the steps below and dispatches the subagents.

| Step | What it does |
|---|---|
| `candidates NAME` | Lists OpenAlex author records for a name. |
| `discover` | Finds the works of each person by ORCID and sorts them into senior, first and essay groups. |
| `sample` | Draws about 15 papers per person, two thirds from high-impact venues, spread across the years. |
| `fetch` | Downloads open full texts from PubMed Central, Europe PMC, bioRxiv and arXiv, and replaces papers without one. |
| `normalize` | Rebuilds the paper files from the cache. |
| `surface` | Measures sentences, paragraphs, hedges, connectives and distinctive words. |
| `select` | Lists the papers for the agreement run or the spot check. |
| `check-quotes` | Checks every quote of every extraction against its paper. |
| `aggregate` | Writes the profile data. |
| `check-card` | Checks a card or the principles file against the profile data. |
| `quality` | Writes `profiles/quality.md`. |
| `status` | Shows the state of each person. |

Run a step by hand with `python3 -I lab/style_lab.py <step> --help`.

## What the repository holds

The repository holds the code, the registry (names, ORCIDs and OpenAlex IDs), the manifests (DOI, title, year, venue, group, tier and fetch result of each paper) and the profiles. A profile quotes at most 25 words at a time, each quote with its DOI. Full texts never enter the repository.

## Tests

Run from `plugins/science-style`:

```
python3 -B -m unittest discover -s tests
```

The tests use invented people and papers and make no network request.
