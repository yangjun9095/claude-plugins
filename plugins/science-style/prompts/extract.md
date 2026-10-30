# Brief: checklist extraction

Prompt version: 1

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
 "schema": 1, "checklist_version": 1, "prompt_version": 1,
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
- `checklist_version` is the `version` of the checklist file.
- `paper_sha256`, `work_id` and `person` come from the paper file.
- `attempt` is the attempt number of the dispatch, and `run` is the run named for the paper.
- `answers` has one entry for each checklist item, keyed by the item id.

## Rules

1. For the fields of type `enum`, `enum_list` and `objects`, use only the values that the checklist lists. Copy each value exactly.
2. Copy every quote from the paper file word for word, with its `[CIT]` and `[EQ]` marks. Do not shorten a quote with an ellipsis. A quote has at most 40 words. A script checks every quote against the paper file and rejects the extraction when more than one quote in ten fails.
3. A `quote` field holds one quote, or null when its value is `none`. A `quotes` field holds a list, which may be empty.
4. A `paragraph` field counts the paragraphs of the introduction from 1, in reading order. The introduction is every section of kind `intro`. Use null when the value is `none`.
5. For `gap_sentence` and `here_we`, a `value` of `present` needs a `quote` and a `paragraph`.
6. For `strongest_claim`, a `value` of `hedged` needs a `quote` and a `hedge_quote`. A `value` of `unhedged` needs a `quote`, and `hedge_quote` is null. A `value` of `none` leaves both null.
7. For `limitations`, a `placement` of `none` needs a `specificity` of `none` and an empty `quotes` list. Any other `placement` needs at least one quote and a `specificity` other than `none`.
8. When the group of a paper is not `essay`, the answer to `essay_argument` is `{"not_applicable": true}`.
9. For `essay_argument`, a `call_to_action` of `yes` needs the sentence as `quote`. A `call_to_action` of `no` needs a `quote` of null.
10. Answer from the text as it stands. When the text shows no answer, choose `none` or `other`, or leave the list empty.
11. Write the output file as valid JSON. Escape every double quote inside a quote as `\"`.

## Meanings of the values

- `title_form`: `claim` states a finding ("X controls Y"). `topic` names an area. `method name` names a method or a tool. `question` asks a question.
- `abstract_moves`, in the order they occur: `context` is background; `gap` is what is not known or not possible; `approach` is what the authors did; `result` is what they found; `implication` is what the finding means beyond the paper.
- `intro_roles`, one value per paragraph: `field` introduces the field; `problem` names the specific problem; `gap` states what is missing; `prior work` reviews earlier approaches and their limits; `approach preview` describes the approach without results; `here-we` states what this paper does.
- `gap_sentence` and `here_we`: the one sentence that states the gap, and the one sentence that states what this paper does.
- `results_headings`: `full-sentence claim` has a verb and states a finding; `noun phrase` names a topic; `question` asks; `none` means the results have no subheadings.
- `results_openings`, one value per results section: `question` opens with a question; `aim` opens with the aim ("To test whether", "We next asked"); `result first` opens with the finding; `method first` opens with the method.
- `storyline`: in `lines`, write one short line for each results section, the question that the section answers. In `quotes`, put the sentences that lead from one section to the next.
- `excitement`, one entry per place where the paper says a result matters. `marker`: `evaluative word` judges a result ("striking", "unexpected"); `first or novelty claim` says first or new; `scope claim` says how far the result reaches ("in all", "across"); `implication sentence` says what the result makes possible. `location` names the part of the paper.
- `strongest_claim`: the claim that reaches furthest. `hedged` means a hedge word stands in the same sentence or the next one; quote that hedge in `hedge_quote`. `unhedged` means none does.
- `limitations`: `placement` is where the limits stand. `specificity`: `specific with a remedy` names a limit and the experiment or method that would remove it; `specific` names a limit; `generic` says only that more work is needed.
- `discussion_moves`, in the order they occur: `summary`, `mechanism` (a proposed explanation), `comparison with prior work`, `limitation`, `future work`, `implication`.
- `explanations`: analogies and plain explanations that a reader outside the field can follow.
- `figure_reference`: `result then reference` states the result and cites the figure at the end; `reference then result` starts with the figure ("Figure 2 shows that"); `mixed` does both often.
- `signature_phrases`: phrases that recur in the paper or stand out from common scientific prose.
- `essay_argument`: `thesis_location` is where the essay states its main point; `argument` is one or two sentences on how the argument proceeds; `call_to_action` is `yes` when the essay asks the reader or the field to act, with that sentence as `quote`.

## Report

When you finish, reply with one line per paper: the work id and "written", or the work id and the problem. Do not paste the JSON into the reply.
