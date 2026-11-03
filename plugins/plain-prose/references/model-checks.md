# Model checks

Run these checks on each proposal that passes the guards. No script can make them. The guards test the form of a proposal. These checks test its meaning.

Answer each check with yes or no for the proposal. Send a proposal back to the rewrite when one answer is no. Name the failed check in the message.

Each line ends with a tag, such as `(T3, authors:S3)`. The tag gives the tier of the check and the key of its source in `references/research-notes/`. The tiers are T1 (measured in a corpus), T2 (stated by a named guide) and T3 (the repository owner's own list).

- The meaning is kept: the rewrite makes the same claim, and its verbs are no stronger than before. (T1, craft:S17)
- The rewrite holds no new fact: no claim, example, number, name or opinion that the sentence itself lacks. The paragraph around the sentence does not count. Each time and each quantity stays with its own verb. (T3, authors:S3)
- The sentence passes the portability test: it holds content, as the section "Rules for every rewrite" of `rewrite-rules.md` defines it. A sentence without content passes when the proposal follows the rule of that section for it. Never add a name or a number to pass the test, because the guards reject it. (T3, authors:S3)
- A hedge that states real doubt stays. When the rewrite removes such a hedge, restore it. Set `hedge_reason` only when the doubt is not real. (T1, craft:S13)
- The voice matches the profile: the length of the sentence, its first word and its hedges stay near the numbers of the profile. (T3, authors:S3)
- Each list holds only the items of the original. The rewrite adds no rule-of-three padding. (T3, authors:S1)
- One term names one thing in the paragraph. The rewrite shows no synonym cycling. (T2, craft:S2)
- The proposal ends on its last new fact. It holds no fake-profound closer, and it does not turn one into a better closer. (T3, authors:S1)
- Each citation still supports the same claim in its new place. The guard `masked-spans` lets a moved citation pass. (T1, craft:S20)
- Each number keeps its quantifier and its noun. The guard `numbers` does not check the noun after a number. (T1, craft:S17)
- A sentence to delete that holds a number or a citation needs a manual edit. The guards fail such a proposal, so tell the author. (T1, craft:S20)
- A result keeps its tense: a past-tense result does not become a present-tense claim. (T1, craft:S17)
- A strong human sentence stays unchanged. (T3, authors:S3)
- The rewrite names no source that the author did not give. A weasel attribution without a source becomes a hedged claim. The missing source goes in `reason`, and no mark enters the manuscript. The section `weasel-attribution` of `rewrite-rules.md` holds the rule. (T2, craft:S8)
- Interpretation stays out of Results, and new data stay out of Discussion. (T3, authors:S9)
