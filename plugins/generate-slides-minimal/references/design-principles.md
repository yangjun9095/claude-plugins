# Design principles

This file distills the four research notes in `references/research-notes/`. Each principle carries a tier and at least one source key. Read the research notes before you cite a rule beyond this file.

## How to read the tiers

Each principle line has one tier tag (`T1`, `T2` or `T3`) and one or more source keys. A key joins the name of a research note and a key of that note, as in `craft:S6`. It resolves to a URL in the section "Pages opened" of that note. The first key of a line names the note that gives the tier. The tag means what that note says it means.

| Research note | T1 | T2 | T3 |
|---|---|---|---|
| `jobs` | Seen in a transcript | Stated by a named expert page | Blog or wiki with no named source |
| `craft` | Controlled study | Named author in a source that the research note opened | Repeated by others, no primary source opened |
| `science` | Controlled study or meta-analysis | Named expert source | Folklore |
| `measurable` | Standard or study | Named source states the number, with no evidence cited | Folklore, derived by the author, or no source |

T1 in `jobs` means that the research note saw the point in a transcript. Do not compare T1 counts between `jobs` and the other research notes.

The controlled tests of slides have limits. Each test changed several features at once, so no study isolates one element (`science:S2`, `science:S3`). The subjects were undergraduates, and no study tests working scientists. The author of the method co-wrote the studies (`science:S10`). One replication missed significance (`science:S4`).

## Talk-level principles

- **Start from one sentence that the audience must keep.** Write the message first and build the talk on it. The slide titles, read in order, state the message. (`T2`; `craft:S6`, `craft:S12`, `science:S26`)
- **Keep one message and at most three take-homes.** Reynolds asks for one core takeaway and one or two more later. (`T2`; `craft:S6`, `craft:S2`)
- **State the need before the finding.** The slide that names the gap comes before the first result. (`T2`; `science:S14`, `science:S26`)
- **Use the rule of three.** Jobs listed three products, three input methods and three stories. The research note saw this in transcripts. Jobs published no slide rules. (`T1`; `jobs:S1`, `jobs:S4`, `jobs:S9`)
- **Open with a surprising number or a short story.** Reynolds, Anderson and Rosling open this way. (`T2`; `craft:S6`, `craft:S2`, `craft:S13`)
- **Tell the talk in three acts, with the audience as the protagonist.** Act 1 states the problem of the audience, act 2 develops it, and act 3 resolves it and asks for a response. (`T2`; `craft:S18`, `craft:S12`, `craft:S2`)
- **Give each number a baseline.** Jobs restated 5 million songs a day as 58 per second. A baseline can be a control, a prior value or chance. (`T1`; `jobs:S1`, `jobs:S3`)
- **Close on the take-homes.** The last content slide restates the message and the ask. The `take_home` layout of this plugin stays on screen during questions. (`T2`; `craft:S6`, `craft:S12`)

## Slide-level principles

- **Put a sentence headline over one visual.** The headline states the claim in one sentence of at most two lines. The visual shows the evidence as a picture, graph, table or diagram. Drop the bullet list. (`T1`; `science:S5`, `science:S2`, `craft:S15`)
- **Give each slide one idea.** One idea and one focal element let a slide pass a glance of three seconds. No opened study tests the glance. (`T2`; `science:S12`, `science:S13`, `craft:S10`)
- **Set a word budget for each slide.** The authors disagree on the number, so the audience profile sets it. (`T2`; `craft:S1`, `craft:S3`, `science:S6`, `science:S12`)
- **Remove decoration.** Delete logos, footers, clip art, 3-D effects and template backgrounds. (`T2`; `craft:S7`, `craft:S14`, `science:S15`, `science:S25`)
- **Label inside the figure.** Put each label next to the curve, bar or point that it names. Use no separate key. (`T2`; `science:S22`, `science:S15`, `science:S27`)
- **Cue the key datum.** Mark the part of the figure that carries the claim with a color, an arrow or an outline. The meta-analysis found r = 0.17 (95% CI 0.11 to 0.22), and the research note read its abstract only. (`T1`; `science:S19`)
- **Put keywords on the slide and speak the full sentence.** In two randomized experiments, identical text hurt recall and transfer. Slightly reworded text did best. (`T1`; `science:S17`, `science:S18`)
- **Keep a number that the audience must recall exactly on the slide.** In one experiment the bullet group recalled secondary statistics better. Primary details were equal. Put the key statistic in the headline or on a label. (`T1`; `science:S3`)
- **Show one chart panel per slide.** Match the form of the chart to the message and explain the axes. Split a multi-panel figure into panels. (`T2`; `science:S12`, `science:S27`)
- **Keep detail off the slide.** Put footnotes and detail in a handout or a separate document. This plugin also uses the speaker notes and backup slides. (`T2`; `craft:S6`, `craft:S7`, `craft:S2`)
- **Keep text legible against its background.** Use a contrast of at least 4.5:1 for text. A ratio of 3:1 is enough for text of 18 pt or more, or bold text of 14 pt or more. (`T1`; `measurable:WCAG-CM`, `measurable:WCAG-DEF`)
- **Use large type.** Opened conference and institute pages ask for body text of 18 to 24 pt. The profile sets the warning size by audience. (`T2`; `measurable:HARV`, `measurable:MSA`, `measurable:UEF`)
- **Describe each picture and chart in alt text.** State in one sentence what the figure shows. (`T2`; `measurable:MSA`)

## Delivery principles

- **Let the speaker notes carry the script.** The slide holds the keywords, and the speaker supplies the explanation. The `notes` rule of the linter warns when more than 80 percent of the slide words appear in the speaker notes. (`T2`; `science:S6`, `science:S12`)
- **Build a complex figure in steps.** Show layers 1 to 3 of one diagram on consecutive slides. This plugin writes no animations, so each step is one slide. (`T2`; `science:S12`, `science:S16`)
- **Plan about one slide per minute.** A talk of 15 minutes has about 15 slides. The note `measurable.md` describes the rate as guidance and found no experiment on it. The note `science.md` calls it opinion. (`T2`; `science:S12`, `science:S13`, `measurable:HARV`, `measurable:NAEGLE`)
- **Rehearse in full, weeks ahead.** Kocienda describes rehearsals that start three weeks to a month before the talk. The sources conflict on whether Jobs used a script. (`T2`; `jobs:S12`, `jobs:S24`)

## Where the authors disagree

Each item gives the positions as the research notes state them, then the choice of this plugin.

- **Text density.** Godin allows at most six words on a slide (`craft:S1`). Alley sits at about 21 words plus one figure (`craft:S15`). Tufte calls a slide of 40 words too thin (`craft:S3`). The profile sets the word budget.
- **Thirty-point type and data slides.** Kawasaki asks for 30 pt (`craft:S22`). That size cannot hold a labelled scatter plot or Tufte's table of 196 numbers. The research note calls this conflict its own inference, because it could not open Kawasaki's page. The profile sets the size floor.
- **Handouts.** Godin says to give nothing at the start and never to print slides (`craft:S1`). Duarte says to send the full document in advance for research findings (`craft:S2`). The plugin keeps detail in notes and backup slides, and the author decides on a handout.
- **Sentence headlines.** Alley requires a sentence headline and a visual on each slide (`craft:S19`). Farkas says that sentence headlines can hinder the speaker. He calls forced visuals often useless and brief bullets harmless (`craft:S16`). The plugin warns about a title that is not a sentence, and it does not block.
- **Slides at all.** Anderson says that many of the best TED speakers use no slides (`craft:S2`). The plugin builds a deck, and the speaker can drop any slide.
- **Rules versus context.** Godin and Kawasaki give hard numbers. Reynolds refuses formulas and ties each choice to the context (`craft:S8`). The plugin labels every threshold with its tier, and a project file can change it.

## Not adopted

- **Hype.** Jobs used words such as "revolutionary" and "works like magic" (`jobs:S1`). Reason: such words fail peer scrutiny, and a data talk has no product to launch.
- **Unsourced numbers.** Jobs gave figures such as "over a quarter billion users" with no source (`jobs:S1`). Reason: reviewers of data need n, uncertainty and a source, so each number on a slide carries a source line.
- **"No bullets, ever".** Gallo states this rule as absolute, and the research note could not test it (`jobs:S10`, `jobs:S11`). Reason: bullets helped recall of secondary statistics in a controlled test (`science:S3`). The linter warns on a list of more than four bullets and does not ban lists.
- **The 30 pt hard rule.** The research note found it in secondary copies only (`craft:S22`). Tier `T3`. Reason: 30 pt cannot hold a labelled data figure, and the pages that the research note opened ask for 18 to 24 pt (`measurable:HARV`, `measurable:UEF`).
- **The "6 by 6" rule.** Reason: the research note found no origin for the 6x6 and 5x5 rules (see the section "Evidence notes" of `measurable.md`).
- **Sparse slides for data.** Tufte says slideware gives 2 percent of the data richness of the tables in a sports section (`jobs:S21`). Reason: peers inspect evidence, so the `peers` profile allows more words than a keynote needs.
- **Nine screens in 70 seconds.** Reynolds counts this pace in a Jobs segment (`jobs:S15`). Reason: Bourne advises at most one visual per minute (`jobs:S28`).
- **"One more thing" as a structure.** Tier `T3`. The phrase is absent from the 2007 iPhone and 1998 iMac transcripts (`jobs:S1`, `jobs:S3`, `jobs:S23`). Reason: the evidence is weak, and a data talk has no reveal.
- **Memory for stories.** Duarte says that people remember stories 22 times more than facts (`craft:S12`). Reason: the research note opened no source for the number and says not to build on it.
