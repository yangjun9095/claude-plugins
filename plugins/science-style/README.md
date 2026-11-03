# science-style

The style lab finds open-access papers of chosen scientists and extracts how each person writes. It publishes one checked profile per person and a file of principles that the people share. The prototype skill `science-write` drafts and revises text with those profiles.

## What it extracts

- Logic and storyline: how a paper moves from its question to its answer.
- How a paper states excitement and limitations.
- Sentence structure and word choice.

## Data directory

Set `STYLE_LAB_DATA` to a scratch folder outside the repository before any step. Every downloaded full text, paper file and extraction stays in that folder. The scripts refuse a folder inside the git worktree.

## People and teams

The registry `data/people.json` holds individuals and teams. An individual has an ORCID and OpenAlex author IDs. A team lists `members`, the ids of at least 2 individuals, and stands for their joint papers: the papers that list every member and where one member is the last author or a corresponding author who is not first. The registry holds one team, `shendure-trapnell`. A team card is built, checked and published like a person card. The principles use individuals only.

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
| `references` | Adds the list of the papers behind a card as the last section, `## Papers`. |
| `quality` | Writes `profiles/quality.md`. |
| `status` | Shows the state of each person. |

Run a step by hand with `python3 -I lab/style_lab.py <step> --help`.

## Write with the profiles (prototype)

Ask for a draft or a revision "in the style of" a profiled person, or "with the shared principles". The skill `science-write` reads `profiles/principles.md` and the card of that person. It applies the card's moves to your content and runs the plain-prose lint when that plugin is installed. Then it reports which moves it applied. It never invents results or citations, and it never presents text as written by the profiled person.

## Known limits of the 2026-10-30 run

- The profiles hold 10 to 14 papers per person: 83 papers in all. Royer and Zou fall 5 papers short of 15, Pinello 4, Shendure and Rives 3, Garcia and Trapnell 1. Their other sampled papers had no open full text.
- Extraction precision on the spot check is 102 of 112 answers (1 wrong, 9 vague). The `excitement` item reaches an agreement of 0.65 only, so the cards state no pattern from it.
- Reviews with more than 3 authors are left out. A few research papers that OpenAlex types as reviews are lost with them.
- Pinello's sample holds his PhD thesis, which OpenAlex does not type as a dissertation.
- In 2 papers (Shendure W2118970626, Trapnell W3010569643) the real results sit in sections after a short "Results" section, so their results items under-describe them.
- The distinctive words are mostly field terms.
- The author has not yet read the cards.

## What the repository holds

The repository holds the code, the registry (names, ORCIDs and OpenAlex IDs), the manifests (DOI, title, year, venue, group, tier and fetch result of each paper) and the profiles. A profile quotes at most 25 words at a time, each quote with its DOI. Full texts never enter the repository.

## Tests

Run from `plugins/science-style`:

```
python3 -B -m unittest discover -s tests
```

The tests use invented people and papers and make no network request.
