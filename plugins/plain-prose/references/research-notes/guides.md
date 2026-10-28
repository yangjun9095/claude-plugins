# Guides and tools that list LLM writing patterns

Method. I read each source on 2026-10-23. I cloned the five repositories S1 to S4 and S6 at depth 1 and read the files listed in section 5. I read S5 as raw wikitext through the MediaWiki API. I read S7 and S8 as downloaded HTML turned into text. T2 means a named source states the pattern and gives no measurement. UNVERIFIED means I saw only a listing, a snippet, a summary, or a claim that one source makes about another source. n/a means the source does not call the item an LLM tell. A row can hold several categories, separated by semicolons. Plugin family names are short forms of the table in section 6 of the design spec. Keys S1 to S9 map to URLs in section 5. Example phrases are short quotes from the sources, set in code spans.

## 1. Pattern categories by source (table)

The table has 85 rows and names 149 categories: S1 19, S2 26, S3 25, S4 3, S5 27, S6 33, S7 10, S8 6. Names repeat across sources, so the count of distinct categories is lower. Two of the three S4 items are not LLM-tell categories (tier n/a).

| ID | Category (as the source names it) | Example phrases (short quotes) | Source | Tier | Source key | Plugin family |
|---|---|---|---|---|---|---|
| SS-01 | Throat-clearing openers; Emphasis crutches; Meta-commentary | `Here's the thing:`, `It turns out`, `Let that sink in.`, `In this section, we'll...` | S1 references/phrases.md | T2 | S1 | Throat-clearing and signposting |
| SS-02 | Business jargon | `Navigate`, `Lean into`, `Landscape`, `Deep dive`, `Game-changer` | S1 references/phrases.md | T2 | S1 | Figurative load words |
| SS-03 | Adverbs | `really`, `just`, `literally`, `fundamentally`, `inherently`, `interestingly` | S1 references/phrases.md | T2 | S1 | none |
| SS-04 | Performative emphasis; Telling instead of showing; Vague declaratives | `I promise`, `This is genuinely hard`, `The implications are significant`, `The stakes are high` | S1 references/phrases.md | T2 | S1 | Importance puffery |
| SS-05 | Binary contrasts; Negative listing | `Not because X, but because Y`, `isn't X, it's Y`, `not just X but also Y`, `Not a X... Not a Y... A Z.` | S1 references/structures.md | T2 | S1 | Binary contrast |
| SS-06 | Dramatic fragmentation | `That's it. That's the [thing].`, `X. And Y. And Z.` | S1 references/structures.md | T2 | S1 | Staccato run |
| SS-07 | Rhetorical setups | `What if [reframe]?`, `Think about it:`, `And that's okay.` | S1 references/structures.md | T2 | S1 | Rhetorical question answered at once |
| SS-08 | Formulaic constructions; False agency; Narrator-from-a-distance | `By the time X, I was Y.`, `the decision emerges`, `the data tells us`, `Nobody designed this.` | S1 references/structures.md | T2 | S1 | none |
| SS-09 | Passive voice | `It is believed that`, `Mistakes were made` | S1 references/structures.md | T2 | S1 | none |
| SS-10 | Sentence starters to avoid | sentences that start with a Wh- word, `So`, `Look,` | S1 references/structures.md | T2 | S1 | none |
| SS-11 | Rhythm patterns | three-item lists, questions answered at once, em dashes, stacked short sentences | S1 references/structures.md | T2 | S1 | Em dash; Rhetorical question answered at once; Staccato run |
| SS-12 | Word patterns | `every`, `always`, `never`, `everyone` | S1 references/structures.md | T2 | S1 | none |
| HU-01 | Not X but Y | `It's not just a feature, it's a shift.`, `This does not mean X. It means Y.` | S2 README; SKILL.md 1 | T2 | S2 | Binary contrast |
| HU-02 | One-line closers and dramatic fragments | `That is the real win.`, `Let that sink in.`, `No prior. No nostalgia.` | S2 SKILL.md 2 | T2 | S2 | Staccato run |
| HU-03 | Sayings that sound deep; Staged run-up before the point | `At its core, what really matters is...`, `Let's dive in`, `Here's the thing.` | S2 SKILL.md 3, 4 | T2 | S2 | Throat-clearing and signposting |
| HU-04 | Arguing with no one | `This isn't mainly about...`, `I'm not saying X, but...`, `A tempting approach would be...` | S2 SKILL.md 5 | T2 | S2 | Binary contrast |
| HU-05 | Forced triads | `innovation, inspiration, and insights` | S2 SKILL.md 6 | T2 | S2 | none |
| HU-06 | Repeated sentence openings | `She noted... She noted... She filed...` | S2 SKILL.md 7 | T2 | S2 | Repeated sentence openers |
| HU-07 | Dashes as the universal connector (weak alone) | em dash, en dash, ` -- ` | S2 SKILL.md 8 | T2 | S2 | Em dash |
| HU-08 | Stacked qualifiers; Hyphenated pairs everywhere; Passive voice and missing subjects (all weak alone) | `could potentially possibly be argued`, `the report is high-quality`, `No configuration file needed` | S2 SKILL.md 9 to 11 | T2 | S2 | none |
| HU-09 | Overused AI words | `delve`, `tapestry`, `testament`, `showcase`, `intricate`, `pivotal`, `underscore` | S2 SKILL.md 12 | T2 | S2 | Vocabulary with measured excess |
| HU-10 | Inflated significance | `stands as a testament`, `plays a key role`, `Despite these challenges... continues to thrive` | S2 SKILL.md 13 | T2 | S2 | Importance puffery |
| HU-11 | Shallow -ing riders | `highlighting`, `underscoring`, `ensuring`, `reflecting`, `showcasing` | S2 SKILL.md 15 | T2 | S2 | Trailing participial benefit clause |
| HU-12 | Borrowed authority | `Experts believe`, `industry reports`, `cited in [list of outlets]` | S2 SKILL.md 17 | T2 | S2 | Weasel attribution |
| HU-13 | Avoiding is, are, and has | `serves as`, `stands as`, `boasts`, `features`, `represents` | S2 SKILL.md 18 | T2 | S2 | Fake-strong verbs |
| HU-14 | Vague connection or association; Sales language | `associated with`, `in connection with`, `nestled`, `breathtaking` | S2 SKILL.md 14, 16 | T2 | S2 | none |
| HU-15 | Bold as decoration; Decorative headings; Curly quotation marks | bold labels on every list item, emoji in headings | S2 SKILL.md 19 to 21 | T2 | S2 | none |
| HU-16 | Chatbot residue; Knowledge-limit disclaimers and guesses | `Great question!`, `I hope this helps!`, `as of [date]`, `While details are limited` | S2 SKILL.md 22, 23 | T2 | S2 | Assistant residue |
| HU-17 | A heading repeated in the first sentence; Writing about the document instead of its subject; Re-explaining what the reader knows | `The table below compares...`, `## Performance` then `Speed matters.` | S2 SKILL.md 24 to 26 | T2 | S2 | none |
| HM-01 | Elegant variation (synonym cycling) | `protagonist... main character... central figure... hero` | S3 SKILL.md 11 | T2 | S3 | none (model check in the spec) |
| HM-02 | False ranges | `from the Big Bang to dark matter` | S3 SKILL.md 12 | T2 | S3 | none |
| HM-03 | Filler phrases | `In order to`, `Due to the fact that`, `It is important to note that` | S3 SKILL.md 22 | T2 | S3 | Throat-clearing and signposting |
| HM-04 | Sycophantic/servile tone | `Great question! You're absolutely right!` | S3 SKILL.md 21 | T2 | S3 | Assistant residue |
| HM-05 | Generic positive conclusions; Outline-like "Challenges and Future Prospects" sections | `The future looks bright`, `Despite these challenges` | S3 SKILL.md 24, 6 | T2 | S3 | Importance puffery |
| HM-06 | The other 19 patterns of S3 repeat the S2 names: Significance inflation; Notability name-dropping; Superficial analyses with -ing endings; Promotional language; Vague attributions; AI vocabulary; Copula avoidance; Negative parallelisms; Rule of three; Em dash overuse; Boldface overuse; Inline-header lists; Title case headings; Emojis; Curly quotes; Chatbot artifacts; Cutoff disclaimers; Excessive hedging; Hyphenated word pairs | see the S2 rows | S3 README | T2 | S3 | see the S2 rows |
| KD-01 | The "AI Bullet-Point Trap" (bulleted main text) | `lazy, unstructured, and very AI-generated` | S4 CLAUDE.md, Narrative Writing Standards | T2 | S4 | none |
| KD-02 | Overstatement words in the manuscript linter | `proves`, `definitively`, `guarantees`, `no limitations`, `universally`, `highly significant` | S4 skills/scientific-writing/scripts/lint_manuscript.py | n/a | S4 | none |
| KD-03 | Word choice table of the Nature style notes | `utilize`, `in order to`, `it is interesting to note that` | S4 skills/venue-templates/references/nature_science_style.md | n/a | S4 | Throat-clearing and signposting |
| WP-01 | Undue emphasis on significance, legacy, and broader trends; Outline-like conclusions about challenges and future prospects | `is a testament/reminder`, `a pivotal role/moment`, `evolving landscape`, `Despite these challenges` | S5 Content | T2 | S5 | Importance puffery |
| WP-02 | Canned emphasis on notability, attribution, and media coverage; Vague attributions and overgeneralization of opinions | `independent coverage`, `Industry reports`, `Experts argue`, `Observers have cited` | S5 Content | T2 | S5 | Weasel attribution |
| WP-03 | Superficial analyses | `highlighting/underscoring/emphasizing ...`, `ensuring ...`, `valuable insights` | S5 Content | T2 | S5 | Trailing participial benefit clause |
| WP-04 | Promotional and advertisement-like language; Vague expression of connection or association; "Awards and recognition" section | `boasts a`, `nestled`, `groundbreaking`, `associated with` | S5 Content | T2 | S5 | none |
| WP-05 | High density of "AI vocabulary" words | `delve`, `intricate`, `tapestry`, `testament`, `pivotal`, `crucial`, `Additionally` | S5 Language and grammar | T2 | S5 | Vocabulary with measured excess |
| WP-06 | AI vocabulary of mid-2026; vocabulary of one chatbot (Grok) | `leverage`, `multifaceted`, `quietly`, `universally`; `causal`, `empirical`, `correlate` | S5 Language and grammar (each claim cites one web page, not opened) | UNVERIFIED | S5 | Vocabulary with measured excess |
| WP-07 | Avoidance of basic copulatives | `serves as`, `stands as`, `functions as`, `boasts`, `refers to` | S5 Language and grammar | T2 | S5 | Fake-strong verbs |
| WP-08 | Negative parallelisms | `Not only ... but ...`, `It's not ..., it's ...`, `Y rather than X` | S5 Language and grammar | T2 | S5 | Binary contrast |
| WP-09 | Rule of three | adjective, adjective, adjective | S5 Language and grammar | T2 | S5 | none |
| WP-10 | Collaborative communication; Hedging disclaimers about source availability; Phrasal templates and placeholder text | `I hope this helps`, `Certainly!`, `While specific details are limited`, `based on available information` | S5 Communication intended for the user | T2 | S5 | Assistant residue |
| WP-11 | Title case; Overuse of boldface; Inline-header vertical lists; Emoji as formatting; Unusual use of tables; Curly quotation marks | formatting only | S5 Style | T2 | S5 | none |
| WP-12 | Section summaries (the page lists it as historical) | `In summary`, `In conclusion`, `Overall` | S5 Historical indicators | T2 | S5 | Recap openers |
| WP-13 | Overuse of em dashes, 2022 to September 2026 (the page lists it as historical) | em dash around clauses | S5 Historical indicators | T2 | S5 | Em dash |
| WP-14 | Lexical diversity/elegant variation (the page lists it as historical) | synonym rotation for one thing | S5 Historical indicators | T2 | S5 | none (model check in the spec) |
| WP-15 | Ineffective indicators (the page says these do not identify AI text) | perfect grammar, formal prose, bland prose, `Additionally,` and `Notably,` in isolation, unsourced text | S5 Ineffective indicators | n/a | S5 | none |
| AW-01 | Tier 1A AI frequency markers | `delve`, `tapestry`, `landscape` (as metaphor) | S6 references/patterns.md | T2 | S6 | Vocabulary with measured excess |
| AW-02 | Tier 1B clarity edits (S6 says these are not evidence of authorship) | `in order to`, `utilize`, `commence`, `ascertain`, `endeavor` | S6 references/patterns.md | n/a | S6 | none |
| AW-03 | Tier 2 cluster words; Tier 3 density words; Tier 3 phrases | `harness`, `foster`, `crucial`, `multifaceted`, `significant`, `unprecedented`, `the intersection of` | S6 references/patterns.md | T2 | S6 | Vocabulary with measured excess (density mode) |
| AW-04 | Em dashes | `--` and the em dash; target zero | S6 references/patterns.md | T2 | S6 | Em dash |
| AW-05 | "It's not X, it's Y", including the split-sentence form | `The headline isn't the speed. The real story is Y.` | S6 references/patterns.md | T2 | S6 | Binary contrast |
| AW-06 | Hollow intensifiers; Hedging; Hedge-stacked predictions | `genuinely`, `truly`, `it's worth noting that`, `could potentially` | S6 references/patterns.md | T2 | S6 | Throat-clearing and signposting |
| AW-07 | Compulsive rule of three; Colon into a triple | `separate ports, processes, and local state.` | S6 references/patterns.md | T2 | S6 | Colon reveal (partial) |
| AW-08 | Significance inflation; Novelty inflation; Aphorism formulas | `a pivotal moment in the evolution of...`, `a concept nobody's naming`, `X is the language of Y` | S6 references/patterns.md | T2 | S6 | Importance puffery |
| AW-09 | Copula avoidance | `serves as`, `features`, `boasts` | S6 references/patterns.md | T2 | S6 | Fake-strong verbs |
| AW-10 | Vague attributions | `Experts believe`, `Studies show`, `Research suggests` | S6 references/patterns.md | T2 | S6 | Weasel attribution |
| AW-11 | Superficial -ing analyses | -ing phrase added to a plain fact | S6 references/patterns.md | T2 | S6 | Trailing participial benefit clause |
| AW-12 | Transition phrases | `Moreover`, `Furthermore`, `Additionally` | S6 references/patterns.md | T2 | S6 | none |
| AW-13 | Synonym cycling | `developers... engineers... practitioners... builders` | S6 references/patterns.md | T2 | S6 | none (model check in the spec) |
| AW-14 | Chatbot artifacts; "Let's" constructions; Cutoff disclaimers; Unfilled placeholders | `I hope this helps!`, `Let's dive in!`, `As of my last update` | S6 references/patterns.md | T2 | S6 | Assistant residue |
| AW-15 | Rhetorical question openers; Stacked rhetorical questions | `So why should you care?`, `Where it breaks? Which corners it cut?` | S6 references/patterns.md | T2 | S6 | Rhetorical question answered at once |
| AW-16 | Same-opener sentence runs | `Maybe nobody needed it. Maybe it solved the wrong problem.` | S6 references/patterns.md | T2 | S6 | Repeated sentence openers |
| AW-17 | Manufactured punchlines and staccato drama; Stranded auxiliary contrast | `The tool died; the data didn't.` | S6 references/patterns.md | T2 | S6 | Staccato run |
| AW-18 | Rhythm and uniformity; Vocabulary diversity (stylometric) | uniform sentence and paragraph length, type-token ratio | S6 references/patterns.md | T2 | S6 | none |
| AW-19 | Generic conclusions; Generic future-narrative closers | `The future looks bright`, `may become one of the most important narratives` | S6 references/patterns.md | T2 | S6 | none |
| SG-01 | Repetitive phrasing or over-explanation | `It is important to note that...` | S7 | T2 | S7 | Throat-clearing and signposting |
| SG-02 | Generic or vague language | `This is an important area of research`, `More research is needed`, `Studies have shown...` | S7 | T2 | S7 | Weasel attribution |
| SG-03 | Flawless but empty prose; Lack of authorial voice or critical analysis | no phrase given | S7 | T2 | S7 | none |
| SG-04 | Contradictions within the text; Misuse of technical terms | no phrase given | S7 | T2 | S7 | none |
| SG-05 | Overly uniform structure | every paragraph starts the same way | S7 | T2 | S7 | Repeated sentence openers (paragraph level) |
| SG-06 | Citation red flags (non-existent references, wrong DOIs or journal titles) | phantom references | S7 | T2 | S7 | none |
| SG-07 | Visual or data red flags (smooth trends, vague captions) | no phrase given | S7 | T2 | S7 | none |
| SG-08 | Unusual formatting or meta red flags (repetitive headers, placeholder text, keyword overuse) | `Insert Table 1 here` | S7 | T2 | S7 | Assistant residue |
| CA-01 | Uniform sentence rhythm | no phrase given | S8 | T2 | S8 | none |
| CA-02 | Generic hedging and false balance | `on the one hand... on the other hand`, `it is important to note that`, `in conclusion, it is clear that` | S8 | T2 | S8 | Throat-clearing and signposting; Recap openers |
| CA-03 | Confident but shallow claims; Inconsistent voice across sections | missing dataset names, sample sizes, instrument settings | S8 | T2 | S8 | none |
| CA-04 | Overuse of certain transitional and evaluative words | `delve`, `boast`, `underscore`, `tapestry`, `furthermore` | S8 | T2 | S8 | Vocabulary with measured excess |
| CA-05 | Fabricated citations | plausible references to papers that do not exist | S8 | T2 | S8 | none |

S6 names 74 categories in its README. The file references/patterns.md has 74 headings of that kind. The rows above cover 24 of those headings, four rules that sit as bullets (em dashes, hollow intensifiers, hedging, rule of three) and the word tiers. The rest are formatting, social-post, launch-copy and tool-fingerprint categories. Two of them, Sycophantic tone and Speculative gap-filling, sit close to the family Assistant residue. I gave them no row. S4 names no LLM-tell category. KD-01 is the only S4 item that links a style rule to AI text.

## 2. Scoring rubrics and thresholds

None of the sources validates its pattern list on a corpus. S6 measures its own composite score, and I report that below.

- S1 scores five dimensions from 1 to 10: Directness, Rhythm, Trust, Authenticity, Density. A total below 35 of 50 means revise. The source gives no method for the numbers and no test data.
- S2 and S3 give no score. S2 orders its 26 patterns by strength and frequency. Patterns 1 to 5 justify an edit on one sighting. Patterns 8, 9, 10, 11 and 21 are "weak alone" and count only when other tells share the passage. Pattern 25 is weak alone in part. S2 states no numeric threshold.
- S4 has no style score. Its two lint scripts return issue codes and line numbers.
- S5 gives no score and no threshold. It calls the em dash "most useful when taken in combination with other indicators". It cites studies on the accuracy of humans and of detectors. Those numbers are UNVERIFIED here.
- S6 sets vocabulary thresholds. Tier 2 words count when two or more share a paragraph. A Tier 3 word counts at `max(3, floor(0.03 x words))` uses of one form. A Tier 3 phrase counts at two uses, or three distinct phrases in one piece. S6 sets a target of zero em dashes and a hard maximum of one per 1,000 words, at severity P2. A type-token ratio under 0.40 on text over 200 words deserves a second look. Severity tiers P0, P1 and P2 order the findings.
- The S6 detector gives a score from 0 to 100. Weights per category include tier1 5, tier2 3, tier3 2, chatbot 8, sycophantic 8 and significance-inflation 4. The raw score is divided by `max(1, log2(words / 50))`. Labels: 0 Clean, up to 15 Minimal, 35 Some, 60 Moderate, 80 Strong, above 80 Heavy.
- S6 reports a measurement (corpus/README.md, version 3.22.0, 2026-07-31). It scored 875 human paragraphs and 779 machine paragraphs. The machine text comes from the HC3 and RAID datasets. At score 5 or more, the false positive rate was 4.2% (95% CI 3.1 to 5.8). The true positive rate was 7.2% (5.6 to 9.2). The ROC-AUC was 0.501 per paragraph and 0.623 per document.
- S6 also lists the share of documents in which each category fired, human against machine. Uniformity: 2.1% against 25.1%. Filler: 2.4% against 8.3%. Tier 1 vocabulary: 8.0% against 7.4%. Em dash: 9.9% against 1.9%.
- The S6 maintainer writes that this run fails his own publication gate on register. HC3 is ChatGPT text from December 2022. RAID is 2024 text. Neither is manuscript text. I read the tables and did not rerun them. I assign no tier to this measurement. The parent note decides.
- S7 gives no score. It says no single red flag "can definitively indicate AI-use".
- S8 gives no score. It says no method is reliable alone. It explains perplexity and burstiness without numbers.

## 3. Handling of voice and of scientific text

- S1 has no step for the author's voice. It imposes one voice: direct, active, second person. Rule 5 says `"You" beats "People."` It bans passive voice, all adverbs, all em dashes and three-item lists without exception. It says nothing about scientific text. Passive Methods sentences, `significantly` and `approximately` would all fail its rules.
- S2 (version 3.1.0) matches a writing sample. The sample overrides the patterns, including the dash rule. Without a sample, S2 takes the voice from the kind of text. Personal writing keeps the writer's opinions and asides. Reference and technical text stays "neutral and plain".
- S2 forbids a new fact, name, number, date, quote or citation that the source lacks. In file mode it edits prose only and keeps code, commands, paths, YAML metadata, data and link targets. It leaves a watched phrase alone inside a quotation, a title or a proper name. It has no rule for LaTeX or for scientific text.
- S2 states that text written before 30 November 2022 is not AI-written. It also states that "People who judge by feel do little better than chance".
- S3 (version 2.3.0) has a section named "PERSONALITY AND SOUL". It tells the editor to have opinions, to use "I", and to "Let some mess in". It treats text that "Reads like a Wikipedia article or press release" as soulless. This advice does not fit a manuscript. S3 lacks the S2 rule that technical text stays neutral.
- S3 pattern 25 tells the editor to drop the hyphen in `high-quality` and `cross-functional` before a noun. The S2 changelog for 3.1.0 says S2 narrowed this rule so that words the dictionary hyphenates keep the hyphen.
- S4 has no check for style, tone or AI text. I searched all 26 skill folders and the Python package. Two lint scripts exist. `lint_manuscript.py` flags placeholders, restricted content, overstatement words and causal words in observational designs. `lint_review.py` checks the tone, channel separation and actionability of a peer review.
- The S4 files CLAUDE.md and AGENTS.md tell the drafter to avoid bullets and to write continuous prose. The S4 file writing_principles.md says the opposite: "there is no universal rule that every scientific section must be continuous prose". The same file says "Do not improve prose by changing scientific meaning".
- S4 handles voice only in venue files. The Cell Press file accepts "we" and encourages active voice. The pptx skill calls accent lines under titles "a hallmark of AI-generated slides". That rule covers slides, not prose.
- S5 describes Wikipedia text. It says some signs "may not apply in a non-Wikipedia context". A footnote says the guide is "less useful for texts which are not informational writing". It does not address manuscripts.
- S5 lists habits of human writers. The plugin should not flag them. They are simple is/has phrases, qualifiers such as `very`, `perhaps` and `tends to`, superlative claims, and plain words such as `used` in place of `utilized`. It also says perfect grammar and formal prose are not signs of AI. One section suggests comparing an author's new text with the author's older text.
- S6 has the most developed handling. A writing sample sets the voice. S6 reads sentence length, contraction rate, paragraph openings and recurring word choices. It does not "upgrade" the writer's vocabulary.
- S6 has a "Never inject" list of seven additions. They are invented speaker perspective, manufactured stakes, forced contrarianism, performed candor, em dash theatrics, staccato conversion and invented specifics. S6 protects quotations, code, tables, URLs and identifiers. It returns the text unchanged when no justified finding remains.
- S6 has context profiles with relaxed hedging and word rules for `technical-blog` and `docs`. It has no manuscript profile. Its catalog keeps some scientific wording. `The robust estimator tolerates outliers.` stays clean. `a key stage in the evolution of the vertebrate eye` stays clean. A conflict-of-interest disclosure is not "narrated candor".
- S6 says over-polishing can push human text toward AI statistical profiles. It says curly quotes, clean typography and em dashes do not show authorship.
- S7 targets reviewers of manuscripts. It says "poor grammar or writing does not necessarily point to the use of AI". It lists "lack of authorial voice or critical analysis" as a flag and gives no test. Its flags on citations, data and captions have no counterpart in a style linter.
- S8 targets editors and integrity offices. It says every style tell occurs "in ordinary human writing too". It warns that detector signals also flag non-native English writers and "narrow technical registers". It advises a comparison with a known writing sample of the same author. It gives no method for that comparison.

## 4. What these sources do not show

- No measurement in the pattern lists. S1, S2, S3, S4, S7 and S8 report no count of a pattern in human text or in LLM text. S5 cites studies for its vocabulary list and for a drop in `is` and `are` in academic writing. The studies are Kobak 2025, Juzek and Ward 2025, Geng and Trotta 2024 and Reinhart 2025. I did not open them. Their results are UNVERIFIED here. Other notes cover the corpus studies.
- S6 reports its own measurement (section 2). In it, Tier 1 vocabulary fires on 8.0% of human documents and 7.4% of machine documents. The em dash fires on 9.9% and 1.9%. The data are ChatGPT text from December 2022 and 2024 text. They are not manuscripts. I ran no S6 measurement script. I ran only its count check, which printed 74 categories and 112 word entries.
- The "16 out of 16" in the S2 README comes from a third-party issue (S9). The judges were language models of one family. The count is 16 pairs. The author ran 77 of 144 planned trials. The test measures preference for quality, not pattern validity. The same issue reports 98.6% detection after the rewrite pass. It also reports that judge-cited vocabulary tells fell from 70 to 0 and rhythm tells rose from 60 to 101. I did not open the study repository. These numbers are UNVERIFIED.
- No source tests manuscripts. S7 and S8 target academic text and give no data on their tells. No source tests LaTeX or Markdown input.
- Overlap and copying. S2 states that its list comes from S5. S3 is a fork of S2 frozen at version 2.3.0. S6 credits S5, S2, brandonwise/humanizer, Pangram Labs and the OpenClaw skill community, and adapts items from other skills. S6 also says its claim for Tier 1A "is inherited, not measured here". It traces the claim to a repository that states a 5 to 20 times ratio without a method. S1 has no credit lines. Its families match S2 and S6, but I found no stated source. Treat S2, S3, S5 and S6 as one lineage, not four confirmations.
- Disagreements. Em dash: S1 removes every one. S2 calls it weak alone and defers to the writer's sample. S5 lists it as historical. S5 cites a July 2026 study, reported by The Economist and not opened, that found only Claude using more than professional writers. S6 rates it P2 and measures an inverted signal. None of the four supports tier T1 for the em dash.
- Elegant variation: S5 lists it as historical. S2 dropped it in version 3.0.0 as "human habits or historical". S3 and S6 keep it. Transitions: S5 says `Additionally,` and `Notably,` are "not a strong tell" in isolation. S6 rates them P2. Recap openers: S5 lists `In summary`, `In conclusion` and `Overall` as historical. Hedges: S1 bans them all. S2, S5 and S6 keep ordinary hedges and real uncertainty.
- Age. Word lists change with each model release. S5 says `delve` fell sharply in 2025. Its 2026 vocabulary row cites a single web page that I did not open.
- Differences from spec section 3. For S1 I counted 76 phrase entries in 8 sections and 48 structure rows in 11 sections. Its README names 6 phrase categories. The 5-part score matches. S2 has 26 patterns in 6 sections at version 3.1.0, not 24 to 29. S4 has no style check, as the spec says. S4 has two lint scripts for other checks. Its MIT license does not cover four vendored folders (section 6).
- Not read, or not read in full. S5: the sections on markup, citations, comments, edit summaries and biases, and the historical entries on knowledge cutoffs, prompt refusal and abrupt cut-offs. S6: SKILL.full.md, evals/, examples/ and most of the detector code. I read about 25 of its 74 category sections. S2: scripts/validate-package.py.
- Named inside S6 and not opened: brandonwise/humanizer, isatimur/de-slop, welttowelt/stop-slop-refined, Aboudjem/humanizer-skill, devswha/patina, tropes.fyi, Simon Willison's LLM cliche highlighter. Also UNVERIFIED are the detector audits that S6 cites (Liang 2023, Jabarian and Imas 2025, arXiv:2506.07001). The studies that S8 cites are UNVERIFIED too (Walters and Wilder 2023, a 2026 Retraction Watch analysis).
- Search listings of S6 gave 21, 36, 43, 53 and 109 as category or entry counts. The repository states 74 categories and 112 word entries. I used the repository and did not use the listings as evidence. I skipped sources that sell a detector.

## 5. Pages opened

- S1 https://github.com/hardikpandya/stop-slop (commit 8da1f03, 2026-03-18; read README.md, SKILL.md, CHANGELOG.md, LICENSE and the three files of references/ in full)
- S2 https://github.com/blader/humanizer (commit 8c307f3, 2026-10-16, version 3.1.0; read README.md, SKILL.md, CHANGELOG.md, AGENTS.md and LICENSE in full)
- S3 https://github.com/c-b-g-m/blader-humanizer (commit 12881ab, 2026-03-19; a fork of S2 at version 2.3.0). I read README.md and LICENSE. I read the head of WARP.md. In SKILL.md I read the head, the voice section, patterns 7, 11 to 13 and 22 to 25, and the process. I skimmed the other pattern titles.
- S4 https://github.com/K-Dense-AI/claude-scientific-writer (commit 529b9f7, 2026-09-29, plugin version 2.22.0). I read LICENSE, plugin.json and the Narrative Writing Standards of CLAUDE.md. I read scripts/lint_manuscript.py, references/writing_principles.md and references/authorship_ai_confidentiality.md. I read the head of lint_review.py and parts of three venue style files. I searched the whole repository for AI-text and style terms.
- S5 https://en.wikipedia.org/wiki/Wikipedia:Signs_of_AI_writing (revision 1381583419, 2026-10-23; raw wikitext). I read the caveats and the section introductions and word boxes of Content, Language and grammar, and Communication. I read the human-signs and ineffective sections. I read the historical sections in part.
- S6 https://github.com/conorbronsdon/avoid-ai-writing (commit 209815c, 2026-10-19, version 3.38.0; read SKILL.md, the Credits of README.md, references/patterns.md in part, PROOF.md, corpus/README.md, and the label bands and weights in detector/patterns.js)
- S7 https://www.sagepub.com/explore-our-content/blogs/posts/sage-perspectives/2025/06/11/ai-detection-for-peer-reviewers-look-out-for-red-flags (published 2025-06-11, by Alex Moersen; read in full as text)
- S8 https://www.casrai.org/guides/how-to-detect-ai-generated-text-in-academic-writing (page dated 2026-08-24, by the CASRAI Editorial Board; read in full as text; the page has no named author and cites no source for its style tells)
- S9 https://github.com/blader/humanizer/issues/229 (opened 2026-08-19, closed; read through the GitHub API)

## 6. Licenses

- S1: MIT, Copyright (c) 2025 Hardik Pandya. The plugin may copy with the notice kept. The spec still limits copying to names and short examples.
- S2: MIT, Copyright (c) 2025 Siqi Chen. Same rule as S1.
- S3: MIT, Copyright (c) 2025 Siqi Chen. The file is identical to the S2 LICENSE. Same rule as S1.
- S4: MIT, Copyright (c) 2025-2026 K-Dense Inc. Four vendored folders (docx, pdf, pptx, xlsx) carry their own LICENSE.txt. The docx file reads "© 2025 Anthropic, PBC. All rights reserved." I did not read the other three. The plugin must copy nothing from those folders.
- S5: no license file, because the source is a wiki page. The wiki states CC BY-SA 4.0 for its text (MediaWiki API, rightsinfo). Copy names and short quotes only. A longer copy would bring the share-alike term into the plugin.
- S6: MIT, Copyright (c) 2026 Conor Bronsdon (NOTICE.md adds a note on a packaging contribution under the same license). Same rule as S1. The corpus code uses HC3 (CC-BY-SA-4.0) and RAID (MIT) and commits only hashes.
- S7: no license file. I saw no license text in the page text. Copy names only, with quotes of about ten words at most.
- S8: no license file. The page footer states "CC-BY 4.0 Open content licence". I did not open the licence page, so the scope is UNVERIFIED. Copy names only until a person checks it.
- S9: no license file. It is an issue comment by a third party. Cite it. Copy nothing.
