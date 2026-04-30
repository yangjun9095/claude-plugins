# Anthropic Science Blog Style Guide

Style derived from three exemplar posts:
- **BioMystery** — *Evaluating Claude For Bioinformatics With BioMysteryBench* — first-person plural, methodology + results, technical-but-accessible
- **Vibe Physics** — *Vibe Physics: The AI Grad Student* — first-person singular, candid, narrative arc with reversals
- **Long-Running Claude** — *How to put long-running Claude to work in HPC environments* — first-person plural, practical methodology, code-heavy

---

## Core principles

1. **Lead with an open question, not an announcement.** The hook frames a real uncertainty, not "we built X".
2. **Punchy section titles with personality.** "Claude loves to please" beats "AI honesty issues". "The Test Oracle" beats "Validation methodology".
3. **First person.** "We" if collaborative, "I" if single-author. Avoid passive voice.
4. **Honest about failures.** Failure modes get their own sections, not a footnote. The "Claude loves to please" section in Vibe Physics is the model.
5. **Figures introduced narratively.** They appear when the argument needs them, with terse one-line captions.
6. **Forward-looking conclusion.** Open questions or a call to action, not a recap.
7. **Short paragraphs, scannable.** ≤4 sentences each.

---

## Structure

| Section | Length | Purpose |
|---------|--------|---------|
| Hook | 2-3 sentences | Frame the open question |
| Setup / Premise | 1-2 paragraphs | What we tried to do, why it mattered |
| 3-6 narrative sections | 200-400 words each | The story with figures inline |
| What didn't work | 1-2 paragraphs | Required. Failure modes are interesting. |
| What's next | 1 paragraph | Open questions, call to action, future work |
| Appendix (optional) | Tables/lists | Numbers, links, full methodology |

Total: 800-2000 words for a typical post.

---

## Voice patterns

### Good hooks (real examples)

- "Almost as soon as large language models could hold a conversation, people started asking how they'd stack up against human experts."
- "Doctors have board exams and lawyers have the bar, but there's no standardized test for becoming a scientist."

### Hedging language (use frequently)

- "We found that..."
- "It appears that..."
- "In our setup..."
- "We can't fully rule out..."
- "Somewhat clunky" (Anthropic's own description of an experiment)

### Figure captions

Terse and informational. Pattern: `Fig N: <one-line statement>`.

- ✅ "Fig 1: Accuracy averaged over 5 trials per 76 human-solvable problems."
- ✅ "The path to sub-percent accuracy over time as the agent worked on the codebase."
- ❌ "Figure 1: This bar chart shows..." (don't say "this chart shows")

---

## Anti-patterns

- ❌ Marketing copy ("revolutionary", "game-changing", "groundbreaking")
- ❌ Bullet-list essays — write prose, not slide notes
- ❌ Recap conclusions ("In summary, we built X and showed Y")
- ❌ Burying failures in an appendix
- ❌ Jargon walls without explanation
- ❌ Vague figure references ("see figure 3" without telling the reader what to notice)

---

## Three skeleton templates

### Template A: BioMystery (we-voice, methodology + results)

1. Hook: open question about AI capability
2. "<Problem domain> is challenging, and so is evaluating it"
3. "Benchmarking models on <X> with <our approach>"
4. "Example tasks/cases" — show concrete instances
5. "Human baselining" — comparison anchor
6. "<Model>'s strategies" — what we observed
7. "What's next" — open invitation

### Template B: Vibe Physics (I-voice, narrative arc)

1. Summary bullet points
2. "Who am I?" — credentials
3. "The hype" — context for why this experiment matters
4. "<Task selection>" — framing the test
5. "Initial steps" — methodology
6. "<First reversal>" — early result, then complication
7. "<Discovery>" — turning point ("Claude loves to please")
8. "The long tail of errors" — failure modes
9. "Lessons" — what worked, what didn't
10. "Conclusions" — implications, philosophical pivot
11. "Epilogue" — impact since publication
12. Appendix: the numbers

### Template C: Long-Running Claude (we-voice, practical methodology)

1. Hook: paradigm framing
2. "The Premise" — problem scope
3. "<Methodology piece 1>" (e.g., "Draft a Plan and Iterate Locally")
4. "<Methodology piece 2>" (e.g., "Memory Across Sessions")
5. "<Methodology piece 3>" (e.g., "The Test Oracle")
6. "<Methodology piece 4>" (e.g., "The Execution Loop")
7. "The Result" — outcome with chart
8. Acknowledgments
9. Conclusion: forward-looking, motivational

---

## When in doubt

- Cut more.
- Quote the conversation if you can.
- Show a figure instead of describing data.
- End the section with a question if you don't have an answer.
