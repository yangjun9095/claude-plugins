# Research notes

Four research notes dated 2026-10-20 support the rules of this plugin. This folder keeps them unchanged.

| File | Topic | Source keys |
|---|---|---|
| `jobs.md` | How Steve Jobs built keynotes | `S1` to `S29` |
| `craft.md` | What the best-known presenters teach | `S1` to `S23` |
| `science.md` | Evidence for slides in scientific talks | `S1` to `S29` |
| `measurable.md` | Measurable rules for a .pptx linter | Names such as `WCAG-CM` |

## How to cite a source

Write the name of the research note, a colon, and the key that the note uses. Examples: `jobs:S1`, `craft:S1`, `science:S1`, `measurable:WCAG-CM`.
Each key resolves to a URL in the "Pages opened" section of its research note.

## Tiers

Each research note gives each of its principles a tier: T1, T2 or T3. The tier has a different meaning in `jobs.md`.

| Research note | T1 | T2 | T3 |
|---|---|---|---|
| `jobs.md` | Seen in a transcript | Stated by a named expert page | Blog or wiki with no named source |
| `craft.md` | Controlled study | Named author in a source that the research note opened | Repeated by others, no primary source opened |
| `science.md` | Controlled study or meta-analysis | Named expert source | Folklore |
| `measurable.md` | Standard or study | Named source states the number, with no evidence cited | Folklore, derived by the author, or no source |

T1 in `jobs.md` means "seen in a transcript". T1 in the other three research notes means a controlled study or a standard.
Do not compare T1 counts between `jobs.md` and the other research notes.

## Limits and edits

Each research note states its own limits. Read them before you cite a rule. UNVERIFIED marks a claim that the research note did not confirm in a source.
Do not edit the research notes. The test `tests/test_manifest.py` records the Secure Hash Algorithm 256 (SHA-256) hash of each file, so an edit fails the test.
