# The author's own pattern lists

Method. I read eleven local files, listed in section 4 as S1 to S11. The files are the author's ban list and the `no-ai-slop` skill with its checklist, agent file and install record. They also include the term file and script of `overleaf-manuscript`, the style rules of two author skills and the design spec. I read no web page and no corpus note. Tier T3 means the author's own preference with no measurement behind it. For S2 to S5 the install record names another owner (section 5), so T3 there records only that the author chose to install the skill. I copied no manuscript text, no result, no number and no project name beyond the skill names.

## 1. Patterns and words (table)

Conventions for the table:
- ID prefixes: W word, F figurative word, C construction or phrase, R sentence-level rhythm, H hedge or intensifier. E em dash, S spelling, P paragraph opener, L LaTeX hygiene, D decoration or evidence, M model check with no regex.
- The source cell gives the key, the section of the file and `l` plus the line number.
- In a regex cell, `\|` stands for the alternation bar. Replace it with `|` before use. A raw bar would split the table cell.
- Matching is case-insensitive unless the cell says case-sensitive. `^` marks a sentence start and `\A` a paragraph start, both after masking. `unless:` gives a second regex that the sentence must not match.
- Tier `T3*` means the spec lists the family at T1 or T2 (S11 l109 to l121). A corpus note or a guide may also back the row. The merge step adds "also in the corpus note" after it checks.
- Family `Vocabulary (check)` means: use the family "Vocabulary with measured excess" only if the corpus note lists the word. Otherwise use family none and keep T3.

| ID | Pattern, word or construction | Regex-ready form | Source key and where in the file | Tier | Plugin family | Science exception |
|---|---|---|---|---|---|---|
| W01 | `delve` | `\bdelv\w*` | S1 C1 l130; S2 l46; S6 l8; S9 l88 | T3* | Vocabulary with measured excess | none |
| W02 | `intricate`, `intricacy` | `\bintricat\w*\|\bintricac\w*` | S1 C1 l134; S2 l46; S6 l5; S9 l88 | T3* | Vocabulary with measured excess | none |
| W03 | `showcase` (S9 limits the ban to the verb) | `\bshowcas\w*` | S1 C1 l134; S6 l6; S9 l88 | T3* | Vocabulary with measured excess | none; the noun is rare in science |
| W04 | `pivotal` | `\bpivotal` | S1 C1 l132; S6 l7; S9 l88 | T3 | Vocabulary (check) | `pivotal trial`, `pivotal study` (regulatory terms) |
| W05 | `crucial` | `\bcrucial` | S1 C1 l132 and fast scan l194; S6 l23; S9 l90 | T3 | Vocabulary (check) | none |
| W06 | `vital` | `\bvital\b` | S1 C1 l132; S6 l24; S9 l90 | T3 | Vocabulary (check) | `vital signs`, `vital dye`, `vital staining`, `vital rates`, `vital capacity` |
| W07 | `realm` | `\brealm` | S1 C1 l131; S2 l46; S6 l4; S9 l88 | T3 | Vocabulary (check) | `realm` as a virus taxonomy rank, near `virus`, `viral`, `ICTV` |
| W08 | `leverage` as a verb | `\bleverag\w*` | S1 C1 l130 and fast scan l194; S2 l46; S6 l9; S9 l88 | T3 | Vocabulary (check) | `high-leverage point`, `leverage score` (statistics); `mechanical leverage` |
| W09 | `harness` as a verb | `\bharness(?:ed\|ing)\b\|\b(?:to\|we\|can\|could\|will\|would\|may\|might\|must\|should\|it\|they\|and\|or\|that\|which)\s+harness(?:es)?\b` (S6 verbatim) | S1 C1 l131; S2 l46; S6 l10; S9 l88 | T3 | Vocabulary (check) | The noun (`test harness`, `animal harness`, a defined framework term, S9 l100). S6 misses the verb after an adverb |
| W10 | `facilitate` | `\bfacilitat\w*` | S2 l46; S6 l11; S9 l89 | T3 | Vocabulary (check) | `facilitated diffusion`, `facilitated transport`, `synaptic facilitation`, `paired-pulse facilitation` |
| W11 | `foster` | `\bfoster\w*` | S2 l46; S6 l12; S9 l89 | T3 | Vocabulary (check) | `cross-foster`, `foster dam`, `foster mother` (rodent husbandry) |
| W12 | `underscore` | `\bunderscor\w*` | S6 l13; S9 l89 | T3 | Vocabulary (check) | The character: sentence also holds `character`, `filename`, `identifier` or `snake_case` |
| W13 | `embark` | `\bembark\w*` (S6 uses `\bembark\w* on\b`) | S2 l46; S6 l14; S9 l89 | T3 | Vocabulary (check) | none |
| W14 | `navigate` as a figure | `\bnavigat\w*` | S1 C1 l131; S6 l15; S9 l89 | T3 | Vocabulary (check) | `spatial navigation`, `animal navigation`, a maze, arena or gradient; `navigation menu` |
| W15 | `unlock` | `\bunlock\w*` | S1 C1 l130; S6 l16; S9 l89 | T3 | Vocabulary (check) | `unlocked nucleic acid`; `locked` and `unlocked` conformations |
| W16 | `comprehensive` | `\bcomprehensive` | S1 C1 l132 and fast scan l194; S6 l17; S9 l90 | T3 | Vocabulary (check) | Names: `comprehensive two-dimensional gas chromatography`, `Comprehensive Antibiotic Resistance Database`, `Comprehensive R Archive Network` |
| W17 | `robust` | `\brobust` | S1 C1 l130 and fast scan l194; S2 l46; S6 l18; S9 l90 | T3 | Vocabulary (check) | `robust regression`, `robust statistics`, `robust standard errors`, `robust to` a named perturbation; `robustness` of a biological network. The stem also matches `robustness` and `robustly` |
| W18 | `seamless`, `seamlessly` | `\bseamless\w*` | S1 C1 l130 and fast scan l194; S6 l19; S9 l90 | T3 | Vocabulary (check) | `seamless cloning`, `seamless assembly`, `seamless ligation`, `seamless genome editing` |
| W19 | `multifaceted`, `holistic`, `nuanced`, `nuance` | `\bmultifaceted\|\bholistic\|\bnuanc\w*` | S1 C1 l130, l134; S2 l46; S6 l20 to l22; S9 l90 | T3 | Vocabulary (check) | none |
| W20 | `paradigm`, `paradigm shift` | `\bparadigm` | S1 C1 l133; S2 l46; S6 l25; S9 l91 | T3 | Vocabulary (check) | `experimental paradigm`, `behavioral paradigm`, `training paradigm`, `conditioning paradigm`, `task paradigm` |
| W21 | `tapestry` | `\btapestr\w*` | S1 C1 l132; S2 l46; S6 l26; S9 l91 | T3 | Figurative load words | `Tapestri` (a single-cell DNA platform name) |
| W22 | `landscape` as a figure | `\blandscape\b` | S1 C1 l131 and B1 l96; S6 l27; S9 l91 | T3 | Figurative load words | `fitness landscape`, `energy landscape`, `adaptive landscape`, `epigenetic landscape`; near ecological or genomic context words (S11 l125); page orientation |
| W23 | `unprecedented`, `transformative`, `revolutionize` | `\bunprecedented\|\btransformative\|\brevolutioni[sz]\w*` | S2 l46 (`transformative`); S6 l28 to l30; S9 l91 | T3 | Vocabulary (check) | A funder program title in a funding statement (`Transformative Research Award`) |
| W24 | `cutting-edge` | `\bcutting[- ]edge` | S1 C1 l132; S2 l46; S6 l31; S9 l92 | T3 | Vocabulary (check) | none |
| W25 | `state-of-the-art` | `\bstate[- ]of[- ]the[- ]art` | S1 C1 l133; S6 l32; S9 l92 | T3 | Vocabulary (check) | A comparison to named, cited prior methods in the same sentence; the label `SOTA` |
| W26 | `utilize` | `\butili[sz]\w*` | S1 C1 l130; S2 l46 | T3 | Vocabulary (check) | `utilization` as a measured quantity (`glucose utilization`, `oxygen utilization`, `CPU utilization`). S6 l43 flags `utilise` as spelling; the author bans both forms |
| W27 | `elevate` as a verb | `\belevat(?:e\|es\|ing)\b` | S1 C1 l130; S2 l46 | T3 | Vocabulary (check) | `elevated` before a measured level (`elevated expression`); `elevated plus maze`; `elevation` |
| W28 | `empower` | `\bempower\w*` | S1 C1 l131; S2 l46 | T3 | Vocabulary (check) | The software name `Empower` (chromatography data software) |
| W29 | `journey`, `testament`, `plethora`, `meticulous`, `boasts`, `paramount`, `ever-evolving` | `\bjourney\w*\|\btestament\b\|\bplethora\b\|\bmeticulous\w*\|\bboasts\b\|\bparamount\b\|\bever-evolving\b` | S1 C1 l131, l132, l134; S2 l46 (`meticulous`, `paramount`, `ever-evolving`) | T3 | Vocabulary (check) | none |
| W30 | `myriad` | `\bmyriad\b` | S1 C1 l134 | T3 | Vocabulary (check) | `Myriad Genetics` (a company name) |
| W31 | `synergy` | `\bsynerg(?:y\|ies)\b` | S1 C1 l133 | T3 | Vocabulary (check) | `drug synergy` defined by a model (`Bliss`, `Loewe`, `HSA`, `ZIP`); a `synergy score` |
| W32 | `streamline` | `\bstreamlin\w*` | S1 C1 l134; S2 l46 | T3 | Vocabulary (check) | Fluid flow: `streamlines` of a flow field; `streamlined body` |
| W33 | `ecosystem` outside biology | `\becosystem\w*` | S1 C1 l133 | T3 | Vocabulary (check) | Biology: `microbial ecosystem`, `gut ecosystem`, `marine ecosystem`; skip near ecological context words (S11 l125) |
| W34 | `beacon` | `\bbeacon\w*` | S2 l46 | T3 | Vocabulary (check) | `molecular beacon`; `GA4GH Beacon` (a genomic data discovery protocol) |
| W35 | `supercharge` | `\bsupercharg\w*` | S2 l46 | T3 | Vocabulary (check) | `supercharged protein`, `supercharged GFP`, `supercharging reagent` (mass spectrometry) |
| W36 | `game-changer`, `this is huge`, `this changes everything` | `\bgame[- ]chang\w*\|\bthis is huge\b\|\bthis changes everything\b` | S1 C1 l133; S2 l46 | T3 | none | none |
| F01 | `load-bearing` | `\bload[- ]bearing\b` | S11 l11 and l110 (the author named it; no local list holds it) | T3 | Figurative load words | `load-bearing` bone, cartilage, joint or structure (biomechanics, engineering) |
| F02 | `cornerstone` | `\bcornerstone\w*` | S11 l110 (no local list holds it) | T3 | Figurative load words | none |
| F03 | `backbone` | `\bbackbone\w*` | S11 l110 (no local list holds it) | T3 | Figurative load words | `peptide backbone`, `protein backbone`, `carbon backbone`, `sugar-phosphate backbone`; the `backbone` of a neural network |
| C01 | `is not X, it is Y` and `was not X. It was Y.` | `\b(?:is\|was\|are\|were\|do\|does\|did)(?: not\|n['’]t)\b[^.;?!]{1,100}[,;.]\s+(?:it\|this\|that\|they)(?:['’]s\|['’]re\| is\| was\| are\| were)\b` | S1 A2 l24 to l25; S2 l54 | T3 | Binary contrast | The sentence rules out a tested alternative; skip when it holds `p =`, `n =`, a figure reference or a citation |
| C02 | `not just X but Y` | `\bnot just\b[^.;]{0,160}?\bbut\b` | S1 A2 l26 and fast scan l190; S2 l54 | T3 | Binary contrast | none |
| C03 | `not only X but also Y` | `\bnot only\b[^.;]{0,160}?\bbut also\b` (S6 verbatim) | S6 l35; S9 l95 | T3 | Binary contrast | none |
| C04 | `less about X, more about Y`; `less a X, more a Y` | `\bless (?:about\|an?)\b[^.;]{1,60}[,;]\s*more (?:about\|an?)\b` | S1 A2 l27, A3 l36 | T3 | Binary contrast | none |
| C05 | `a X, not a Y` (matched pair of nouns) | `\b(?:an?\|the)\s+\w+(?:\s+\w+)?,\s+not\s+(?:an?\|the)\s+\w+` | S1 A3 l34 to l35 | T3 | Binary contrast | Both nouns name literal scientific entities (`a missense variant, not a deletion`); the detector flags and the model decides |
| C06 | `Not a X. Not a Y. A Z.` | `(?:^\|[.!?]\s+)Not an? [^.!?]{1,40}[.!?]\s+Not an? [^.!?]{1,40}[.!?]` (case-sensitive) | S2 l74 | T3 | Binary contrast | none |
| C07 | Fast-scan strings: `isn't a`, `it's not`, `rather than a`, `that's the`, `this is what`, `and that`, `which is` | none (screening only; too broad to flag) | S1 fast scan l190 to l191 | T3 | none | Ordinary grammar: `which is`, `and that`, and `rather than a` in a comparison. The author calls them "probable hit" strings |
| C08 | Backward reference | `\b(?:that(?:['’]s)?\|this)(?: is)? (?:the key insight\|what makes (?:it\|this\|that) work)\b\|\band that matters\b\|\bwhich is exactly the problem\b\|\btherein lies\b` | S1 A4 l43 to l44 | T3 | none | none |
| C09 | `it is worth noting that`, `it is important to note` | `\bit(?:['’]s\| is) (?:worth noting\|important to (?:note\|understand))\b` | S1 B1 l95 to l96 and fast scan l192; S2 l50; S6 l36; S9 l95 | T3* | Throat-clearing and signposting | none |
| C10 | Sentence-initial `Interestingly`, `Importantly`, `Notably`, `Essentially`, `Fundamentally`, `Crucially`, `Simply put` | `(?:^\|[.!?]\s+)(?:Interestingly\|Importantly\|Notably\|Essentially\|Fundamentally\|Crucially\|Simply put)\b` (case-sensitive) | S1 B1 l97; S2 l48 | T3* | Throat-clearing and signposting | none; the spec sets density mode (S11 l116) |
| C11 | Stock openers | `\bat its core\b\|\bat the end of the day\b\|\bin today['’]s (?:world\|landscape)\b\|\bin the (?:age\|world) of\b\|\bas we all know\b\|\bthe (?:reality\|truth) is\b\|\bgoing forward\b\|\bwhen it comes to\b\|\bin this article\b` | S1 B1 l96 and fast scan l192; S2 l50 | T3* | Throat-clearing and signposting | `this Article` with a capital A in Nature-family text |
| C12 | Wordy phrases: `in terms of`, `with regard to`, `in order to` | `\bin terms of\b\|\bwith regard to\b\|\bin order to\b` | S2 l50 | T3 | none | `in terms of` with a defined unit or model (`expressed in terms of free energy`); `in order not to` |
| C13 | Chatty openers | `\bhere['’]s (?:the thing\|what i mean\|what nobody tells you)\b\|\blet me be clear\b\|\bi['’]ll be honest\b\|\bthe uncomfortable truth is\b\|\blet['’]s (?:dive\|get started)\b\|\bdive (?:in\|into)\b` | S1 B1 l96 and fast scan l192; S2 l56 | T3* | Throat-clearing and signposting | none for these phrases. The bare fast-scan string `dive` hits diving studies (`dive depth`, `dive duration`); do not use it |
| C14 | Faux-insight setups | `\bthe part (?:most people\|everyone) (?:skip\|skips\|misses)\b\|\bwhat (?:most people\|everyone) (?:get\|gets) wrong\b\|\bwhat nobody tells you\b` | S2 l58 | T3 | none | none |
| C15 | Interpretive metadiscourse | `\bthe key point is\b\|\bas you can see\b\|\bthis distinction matters\b\|\bthat last part matters\b\|\bin other words\b` | S2 l66 | T3 | none | `in other words` that restates a definition once |
| C16 | Recap openers | `(?:^\|[.!?]\s+)(?:In conclusion\|Ultimately\|Overall\|Taken together),` (case-sensitive) | S2 l84; S11 l117 (`Taken together`) | T3* | Recap openers | The first sentence of a Conclusions section. `Overall survival` has no comma and does not match. `Taken together` is density only (S11 l125) |
| C17 | Importance puffery phrases | `\b(?:stands?\|stood) as (?:an?\|the) testament\b\|\bmarks? a (?:pivotal\|turning\|watershed) (?:moment\|point)\b\|\bplays? an? (?:vital\|pivotal\|crucial) role\b\|\bsolidif(?:y\|ies\|ied\|ying) (?:its\|their) (?:position\|place)\b\|\bunderscor\w+ (?:its\|their\|the) (?:significance\|importance)\b` | S2 l64; S11 l112 | T3* | Importance puffery | A measured or cited role in the same sentence |
| C18 | `plays a key role in` | `\bplays? a key role in\b` (S6 verbatim) | S6 l37; S9 l96 | T3* | Importance puffery | A measured or cited role in the same sentence |
| C19 | Trailing participial benefit clause | `,\s+(?:making\|ensuring\|allowing\|enabling\|highlighting\|underscoring\|reflecting\|showcasing)\b` | S1 A6 l58 and fast scan l193; S2 l62 | T3* | Trailing participial benefit clause | Methods text that names the step that gives the property (`ensuring equal loading by a protein assay`); report as `info` there |
| C20 | Weasel attribution | `\b(?:experts\|researchers\|scientists\|studies\|reports\|critics)(?: have)?\s+(?:agree\|argu\|say\|suggest\|show\|believ\|claim)\w*\b\|\bmany (?:argue\|say\|believe)\b\|\bwidely (?:regarded\|considered)\b` | S2 l68 | T3* | Weasel attribution | A citation in the same sentence (S11 l96 masks citations) |
| C21 | Fake-strong verb | `\b(?:serves?\|served\|serving\|acts?\|acted\|acting) as an?\b` | S2 l70; S11 l115 | T3* | Fake-strong verbs | A role in biology or Methods (`served as a loading control`, `acts as a repressor`, `serves as a template`) |
| C22 | Colon reveal | `(?:^\|[.!?]\s+)The (?:[a-z-]+ ){0,6}[a-z-]+: [a-z]` (case-sensitive) | S2 l60; S11 l119 | T3 | Colon reveal | A definition list or a structured-abstract label |
| C23 | Capital letter after a colon | `:\s+[A-Z][a-z]+\b` (case-sensitive) | S2 l60; S3 l34 | T3 | none | Proper nouns, titles, code, structured-abstract labels. Weak rule: keep it off by default (decision for the plan) |
| C24 | Meta-narration | `\blet me (?:analy[sz]e\|break\|walk\|explain\|start)\b\|\bi will now proceed\b\|\bi have completed (?:the\|this)\b` | S1 B2 l104 | T3* | Assistant residue | none |
| C25 | Sycophancy | `\bgreat question\b\|\byou(?:['’]re\| are) absolutely right\b\|\bexcellent catch\b\|\bi love this idea\b` | S1 B3 l109 and fast scan l196 | T3* | Assistant residue | A reviewer-response letter that thanks the reviewer (`thank the reviewer for this excellent catch`) |
| R01 | Self-answered question: `Why does this matter?`, `The result?` | `(?:^\|[.!?]\s+)(?:So )?(?:what\|why\|how) (?:does\|do\|did\|is\|are\|was) (?:this\|that\|it)\b[^?]{0,60}\?\s+\S\|(?:^\|[.!?]\s+)The result\?` | S1 A7 l65; S2 l80 | T3 | Rhetorical question answered at once | A research question in an Introduction (a `whether` clause); a question in a heading (masked) |
| R02 | Rhetorical setups | `\bwhat if i told you\b\|\bthink about it:\|\bplot twist\b` | S2 l80 | T3 | Rhetorical question answered at once | none |
| R03 | Staccato run | none (sentence rule): N or more consecutive sentences of at most K words. S1 gives N = 2 or 3 with 1 to 3 words each; the spec gives N = 3, K = 5 | S1 A1 l15 to l17; S2 l76 and l78; S11 l123 | T3 | Staccato run | Figure legends and table notes (`Scale bar, 10 um.`); list items; headings. The spec threshold misses `No config. No setup.` (decision for the plan) |
| R04 | Repeated sentence openers | none (sentence rule): three or more consecutive sentences or bullets with the same first word | S1 A8 l70 to l72 | T3 | Repeated sentence openers | `We` openers (S11 l125); Methods lists; panel descriptions in legends. Decision: skip `The`, `A`, `In` or flag them as `info` |
| R05 | Dramatic fragmentation | `[.!?]\s+And [^.!?]{1,30}[.!?]\s+And\b\|\bthat['’]s (?:it\|the whole thing)\.` | S2 l76 | T3 | none | none |
| R06 | Fake-profound closer, known phrases | `\bthe rest is (?:just )?(?:implementation\|detail)\b\|\beverything else is (?:just )?detail\b\|\bthat(?:['’]s\| is) the difference between\b` | S1 A9 l79 to l80; S2 l82 | T3 | none | none |
| H01 | Intensifiers | `\b(?:very\|really\|truly\|incredibly\|remarkably\|extremely\|quite\|dramatically)\b` | S1 C2 l138 and fast scan l195 | T3 | none | Named terms: `very low-density lipoprotein`, `very long-chain fatty acid`, `very late antigen`, `extremely low frequency` |
| H02 | Often-empty adverbs | `\b(?:just\|literally\|honestly\|simply\|actually\|fundamentally\|importantly\|crucially\|inherently\|inevitably)\b` | S2 l48 | T3 | none | Keep when it carries emphasis, uncertainty or contrast (S2 l48); `just noticeable difference`; `simply connected`. Report as `info` |
| H03 | `significant` without a test | `\bsignifican(?:t\|tly)\b` unless: `\b[pP]\s*[<=>]\|P value\|confidence interval` | S1 C2 l140 | T3 | none | `significant figures`, `significant digits`, `most significant bit`; any sentence with a test statistic |
| H04 | Hedge stacking | `\b(?:may\|might\|could\|can)\s+(?:potentially\|possibly\|perhaps)\b\|\b(?:potentially\|possibly)\s+(?:may\|might\|could)\b\|\bit seems (?:likely\|possible) that (?:perhaps\|maybe)\b` | S1 B5 l119 | T3 | none | One hedge (`may`, `suggest`, `indicate`, `consistent with`) is allowed (S9 l99; S11 l125); only a stack matches |
| E01 | Em dash: second one in a paragraph | `---\|\u2014` (count above one per paragraph; `\u2014` is the Unicode em dash) | S1 C3 l145; S7 l112 to l114; S9 l83 to l85; S2 l88 | T3* | Em dash | Markdown `---` rule and front matter (masked); a table cell that holds U+2014 for a missing value (masked); one genuine parenthetical (S9 l99) |
| E02 | Em dash density | same regex; flag the file when the count exceeds `max(1, words // 400)` | S7 l115 to l119; S9 l84 | T3* | Em dash | same as E01 |
| S01 | Oxford mode: US `-or` and `-er` forms | `\b(?:color\|behavior\|harbor\|neighbor\|center\|fiber)\w*` | S6 l42; S9 l104 to l106 | T3 | none | `colorectal`, `colorimetric`, `colorimeter` (British English keeps `color` there); `Cold Spring Harbor` and other proper names; `Center` in institution names |
| S02 | Both modes: `-ise` forms (the author wants `-ize`) | `\b(?:(?:optimis\|organis\|summaris\|generalis\|normalis\|characteris\|visualis\|utilis\|recognis\|minimis\|maximis\|prioritis\|specialis\|standardis\|randomis\|categoris\|parameteris\|tokenis\|vectoris\|regularis\|hybridis\|discretis\|localis\|stabilis\|quantis\|binaris\|centralis\|digitis\|mobilis\|sensitis\|polaris\|immunis)(?:e\|es\|ed\|ing\|er\|ers\|ation\|ations)\|synthesis(?:e\|es\|ed\|ing\|er\|ers))\b` (S6 verbatim) | S6 l43 and l48; S9 l107 | T3 | none | Institution and funder names that use `-isation`; reference titles. `analyse` stays (the `-yse` exception, S9 l108); the regex omits it |
| S03 | `organizm` typo | `\borganizm` | S6 l44; S9 l108 | T3 | none | none. S6 holds it in the Oxford list only |
| S04 | US mode: UK `-our` and `-re` forms | `\b(?:colour\|behaviour\|harbour\|neighbour\|centre\|fibre)\w*` | S6 l47; S9 l110 | T3 | none | `Centre` in UK institution names; reference titles |
| P01 | Paragraph-initial `Furthermore`, `Moreover`, `Additionally` | `\A\s*(?:Furthermore\|Moreover\|Additionally)\b` on each paragraph, heading lines blanked first | S6 l39; S7 l103 to l111; S9 l95 to l96 | T3 | none | none |
| L01 | `Fig.` before `\ref` with a plain space | `\bFigs?\.\s*\\(?:ref\|cref\|Cref\|autoref)\b` (fix: `Fig.~\ref{...}`) | S7 l34; S9 l78 | T3 | none | none |
| L02 | `\todo{cite ...}` inventory | `\\todo\{\s*cite[^}\n]*` | S7 l35; S9 l22 to l23 | T3 | none | Info only; it does not fail the audit (S7 l198; S8 l29) |
| L03 | Markdown syntax leaked into LaTeX | `\*\*[^*\n]+\*\*` in `.tex` after math masking | S9 l150 to l151 | T3 | none | none |
| D01 | Emoji | `[\U0001F300-\U0001FAFF\u2705\u274C]` | S1 E1 l174; S2 l86 | T3 | none | `U+2713`, `U+2717` and `U+2605` in comparison tables are not emoji |
| D02 | `TL;DR` | `\bTL;DR\b` | S1 E1 l175 | T3 | none | none |
| D03 | Bold inside a sentence | `(?<=\w )\*\*[^*\n]+\*\*(?= \w)\|(?<=\w )\\textbf\{[^}\n]+\}(?= \w)` | S1 E1 l174; S2 l86 | T3 | none | A defined term at first use; a run-in paragraph title |
| D04 | Vague quantity | `\b(?:most\|many\|several\|numerous) (?:users\|researchers\|studies\|experts\|people)\b\|\babout \d+\s?%` | S1 D1 l160 | T3 | Weasel attribution | A citation, a table or figure reference or `n =` in the same sentence |
| D05 | Unmeasured multiple: `3x faster` | `\b\d+(?:\.\d+)?\s?(?:x\|×\|-fold) (?:faster\|slower\|more\|less\|better\|higher\|lower)\b` | S1 D1 l160 | T3 | none | A figure, table or citation reference in the same sentence; report as `info` |
| D06 | Claim without a check: `This now works.` | `\b(?:this\|it) now works\b\|\btests? pass(?:es)?\b` | S1 D2 l165 | T3 | none | Chat, README and commit text only; not a manuscript pattern |
| M01 | Rule-of-three padding; three synonymous adjectives in a row | none (model check) | S1 A5 l47 to l52; S9 l96 | T3 | none | Three real items, such as three named samples |
| M02 | Synonym cycling and term drift | none (model check) | S1 C4 l147 to l152; S2 l72; S9 l79 to l80 | T3 | none | An abbreviation after its first spelled-out use |
| M03 | Fake-profound closer (judgment) | none (model check; R06 holds known phrases) | S1 A9 l75 to l81; S2 l82 | T3 | none | none |
| M04 | Summary restatement paragraph | none (model check) | S1 A10 l83 to l87; S2 l84 | T3 | none | An Abstract or Conclusions section that the journal requires |
| M05 | Hedged non-answer | none (model check) | S1 B4 l112 to l115 | T3 | none | none |
| M06 | Em dash that lands a point | none (model check) | S1 C3 l144 to l145 | T3* | Em dash | One genuine parenthetical |
| M07 | Bullets for connected reasoning; headers over two-sentence sections | none (model check) | S1 E2 l177 to l181; S2 l86 | T3 | none | Parallel independent items (reagent lists, numbered Methods steps); journal-required headings |
| M08 | Robotic rhythm: repeated sentence shapes and paragraph shapes | none (model check; R03 and R04 hold the countable part) | S2 l78; S3 l39 | T3 | none | none |

Notes on the rules of `audit.py` (S7) and the term file (S6):
- S7 blanks `%` comments and `comment`, `verbatim` and `lstlisting` blocks (l45 to l61). It blanks each command name and the argument of identifier commands such as `\label`, `\ref`, `\cite*`, `\input` and `\url` (l22 to l27, l64 to l67). The argument of `\section`, `\caption` and `\emph` stays visible. The spec masker (S11 l91 to l92) hides unknown arguments instead.
- A paragraph is a run of non-blank lines (l70 to l83). A heading line is blanked before the paragraph split, so the text under a heading starts a paragraph (l104 to l106). The word and construction checks still see heading text.
- Vocabulary and spelling patterns run with case-insensitive matching. Construction patterns add the dot-all flag (l97 to l102). Most stems have no closing `\b`, so `robust` also matches `robustness`.
- Em dash: `---` or U+2014 (l36). The second one in a paragraph flags (l112 to l114). The file allows `max(1, words // 400)` (l117), and S7 counts words with `[A-Za-z][A-Za-z']*` after masking (l37, l115).
- S7 exits 1 for any hit except `todo-cite`, 2 on an error, 0 otherwise. Spelling defaults to `off` (l170, l198).
- S6 says it is a machine copy of S9 section 3 (l2). I compared the lists: the 29 vocabulary terms of S6 and S9 match one to one.
- In S1 or S2 but not in S6 or S9: `utilize`, `elevate`, `empower`, `streamline`, `journey`, `testament`, `synergy`, `myriad`, `plethora`, `meticulous`, `boasts`, `ecosystem`, `game-changer`, `beacon`, `paramount`, `supercharge`, `ever-evolving`. In S6 and S9 but not in S1: `facilitate`, `foster`, `underscore`, `embark`, `multifaceted`, `unprecedented`, `transformative`, `revolutionize`.
- Gaps in S6 and S7: `organizm` sits in the Oxford list only (S6 l44, l46 to l49). The `harness` verb after an adverb is missed. `\bcolor\w*` matches `colorectal`. No pattern has an exception field.
- S7 counts `---` as an em dash. For `.md` files, mask the Markdown rule line and the YAML front matter before that rule runs.
- Not found in S1 to S10: `Certainly!`, `Here is the revised`, `As an AI` (the spec names them at S11 l121). The corpus note or a guide must supply them.

## 2. Rewrite preferences the author states

| Pattern | What the source says to do instead | Key |
|---|---|---|
| Staccato fragments | Write one full sentence. | S1 A1 l18 |
| Binary contrast, negative listing | State the positive claim once. State Y directly. Write only the Z. | S1 A2 l28; S2 l54, l74 |
| Metaphor pair | Delete the figure and name the property. | S1 A3 l37 |
| Backward reference | Delete the sentence. Rewrite the earlier sentence if it needed the emphasis. | S1 A4 l45 |
| Rule of three | List only the items you can support. | S1 A5 l52 |
| Trailing participle | Start a new sentence with a subject, or name the concrete consequence (`so users can find old drafts`). | S1 A6 l59; S2 l62 |
| Self-answered question | Delete the question and write the answer. Drop the setup. | S1 A7 l66; S2 l80 |
| Repeated openers | Vary the openings or merge the items. | S1 A8 l73 |
| Closing kicker | Delete it and end on the clearest concrete sentence. Do not rewrite it into a better metaphor. Add a plain takeaway or next action only if the ending needs closure. | S1 A9 l81; S2 l82 |
| Summary ending | Delete it. Put a summary above the body if the reader needs one. End on the last concrete point. | S1 A10 l87; S2 l84 |
| Throat clearing, faux insight, metadiscourse | Start with the claim. Cut the setup. Delete the aside or replace it with support. | S1 B1 l98; S2 l56 to l66 |
| Assistant residue | Report what happened and the result. Answer the question. Show agreement by acting on the point. | S1 B2 l105, B3 l110 |
| Hedge stack | Use one hedge, or state the uncertainty as a fact (`I did not test this`). | S1 B5 l120 |
| Banned word | Replace it with a plain equivalent. No table of pairs exists. Use a direct verb (`made a decision` becomes `decided`). | S1 C1 l128; S2 l39 |
| Intensifier | Delete it or use a precise adjective. Write `significant` only with the test and the p-value. | S1 C2 l139 to l140 |
| Em dash | Use commas, parentheses, a colon or a new sentence. Remove clusters. A colon in place of a dash can create a colon reveal (C22). | S9 l85; S2 l88 |
| Colon reveal | Rewrite as a plain sentence. Use colons for lists, labels and quotes. | S2 l60 |
| Puffery, fake-strong verb | State the fact and let the reader judge. Use `is` or `has`, or the concrete verbs. | S2 l64, l70 |
| Weasel attribution | Name the source or cut the claim. With no source, ask. Never invent one. In LaTeX, flag `\todo{cite ...}`. | S2 l68; S9 l22 to l23 |
| Term drift | Pick one term and repeat it. | S1 C4 l152; S2 l72; S9 l79 to l80 |
| Unmeasured number | Give the measurement and how you got it, or drop the number. Trace a manuscript number to a file, run or table; else mark `\red{XX}`. | S1 D1 l161; S9 l32 to l34 |
| Decoration, bullets | Remove emoji. Write a paragraph when the items depend on each other. | S1 E1 l175, E2 l181; S2 l86 |
| Edit scope | Make the minimum effective edit. Keep the meaning. Add no claim, number or example. Ask when unclear. | S2 l12, l27, l30 |
| Needless words | Omit them. Use the active voice. Cut a sentence that can go. | S9 l39, l73 |
| Approval (plan conflict) | Approval does not carry over between turns. The spec apply step (S11 l159) must ask in the same turn as the edit. | S9 l19 to l21 |
| Deletion (plan conflict) | The author prefers commenting out to deleting, with a one-line comment. The spec allows `delete: true` (S11 l173). | S9 l30 to l31 |
| Redline display | Show bold for an addition, strikethrough for a deletion and plain text for kept text, in chat, before applying. | S9 l47 to l48 |
| Hedges and caveats | Never drop an agreed caveat. Keep scientific hedges. | S9 l59 to l60, l99 |

## 3. Checklist items

The model makes each check. Where the column "Fit" says "script", section 1 holds a partial script check and the model still decides. "Fit" also says whether the item suits scientific text.

| ID | Model-judgment check | Source | Fit |
|---|---|---|---|
| EP1 | The edit keeps the point and adds no claim, example, statistic, quote or opinion. | S3 l9; S2 l30 | keep; guards `numbers` and `no-new-names` cover part |
| EP2 | The edit keeps the writer's vocabulary, cadence, bluntness, uncertainty and polish. | S3 l10 | adapt: drop humor and digressions for a paper; use the voice profile |
| EP3 | Strong human sentences stay unchanged. | S3 l11 | keep |
| EP4 | The amount of cutting fits the amount of slop. | S3 l12 | keep; guard `not-longer` covers part |
| EP5 | The text leads with what the reader needs. | S3 l13 | adapt: a paper has a fixed structure |
| EP6 | Front-loading helps clarity and does not force one shape. | S3 l14 | keep |
| EP7 | Sentences carry concrete facts and direct verbs. | S3 l15 | keep |
| EP8 | Each generic sentence passes the portability test: it names this subject. | S3 l16; S2 l36 | keep |
| EP9 | The text uses the active voice with human subjects. | S3 l17 | adapt: the passive voice in Methods is allowed (S11 l125) |
| EP10 | The edit keeps useful edge and the structure. | S3 l18 | adapt: drop edge |
| EP11 | Tangled sentences are fixed. Clear spoken cadence stays. | S3 l19 | adapt |
| WD1 | Banned words, filler phrases and empty adverbs are gone unless quoted. | S3 l23 | script covers it |
| PT1 | Binary contrasts, negative listings, rhetorical setups and throat clearing are gone. | S3 l27 | script plus model |
| PT2 | Faux insight, colon reveals, superficial analysis, fake-strong verbs, synonym cycling, dramatic fragments and robotic rhythm are fixed. | S3 l28 | script, except synonym cycling and rhythm |
| PT3 | Puffery and weasel attribution give plain facts and named sources, or the draft flags the missing source. | S3 l29 | keep; the model must flag and never invent a source |
| PT4 | Metadiscourse is gone, including reader guidance and redundant glossing. | S3 l30 | script partly |
| PT5 | Fake-profound kickers are deleted, not rewritten. | S3 l31 | keep |
| PT6 | Summary-recap endings are cut. | S3 l32 | keep; the Abstract and Conclusions stay |
| PT7 | Formatting slop is gone. | S3 l33 | script partly (D01 to D03) |
| PT8 | A colon is followed by lower case unless grammar requires otherwise. | S3 l34 | script (C23); off by default |
| PT9 | Em dashes are rare. | S3 l35 | script (E01, E02) |
| FR1 | The text avoids robotic symmetry, repeated shapes and stacked fragments. | S3 l39 | script partly (R03, R04) |
| FR2 | The writer would recognize the edited draft as their own voice. | S3 l40 | keep; the author judges (spec voice check) |
| FR3 | The draft sounds natural when read to a sharp colleague. | S3 l41 | drop: a spoken-style test |
| FR4 | The output has the full draft and a What changed section. | S3 l42 | drop: the plugin returns proposals with a `reason` |
| FR5 | A detect request names each pattern with a quoted line and a short fix. It does not rewrite, score or claim who wrote the text. | S3 l43; S2 l14 | keep; matches decision D6 (S11 l34) |
| HN1 | A rewrite does not upgrade a weaker claim: `informed by` is not `predict`. | S9 l121 to l122 | keep |
| HN2 | A rewrite does not move interpretation into Results or new data into Discussion. | S9 l76 to l77 | keep |
| HN3 | A rewrite keeps one term per concept and turns private shorthand into the precise term. | S9 l63 to l64, l79 to l80 | keep |
| HN4 | No citation, key or number is invented. An unknown number gets `\red{XX}`. | S9 l22, l32 to l34 | keep |
| HN5 | Parameters, scope limits, reliability and independence limits are stated. | S9 l119 to l131 | out of scope in version 1 (S11 l20 to l21); list only |

## 4. Files read

- S1 `~/.claude/forbidden.md` (all of it: sections A to E and the fast scan).
- S2 `~/.agents/skills/no-ai-slop/SKILL.md` (all of it: the two jobs, the editing principles, the word lists, 18 pattern families, the workflow).
- S3 `~/.agents/skills/no-ai-slop/eval.md` (all of it: 26 pass-or-fail checks).
- S4 `~/.agents/skills/no-ai-slop/agents/openai.yaml` (all of it: a display name, a short description and a default prompt).
- S5 `~/.agents/.skill-lock.json` (the install record; the only origin record found).
- S6 `plugins/overleaf-manuscript/skills/overleaf-manuscript/audit_terms.json` (all of it, in this repository).
- S7 `plugins/overleaf-manuscript/skills/overleaf-manuscript/scripts/audit.py` (all of it).
- S8 `plugins/overleaf-manuscript/skills/overleaf-manuscript/SKILL.md` (all of it, for how the audit runs).
- S9 `~/.claude/skills/synced/*/manuscript-write/SKILL.md` (all of it; the rules of sections 1 to 5). It names no other rule file.
- S10 `~/.claude/skills/synced/*/<project-skill>/SKILL.md` (all of it; style rules only).
- S11 `docs/superpowers/specs/2026-10-23-plain-prose-design.md` (all of it; sections 3 and 6 in detail).

Not read: `preflight.sh` of S8, the global `CLAUDE.md`, any corpus note. No file was unreadable, so no row is UNVERIFIED.

## 5. Origin and license

| Source | Origin | License | What the plugin may copy |
|---|---|---|---|
| S1 | The author's own file (the owner of this repository). It has no author, license or source line. | None stated. The author agreed to the lists entering the plugin. | Pattern names, words and short examples. |
| S2, S3, S4 | S5 records the source `petergyang/no-ai-slop` (type `github`, URL `https://github.com/petergyang/no-ai-slop.git`, path `skills/no-ai-slop/SKILL.md`, folder hash `3d8be37cd59f6601cbc33676ecaf5b42865daf63`, installed 2026-09-07). The files hold no author, source or URL line. I did not check that the repository exists. | No license found. A search of the folder for license, author, copyright, source, origin and URL words found no license text, and the folder has no LICENSE file. | Family names and short examples only, because the origin is third-party and the license is unknown. Wait for the web check before copying more. |
| S5 | A local install record. | Not a pattern source. | Nothing. |
| S6, S7, S8 | The author's own plugin `overleaf-manuscript` (the author field of its `plugin.json` names the repository author). | MIT, from `plugin.json`. The plugin folder and the repository root have no LICENSE file. Only `plugins/agent-board/LICENSE` exists (MIT, 2026, the repository author). | The lists and the rule logic. |
| S9 | The author's claude.ai skill, a synced copy. S6 says S6 is a machine copy of its section 3. | None stated in the file. | Words, phrases and constructions. Not the skill text. |
| S10 | The author's skill for an unpublished project. | None stated. The project state is private. | Two generic style items only (Oxford spelling; one vocabulary per concept). No project noun, number or result. |
| S11 | The design spec of this repository. | Internal. | Not a pattern source. |

The spec (S11 l44) calls `no-ai-slop` "the author's local skill". S5 names a third-party source. The plan can correct that line. The author's choice to install the skill is the only T3 basis for rows that rest on S2 alone.
