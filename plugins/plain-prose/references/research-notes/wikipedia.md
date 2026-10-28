# Wikipedia "Signs of AI writing" for scientific manuscripts

Method. I downloaded the wikitext of each page through the MediaWiki application programming interface (API) on 2026-10-23 and read it in a terminal. I read the main guide, S1, from the first line to the last (revision 1381583419, saved 2026-10-23T13:57:49Z, about 1,640 lines). I read its markup sub-page S2 and the page on Markdown code fences S3 in full. For the comments sub-page S4, I read the prose, the word boxes and the lead of each section. I did not read every example block. I read only the intro and the headings of S5, and parts of S6 to S9, S11 and S12, as section 4 states. The page `AI catchphrases` that the task names is a redirect to S1, so no separate catchphrase list exists. Tier T2 means the guide states the sign and gives no measurement. Tier UNVERIFIED means I saw only part of a text or could not open it. Keys S1 to S12 map to URLs in section 4. Abbreviations: LLM means large language model. DOI means digital object identifier. AfC means Articles for Creation, the Wikipedia queue for new drafts. ANI means the Administrators' noticeboard for incidents.

Family labels shorten the names in section 6 of the design spec. Family key: Vocabulary = vocabulary with measured excess; Figurative = figurative load words; Binary = binary contrast; Puffery = importance puffery; Participial = trailing participial benefit clause; Weasel = weasel attribution; Fake verbs = fake-strong verbs; Throat = throat-clearing and signposting; Recap = recap openers; Residue = assistant residue. "none" means no family fits. "model check" means the sign belongs in `model-checks.md`. I graded relevance by judgment. No source grades it.

## 1. Signs (table, grouped by the guide's own sections)

| ID | Sign | Description | Example phrases (short quotes) | Relevance to manuscripts | Plugin family | Tier | Source key |
|---|---|---|---|---|---|---|---|
| **Content** | | | | | | | |
| A1 | Undue emphasis on significance, legacy and trends | The text says a minor fact stands for or feeds a larger theme. | `stands/serves as`, `is a testament/reminder`, `a crucial/pivotal/vital/significant/key role/moment`, `underscores/highlights its importance/significance`, `reflects broader`, `setting the stage for`, `evolving landscape`, `focal point`, `indelible mark`, `deeply rooted` | high: Introduction and Discussion claim significance without data | Puffery | T2 | S1 |
| A2 | Debate and discussion framing | The text places the subject inside "debates" or "public discussions". | `generated debate`, `shaped emerging policy discussions`, `prompted broader reflection`, `raising philosophical questions` | medium: a review can state a real dispute with these words | Puffery | T2 | S1 |
| A3 | Low-importance preamble | The text admits limited importance, then claims importance. | `Though it saw only limited application`, `contributes to the broader history` | medium: fits Discussion sentences that open with "Although limited" | Puffery | T2 | S1 |
| A4 | Ecosystem and conservation emphasis | For a species, the text stresses ecosystem links and conservation even when the link is weak. | `plays a role in the ecosystem`, `crucial for the survival of this and other endemic species`, `Preserving this endemic species is vital` | medium: biology manuscripts, but real ecological context is legitimate | Puffery | T2 | S1 |
| A5 | Canned emphasis on notability, attribution and media coverage | The text proves notability by naming outlets and source types. | `independent coverage`, `trade publications`, `cited/featured/profiled in`, `written by a leading expert`, `active social media presence`, `was identified by` | low: Wikipedia notability rules drive it; manuscripts do not argue notability | none | T2 | S1 |
| A6 | Superficial analyses | A present participle phrase ends the sentence and adds an empty comment on impact. | `highlighting/underscoring/emphasizing ...`, `ensuring ...`, `reflecting/symbolizing ...`, `contributing to ...`, `cultivating/fostering ...`, `encompassing ...`, `enhancing ...`, `valuable insights`, `align/resonate with` | high: the trailing `-ing` clause is common in Abstract and Discussion | Participial | T2 | S1 |
| A7 | Promotional and advertisement-like language | A neutral topic reads like advertising or a travel guide. | `boasts a`, `vibrant`, `rich`, `profound`, `enhancing`, `showcasing`, `exemplifies`, `commitment to`, `nestled`, `in the heart of`, `groundbreaking`, `renowned`, `featuring`, `diverse array` | medium: `groundbreaking` and `showcasing` fit Abstract hype; travel words are rare | Puffery | T2 | S1 |
| A8 | Promotional subtypes | The guide names two: reminders of cultural heritage, and press-release tone about people and firms. | `align with KQ's goals`, `emphasized the airline's commitment to`, `acts as the gateway` | low: most manuscripts have no cultural or corporate subject | Puffery | T2 | S1 |
| A9 | Vague connection or association | The text says two items are linked and does not state the relation. | `in connection with/to`, `connected with/to`, `in association with`, `associated with` | low: `associated with` is exact wording for statistical association in genetics and epidemiology | none | T2 | S1 |
| A10 | Vague attributions and overgeneralized opinions | A vague authority holds the claim, or the count of sources is inflated. | `Industry reports`, `Observers have cited`, `Experts argue`, `Some critics argue`, `several sources/publications` (when few are cited), `such as` (before lists that look complete) | high: "studies show" and "experts agree" without a citation occur in Introduction | Weasel | T2 | S1 |
| A11 | Outline-like challenges and future prospects | A formula: "Despite its X, the subject faces challenges and continues to Y". | `Despite its... faces several challenges...`, `Despite these challenges`, `Challenges and Legacy`, `Future Outlook` | medium: Limitations sections are normal, so only the formula signals | none (nearest Recap) | T2 | S1 |
| A12 | "X and Y" section titles | Section titles of the form "X and Y", mainly "Awards and recognition". | `Awards and recognition`, `Recognition` | low: a Wikipedia section habit | none | T2 | S1 |
| A13 | Marketing buzzspeak (essay linked from the promotional section) | Words that persuade and add no meaning. The essay says it does not matter whether an LLM wrote a page full of them. | `thought leader`, `cutting edge`, `award-winning`, `methodology` (for "method") | medium: `methodology` for `method` and `cutting edge` occur in manuscripts | none | T2 | S8 |
| **Language and grammar** | | | | | | | |
| B1 | High density of "AI vocabulary" words | Words that rose after 2022 and co-occur. The guide calls many hits in one edit a strong tell. | `Additionally` (sentence start), `align with`, `boasts` (for "has"), `bolstered`, `crucial`, `deep dive`, `delve`, `emphasizing`, `enduring`, `enhance`, `fostering`, `garner`, `highlight` (verb), `interplay`, `intricate/intricacies`, `landscape` (abstract), `meticulous/meticulously`, `pivotal`, `robust`, `showcase`, `tapestry` (abstract), `testament`, `underscore` (verb), `valuable`, `vibrant` | high: the footnotes cite studies of scientific abstracts | Vocabulary | T2 | S1 |
| B2 | AI vocabulary by model era | The guide sorts words by the model period in which they peaked. | 2023 to mid-2024: `delve`, `tapestry`, `testament`. Mid-2024 to mid-2025: `align with`, `fostering`, `showcasing`. Mid-2025 to mid-2026: `emphasizing`, `highlighting`. From mid-2026: `leverage`, `multifaceted`, `prioritize`, `quietly`, `universally` | medium: shows which words age; the mid-2026 list cites one web review | Vocabulary | T2 | S1 |
| B3 | Grok vocabulary | Output of one chatbot overuses science-flavored words. | `causal`, `empirical`, `correlate`, `underscore` | low: `causal`, `empirical` and `correlate` are normal science words, so do not flag them | none | T2 | S1 |
| B4 | Avoidance of basic copulatives | Short "is/are" gives way to longer verbs. | `serves as`, `stands as`, `marks`, `functions as`, `operates as`, `represents [a]`, `boasts/features/maintains/offers [a]`, `refers to`, `began his career as` | high: `serves as` and `acts as` occur in Methods and Discussion | Fake verbs | T2 | S1 |
| B5 | Negative parallelism: not just X, but also Y | A sentence denies one claim and adds a second. | `Not only ... but ...`, `It is not just ..., it's ...`, `doesn't just undermine ...; it questions ...` | high: common in Discussion | Binary | T2 | S1 |
| B6 | Negative parallelism: not X, but Y | The text denies the first trait and names another. | `It's not ..., it's ...`, `no ..., no ..., just ...`, `is not dissolution. Rather, it constitutes` | high: common in Discussion | Binary | T2 | S1 |
| B7 | Negative parallelism: Y rather than X | The reverse order. The guide calls it common in recent output. | `prioritizing ... rather than ...` | medium: `rather than` also states honest comparisons | Binary | T2 | S1 |
| B8 | Leads that treat a title as a proper noun | The first sentence defines the page title as if it were a thing. | `refers to`, `is the chronological list`, `is a curated compilation` | low: applies to Wikipedia list pages | none | T2 | S1 |
| B9 | Rule of three | Triplets of adjectives or short phrases. | `adjective, adjective, adjective`, `short phrase, short phrase, and short phrase`, `tiles, metals, and plastics` | medium: triplets are normal in science, so use it as a model check only | none (model check) | T2 | S1 |
| **Style** | | | | | | | |
| C1 | Title case in headings | Chatbots capitalize all main words in headings. | `Impact of Technology and Digitalization` | low: journals set heading case | none | T2 | S1 |
| C2 | Overuse of boldface | Mechanical bold on chosen phrases, in a "key takeaways" style. | `leveraged buyout (LBO)`, `debt financing` (bold in the guide's example) | medium: bold is rare in a manuscript, so a cluster stands out | none | T2 | S1 |
| C3 | Inline-header vertical lists | Each list item starts with a bold header and a colon. | `Key highlights:`, `Timeline and Impact` | medium: response letters and Markdown drafts use this shape | none | T2 | S1 |
| C4 | Heading errors | Four forms: a title heading before the content, skipped heading levels, level 1 headings, headings that hold only other headings. | `= History =` | low: wiki heading levels do not map to LaTeX | none | T2 | S1 |
| C5 | Emoji as formatting | Emoji before headings or bullets. The guide says this is rarer now. | `👋`, `🎯`, `📚` | medium: rare in manuscripts and easy to detect | none | T2 | S1 |
| C6 | Unusual use of tables | Small tables that prose or an infobox would hold better. | none quoted | low | none | T2 | S1 |
| C7 | Curly quotation marks and apostrophes | Left and right double quotes (U+201C, U+201D) and the apostrophe U+2019 replace straight ones, sometimes mixed. | none quoted | low: LaTeX source uses its own quote marks, and the guide says curly quotes alone do not prove LLM use | none | T2 | S1 |
| **Communication intended for the user** | | | | | | | |
| D1 | Collaborative communication | A chat reply to the user sits inside the text. | `I hope this helps`, `Of course!`, `Certainly!`, `You're absolutely right!`, `Would you like...`, `is there anything else`, `let me know`, `here is a`, `more detailed breakdown`, `Delete this section before submission` | high: pasted chat text in drafts | Residue | T2 | S1 |
| D2 | Didactic disclaimers (2023 to 2024) | Older models warn the reader about what matters. | `it's important to note`, `It is crucial to differentiate`, `It's important to remember` | high: matches "It is important to note that" in Discussion | Throat | T2 | S1 |
| D3 | Source-gap disclaimers (2024 to 2025) | The model says information is missing and guesses what it might be. | `aren't widely documented`, `is limited in the provided search results`, `based on available information`, `I've inferred` | medium: `provided search results` is chat residue, and `based on available information` also occurs in human text | Residue | T2 | S1 |
| D4 | Corrective framings (mid-2026 on) | The text warns how a source should be read. | `should be treated as ... rather than ...`, `does not establish`, `should not be confused with` | low: `does not establish` is honest hedging that the spec keeps, and the guide rates `should not be confused` as less reliable | Binary (for `rather than`) | T2 | S1 |
| D5 | Phrasal templates and placeholder text | Fill-in-the-blank text stays unfilled. | `[Your Name]`, `[Describe the specific section ...]`, `2025-XX-XX`, `INSERT_SOURCE_URL_30`, `PASTE_SPOTIFY_TRACK_URL_HERE`, `<!-- Add if available with citation -->` | high: unfilled brackets and `XX` in cover letters and tables | Residue | T2 | S1 |
| **Markup** (S1 gives a summary; S2 and S3 give the detail) | | | | | | | |
| E1 | Markdown asterisks | `**` wraps text that the model meant as bold. | `**summary rejection**` | medium: asterisks pass through LaTeX unseen, and the guide calls Markdown alone a weak signal | none | T2 | S2 |
| E2 | Markdown number signs | `##` marks section headings. | `## Geography` | low: LaTeX has its own heading commands (I did not test how it treats `#`) | none | T2 | S2 |
| E3 | Markdown link format | `[text](url)` replaces the target syntax. | `[here](https://...)` | medium: survives in plain text and in pasted LaTeX source | none | T2 | S2 |
| E4 | Thematic breaks between sections | A rule of dashes sits between sections. | `----`, `---` | low | none | T2 | S2 |
| E5 | Markdown code fences | Backtick fences wrap the pasted text. | `` ```wiki ``, and a trailing `` ``` `` | medium: the guide covers wikitext, and a `` ```latex `` fence is my inference | Residue (by inference) | T2 | S3 |
| E6 | Broken wikitext | Garbled template code from a model that does not know wikitext. | none quoted | low | none | T2 | S2 |
| E7 | ChatGPT markup bugs | Tool metadata replaces links to sources. | `contentReference`, `oaicite`, `oai_citation`, `turn0search0`, `attributableIndex`, `+1` after a source name | high: pasted chat output carries these into text and references | Residue | T2 | S2 |
| E8 | Gemini markers | Citation and span tags from one chatbot. | `[cite: 1]`, `[span_1](start_span)` | high: same | Residue | T2 | S2 |
| E9 | Grok markers | Card tags from one chatbot. | `grok_card`, `grok_render_citation_card_json` | high: same | Residue | T2 | S2 |
| E10 | DeepSeek markers | Lenticular brackets with a dagger replace links. | `【85†L261-269】` | high: same | Residue | T2 | S2 |
| E11 | Perplexity markers | File and web tags at sentence ends. | `[attached_file:1]`, `[web:1]`, `ppl-ai-file-upload` | high: same | Residue | T2 | S2 |
| E12 | Unclassified tool marker | A document tag of unknown origin, seen from June 2026. | `:::writing{variant="document" id="..."}` | high: same | Residue | T2 | S2 |
| E13 | Non-existent categories and templates | Invented category and template names. | `[[Category people]]` for `[[:Category:Living people]]` | low: wiki-specific | none | T2 | S2 |
| **Citations** | | | | | | | |
| F1 | Broken external links | Several links in a new draft fail and have no archive copy. | none quoted | medium: matters for reference lists, but the plugin does not use the network | none | T2 | S1 |
| F2 | Invalid DOIs and ISBNs | An ISBN fails its checksum, or a DOI does not resolve. | none quoted | high: hallucinated references. The plugin can test the ISBN checksum offline and cannot resolve a DOI | none | T2 | S1 |
| F3 | DOIs that lead to unrelated articles | A DOI resolves to another paper, and the cited paper does not exist. | `Proceedings of the IEEE` (the guide's ChatGPT example) | high: same, and it needs the network | none | T2 | S1 |
| F4 | Book citations without pages or URLs | A real book is cited with no page, so nobody can check the claim. | none quoted | medium | none | T2 | S1 |
| F5 | Unconventional reference syntax | Wrong reuse syntax, and the `↩` character after footnotes. | `↩` | low: wiki syntax | none | T2 | S1 |
| F6 | utm_source parameters | Tool names sit in the query string of a URL. | `utm_source=openai`, `utm_source=chatgpt.com`, `utm_source=copilot.com`, `referrer=grok.com` | high: URL fields in reference lists keep them | Residue | T2 | S1 |
| F7 | Named references declared and unused | References sit in the reference block and no sentence cites them. | none quoted | low: the LaTeX analog (unused bibliography entries) is my inference | none | T2 | S1 |
| **Comment-specific indicators** (S1 lists seven tells, S4 details them) | | | | | | | |
| G1 | Overassurance of quality or goodwill | Policies appear as an abstract whole, in a legal tone. | `I am committed to ...`, `I assure you that ...`, `I have taken the time to ...`, `Going/Moving forward, I will ...`, `my aim/goal/intention is to ...` | medium: cover letters and responses to reviewers | none | T2 | S4 |
| G2 | Denial of promotional intent | A denial of the form "not X but Y". | `My intention is not to promote` | low | Binary | T2 | S4 |
| G3 | Dubious assurance of human curation | After an AI admission, the user claims personal review. | `reflects my own intent and understanding` | low | none | T2 | S4 |
| G4 | Assertions of notability | Comments inflate how well a topic meets the notability rule. | `well-established national organization` | low | none | T2 | S4 |
| G5 | Uncertainty and requests for input | The user feigns doubt about what is wrong and asks for guidance. | `If there are specific [areas/examples/passages/sections] that ...`, `I [would appreciate]/[welcome] (any) [additional/further] feedback/guidance/input/suggestions` | medium: responses to reviewers | none | T2 | S4 |
| G6 | Requests for third-party review, and confusion over a decline | Stock requests for an "uninvolved" editor, and vague questions about a clear decline notice. | `[Can/Could/Would] an [experienced/independent/uninvolved] [editor/administrator] (please) [advise/review] ...`, `Is the (main/primary) concern/issue (related to) ...?` | low | none | T2 | S4 |
| G7 | Dismissal of AI accusations | The user calls the accusation speculation. | `accusations`, `speculation`, `subjective`, `unsubstantiated/unsupported/unwarranted` | low | none | T2 | S4 |
| G8 | Requests to focus on content instead | A request to discuss content and not the origin of the text. | `instead of/rather than ...`, `let's [focus / keep this (discussion) focused] on ...` | low | Binary | T2 | S4 |
| G9 | Misquoted policies, invented shortcuts, minimized AI rule | Rules are misquoted or cited by shortcuts that do not exist. | `WP:SECONDOPINION`, `Wikipedia allows tools like AI` | low | none | T2 | S4 |
| G10 | Procedural language, overjustified suggestions, spelled-out policies | The text stresses how rules are or will be followed. | `adhere to`, `align with`, `ensure (that)`, `in compliance/line with`, `These edits/changes would make the article ...` | low: `adhere to` also occurs in Methods | none | T2 | S4 |
| G11 | Frequent words and phrases | A catch-all list. The sub-signs `concrete` (adjective) and `I am happy to...` sit here. | `address concerns`, `concrete`, `I'm happy to ...`, `I respectfully request ...`, `particularly regarding ...`, `Thank you for your time and consideration` | medium: closings and offers in cover letters and review responses | none | T2 | S4 |
| G12 | Failed project-page citations | Comments cite "WP" where a shortcut belongs. | `WP and WP` | low | none | T2 | S4 |
| G13 | Subject lines | A comment starts with a mail subject line. | `Subject: Concerns about Inaccurate Information` | medium: a stray `Subject:` line in a cover-letter draft is chat residue | Residue | T2 | S4 |
| G14 | Titled sections and subheadings in comments | Comments split into titled sections, in Markdown or plain text. | `##` | low | none | T2 | S4 |
| G15 | Transcluded maintenance banners | Template names in curly braces run as real templates. | `{{Example}}` | low | none | T2 | S4 |
| G16 | Chat log disclosures | Pasted chat logs keep the speaker labels. | `You said:`, `ChatGPT said:` | high: chat residue | Residue | T2 | S4 |
| G17 | Canned unblock requests | Generic requests that fit any blocked user. | `I respectfully request that the block on my account be lifted`, `If unblocked, I will ...` | low | none | T2 | S4 |
| G18 | Apologies for potential past damage | The user apologizes for harm they "may have" caused. | `I apologize for any ... that may have ...` | medium: responses to reviewers use similar lines, so precision is low | none | T2 | S4 |
| G19 | Clerk or customer-service tone | Comments read like a service desk. | `carefully reviewed`, `please point them out to me, and I will try to resolve them` | medium: response letters | none | T2 | S1 |
| G20 | Canned ANI reports | Numbered complaints with quoted edits, sometimes with emoji. | none quoted | low | none | T2 | S7 |
| G21 | Sealioning and wikilawyering | Long comments demand evidence and cite policy at length. | none quoted | low | none | T2 | S4 |
| G22 | General signs of AI unblock requests | Unfilled placeholders, leftover prompts, letter format, Markdown, generalities, lists, stock closings. | `Write me a Wikipedia unblock request`, `Thank you for your time`, `Thank you for considering my request` | medium: letter format and stock closings apply to cover letters | Residue | T2 | S6 |
| **Edit summaries** | | | | | | | |
| H1 | General AI edit summaries | Older ones are first-person with chat preambles. Newer ones stress procedure. | `Concise edit summary`, `Claude responded:` | low: manuscripts have no edit summaries | none | T2 | S1 |
| H2 | Canned assurance of adherence | Summaries assure that the edit follows policy. | `ensured that... adheres to`, `refined`, `enhanced`, `in compliance/complies with`, `neutral tone`, `clarity`, `flow` | low | none | T2 | S1 |
| H3 | "Preserved", "retained", "avoided" | Summaries name what the edit left unchanged. | `preserved/preserving`, `retained/retaining`, `avoided/avoiding`, `ensured/ensuring`, `aimed/aiming to`, `while preserving` | low: appears in revision notes, not in manuscript text | none (nearest Participial) | T2 | S1 |
| H4 | Overemphasis on citations | Summaries stress that content is sourced. | `added sourced [information/content/...]`, `improved attribution`, `with [independent/secondary/third-party/peer-reviewed] sources` | low | none | T2 | S1 |
| H5 | Overemphasis on parameter and template names | Summaries list markup names. | `infobox parameters (image_size)` | low | none | T2 | S1 |
| H6 | Reference to AfC review | Summaries say the edit answers a reviewer. | `Addressing reviewer feedback`, `per reviewer feedback` | low: "reviewer feedback" is normal in a response letter | none | T2 | S1 |
| **Miscellaneous** | | | | | | | |
| I1 | Pronounced shift in writing style | A sudden change against the editor's earlier writing. | none quoted | low: it needs earlier text, and the spec makes no authorship claim | none | T2 | S1 |
| I2 | AfC submission statements | A note to reviewers that argues for notability. | `Reviewer note (for AfC)` | low | none | T2 | S1 |
| I3 | Pre-placed maintenance templates | A draft arrives with a decline or maintenance template already set. | `AfC submission` | low | none | T2 | S1 |
| I4 | Canned user pages | A rigid user page. S5 lists nine features: generic outline of contributions, talk page invitation, vague conflict statement, creator-facing message, missing userboxes, emoji in userboxes, unclosed tables, rounded boxes, non-stylistic traits. | `About Me`, `My Interests`, `Let's Connect!` | low | none | T2 | S1, S5 |
| I5 | Permissions gaming | Many small AI edits raise an access level. | none quoted | low | none | T2 | S1 |
| I6 | Differences between LLMs | Each model has its own style. ChatGPT and Grok stress broader context more than Gemini and Claude. | none quoted | low: context for model-specific word lists | none | T2 | S1 |
| I7 | Pro-authoritarian bias | A content bias on some prompts. | none quoted | low | none | T2 | S1 |
| **Signs of human writing** (counter-signs: more common in human text) | | | | | | | |
| J1 | Age of text | Text from before 2022-11-30 cannot come from ChatGPT. | `before November 30, 2022` | medium: a date check, outside a style linter | none | T2 | S1 |
| J2 | Ability to explain one's own choices | A human author can explain an edit or an error. | none quoted | low | none | T2 | S1 |
| J3 | Simple "is" and "has" phrases | Plain copulas occur more in human text. | `there is a`, `it has a` | medium: supports leaving plain `is` and `has` alone (counter to B4) | none | T2 | S1 |
| J4 | Plain words over stiff synonyms | Humans write the short word. | `wrote`, `moved`, `used`, `tried`, `died` (against `authored`, `relocated`, `utilized`, `attempted`, `passed away`) | medium: supports plain-word rewrites | none | T2 | S1 |
| J5 | Superlative or definitive statements | Humans state firsts and onlys. | `one of the best`, `is the only`, `was the first` | medium: priority claims are normal in science (counter to A1) | none | T2 | S1 |
| J6 | Qualifiers and intensifiers | Humans use these words more than LLMs do. | `very`, `perhaps`, `tends to` | high: a rule that flags these words conflicts with this guide | none | T2 | S1 |
| J7 | Isolated wordy constructions | Humans write these phrases more often. | `as a result of`, `in order to`, `all of the`, `a part of`, `the fact that` | medium: a human habit, though plain-writing rules may still trim them | none | T2 | S1 |
| **Ineffective indicators** (the guide says these do not indicate AI) | | | | | | | |
| K1 | Perfect grammar | Skilled human writers also write with perfect grammar. | none quoted | low | none | T2 | S1 |
| K2 | Mixed casual and formal register | A human can mix registers. | none quoted | low | none | T2 | S1 |
| K3 | "Bland" or "robotic" prose | LLM traits are specific, and many readers do not see them as robotic. | none quoted | low | none | T2 | S1 |
| K4 | "Fancy", "academic" or "formal" prose | Only specific words correlate with AI. Formal style as a whole does not. | none quoted | medium: warns against flagging formal science prose | none | T2 | S1 |
| K5 | Transition words in isolation | Humans also open sentences with them. | `Additionally,`, `Consequently,`, `Notably,` | high: supports density mode for Throat | Throat | T2 | S1 |
| K6 | Unsourced content | Many pre-LLM pages lack citations, and modern chatbots add citations. | none quoted | low | none | T2 | S1 |
| K7 | Bizarre or correct wikitext | Odd markup comes from human tools, and correct markup is normal. | none quoted | low | none | T2 | S1 |
| K8 | Letter-like writing and source-assessment requests in isolation | Letters and emails had these forms long before LLMs. | none quoted | medium: cover letters take letter form anyway | none | T2 | S4 |
| **Historical indicators** | | | | | | | |
| L1 | Knowledge-cutoff statements (2022 to 2023) | The model states the date of its last training update. | `Up to my last training update`, `as of my last knowledge update` | high: a footnote in the guide cites a paper on such text in scientific journals | Residue | T2 | S1 |
| L2 | Section summaries | Older models end sections with a recap or a "Conclusion". | `In summary`, `In conclusion`, `Overall` | high: matches recap sentences in Discussion | Recap | T2 | S1 |
| L3 | Prompt refusal | The model declines the task and apologizes. | `as an AI language model`, `as a large language model`, `I cannot offer medical advice, but I can...`, `I'm sorry` | high: chat residue | Residue | T2 | S1 |
| L4 | Overuse of em dashes (2022 to September 2026) | LLM output uses more em dashes than nonprofessional human text, usually with spaces around them. | the em dash (U+2014) with spaces; `---` in LaTeX source | high: the guide says it works best with other signs, and newer models suppress it | Em dash | T2 | S1 |
| L5 | Absence of em dashes (September 2026 on) | The guide says the newest models avoid em dashes and that commas and periods now signal AI. The guide tags this claim "citation needed". | none quoted | low: no pattern to detect, and the claim has no source | none | T2 | S1 |
| L6 | Abrupt cut offs | The text stops in mid-sentence. | text ends after `that automatically` | medium: truncated pasted text, though the guide says the test is not foolproof | none | T2 | S1 |
| L7 | Outdated access-date parameters | Citations carry an access date older than the edit. | none quoted | low | none | T2 | S1 |
| L8 | Lexical diversity and elegant variation | One thing gets several names in a row. | `non-conformist artists`, `like-minded artists`, `these artists` | high: term drift in Methods and Results | none (model check) | T2 | S1 |

Notes on the table. I mapped the tool tags of E7 to E12 and F6 to Residue, the nearest family. They are tags and not phrases, so the definition of Residue in the spec needs one more sentence. Section 6 has no family for Markdown formatting (E1 to E4), reference checks (F1 to F4, F7) or counter-signs (groups J and K). The guide has no sign for the families Colon reveal, Rhetorical question, Repeated openers and Staccato. It lists no figurative load word such as `load-bearing` or `backbone`. It never lists `Importantly,`, `Interestingly,` or `Taken together,`. I searched the full text of S1 for these strings. Figurative is covered only in part by `tapestry`, `landscape` and `testament` in B1. The word `cornerstone` occurs once in S1, inside a quoted ChatGPT citation example, and not as a sign.

## 2. The guide's own warnings

- Lede (S1): "Not all text featuring these indicators is AI-generated".
- Status (S1): the list is "descriptive, not prescriptive", and "it consists of observations, not rules".
- Meaning (S1): "only potential signs of a problem, not the problem itself".
- Fix order (S1): "Please do not merely treat these signs as the problems to be fixed; that could just make detection harder."
- Scope (S1): "some of the signs may be broadly applicable, some may not apply in a non-Wikipedia context". The guide is "less useful for texts which are not informational writing".
- Detectors (S1): "Do not solely rely on artificial intelligence content detection tools". The tools "have non-trivial error rates".
- Human judgment (S1): "Do not rely too much on your own judgment." It cites a 2025 study that found human ability "no better than random chance". It cites a second study with 57% and 64% recognition rates on German theses. It cites a preprint in which expert annotators "correctly identified 90%". The guide did not run these studies, and I did not open them.
- Vocabulary (S1): "One or two of these words appearing in an edit may be coincidental". Many such words in one edit are "one of the strongest tells".
- Synonyms (S1): "a word being overused by AI does not imply that its synonyms are also overused."
- Curly quotes (S1): "Curly quotes alone do not prove LLM use."
- Em dash (S1): "most useful when taken in combination with other indicators, not by itself."
- Markdown (S2): "Markdown alone is not such a strong indicator".
- Tool markup (S2): internal formatting tags are "an unambiguous indicator that the text originated with AI".
- Tool URLs (S1): `utm_source` "near-definitively proves ChatGPT's involvement", yet it "doesn't prove, on its own, that ChatGPT also generated the writing".
- Transitions (S1): isolated transition words are "not a strong tell".
- Formula signs (S1): the challenges sign "is about the rigid formula, not simply the mention of challenges". Permissions gaming "should only be used in one direction".
- Style alone (S4): "Detecting LLM texts on the basis of style alone is not as easy as it seems".
- Probability (S9): the signs "are probabilistic, meaning editors should remain wary of false positives and alternative explanations."
- Project view (S11): "the generated text is often indistinguishable from human text."

## 3. What this source does not show

- The guide measures nothing. It reports no count, rate or precision for any sign. The word boxes carry footnotes that cite measured studies, for example Kobak et al. in Science Advances 2025 and Juzek and Ward. I did not open these papers. The notes on corpus sources must record them as T1.
- The one calculation in the project pages (S9) uses invented figures ("say, 20%") and multiplies them. That step assumes the signs occur independently, and the guide does not test this.
- The first paragraph of S1 names the "most common signs" as of October 2026. It gives no count.
- Signs change. I counted 91 revisions of S1 from 2026-09-24 to 2026-10-23 through the API. The guide says `delve` "dropped off sharply in 2025" and that newer models suppress em dashes. Treat every word list as dated 2026-10-23.
- The guide names models and dates for 2026 (for example GPT-5.6 and GPT-6). I could not check them. The footnotes for the mid-2026 claims are web articles dated September and October 2026.
- The guide targets Wikipedia articles, drafts and talk pages. About half of the rows (groups Markup, Citations, Comment-specific, Edit summaries, Miscellaneous) describe wiki workflow, and I graded most of them low.
- The guide says to fix the deeper problems and not only the signs. A plugin that replaces a sign does not fix an unsupported claim or a made-up reference. The plugin makes no authorship claim (design decision D6).
- Some word boxes hold words with no footnote. In the B1 box, `robust` has none.
- The guide says the items of J3 to J7 were "empirically observed" over 25 years of Wikipedia writing. Only two of the five bullets carry a footnote.
- UNVERIFIED: S1 links to a section "Sudden shift in English variety use". I found no such section in the revision I read. The guide has "Pronounced shift in writing style" instead.
- UNVERIFIED: I did not open the 36 example pages under `Signs of AI writing/Examples`. I did not read the example list of S5, the example blocks of S4 and S6, or the cited papers. I did not open the two external links of S1 (`tropes.fyi/directory` and `canyoupasstheturingtest.com`). The page `Signs of AI writing/Examples` redirects to a category.

## 4. Pages opened

Permalinks use the form `https://en.wikipedia.org/w/index.php?oldid=<revision>`.
- S1 https://en.wikipedia.org/wiki/Wikipedia:Signs_of_AI_writing (revision 1381583419, 2026-10-23T13:57:49Z; full text read)
- S2 https://en.wikipedia.org/wiki/Wikipedia:Signs_of_AI_writing/Markup (revision 1381581413, 2026-10-23T13:38:35Z; full text read, long example lines cut at 700 to 900 characters)
- S3 https://en.wikipedia.org/wiki/Wikipedia:Signs_of_AI_writing/Wikitext_wrapped_in_Markdown_code_blocks_from_chatbots (revision 1379493064, 2026-10-10T09:02:37Z; full text read)
- S4 https://en.wikipedia.org/wiki/Wikipedia:Signs_of_AI_use_in_comments (revision 1381494590, 2026-10-22T22:03:05Z; prose, word boxes and section leads read, examples partly read)
- S5 https://en.wikipedia.org/wiki/Wikipedia:Canned_user_pages (revision 1381379755, 2026-10-22T01:37:15Z; intro, feature headings and feature leads read, example list not read)
- S6 https://en.wikipedia.org/wiki/Wikipedia:Identifying_LLM_unblock_requests (revision 1381430804, 2026-10-22T12:46:29Z; lead and general signs read, examples not read)
- S7 https://en.wikipedia.org/wiki/Wikipedia:The_LLM-written_ANI_report (revision 1355710059, 2026-05-23T12:55:55Z; opening and problem sections read)
- S8 https://en.wikipedia.org/wiki/Wikipedia:Marketing_buzzspeak (revision 1378707943, 2026-10-05T20:12:04Z; full text read; the page is an essay)
- S9 https://en.wikipedia.org/wiki/Wikipedia:WikiProject_AI_Cleanup/Guide_and_resources (revision 1381324783, 2026-10-21T16:51:43Z; the sections on determining LLM text and on detection software read, the rest not read)
- S10 https://en.wikipedia.org/wiki/Signs_of_AI_writing (revision 1380833864, 2026-10-18T06:07:39Z; full text read; this encyclopedia article describes S1 and is context only, with no signs)
- S11 https://en.wikipedia.org/wiki/Wikipedia:WikiProject_AI_Cleanup (revision 1381398955, 2026-10-22T05:14:57Z; UNVERIFIED beyond the headings and one search hit)
- S12 https://en.wikipedia.org/wiki/Wikipedia:WikiProject_AI_Cleanup/Research (revision 1323683105, 2025-11-23T04:55:23Z; skimmed, a reading list with no signs)
- Redirects, not keyed: `Wikipedia:WikiProject AI Cleanup/AI catchphrases` and `.../AI Catchphrases` (both to S1), and `.../Guide` (to S9).

## 5. License

Wikipedia text is available under the Creative Commons Attribution-ShareAlike 4.0 license (CC BY-SA 4.0). The API call `meta=siteinfo&siprop=rightsinfo` returned "Creative Commons Attribution-Share Alike 4.0" with the link `https://creativecommons.org/licenses/by-sa/4.0/deed.en` on 2026-10-23. I did not read the page footer in a browser. The note below is not legal advice.

Consequence for the plugin. The file `patterns.json` copies sign names and short quoted examples of two to ten words. It copies no longer passage, no example block, no guide paragraph and no word box in its original layout. The descriptions in this note use my own words. Each source key resolves to the page URL, so each row credits the Wikipedia contributors. A later change that copies a passage adapts the text. That passage would then need attribution and the same license, and the plugin folder would need a notice.
