# science-style, part 1: the style lab

Status: design. Nothing in this spec exists yet. The author approved the design in conversation on 2026-10-29 and asked for this spec.

Date: 2026-10-29. The repository owner (the author) requested the plugin. The assistant wrote this spec from the brainstorming answers and from the feasibility checks in section 4.

## 1. Purpose and scope

The plugin `science-style` (a working name) helps the author write scientific text that is clear and insightful. The text has no LLM-style patterns. The model is the writing of seven scientists the author admires. The plugin has two parts:

1. **The style lab** (this spec). A pipeline that finds open-access papers of each person and extracts how each person writes. It publishes one profile per person plus a file of shared principles.
2. **The writing skill** (a later spec). A skill that drafts manuscript sections, blog posts and grant text from the profiles and runs the `plain-prose` checks on the draft.

The style lab extracts four layers, in order of importance to the author:

1. Logic and storyline: how a paper moves from question to answer.
2. How a paper states excitement and limitations.
3. Sentence structure.
4. Words and phrases.

In scope:
- A people registry, paper discovery, a weighted sample, open-access fetching and a normalized text format.
- Measurements by script (the surface layer) and checklist extraction by subagents (the structure layer).
- One profile per person and one principles file, with every count traced to data and every quote checked against the source.
- A pilot on one person before the full run.

Out of scope:
- The writing skill and any change to `plain-prose`.
- Publisher web pages and PDF files (decision D14).
- Book chapters, theses, talks, blog posts and social media.
- Any ranking or judgment of the seven people.

## 2. Terms

Each term has one meaning in this spec and in the code.

| Term | Meaning |
|---|---|
| person | One of the seven scientists in the registry. |
| registry | `data/people.json`: the identity of each person. |
| work | Any record that OpenAlex returns for a person. |
| paper | A work that passes the discovery filters (section 7). |
| group | The role of the person in a paper: `senior`, `first` or `essay`. |
| tier | The venue class of a paper: `high` or `other`. |
| cell | One group and one tier of one person, for example `senior/high`. |
| sample | The papers chosen for one person. |
| manifest | The committed list of one person's sample, with metadata and fetch results. |
| route | One way to get the full text of a paper. |
| text version | `published`, `accepted`, `preprint` or `arxiv`. |
| paper file | The normalized JSON text of one paper. |
| checklist | `data/checklist.json`: the questions of the structure layer. |
| extraction | The checklist answers for one paper, written by one subagent. |
| profile | The data file `profiles/<id>.json` and the card `profiles/<id>.md` of one person. |
| principles file | `profiles/principles.md`: the moves the seven people share, and the moves where each person differs from the others. |
| data directory | The scratch directory named by the variable `STYLE_LAB_DATA`. It holds all full texts. |

## 3. Decisions

| ID | Decision | Made by |
|---|---|---|
| D1 | Two parts: a reusable style lab, then a writing skill that uses the profiles and the `plain-prose` checks. | Author, 2026-10-29 |
| D2 | The plugin lives in the public repository `claude-plugins`. | Author, 2026-10-29 |
| D3 | The people are Hernan Garcia, Loic Royer, Jay Shendure, Cole Trapnell, Luca Pinello, James Zou and Alexander Rives. | Author, 2026-10-29 |
| D4 | The sources are papers, preprints and essays. | Author, 2026-10-29 |
| D5 | The writing skill will produce manuscripts and sections, blog posts, and grant and fellowship text. | Author, 2026-10-29 |
| D6 | Open-access sources only: PubMed Central (PMC) through NCBI and Europe PMC, bioRxiv and arXiv. | Author, 2026-10-29 |
| D7 | About 15 papers per person. A pilot on one person runs first. | Author, 2026-10-29 |
| D8 | The sample favors high-impact venues: two tiers, a target of 10 high-tier and 5 other papers, with a fallback. | Author, 2026-10-29 (the assistant proposed the tiers and the numbers) |
| D9 | Current Biology is in the high tier. | Author, 2026-10-29 |
| D10 | NeurIPS, ICML and ICLR are in the high tier for Zou and Rives. | Author, 2026-10-29 |
| D11 | Discovery finds works by ORCID. | Assistant, from section 4 (one person has two OpenAlex records) |
| D12 | A person is the senior author of a paper when the person is the last author or a corresponding author in a position other than first. A paper shared by two people goes to one of them only. | Assistant, from section 4 |
| D13 | One script process fetches all papers. Subagents work per person on the extraction and the cards. | Assistant: rate limits apply per host, so parallel fetch agents would break them |
| D14 | No publisher route and no PDF route. | Assistant: PMC and preprint XML cover the routes (section 4), the author excluded publisher pages, and PDF text loses the section structure |
| D15 | The pilot person is Hernan Garcia. | Assistant: the author knows his writing and can judge the card, and his sample tests the fallback (7 high-tier papers) |
| D16 | Scripts use Python 3.6.8 and the standard library only. Only the subcommands `candidates`, `discover` and `fetch` use the network. | Assistant, from the environment |
| D17 | Full texts stay in the data directory. The repository holds metadata, counts and quotes of at most 25 words, each with a DOI. | Author (standing rule for public repositories) |
| D18 | The orchestrating session runs on Opus. Every subagent has an explicit model: Sonnet or Haiku. | Author, 2026-10-29 |

## 4. Feasibility evidence

The assistant ran these checks on 2026-10-29 with Python 3.6.8 `urllib`. The scripts and outputs are in the session scratch directory, outside the repository.

- **OpenAlex by ORCID.** The filter `author.orcid` returned 145 works for Garcia (ORCID 0000-0002-5212-3649) and 228 for Trapnell (ORCID 0000-0002-8105-4347). The filter on Trapnell's OpenAlex author ID returned the same 228 works.
- **Split records.** Garcia has two OpenAlex author records with the same ORCID: 135 works and 7 works. A search by one record misses the other.
- **High-tier counts.** With the draft venue list, Trapnell is first, last or sole author of 20 high-tier articles and reviews (17 with a PMC ID). Garcia has 7 (6 with a PMC ID).
- **Co-senior papers.** Trapnell is a corresponding author in the second-to-last position on 12 articles and reviews. Most are joint papers with Shendure.
- **PMC author manuscripts.** NCBI E-utilities (`efetch`, `db=pmc`) returned the full body of PMC6003873 (Cell, 2018, an author manuscript): 334 paragraph elements. Europe PMC `fullTextXML` returned HTTP 500 for that paper and for two other author manuscripts.
- **PMC open access.** Europe PMC `fullTextXML` returned the full text of PMC4532966 (eLife).
- **bioRxiv.** The bioRxiv API returned a JATS URL for 10.1101/2020.08.29.273474, and the file had a full body. Cold Spring Harbor journals share the DOI prefix 10.1101: a Genes & Development DOI returned no bioRxiv record.
- **arXiv.** `arxiv.org/html/1901.11365` returned LaTeXML HTML with 14 section elements. The ar5iv mirror timed out.

## 5. Constraints

- The repository is public. Fixtures and examples use invented people, papers and text only.
- No request carries the author's email address. Requests carry a user agent that names the tool and the repository URL.
- The data directory must exist and must be outside the git worktree. A script exits with code 2 when `STYLE_LAB_DATA` is unset or points inside the worktree.
- Downloaded files are data. The XML reader refuses any document that declares an entity (`<!ENTITY`). No script runs code from the data directory.
- Each host has a minimum interval between requests: OpenAlex 0.2 s, NCBI 0.4 s, Europe PMC 0.2 s, bioRxiv 1 s, arXiv 3 s.
- A run with `--pilot` writes only to `<data directory>/pilot/`. A script never replaces a committed manifest or profile with one that has fewer papers, unless the call gives `--force`.
- Exit codes: 0 for success, 1 for a failed check, 2 for a usage or input error.
- Cards and the principles file follow the author's Writing Standard. Before a commit, the orchestrator runs the `plain-prose` lint on them. PR 5 holds that plugin.

## 6. Pipeline

```
registry ─► discover ─► sample ─► fetch ─► normalize ─► surface ─────────────┐
 (Opus      (script)    (script)  (script)  (script)    (script)             │
 confirms)                                                                   ▼
                                    extract ─► check quotes ─► aggregate ─► card ─► check card ─► principles
                                    (Sonnet)   (script)        (script)     (Sonnet) (script)      (Opus)
```

The command `lab/style_lab.py` has one subcommand per script step: `candidates`, `discover`, `sample`, `fetch`, `normalize`, `surface`, `check-quotes`, `aggregate`, `check-card` and `status`. Each step writes one file per paper or per person. A rerun skips an item whose output exists with the same version key.

The command `/style-lab` (`commands/style-lab.md`) gives a session the steps of this pipeline, the brief of each subagent and the model of each subagent. To add a person later, the session adds a registry entry and runs the same steps.

## 7. Registry and discovery

**Registry.** `candidates "<name>"` lists the OpenAlex author records for a name, with ORCID, works count and last institutions. The orchestrator (Opus) picks the records of the right person and writes the entry in `data/people.json`:

```json
{"id": "garcia", "name": "Hernan G. Garcia", "orcid": "0000-0002-5212-3649",
 "openalex_ids": ["A5087070135", "A5136536694"], "ml_venues": false,
 "confirmed_by": "orchestrator, 2026-10-29", "note": "two OpenAlex records share the ORCID"}
```

If the orchestrator cannot tell two people apart from the records, it stops for that person and asks the author.

**Discovery.** `discover <id>` fetches all works by ORCID and by every listed OpenAlex ID, and removes duplicates. For each work it records:
- the person's author position, the corresponding-author flag and the author count;
- the type, the venue and the year;
- the DOI, the PMC ID, and the preprint and arXiv identifiers.

Discovery keeps works of type `article`, `review`, `preprint`, `editorial`, `letter` and `conference-paper`. It drops the other types, and it drops titles that start with a correction or retraction notice (for example "Author Correction:").

A preprint and a journal paper with the same normalized title become one paper. Discovery keeps the journal record and stores the preprint DOI as a route.

Each paper gets one group, and discovery drops the rest:

| Group | Rule |
|---|---|
| `essay` | Type `review`, `editorial` or `letter`, or a venue in the essay list ("Nature Reviews", "Trends in", "Current Opinion in", "Annual Review of"). At most 3 authors. Any author position. |
| `senior` | Any other paper where the person is the last author, the sole author, or a corresponding author in a position other than first. |
| `first` | Any other paper where the person is the first author. |
| (dropped) | Middle author and not a corresponding author. |

**Shared papers.** A paper may list two or more people from the registry. Only one of them can draw it: first choice is the last author, then a corresponding author, then the first author. Registry order breaks a tie. The flag `co_senior` marks a paper where another author, in or outside the registry, is also a corresponding author.

## 8. Sample

**Tiers.** `data/venues.json` holds the venue lists. The match is on the OpenAlex venue name and ignores case.

- `high`: Science, Nature and Cell, and every venue whose name starts with "Nature " except Nature Communications. Also these venues: Science Translational Medicine, Science Immunology, Science Robotics, Science Signaling, Cell Systems, Cell Genomics, Molecular Cell, Developmental Cell, Cell Stem Cell, Current Biology, Neuron, Immunity, Cancer Cell, Cell Metabolism, Cell Host & Microbe and Cell Chemical Biology.
- For a person with `"ml_venues": true` (Zou and Rives), the names of NeurIPS, ICML and ICLR also count as `high`. The file lists the names that OpenAlex uses for each.
- `other`: every other venue, including Nature Communications, Science Advances, Cell Reports, PNAS and eLife, and preprints that have no journal record.

**Targets.** The target is 15 papers per person:

| Group | High | Other | Total |
|---|---|---|---|
| senior | 5 | 3 | 8 |
| first | 3 | 1 | 4 |
| essay | 2 | 1 | 3 |
| total | 10 | 5 | 15 |

**Fallback.** When a cell has too few papers, its spare slots move in this order:

1. To the other tier of the same group.
2. To the other two groups, in the order senior, first, essay. Inside a group, the high tier fills first.

The manifest records the target and the result for every cell, and the total shortfall when a person has fewer than 15 papers.

**Draw.** Each cell has its own random generator. The seed is the text `"<seed>:<person>:<group>:<tier>"`, and the default seed is 20261029. Python 3 seeds a generator from a string through SHA-512, so the draw is the same on every run.

To draw k papers from a cell, the sampler:

1. Sorts the cell's papers by year, then by work ID.
2. Splits the list into k bins of near-equal size.
3. Draws one paper from each bin.

The bins spread the sample across the person's career. The papers left over form a replacement queue, shuffled by the same generator.

## 9. Fetch

`fetch` processes every paper in the sample, in one process for all people. It tries the routes in this order and stops at the first success:

| Order | Route | When | Text version |
|---|---|---|---|
| 1 | NCBI E-utilities `efetch`, `db=pmc` | The paper has a PMC ID | `accepted` if Europe PMC flags an author manuscript, else `published` |
| 2 | Europe PMC `fullTextXML` | Route 1 failed | as route 1 |
| 3 | bioRxiv or medRxiv API, then the JATS file it names | The paper or its merged preprint has a 10.1101 DOI that the API confirms | `preprint` |
| 4 | `arxiv.org/html/<id>` | The paper has an arXiv ID | `arxiv` |

Before the routes, `fetch` asks the Europe PMC search for each DOI. The answer can supply a missing PMC ID, the author-manuscript flag, and a preprint record that matches the title.

A route succeeds when the reader in section 10 finds at least 600 words of body text outside Methods.

When every route fails, the sampler replaces the paper. The replacement comes from the same year bin when the bin has another paper, else from the cell's replacement queue. The manifest records the replaced paper, the reason and the replacement.

Raw responses go to `<data directory>/raw/<host>/` under a hash of the URL, with a sidecar file that holds the URL, the status and the date. A rerun reads the cache. `--refresh` downloads again. Each request has a 60 s timeout and up to 3 retries with backoff for HTTP 429 and 5xx. An HTTP 500 from Europe PMC `fullTextXML` counts as a route failure after one retry.

## 10. Normalize

`normalize` turns each response into one paper file in `<data directory>/papers/<person>/<work id>.json`:

```json
{"schema": 1, "normalizer_version": "1",
 "work_id": "W0000000001", "person": "garcia", "doi": "10.0000/invented", "title": "...",
 "year": 2018, "venue": "...", "tier": "high", "group": "senior", "co_senior": false,
 "text_version": "accepted", "route": "ncbi-pmc", "article_type": "research-article",
 "abstract": ["..."],
 "sections": [{"heading": "Introduction", "kind": "intro", "paragraphs": ["..."],
               "subsections": [{"heading": "...", "paragraphs": ["..."]}]}],
 "legends": ["..."], "word_counts": {"intro": 0}, "sha256": "..."}
```

- **Section kinds.** Keywords in the heading set the kind: `intro`, `results`, `discussion`, `methods` or `other`. Unheaded text before the first heading is `intro`. A paper with no headings, such as a Science report, has one section of kind `body`. The reader drops references, acknowledgments, author contributions, competing interests, data availability and supplements.
- **Inline marks.** A run of citations becomes one `[CIT]`. A formula becomes `[EQ]`. Figure references stay as written. Tables leave the paragraphs, and their legends go to `legends`.
- **Readers.** There are two readers: JATS XML (PMC, Europe PMC, bioRxiv) and LaTeXML HTML (arXiv).
- **Hash.** `sha256` is the hash of the canonical text. Later steps use it in their cache keys.

## 11. Surface layer

`surface` measures each paper file by script and pools the results per person. Methods text is left out.

| Measure | Definition |
|---|---|
| Sentence length | Words per sentence: mean, median, 90th percentile, per section kind. |
| Paragraph length | Sentences per paragraph: mean and median. |
| First person | Share of sentences with "we", "our", "us", "I" or "my". |
| Passive estimate | Share of sentences with a form of "be" followed by a past participle (regular "-ed" or a listed irregular form). The pilot measures its precision. |
| Hedges | Per 1,000 words, from a word list in `data/wordlists.json`. |
| Connectives and evaluative words | Per 1,000 words, for each word in a fixed list (for example "however", "thus", "together", "surprisingly", "importantly"). |
| Questions | Per 100 sentences. |
| Density | Numbers, `[CIT]` marks and figure references per sentence. |
| Openers | The 15 most common first words and the 10 most common first word pairs. |
| Distinctive vocabulary | The log-odds ratio with an informative Dirichlet prior (Monroe, Colaresi and Quinn, 2008), each person against the other six. Only words that occur in the texts of at least 4 people count, which removes most field-specific terms. The output is the top 30 words and the top 20 word pairs, with z-scores. |

The sentence splitter knows common abbreviations ("Fig.", "et al.", "e.g.", "i.e.", "vs.") and decimal numbers. The style lab has its own splitter, because one plugin cannot import another plugin's code.

## 12. Structure layer

**Checklist.** `data/checklist.json` (version 1) holds one entry per item: an ID, the question, the answer type and the evidence rule. Most answers come from a closed set, so a script can count them.

| ID | Question | Answer |
|---|---|---|
| `title_form` | What does the title state? | one of: claim, topic, method name, question |
| `abstract_moves` | Which moves does the abstract make, in order? | ordered list from: context, gap, approach, result, implication, other |
| `intro_roles` | What is the role of each introduction paragraph? | ordered list from: field, problem, gap, prior work, approach preview, here-we, other |
| `gap_sentence` | Which sentence states the gap? | quote and paragraph number, or none |
| `here_we` | Which sentence states what this paper does? | quote and paragraph number, or none |
| `results_headings` | What form do the results subheadings take? | one of: full-sentence claim, noun phrase, question, none; plus the headings |
| `results_openings` | How does each results section open? | list from: question, aim ("To test whether"), result first, method first |
| `storyline` | What question does each results section answer, and how does it lead to the next? | one line per section (free text) and the transition sentences as quotes |
| `excitement` | Where and how does the paper say a result matters? | list of: marker (evaluative word, first or novelty claim, scope claim, implication sentence), location, quote |
| `strongest_claim` | What is the strongest claim, and how is it hedged? | quote of the claim and of its hedge, or none |
| `limitations` | Where and how does the paper state its limits? | placement (own paragraph, own section, inline in results, inline in discussion, none), specificity (specific with a remedy, specific, generic), quotes |
| `discussion_moves` | Which moves does the discussion make, in order? | ordered list from: summary, mechanism, comparison with prior work, limitation, future work, implication, other |
| `explanations` | Which analogies or plain explanations for non-specialists does the paper use? | list of quotes, or none |
| `figure_reference` | How does the text refer to figures? | one of: result then reference, reference then result, mixed |
| `signature_phrases` | Which phrases recur or stand out? | list of quotes |
| `essay_argument` | For essays only: where is the thesis, how does the argument proceed, is there a call to action? | thesis location, argument form (free text), call to action (yes or no, with quote) |

**Evidence.** Each quote in an extraction is copied from the paper file and is at most 40 words long. The repository copy of a quote is at most 25 words (section 13).

**Subagents.** One Sonnet subagent works on each batch of up to 5 papers of one person, so each person needs 3 batches. The brief is `prompts/extract.md` plus the checklist and the paths of the paper files. The subagent reads only the paper files. It writes one extraction per paper to `<data directory>/extract/<person>/<work id>.json` with the checklist version, the prompt version and the paper hash.

**Quote check.** `check-quotes` looks for each quote in the paper file, after both texts get Unicode NFKC, single spaces, straight quotes and one dash form. A quote may include `[CIT]` and `[EQ]` marks.

- A quote that is not in the paper marks its item as `unverified`.
- When more than 10% of a paper's quotes fail, a fresh Sonnet subagent redoes the extraction once.
- A second failure marks the paper `extraction_failed`. The aggregate leaves it out and reports it.

**Agreement.** A second, independent Sonnet subagent extracts a seeded 20% of each sample, at least 3 papers per person. A script computes the agreement of the two extractions for each closed item. An item with agreement below 0.7 across all people is `unstable`, and no card states a pattern from it.

**Cache key.** The key is the checklist version, the prompt version and the paper hash. A new checklist version runs the extraction again.

## 13. Synthesis

**Aggregate.** `aggregate <id>` writes `profiles/<id>.json`:
- the counts of every closed answer, by group and by tier;
- the surface measures;
- the stable and unstable items;
- candidate quotes of at most 25 words, each verified and each with its DOI.

**Card.** One Sonnet subagent per person writes `profiles/<id>.md` from the profile data and the free-text answers (the storyline lines and transitions). The brief is `prompts/card.md`. The card has at most 900 words and these headings, in order:

Sample · Storyline · Introduction · Results · Excitement · Limitations · Discussion · Sentences and words · Signature moves · Caveats

The card follows these rules:
- Every count comes from the profile data and takes the form "N of M papers".
- Every quote has at most 25 words and a DOI. A card has at most 2 quotes from one paper and at most 20 quotes in total.
- The card describes and does not rank or praise.
- The text follows the Writing Standard.

**Check card.** `check-card <id>` fails a card when:
- a number in it is not in the profile data;
- a quote is not in a verified extraction, has more than 25 words, or has no DOI from the manifest;
- it exceeds a word or quote limit.

A failed card is rewritten once. A second failure stops the run and reports the failures.

**Principles.** The orchestrator (Opus) writes `profiles/principles.md` from the seven profiles, in at most 1,200 words. It has two parts:
- Shared moves: closed answers present in at least half of the papers of at least 5 people, with the counts for each person.
- Distinctive moves: for each person, the items where the person differs most from the median of the others.

`check-card` checks the principles file with the same rules.

**Quality file.** `profiles/quality.md` reports, per person and per item, the quote failure rate, the agreement and the spot-check precision (section 15). It reports each measure separately and combines none into a score.

## 14. What lives where

| Item | Place |
|---|---|
| Code, tests, invented fixtures, prompts, checklist, venue lists, word lists | repository |
| Registry: names, ORCIDs, OpenAlex IDs | repository |
| Manifests: DOI, title, year, venue, tier, group, text version, route, replacements | repository |
| Profiles, principles file, quality file | repository |
| Raw responses, paper files, extractions, surface measures, logs | data directory |
| Pilot outputs | `<data directory>/pilot/` |

## 15. Pilot and scale

**Stage A: discovery pilot, all seven people.** The orchestrator confirms the registry. `discover` and `sample --pilot` run for all seven, which costs only metadata requests. The orchestrator reads every manifest row (about 105) and the dropped and merged lists of two people. It checks:
- the group and tier of each paper;
- the ML venue names for Zou and Rives;
- the merged preprints and the shared papers;
- the empty cells, which the manifest reports. An essay cell for Rives may be empty.

The orchestrator fixes the rules before Stage B.

**Stage B: text pilot.** The orchestrator picks five papers from Garcia's pilot sample. Together they cover the three groups, both tiers and the text versions `published`, `accepted` and `preprint`. One arXiv-only paper of Zou or Rives tests the arXiv reader. For these six papers:
1. Fetch and normalize. The orchestrator reads the section list of every paper file and reads paragraphs at the start, the middle and the end.
2. Extract. The orchestrator reads every checklist answer (16 items for each of 6 papers) and marks each correct, wrong or vague.
3. Revise the checklist and the prompt from those marks, with a new version, and run again. The cache key makes the rerun use the new version.
4. Measure the precision of the passive estimate on 50 seeded sentences.
5. Write a pilot card for Garcia. The author reads it and says what is wrong.

**Stage C: scale.** Full samples for all seven people. The scale run recomputes the pilot measures (quote failure rate, agreement per item) and compares them with the pilot. A large difference means the pilot was not representative, and the orchestrator reports it. For the spot check, the orchestrator reads every item of one seeded paper per person and reports precision per item.

**Stage D: synthesis.** Cards, card checks, the principles file and the quality file. The author reads the Garcia and Royer cards.

**Success.**
- Seven manifests, each with at least 12 papers with full text, or a recorded shortfall.
- Every quote in the repository is verified against its paper, has at most 25 words and has a DOI.
- `profiles/quality.md` reports the agreement and the spot-check precision per item.
- The author confirms that the Garcia and Royer cards match the author's knowledge of their writing, or lists what is wrong.

## 16. Model tiers

| Step | Done by | Reason |
|---|---|---|
| `candidates`, `discover`, `sample`, `fetch`, `normalize`, `surface`, `check-quotes`, `aggregate`, `check-card` | script | Deterministic, and the tests check them. |
| Registry confirmation | Opus (orchestrator) | A wrong identity makes every later step wrong. |
| Extraction and agreement run | Sonnet, one subagent per batch of up to 5 papers | Judgment inside a fixed checklist. |
| Card | Sonnet, one subagent per person | Drafting to a fixed outline. |
| Pilot reading, spot check, principles file | Opus (orchestrator) | Designing checks and arguing against findings. |

The style lab gives Haiku no task. Every mechanical step is a script that the tests check, and one process does the fetch (D13).

## 17. Errors

| Condition | Behavior |
|---|---|
| The registry cannot tell two people apart | Stop for that person and ask the author. |
| `STYLE_LAB_DATA` unset or inside the worktree | Exit 2. |
| Host down or timeouts after retries | The step stops. A rerun resumes from the per-item files. |
| A paper with no open full text | Replace it from the same cell, and record the replacement. |
| A person with fewer than 15 papers | Record the shortfall. Cards state N of M. |
| An empty cell | Record it in the manifest. |
| A document that declares an entity | Refuse it as a route failure. |
| A paper file with less than 600 words of body text | Route failure. |
| A rerun that would shrink a committed manifest or profile | Refuse it without `--force`. |

## 18. Tests

Unit tests use the standard `unittest` module, invented fixtures and no network. A fake HTTP layer and a fake clock stand in for the hosts.

- Discovery: author positions, the corresponding-author rule, groups, type filters, correction titles, preprint merges, shared-paper assignment.
- Tiers: exact names, the "Nature " prefix and its exclusion, the `ml_venues` flag per person.
- Sample: the same seed gives the same draw, and a different seed gives a different draw. Also year bins, cell targets, the fallback order, the replacement order and shortfall records.
- Fetch: route order, text version from the flags, the 600-word test, the bioRxiv confirmation of a 10.1101 DOI, the spacing per host, cache hits.
- Readers: section kinds, `[CIT]` runs, `[EQ]`, legends, dropped sections, refusal of entity declarations, the no-heading case.
- Surface: the splitter on abbreviations and decimals; each measure on a short invented text with values computed by hand; log-odds on a toy corpus.
- Quote check: an exact quote passes, a quote with changed spaces or curly quotes passes, a paraphrase fails, a quote across a `[CIT]` passes.
- Card check: an invented number fails, a quote over 25 words fails, a quote with no DOI fails, a quote absent from the extraction fails.
- Guards: each guard has one test where it fires and one where it stays silent.
- Paths: the data directory guard and the shrink guard.

## 19. Files

```
plugins/science-style/
  .claude-plugin/plugin.json
  LICENSE                     MIT, the same text as plain-prose
  README.md
  commands/style-lab.md       the steps a session follows to run the lab for one or more people
  lab/
    style_lab.py              command line with the subcommands of section 6
    lab_paths.py              data directory guard and paths
    lab_http.py               requests, cache, spacing per host, retries
    lab_openalex.py           candidates, discovery, positions, groups, merges
    lab_venues.py             tiers
    lab_sample.py             targets, bins, fallback, replacements
    lab_fetch.py              routes and text versions
    lab_jats.py               JATS reader
    lab_arxiv.py              LaTeXML HTML reader
    lab_text.py               splitter, normalization for the quote check
    lab_surface.py            surface measures and log-odds
    lab_quotes.py             quote check
    lab_aggregate.py          profile data
    lab_card_check.py         card and principles check
  data/  people.json  venues.json  checklist.json  wordlists.json
  prompts/  extract.md  card.md  principles.md
  manifests/                  one file per person
  profiles/                   <id>.json, <id>.md, principles.md, quality.md
  tests/                      unittest files and invented fixtures
```

The plugin also gets an entry in `.claude-plugin/marketplace.json`.

## 20. Interface for part 2

The writing skill reads the cards and the principles file. It can read the profile data for counts. The card headings in section 13 are the contract between the two parts. A change to them needs a change in both parts.

Part 2 must decide:
- one skill or one skill per person;
- how to blend two or more people;
- how to run the `plain-prose` checks, which are in PR 5 and not yet merged;
- how to write blog posts and grant text, since no paper in the sample has that form. Essays are the closest.

## 21. Risks and open questions

1. **Authorship.** Trainees draft most senior-author papers, and the person edits them. A card therefore describes the papers of the person's lab. First-author papers and essays carry more of the person's own words. The profile reports counts by group, so part 2 can weight the groups.
2. **Text versions.** An accepted manuscript lacks the journal's last edits, and a preprint is an earlier draft. Each paper file records its text version.
3. **Essay detection.** Some commentaries carry the type `article` in OpenAlex. Stage A reads the lists to find them.
4. **ML venue names.** OpenAlex names conference venues in more than one way. Stage A checks the manifests of Zou and Rives.
5. **Small counts.** Fifteen papers give wide uncertainty. Cards use "N of M papers" and no percentages.
6. **Field terms.** Field-specific words can still pass the shared-word filter. Stage B reads the distinctive word lists.
7. **Exclusions.** Book chapters (Garcia has 26 such records) and PDF-only papers are out. The manifests record the replacements.
8. **Text mining.** PMC author manuscripts and bioRxiv allow text mining for research. The style lab keeps full texts in the data directory and publishes only metadata, counts and short quotes.
