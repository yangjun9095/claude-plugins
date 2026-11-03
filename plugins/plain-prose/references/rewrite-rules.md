# Rewrite rules

Read this file before you write a proposal. It holds the rules for the rewrite of one sentence.

Each rule line ends with a tag, such as `(T2, craft:S4)`. The tag gives the tier of the rule and the key of its source in `references/research-notes/`. The tiers are T1 (measured in a corpus), T2 (stated by a named guide) and T3 (the repository owner's own list).

Each family section below has the same lines. The strategy line comes first. The line "Delete when" says what to remove. The line "Keep" says what the rewrite must not change. Two examples follow. A made-up sentence stands in each example.

## Rules for every rewrite

- State the claim in the first words of the sentence. (T2, craft:S6)
- Add no fact. Add no number, example, citation, opinion or recommendation. (T1, craft:S17)
- Keep a hedge that carries real doubt. The section "Hedges" gives the rules. (T1, craft:S13)
- Keep every number, citation and name. (T1, craft:S20)
- Make the minimum effective edit. Change the words that cause the fault and leave the rest. (T1, craft:S19)
- A sentence has content when it holds an observation, a number, a citation, a figure reference or a name from this study. (T3, authors:S3)
- When a flagged word is the only fault of the sentence, swap the style words. Otherwise delete a sentence that has no content when every family of its window allows deletion. Leave the window alone when the sentence has no content and a family forbids deletion. The "Delete when" line of a family wins over this deletion, which applies only when every family of the window allows a deleted sentence. (T2, craft:S5)
- Leave a strong human sentence alone. (T3, authors:S3)
- Use one name for one thing. Repeat the term. (T2, craft:S2)

## Hedges

A hedge is a word that limits a claim, such as `may` or `suggests`. Scientists place hedges where they interpret a result.

- Never flag a hedge from a word list alone. A list matches many words that are no hedge. (T1, craft:S14)
- Keep a hedge that qualifies an inference. Keep a hedge on a causal claim from an observational design or on a result beyond the sample. (T1, craft:S13)
- Propose an edit for stacked hedges only, such as `may possibly suggest`. Keep the one hedge that the data support. (T2, craft:S6)
- Never change a past-tense result to present tense. Keep every quantifier and add no recommendation. (T1, craft:S17)
- Replace a vague hedge with a number and an interval only when the paragraph already holds them. Otherwise keep the hedge. (T2, craft:S6)
- Give a `hedge_reason` when a rewrite changes the number of hedge words. The guard `hedge-kept` then passes. (T1, craft:S17)

## vocabulary-excess

Strategy: Replace the style word with the plain word, or with the fact that the word stands for. (T2, craft:S4)

Delete when: the word adds no meaning, as `intricate` before "link". Remove the word and keep the sentence. The family does not allow a deleted sentence.

Keep: terms of art such as `robust standard errors`, `pivotal trial` and `genomic landscape`. Keep every number and every hedge.

Example 1 before: `Here we delve into how Marlin-2 expression changes after heat shock (n = 24 plants).`
Example 1 after: `Here we examine how Marlin-2 expression changes after heat shock (n = 24 plants).`
Example 2 before: `The assay underscores the intricate link between dose and response (Fig. 2).`
Example 2 after: `The assay shows a link between dose and response (Fig. 2).`

## vocabulary-density

Strategy: Replace the style word with the plain word, or with the fact that the word stands for. (T2, craft:S4)

Delete when: the word adds no meaning, as `groundbreaking` before "assay". Remove the word and keep the sentence. The family does not allow a deleted sentence.

Keep: the word inside a term of art, such as `robust regression` or `facilitated diffusion`. Keep every number and every hedge. The detector flags these words only when the file holds more findings than the threshold.

Example 1 before: `Here we utilize a comprehensive panel of six Marlin-2 mutants (Table 1).`
Example 1 after: `Here we use a panel of six Marlin-2 mutants (Table 1).`
Example 2 before: `This groundbreaking assay measures Tavo binding in 12 root samples.`
Example 2 after: `This assay measures Tavo binding in 12 root samples.`

## figurative-load

Strategy: Replace the figure with the literal term for the relation that the figure names. (T2, craft:S5)

Delete when: the figure only decorates a sentence that already has a plain predicate. Remove the figure and keep the sentence. The family does not allow a deleted sentence.

Keep: the strength of the claim. The phrase `central to` must not become `required for`. Keep literal uses such as `load-bearing bone`, `peptide backbone` and `fitness landscape`.

Example 1 before: `This result is load-bearing for our argument that Marlin-2 acts upstream of Tavo.`
Example 1 after: `This result is essential to our argument that Marlin-2 acts upstream of Tavo.`
Example 2 before: `Tavo mutants weave a tapestry of phenotypes across the six tissues we examined.`
Example 2 after: `Tavo mutants show varied phenotypes across the six tissues we examined.`

## binary-contrast

Strategy: State the positive claim once. Drop the denied half unless a reader holds that view or a test addressed it. (T2, craft:S4)

Delete when: no reader holds the denied view and no test addressed it. Remove the denied half and keep the sentence. The family does not allow a deleted sentence.

Keep: a tested alternative with its result, its number and its figure reference.

Example 1 before: `The delay is not a technical artifact but a property of the cell cycle.`
Example 1 after: `The delay is a property of the cell cycle.`
Example 2 before: `Marlin-2 is not just a growth factor but a regulator of root hair length.`
Example 2 after: `Marlin-2 is a growth factor and a regulator of root hair length.`

## importance-puffery

Strategy: Replace the praise with the measured result or the cited fact that supports it. (T2, craft:S8)

Delete when: the paragraph holds no result that the praise could summarize. Set `delete` to true only then. The family allows a deleted sentence.

Keep: the number, the unit and the citation. Keep praise that a cited source states.

Example 1 before: `Survival under drought fell from 81% to 34% in the mutant (n = 60 per genotype). Marlin-2 therefore plays a pivotal role in drought tolerance.`
Example 1 after: `Survival under drought fell from 81% to 34% in the mutant (n = 60 per genotype). Marlin-2 therefore contributes to drought tolerance.`
Example 2 before: `Our 18-year record of weekly samples (n = 936) stands as a testament to the value of long-term monitoring.`
Example 2 after: `Our record holds weekly samples for 18 years (n = 936).`

## participial-benefit

Strategy: Move the clause into its own sentence with a subject and a verb. Delete it when it states a benefit that the data do not show. (T2, craft:S1)

Delete when: the clause states an unmeasured benefit or implication. Remove the clause and keep the sentence. The family does not allow a deleted sentence.

Keep: any number or citation in the clause. Keep the hedge on an implication.

Example 1 before: `Cells were sorted by flow cytometry, ensuring 94% pure populations (Fig. 1B).`
Example 1 after: `Cells were sorted by flow cytometry. The sorted populations were 94% pure (Fig. 1B).`
Example 2 before: `The model was trained on 12,000 images, ensuring reproducibility across sites.`
Example 2 after: `The model was trained on 12,000 images.`

## weasel-attribution

Strategy: Name the source with a citation. With no source, state the claim as your own or delete it. Never add a citation. (T2, craft:S8)

Delete when: the sentence holds no claim beyond the attribution. Set `delete` to true only then. The family allows a deleted sentence.

Keep: the citation and the count of sources, so that `two studies` stays two. Never add a citation that the author did not give. With no source, state the claim as a hedged claim about the subject, with `may` or `could`, never as a certain claim. Add no mark to the manuscript. Say in `reason` that the claim needs a source.

Example 1 before: `Studies suggest that Marlin-2 is expressed in the root.`
Example 1 after: `Marlin-2 may be expressed in the root.`
Example 2 before: `Experts suggest that sample size limits the precision of the estimate.`
Example 2 after: `Sample size may limit the precision of the estimate.`

## fake-strong-verb

Strategy: Use the verb that names the action, or use `is`. (T2, craft:S1)

Delete when: the verb phrase repeats its own heading or caption. Replace the verb phrase and keep the sentence. The family does not allow a deleted sentence.

Keep: the functional claim. The phrase `serves as` stays when it states a role, as in `serves as a binding site`. Keep the tense and the subject.

Example 1 before: `Figure 3 stands as a summary of the three assays.`
Example 1 after: `Figure 3 summarizes the three assays.`
Example 2 before: `The Marlin-2 pathway acts as a powerful driver of root growth.`
Example 2 after: `The Marlin-2 pathway drives root growth.`

## throat-clearing

Strategy: Delete the opener and start with the claim. (T2, craft:S6)

Delete when: the sentence only announces the next sentence or the section. Set `delete` to true only then. The family allows a deleted sentence.

Keep: any hedge, number or citation in the sentence. Keep the sentence that states the question that a Results paragraph answers.

Example 1 before: `It is worth noting that survival fell from 81% to 34% in the mutant.`
Example 1 after: `Survival fell from 81% to 34% in the mutant.`
Example 2 before: `In this section, we describe how the cohorts were recruited. The cohorts came from two clinics.`
Example 2 after: `The cohorts came from two clinics.`

## recap-opener

Strategy: Delete the opener word and keep the statement when it draws a new inference. (T2, craft:S2)

Delete when: the sentence repeats the previous sentence and draws no new inference. Set `delete` to true only then. The family allows a deleted sentence.

Keep: the hedge and the numbers. Keep the summary that opens a Discussion.

Example 1 before: `Overall, these data suggest that Marlin-2 limits root growth.`
Example 1 after: `These data suggest that Marlin-2 limits root growth.`
Example 2 before: `Tavo limited root growth in the mutant (Fig. 2). Taken together, Tavo limited root growth in the mutant.`
Example 2 after: `Tavo limited root growth in the mutant (Fig. 2).`

## em-dash

Strategy: Use commas or parentheses for an aside, a period for a second clause and a colon for a list. (T2, craft:S1)

Delete when: the aside holds no datum and the sentence is complete without it. Remove the aside and keep the sentence. The family does not allow a deleted sentence.

Keep: the names and numbers inside the aside. Keep one em dash per paragraph where a human would write it. In the examples, the text `&mdash;` stands for the em dash character.

Example 1 before: `The mutant &mdash; which lacks the C-terminal domain &mdash; grows slowly.`
Example 1 after: `The mutant, which lacks the C-terminal domain, grows slowly.`
Example 2 before: `Growth slowed at day 3 &mdash; and the effect was larger in the mutant.`
Example 2 after: `Growth slowed at day 3. The effect was larger in the mutant.`

## colon-reveal

Strategy: State the finding as the main clause. (T2, craft:S1)

Delete when: the lead-in only announces the finding. Remove the lead-in and keep the sentence. The family does not allow a deleted sentence.

Keep: colons before lists, equations and definitions.

Example 1 before: `The result was clear: Marlin-2 limits root growth.`
Example 1 after: `Marlin-2 limits root growth.`
Example 2 before: `We found one explanation: the mutant lacks the C-terminal domain.`
Example 2 after: `One explanation is that the mutant lacks the C-terminal domain.`

## rhetorical-question

Strategy: State the answer as a statement. (T2, craft:S6)

Delete when: the question adds nothing to its answer. Set `delete` to true only when the answer sentence needs no change. The family allows a deleted sentence. Never widen a deletion: it covers the question alone.

Keep: a question that opens a Results paragraph or states a tested hypothesis. Leave such a question alone and write no proposal. Otherwise one proposal covers the question and its answer. The window holds the question, so keep `start` and set `end` and `before` to span both sentences.

Example 1 before: `The mutant grew slowly. Why does Marlin-2 limit growth? Because it represses the Tavo gene.`
Example 1 after: `The mutant grew slowly. Marlin-2 limits growth because it represses the Tavo gene.`
Example 2 before: `The delay lasted 6 h. What explains the delay? Our data suggest that it reflects the cell cycle.`
Example 2 after: `The delay lasted 6 h. Our data suggest that the delay reflects the cell cycle.`

## assistant-residue

Strategy: Delete the whole span and tell the author to check the sentences that followed it. (T3, authors:S1)

Delete when: always. The family allows a deleted sentence. It covers a chat opener, a refusal, a placeholder and a tool-citation tag such as `oaicite` or `contentReference`. The masker hides a tag inside a URL, so the detector misses `utm_source=chatgpt.com`.

Keep: nothing from the span. Say in `reason` that the author must check the sentences after the span and the source of their numbers. Step 5 of the command shows the `reason` to the author.

Example 1 before: `Certainly! Here is the revised paragraph: Survival fell from 81% to 34%.`
Example 1 after: `Survival fell from 81% to 34%.`
Example 2 before: `As an AI language model, I cannot verify these values. The mutant grew 20% slower.`
Example 2 after: `The mutant grew 20% slower.`

## hedge-stack

Strategy: Keep the one hedge that the data support. Delete the other hedge word. (T2, craft:S6)

Delete when: a second hedge word adds no doubt. Remove that word and keep the sentence. The family does not allow a deleted sentence.

Keep: one hedge, the tense of the result and every quantifier. Ask the author when the choice of hedge is unclear. The guard `hedge-kept` passes when `families` holds `hedge-stack` and `after` keeps at least one hedge word and no more than `before` has.

Example 1 before: `Marlin-2 may possibly limit root growth in the mutant (Fig. 2).`
Example 1 after: `Marlin-2 may limit root growth in the mutant (Fig. 2).`
Example 2 before: `These data could potentially suggest that Tavo acts upstream of Marlin-2.`
Example 2 after: `These data suggest that Tavo acts upstream of Marlin-2.`

## repeated-openers

Strategy: Merge the sentences, or put the old information first so that each opener differs for a reason. (T2, craft:S1)

Delete when: a sentence repeats a neighbor. Set `delete` to true only then. The family allows a deleted sentence. Never widen a deletion: it covers one window.

Keep: parallel form for parallel claims. Keep `We` in Methods. The window holds the third sentence of the series. A series of four or more openers has one window for each sentence from the third on. Cover the series in one proposal. Set `start` to the first sentence and `end` to the end of the last window. Set `before` to the text between them.

Example 1 before: `The mutant grew slowly. The mutant lost the C-terminal domain. The mutant failed to bind Tavo.`
Example 1 after: `The mutant grew slowly. It lost the C-terminal domain and failed to bind Tavo.`
Example 2 before: `The assay measured growth. The assay measured binding. The assay measured expression.`
Example 2 after: `The assay measured growth, binding and expression.`

## staccato-run

Strategy: Join three or more fragments into one or two sentences. Put the new fact last. (T2, craft:S1)

Delete when: a fragment repeats a neighbor. Set `delete` to true only then. The family allows a deleted sentence. Never widen a deletion: it covers one window.

Keep: the numbers. Each time and each quantity stays with its own verb. Keep a short sentence that states a main finding or one Methods step. The window holds the third fragment. Cover the series in one proposal. Set `start` to the first fragment. Set `before` to the text from there to the end of the window.

Example 1 before: `Growth slowed. Cells arrested. Death followed at 48 h.`
Example 1 after: `Growth slowed and cells arrested; death followed at 48 h.`
Example 2 before: `The signal rose. It peaked. It fell by 60%.`
Example 2 after: `The signal rose and peaked, then fell by 60%.`
