# Brief: checklist extraction

Prompt version: 2

You fill the checklist of the style lab for each paper file that the dispatch lists. Read only those paper files and the checklist file. Do not use the web. Do not dispatch other agents.

## Inputs

The dispatch gives you:
- the path of the checklist, `data/checklist.json`;
- for each paper: the path of the paper file, the path of the output file, the group (`senior`, `first` or `essay`) and the run (`main` or `agreement`);
- the attempt number.

A paper file is JSON. Its `abstract` is a list of paragraphs. Its `sections` list holds each section's `heading`, `kind` (`intro`, `results`, `discussion`, `methods`, `body` or `other`), `paragraphs` and `subsections`. The mark `[CIT]` stands for citations and `[EQ]` for a formula.

## Output

Write one JSON file per paper, at its output path, in this shape:

```json
{
 "schema": 1, "checklist_version": 2, "prompt_version": 2,
 "paper_sha256": "0000000000000000000000000000000000000000000000000000000000000000",
 "work_id": "W0000000001", "person": "ada", "attempt": 1, "run": "main",
 "answers": {
  "title_form": {"value": "claim"},
  "abstract_moves": {"value": ["context", "gap", "approach", "result", "implication"]},
  "intro_roles": {"value": ["field", "problem", "gap", "here-we"]},
  "gap_sentence": {"value": "present", "paragraph": 3, "quote": "How spores time this split is not known [CIT]."},
  "here_we": {"value": "present", "paragraph": 4, "quote": "Here we show that the coat splits when it takes up water."},
  "results_headings": {"value": "full-sentence claim", "headings": ["Spores swell before they split", "Water opens the seam"]},
  "results_openings": {"value": ["question", "result first"]},
  "storyline": {"lines": ["Do spores swell before they split?", "What opens the seam?"], "quotes": ["We next asked what opens the seam."]},
  "excitement": {"value": [{"marker": "scope claim", "location": "abstract", "quote": "The same rule holds in all 12 fern species we tested."}]},
  "strongest_claim": {"value": "hedged", "quote": "Water alone opens the seam.", "hedge_quote": "These data suggest that no enzyme is needed."},
  "limitations": {"placement": "own paragraph", "specificity": "specific with a remedy", "quotes": ["We did not measure the force on the seam, which a needle probe could test."]},
  "discussion_moves": {"value": ["summary", "mechanism", "limitation", "future work"]},
  "explanations": {"quotes": ["The coat works like a zip that opens from one end."]},
  "figure_reference": {"value": "result then reference"},
  "signature_phrases": {"quotes": ["Together, these results show"]},
  "essay_argument": {"not_applicable": true}
 }
}
```

Fill the top fields this way:
- `schema` is 1.
- `checklist_version` is the `version` of the checklist file.
- `prompt_version` is the number on the `Prompt version` line of this brief.
- `paper_sha256` is the `sha256` field of the paper file. `work_id` and `person` also come from the paper file.
- `attempt` is the attempt number of the dispatch, and `run` is the run named for the paper.
- `answers` has one entry for each checklist item, keyed by the item id.

## Rules

1. For the fields of type `enum`, `enum_list` and `objects`, use only the values that the checklist lists. Copy each value exactly.
2. Each answer holds every field of its item and no other field. Each `excitement` entry holds `marker`, `location` and `quote`, and the quote is not empty.
3. Copy every quote from the paper file word for word, with its `[CIT]` and `[EQ]` marks. Do not shorten a quote with an ellipsis. A quote has at most 40 words.
4. Prefer quotes of 25 words or fewer. A longer quote never reaches a profile.
5. A script checks every quote against the paper file. The script rejects an extraction when more than 1 quote in 10 fails. With fewer than 10 quotes, one failed quote rejects the extraction. The script also rejects an extraction with no quote.
6. A `quote` field holds one quote, or null when its value is `none`. A `quotes` field holds a list, which may be empty.
7. A `paragraph` field counts the paragraphs of the introduction from 1, in reading order. Use null when the value is `none`. The introduction is every section of kind `intro`. When no section has kind `intro`, the introduction is the first section, if its kind is `other` or `body`. When the first section has any other kind, for example `results`, the paper has no introduction. Leave `intro_roles` empty. Answer `none` to `gap_sentence` and `here_we`.
8. A `value` of `present` in `gap_sentence` or `here_we` needs a `quote` and a `paragraph`.
9. In `strongest_claim`, a `value` of `hedged` needs a `quote` and a `hedge_quote`. A `value` of `unhedged` needs a `quote`, and `hedge_quote` is null. A `value` of `none` leaves both null.
10. `limitations` needs a `specificity` of `none` and an empty `quotes` list when `placement` is `none`. Any other `placement` needs at least one quote and a `specificity` other than `none`.
11. When the group of a paper is not `essay`, the answer to `essay_argument` is `{"not_applicable": true}`.
12. When no section of the paper has kind `results`, answer `{"not_applicable": true}` to `results_headings`, `results_openings` and `storyline`. When any section has kind `results`, fill these three items.
13. Each section of kind `results` is one results section. When the paper has one section of kind `results` and it has subsections, each subsection is one results section instead. A section of any other kind is never a results section.
14. A `call_to_action` of `yes` in `essay_argument` needs the sentence as `quote`. A `call_to_action` of `no` needs a `quote` of null.
15. Answer from the text as it stands. When the text shows no answer, choose `none` or `other` if the item lists it, or leave the list empty.
16. For `figure_reference`, choose `no figures` when the text cites no figure.
17. Write the output file as valid JSON. Escape every double quote inside a quote as `\"`.

## Meanings of the values

- `title_form`: `claim` states a finding ("X controls Y"). `topic` names an area. `method name` names a method or a tool. `question` asks a question.
- `abstract_moves`, in the order they occur: `context` is background; `gap` is what is not known or not possible, what earlier work has not done ("studied to date", "current models only"), or a stated need; `approach` is what the authors did; `result` is what they found; `implication` is what the finding means beyond the paper. In a paper with no section of kind `results`, a sentence on what the paper covers or teaches is `approach`. In such a paper, a sentence on what the reviewed work found is `context`. In such a paper, an outlook or a recommendation is `implication`. Do not use `result` for such a paper.
- `intro_roles`, one value per paragraph: `field` introduces the field; `problem` names the specific problem; `gap` states what is missing; `prior work` reviews earlier approaches and their limits; `approach preview` describes the approach without results; `result preview` summarizes the findings of this paper before the results section; `here-we` states what this paper does.
- `gap_sentence` and `here_we`: the one sentence that states the gap, and the one sentence that states what this paper does.
- `results_headings`: `full-sentence claim` has a verb and states a finding; `noun phrase` names a topic; `question` asks; `none` means the results have no subheadings. Choose the form that most headings take. Use the lowest heading level inside the results. That means the subsection headings when the results have subsections, and the section headings when they have none.
- `results_openings`, one value per results section: `question` opens with a question; `aim` opens with the aim ("To test whether", "We next asked"); `result first` opens with the finding; `method first` opens with the method. Judge each results section by its first sentence that asks a question, states an aim, states a finding or describes a method. Skip sentences that give background, cite earlier work or state a hypothesis. A sentence that states the finding ("we begin by showing that X") is `result first`.
- `storyline`: in `lines`, write one short line for each results section, the question that the section answers. When the results are one section with no subsections, write one line for each new question that the text answers. A step that serves the same question gets no line of its own. In `quotes`, put the sentences that lead from one section to the next.
- `excitement`, one entry per place where the paper says a result matters. `marker`: `evaluative word` judges a result ("striking", "unexpected"); `first or novelty claim` says first or new; `scope claim` says how far the result reaches ("in all", "across"); `implication sentence` says what the result makes possible. `location` names the part of the paper.
- `strongest_claim`: the claim with the widest scope, the one that carries the findings furthest beyond the systems the authors tested. Choose it over a narrower claim even when it is hedged. `hedged` means a hedge word stands in the same sentence or the next one; quote that hedge in `hedge_quote`. `unhedged` means none does.
- `limitations`: `placement` is where most limits stand. When no place holds most, choose the first place in reading order. `inline in methods` means that the limits stand in the Methods. `inline in body` is for a paper with no results or discussion section. A limit is a weakness or boundary of this paper's own data, method or claims. A hypothesis, or a limit of earlier work, is not a limit. `specificity` is the most specific level that any limit reaches. `specific with a remedy` names a limit and the experiment or method that would remove it. `specific` names a limit. `generic` says only that more work is needed. These levels run from most to least specific.
- `discussion_moves`, in the order they occur: `summary`, `mechanism` (a proposed explanation), `comparison with prior work`, `limitation`, `future work`, `implication`.
- `explanations`: analogies, and sentences that say in everyday words why or how something works, so that a reader outside the field can follow. Do not quote method steps written in field terms, or clauses that only pose a question.
- `figure_reference`: `result then reference` states the result and cites the figure at the end. `reference then result` starts with the figure ("Figure 2 shows that"). `no figures` means the text cites no figure. `mixed` means that each of these two patterns makes up at least one third of the figure and table citations outside the Methods. Otherwise choose the pattern that most citations follow.
- `signature_phrases`: phrases that recur in the paper or stand out from common scientific prose. Quote only the recurring or unusual words, at most 12 words, not the sentence around them.
- `essay_argument`: `thesis_location` is where the essay states its main point; `argument` is one or two sentences on how the argument proceeds; `call_to_action` is `yes` when the essay asks the reader or the field to act, with that sentence as `quote`.

## Report

When you finish, reply with one line per paper: the work id and "written", or the work id and the problem. Do not paste the JSON into the reply.
