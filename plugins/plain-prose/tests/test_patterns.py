"""Tests for scripts/prose_patterns.py and data/patterns.json. All sentences are made up.

The tests check seven groups of facts.

Schema. Family ids are unique and in the fixed list. A density family has a threshold above
zero. Every regex compiles and none matches the empty string. Every rule has a tier, a severity
and a non-empty list of source keys. The data file holds only ASCII characters. The prose fields
follow the writing rules.

Sources. A key has the form `<note>:S<n>`. It resolves to a line `- S<n> ` in the "Pages
opened" or "Files read" section of the note. No rule cites a key whose line says UNVERIFIED.
A T1 rule cites a corpus key. A T3 rule cites only author keys. The tier of a rule equals the
strongest tier of the keys that it cites. The word of each word rule appears in the row of each
key that the rule cites. The test prints the unresolved keys on failure.

Rules. Each rule that has a regex fires on a seeded sentence. Each rule with `unless` or
`unless_citation` has a sentence that the regex matches and the exception silences. Each option
of each `unless` regex has a pinned sentence, and the test removes each option in turn to check
it. Each entry of each word rule fires on itself.

Clean text. A set of plain sentences stays quiet in all families. It holds function words,
ordinary science words, plain biology roles and the plain forms of the exceptions. The words that
the research report left out are in no word rule. No rule matches a K9 word of the corpus note
unless an author key backs the rule. A table of 88 ordinary and risky sentences pins the
decided outcome of each.

Words. The notation `delv*` means a stem with any ending. A plain entry means that exact word.
The flag `lower_only` makes the first letter lower case.

Loader. A bad data file raises PatternError, and the message names the family id and the rule
label. The messages list the valid choices. The new rule and params fields are checked.

Project file. Each key works, including `disable_labels`. A typo in a family id raises
PatternError with the id in the message. An override that changes nothing raises PatternError.
An extra pattern gets tier T3 and the source key `project:<file name>`. A bad regex names the
pattern. `find_project_file` searches `./`, `docs/` and `.claude/` in that order.
"""
import copy
import json
import os
import re
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
PLUGIN_DIR = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(PLUGIN_DIR, "scripts"))

import prose_patterns as pp  # noqa: E402

DATA_PATH = os.path.join(PLUGIN_DIR, "data", "patterns.json")
NOTES_DIR = os.path.join(PLUGIN_DIR, "references", "research-notes")
NOTE_NAMES = ("corpus", "wikipedia", "guides", "authors", "craft")
OPEN, CLOSE = "\ue000", "\ue001"
CITE = OPEN + "0" + CLOSE

FAMILY_IDS = [
    "vocabulary-excess", "vocabulary-density", "figurative-load", "binary-contrast",
    "importance-puffery", "participial-benefit", "weasel-attribution", "fake-strong-verb",
    "throat-clearing", "recap-opener", "em-dash", "colon-reveal", "rhetorical-question",
    "assistant-residue", "hedge-stack", "repeated-openers", "staccato-run",
]
STRUCTURAL = {
    "rhetorical-question": "question_answer",
    "repeated-openers": "repeated_openers",
    "staccato-run": "staccato",
}
VOCABULARY_FAMILIES = ("vocabulary-excess", "vocabulary-density")
TIER_RANK = {"T1": 1, "T2": 2, "T3": 3}
FUNCTION_WORDS = ("within", "across", "while", "these", "this", "particularly", "potential",
                  "findings", "like", "into")
ORDINARY_WORDS = ("holds", "stands", "poses", "involves", "serves", "reveals", "challenges",
                  "strategies", "approach")
# Words that the research report left out on purpose. Each has a plain sense in a manuscript or a technical use.
LEFT_OUT_WORDS = (
    "notable", "significant", "offer", "offers", "explore", "explores", "exhibit", "exhibits", "exhibited", "employ",
    "employs", "employed", "elucidate", "elucidates", "enhance", "enhanced", "enhancing", "enhancer", "align", "aligns",
    "aligned", "encompass", "encompasses", "emphasize", "emphasizes", "emphasizing", "highlight", "highlights",
    "pinpoint", "discern", "heightened", "consolidate", "encapsulate", "illuminate", "delineate", "exacerbate",
    "gauge", "shedding", "foundational", "pioneer", "pioneers", "conversely", "interplay", "spanning", "unravel",
    "advocating", "emerges", "thus", "moreover", "furthermore", "causal", "empirical", "correlate", "prioritize",
    "quietly", "universally", "demonstrated", "provide", "provides", "indicate", "indicates", "suggest", "suggests",
    "novel", "unique", "diverse", "primarily", "thereby", "substantial", "evolving", "ultimately",
)

PATTERNS = pp.load_patterns()


def hits(family, sentence):
    """Return the labels of the rules of the family that fire on the sentence.

    A sentence that holds a placeholder counts as a sentence with a citation.
    """
    if isinstance(family, str):
        family = PATTERNS.family(family)
    cited = OPEN in sentence
    return [rule.label for rule in family.rules if rule.fires(sentence, cited)]


def all_hits(sentence):
    """Return (family id, label) for every rule of every family that flags the sentence."""
    found = []
    for family in PATTERNS.families:
        for label in hits(family, sentence):
            found.append((family.id, label))
    return found


def family_of(label):
    """Return the id of the vocabulary family that holds the rule with this label."""
    for family_id in VOCABULARY_FAMILIES:
        if any(rule.label == label for rule in PATTERNS.family(family_id).rules):
            return family_id
    raise KeyError(label)


def rule_of(family_id, label):
    for rule in PATTERNS.family(family_id).rules:
        if rule.label == label:
            return rule
    raise KeyError("no rule %r in family %r" % (label, family_id))


# ---------------------------------------------------------------------------------------
# Reading the research notes
# ---------------------------------------------------------------------------------------

def read_note(name):
    with open(os.path.join(NOTES_DIR, name + ".md"), encoding="utf-8") as handle:
        return handle.read()


def source_lines(name):
    """Return {n: line} for the lines `- S<n> ` of the section "Pages opened" or "Files read"."""
    found, inside = {}, False
    for line in read_note(name).split("\n"):
        if line.startswith("## "):
            inside = "Pages opened" in line or "Files read" in line
            continue
        if inside:
            match = re.match(r"^- S([1-9][0-9]*) ", line)
            if match:
                found[int(match.group(1))] = line
    return found


def split_row(line):
    """Split a table row at the bars that are not written as \\|."""
    cells, current, i = [], "", 1
    while i < len(line):
        if line[i] == "\\" and line[i + 1:i + 2] == "|":
            current += "\\|"
            i += 2
            continue
        if line[i] == "|":
            cells.append(current.strip())
            current = ""
        else:
            current += line[i]
        i += 1
    return cells


def note_rows(name):
    rows = []
    for line in read_note(name).split("\n"):
        if line.startswith("|") and not re.match(r"^\|[-| ]+\|$", line.strip()):
            rows.append(split_row(line.strip()))
    return rows


def key_numbers(cell):
    return [int(n) for n in re.findall(r"\bS([1-9][0-9]*)\b", cell)]


KEY_COLUMN = {"corpus": 4, "wikipedia": 7, "guides": 5, "authors": 3}


def rows_citing(note, number):
    """Return the text of each table row of the note that cites S<number>."""
    texts = []
    for cells in note_rows(note):
        column = KEY_COLUMN.get(note)
        if column is not None:
            if len(cells) > column and number in key_numbers(cells[column]):
                texts.append(" ".join(cells))
        elif number in key_numbers(" ".join(cells)):
            texts.append(" ".join(cells))
    return texts


def _split_key(key):
    note, _, number = key.partition(":S")
    return note, int(number)


def word_row_regex(entry):
    """Return a regex for an entry of a word rule, as it would appear in a row of a note."""
    stem = entry.endswith("*")
    raw = entry[:-1] if stem else entry
    raw = re.sub(r"i[sz]$", "iSZ", raw)
    body = re.escape(raw).replace(r"\-", "[- ]").replace(r"\ ", "[- ]").replace("iSZ", "i[sz]")
    return re.compile(r"\b" + body + (r"\w*" if stem else r"\b"), re.I)


def key_tiers():
    """Return {"note:S<n>": strongest tier of the rows of the note that cite the key}.

    The notes keep the tier of a row in a column of their tables. The author keys all have T3.
    The craft note has no tier column, so its keys count as T2.
    """
    tiers = {}

    def add(note, numbers, tier):
        tier = {"T3*": "T3"}.get(tier, tier)
        if tier not in TIER_RANK:
            return
        for number in numbers:
            key = "%s:S%d" % (note, number)
            if key not in tiers or TIER_RANK[tier] < TIER_RANK[tiers[key]]:
                tiers[key] = tier

    for cells in note_rows("corpus"):
        if len(cells) >= 5 and cells[0] != "ID":
            add("corpus", key_numbers(cells[4]), cells[3])
    for cells in note_rows("wikipedia"):
        if len(cells) >= 8 and cells[0] != "ID":
            add("wikipedia", key_numbers(cells[7]), cells[6])
    for cells in note_rows("guides"):
        if len(cells) >= 7 and cells[0] != "ID":
            add("guides", key_numbers(cells[5]), cells[4])
    for cells in note_rows("authors"):
        if len(cells) >= 7 and re.match(r"^[A-Z][0-9][0-9]$", cells[0]):
            add("authors", key_numbers(cells[3]), "T3")
    for number in source_lines("craft"):
        tiers["craft:S%d" % number] = "T2"
    for number in source_lines("authors"):
        tiers.setdefault("authors:S%d" % number, "T3")
    for number in source_lines("corpus"):
        tiers.setdefault("corpus:S%d" % number, "T1")
    for number in source_lines("wikipedia"):
        tiers.setdefault("wikipedia:S%d" % number, "T2")
    for number in source_lines("guides"):
        tiers.setdefault("guides:S%d" % number, "T2")
    return tiers


CRAFT_FAMILY_IDS = {
    "Vocabulary with measured excess": "vocabulary-excess",
    "Figurative load words": "figurative-load",
    "Binary contrast": "binary-contrast",
    "Importance puffery": "importance-puffery",
    "Trailing participial benefit clause": "participial-benefit",
    "Weasel attribution": "weasel-attribution",
    "Fake-strong verbs": "fake-strong-verb",
    "Throat-clearing and signposting": "throat-clearing",
    "Recap openers": "recap-opener",
    "Em dash": "em-dash",
    "Colon reveal": "colon-reveal",
    "Rhetorical question answered at once": "rhetorical-question",
    "Assistant residue": "assistant-residue",
    "Repeated sentence openers": "repeated-openers",
    "Staccato run": "staccato-run",
}


# Before-sentences of the craft note that the data no longer flags. The craft note shows a role
# statement from biology here, and the review of the data decided to leave such sentences quiet.
CRAFT_BEFORE_QUIET = {"The Marlin-2 promoter serves as a binding site for Tavo."}


def craft_examples():
    """Return (family id, before, after) for each made-up example of section 3 of the craft note."""
    found = []
    for cells in note_rows("craft"):
        if len(cells) == 3 and cells[0] in CRAFT_FAMILY_IDS and cells[1].startswith("`"):
            spans = [re.match(r"`(.*?)`", cell).group(1).replace("&mdash;", "\u2014") for cell in cells[1:]]
            found.append((CRAFT_FAMILY_IDS[cells[0]], spans[0], spans[1]))
    return found


def k9_words():
    for cells in note_rows("corpus"):
        if cells and cells[0] == "K9":
            return [word.strip() for word in cells[1].split(",")]
    raise AssertionError("row K9 of corpus.md not found")


def all_rules():
    for family in PATTERNS.families:
        for rule in family.rules:
            yield family, rule


# ---------------------------------------------------------------------------------------
# Seeded sentences (made-up science text)
# ---------------------------------------------------------------------------------------

# (family id, label, sentence): the rule must flag the sentence. Each rule that has a regex
# needs at least one entry. Entries for word rules are extra.
FIRES = [
    ("vocabulary-excess", "delve", "Here we delve into how Marlin-2 expression changes after heat shock (n = 24 plants)."),
    ("vocabulary-excess", "underscore", "The assay underscores the intricate link between dose and response (Fig. 2)."),
    ("vocabulary-excess", "intricate", "The assay underscores the intricate link between dose and response (Fig. 2)."),
    ("vocabulary-excess", "meticulous", "Samples were handled meticulously at every step."),
    ("vocabulary-excess", "realm", "The paper opens a new realm of antiviral design."),
    ("vocabulary-density", "leverage", "We leverage a large library of variants."),
    ("vocabulary-excess", "harness", "We harness the signal from the sensor array."),
    ("vocabulary-excess", "harness", "The method can effectively harness read depth."),
    ("vocabulary-excess", "harness", "The method harnessed the full read depth."),
    ("vocabulary-density", "elevate", "The result elevates the study of root growth."),
    ("vocabulary-density", "crucial", "A crucial control was missing."),
    ("vocabulary-excess", "testament", "The archive is a testament to decades of sampling."),
    ("vocabulary-density", "utilize", "We utilize a standard buffer."),
    ("vocabulary-density", "robust", "A robust framework for growth analysis follows."),
    ("vocabulary-excess", "pivotal", "This is a pivotal moment for the field."),
    ("vocabulary-density", "foster", "The program fosters collaboration."),
    ("vocabulary-density", "foster", "We foster growth."),
    ("vocabulary-density", "paradigm", "This is a new paradigm."),
    ("vocabulary-density", "streamline", "We streamline the work."),
    ("vocabulary-density", "valuable", "The maps are a valuable resource for the field."),
    ("vocabulary-density", "intersection", "The tool works at the intersection of imaging and statistics."),
    ("figurative-load", "load-bearing", "This result is load-bearing for our argument that Marlin-2 acts upstream of Tavo."),
    ("figurative-load", "tapestry", "Tavo mutants weave a tapestry of phenotypes across the six tissues we examined."),
    ("figurative-load", "landscape", "The study maps the landscape of root growth."),
    ("figurative-load", "backbone", "The pipeline is the backbone of our analysis."),
    ("figurative-load", "cornerstone", "Imaging is a cornerstone of the method."),
    ("figurative-load", "ecosystem", "The tool joins a wider software ecosystem."),
    ("figurative-load", "ecosystem", "The software ecosystem needs a new driver."),
    ("figurative-load", "game-changer", "The kit is a game-changer for field work."),
    ("figurative-load", "deep dive", "The next section is a deep dive into the assay."),
    ("figurative-load", "lean into", "We lean into the noise of the data."),
    ("figurative-load", "lean into", "The paper leans into the noise of the data."),
    ("figurative-load", "lean into", "The authors leaned into the noise of the data."),
    ("figurative-load", "lean into", "The authors are leaning into the noise of the data."),
    ("binary-contrast", "not just X but Y", "The delay is not just a technical artifact but a property of the cell cycle."),
    ("binary-contrast", "not just X but Y", "The mutation doesn't just slow growth; it alters the cell cycle."),
    ("binary-contrast", "not just X but Y", "It is not just a feature, it's a shift."),
    ("binary-contrast", "not only X but also Y", "The assay captures not only growth but also death in each line."),
    ("binary-contrast", "is not X, it is Y", "The delay is not an artifact, it is a property of the cell cycle."),
    ("binary-contrast", "is not X; it is Y", "The delay isn't an artifact; it is a property of the cell cycle."),
    ("binary-contrast", "is not X; it is Y", "These cells are not stem cells; they are committed progenitors."),
    ("binary-contrast", "is not X; it is Y", "The mutation is not lethal; it is viable in the homozygous state."),
    ("binary-contrast", "is not X; it is Y", "It's not a technical artifact; it's a property of the cell cycle."),
    ("binary-contrast", "it's not X, it's Y", "It's not a technical artifact, it's a property of the cell cycle."),
    ("binary-contrast", "it's not X, it's Y", "It\u2019s not a technical artifact, it\u2019s a property of the cell cycle."),
    ("binary-contrast", "is not a X but a Y", "The delay is not a technical artifact but a property of the cell cycle."),
    ("binary-contrast", "less about X, more about Y", "The effect of Marlin-2 on growth is less about nutrient uptake and more about cell wall remodeling."),
    ("binary-contrast", "less about X, more about Y", "The tool is less a library, more a language."),
    ("binary-contrast", "a X, not a Y", "Marlin-2 is a switch, not a dial."),
    ("binary-contrast", "Not a X.", "Not a technical artifact."),
    ("binary-contrast", "not because X, but because Y", "The cells died not because the dose was high, but because the exposure was long."),
    ("binary-contrast", "no X, no Y, just Z", "No pellet, no supernatant, just a thin film."),
    ("binary-contrast", "prioritizing X rather than Y", "The protocol, prioritizing depth rather than breadth, used 12 samples."),
    ("binary-contrast", "does not mean X, it means Y", "This does not mean the effect is weak; it means the assay is noisy."),
    ("binary-contrast", "not mainly about X", "This isn't mainly about growth."),
    ("binary-contrast", "not mainly about X", "I'm not saying the effect is large, but it is real."),
    ("binary-contrast", "is not X; rather, it is Y", "The delay is not an artifact; rather, it is a property of the cell cycle."),
    ("importance-puffery", "stands as a testament", "Our 18-year record of weekly samples (n = 936) stands as a testament to the value of long-term monitoring."),
    ("importance-puffery", "stands as a testament", "The result is a testament to the team."),
    ("importance-puffery", "stands as a testament", "The map serves as a reminder that sampling matters."),
    ("importance-puffery", "plays a pivotal role", "Survival under drought fell from 81% to 34% in the mutant (n = 60 per genotype). Marlin-2 therefore plays a pivotal role in drought tolerance."),
    ("importance-puffery", "plays a pivotal role", "Marlin-2 played a crucial role in the response."),
    ("importance-puffery", "plays a key role", "Tavo plays a key role in growth."),
    ("importance-puffery", "plays a key role", "Marlin-2 plays a significant role in the response."),
    ("importance-puffery", "marks a turning point", "This result marks a turning point for the field."),
    ("importance-puffery", "solidifies its position", "The study solidifies its position as the reference."),
    ("importance-puffery", "underscores its importance", "The assay underscores its importance for diagnosis."),
    ("importance-puffery", "underscores its importance", "The survey highlights the significance of long records."),
    ("importance-puffery", "sets the stage", "The map is a first step, setting the stage for later work."),
    ("importance-puffery", "sets the stage", "This pattern reflects broader trends in growth."),
    ("importance-puffery", "sets the stage", "The work enters an evolving landscape of methods."),
    ("importance-puffery", "sets the stage", "The record left an indelible mark on the field."),
    ("importance-puffery", "focal point", "The focal point of the discussion is the decay rate."),
    ("importance-puffery", "deeply rooted", "The belief is deeply rooted in the field."),
    ("importance-puffery", "promotional words", "The lab is nestled among many sites."),
    ("importance-puffery", "promotional words", "The panel covers a diverse array of species."),
    ("importance-puffery", "promotional words", "The tool exemplifies the trend."),
    ("importance-puffery", "high stakes", "The stakes are high for every patient."),
    ("importance-puffery", "high stakes", "The implications are significant."),
    ("importance-puffery", "bright future", "The future looks bright for this method."),
    ("importance-puffery", "despite challenges", "Despite these challenges, the field continues to thrive."),
    ("participial-benefit", "mild participial clause", "Cells were sorted by flow cytometry, yielding 94% pure populations (Fig. 1B)."),
    ("participial-benefit", "trailing participial clause", "The model was trained on 12,000 images, ensuring reproducibility across sites."),
    ("participial-benefit", "mild participial clause", "The tool logs each step, making it easier to debug."),
    ("participial-benefit", "mild participial clause", "The tank was drained daily, allowing fresh medium to enter."),
    ("participial-benefit", "mild participial clause", "Expression peaked at day 3, reflecting the timing of germination."),
    ("participial-benefit", "mild participial clause", "The sequence was codon-optimized, enhancing expression in yeast."),
    ("participial-benefit", "mild participial clause", "The kit is sold in sets of four, enabling parallel runs."),
    ("participial-benefit", "mild participial clause", "The work covers six sites, contributing to a wider map."),
    ("participial-benefit", "trailing participial clause", "The new assay is fast, paving the way for screens."),
    ("participial-benefit", "trailing participial clause", "Each model is a mean over runs, underscoring the stability of the fit."),
    ("participial-benefit", "trailing participial clause", "Each tissue is shown, emphasizing the range of the data."),
    ("participial-benefit", "trailing participial clause", "The curve is flat, highlighting the limit of the assay."),
    ("participial-benefit", "trailing participial clause", "The panel is wide, showcasing the range of the data."),
    ("participial-benefit", "valuable insights", "The data give valuable insights into growth."),
    ("weasel-attribution", "studies show", "Studies show that Marlin-2 is expressed in the root."),
    ("weasel-attribution", "studies show", "Experts agree that sample size limits the precision of the estimate."),
    ("weasel-attribution", "studies show", "Researchers have shown that the pathway is conserved."),
    ("weasel-attribution", "many argue", "Many argue that the effect is small."),
    ("weasel-attribution", "many argue", "The method is widely regarded as the reference."),
    ("weasel-attribution", "industry reports", "Industry reports suggest that the market is growing."),
    ("weasel-attribution", "industry reports", "Several sources describe the same limit."),
    ("weasel-attribution", "research suggests", "Research suggests that the effect is small."),
    ("weasel-attribution", "studies show", "Studies have shown a link between dose and growth."),
    ("weasel-attribution", "vague quantity", "Most researchers use this assay."),
    ("weasel-attribution", "vague quantity", "About 40% of cases improved."),
    ("fake-strong-verb", "stands as a", "Figure 3 stands as a summary of the three assays."),
    ("fake-strong-verb", "stands as a", "The result stood as a record for ten years."),
    ("fake-strong-verb", "serves as praise", "The archive serves as a testament to careful sampling."),
    ("fake-strong-verb", "serves as praise", "The map acts as a powerful reminder of the gap."),
    ("fake-strong-verb", "serves as praise", "The tool functions as a cornerstone of the pipeline."),
    ("fake-strong-verb", "serves as praise", "Tavo serves as a critical checkpoint for growth."),
    ("fake-strong-verb", "serves as praise", "The study operates as a blueprint for later work."),
    ("fake-strong-verb", "serves as a figure", "The model serves as a bridge between the two fields."),
    ("fake-strong-verb", "serves as a figure", "Figure 3 acts as an illustration of the three assays."),
    ("throat-clearing", "it is worth noting that", "It is worth noting that survival fell from 81% to 34% in the mutant."),
    ("throat-clearing", "it is worth noting that", "It's important to remember that the sample was small."),
    ("throat-clearing", "it is worth noting that", "It is crucial to differentiate the two cases."),
    ("throat-clearing", "sentence adverb", "Interestingly, the mutant grew faster."),
    ("throat-clearing", "sentence adverb", "Notably, the effect held in both sexes."),
    ("throat-clearing", "sentence adverb", "The mutant grew slowly. Essentially, the cells stopped dividing."),
    ("throat-clearing", "Importantly,", "Importantly, the effect held in both sexes."),
    ("throat-clearing", "stock opener", "At its core, the method counts reads."),
    ("throat-clearing", "stock opener", "When it comes to growth, the mutant lags."),
    ("throat-clearing", "stock opener", "Going forward, we will add more lines."),
    ("throat-clearing", "in this article", "In this article, we describe the cohort."),
    ("throat-clearing", "chatty opener", "Let's dive into the data."),
    ("throat-clearing", "chatty opener", "Here's the thing: the assay is noisy."),
    ("throat-clearing", "chatty opener", "It turns out that the mutant is stable."),
    ("throat-clearing", "in this section, we", "In this section, we describe how the cohorts were recruited."),
    ("throat-clearing", "on the one hand", "On the one hand the mutant grows slowly, and on the other hand it survives."),
    ("recap-opener", "recap opener", "Overall, these data suggest that Marlin-2 limits root growth."),
    ("recap-opener", "recap opener", "Taken together, Marlin-2 limited root growth in all four lines."),
    ("recap-opener", "recap opener", "In summary, the mutant grows slowly."),
    ("recap-opener", "recap opener", "In conclusion, the mutant grows slowly."),
    ("recap-opener", "recap opener", "The mutant grew slowly. Ultimately, Marlin-2 limits growth."),
    ("em-dash", "em dash", "The mutant \u2014 which lacks the C-terminal domain \u2014 grows slowly."),
    ("em-dash", "em dash", "Growth slowed at day 3---and the effect was larger in the mutant."),
    ("em-dash", "spaced dash", "The mutant -- which lacks the C-terminal domain -- grows slowly."),
    ("em-dash", "spaced dash", "The mutant \u2013 which lacks the C-terminal domain \u2013 grows slowly."),
    ("em-dash", "spaced dash", "Growth slowed at day 3 -- and the effect was larger in the mutant."),
    ("colon-reveal", "The X is Y: z", "The answer is simple: the mutant grows slowly."),
    ("colon-reveal", "The X is Y: z", "The result was clear: Marlin-2 limits root growth."),
    ("colon-reveal", "found one reason", "We found one explanation: the mutant lacks the C-terminal domain."),
    ("assistant-residue", "chat opener", "Certainly!"),
    ("assistant-residue", "chat opener", "I hope this helps."),
    ("assistant-residue", "chat opener", "Would you like me to shorten it?"),
    ("assistant-residue", "here is the revised", "Here is the revised paragraph: Survival fell from 81% to 34%."),
    ("assistant-residue", "as an AI", "As an AI language model, I cannot verify these values."),
    ("assistant-residue", "refusal", "I cannot verify these values."),
    ("assistant-residue", "refusal", "I'm sorry, but I cannot access the file."),
    ("assistant-residue", "knowledge cutoff", "As of my last training update, the value was unknown."),
    ("assistant-residue", "draft marker", "Delete this section before submission."),
    ("assistant-residue", "draft marker", "Regenerate response."),
    ("assistant-residue", "chat label", "You said: write a summary."),
    ("assistant-residue", "tool marker", "The effect was large contentReference[oaicite:0]{index=0}."),
    ("assistant-residue", "tool marker", "The effect was large [cite: 1]."),
    ("assistant-residue", "tool marker", "The effect was large [web:1]."),
    ("assistant-residue", "placeholder", "Dear [Your Name], thank you for the review."),
    ("assistant-residue", "placeholder", "The sample was taken on 2025-XX-XX."),
    ("assistant-residue", "placeholder", "Insert Table 1 here."),
    ("assistant-residue", "source gap", "While specific details are limited, the effect seems large."),
    ("assistant-residue", "source gap", "The effect is small, based on the provided search results."),
    ("assistant-residue", "sycophancy", "Great question! The answer follows."),
    ("assistant-residue", "sycophancy", "You're absolutely right about the control."),
    ("assistant-residue", "meta-narration", "Let me analyze this before I answer."),
    ("hedge-stack", "modal and adverb", "These data may potentially explain the delay."),
    ("hedge-stack", "modal and adverb", "The effect could possibly be larger."),
    ("hedge-stack", "modal and adverb", "The effect possibly could explain the delay."),
    ("hedge-stack", "modal and adverb", "It seems likely that perhaps the mutant is unstable."),
]

# (family id, label, kind, sentence): the regex of the rule matches the sentence and the
# exception silences it. kind "unless" means the `unless` regex does it. kind "citation" means
# the placeholder does it. Each rule with `unless` needs a "unless" entry and each rule with
# `unless_citation` needs a "citation" entry.
EXCEPTIONS = [
    ("vocabulary-excess", "underscore", "unless", "Replace each underscore character in the filename with a hyphen."),
    ("vocabulary-excess", "realm", "unless", "The virus belongs to the realm Riboviria in the ICTV scheme."),
    ("vocabulary-excess", "pivotal", "unless", "The pivotal trial enrolled 200 patients."),
    ("vocabulary-excess", "pivotal", "unless", "The pivotal Phase 3 trial of the inhibitor enrolled 412 patients at 38 sites."),
    ("vocabulary-density", "comprehensive", "unless", "Lipids were separated by comprehensive two-dimensional gas chromatography."),
    ("vocabulary-density", "robust", "unless", "We fitted robust regression to the counts."),
    ("vocabulary-density", "robust", "unless", "The estimate is robust to outliers."),
    ("vocabulary-density", "robust", "unless", "Network robustness fell after the knockout."),
    ("vocabulary-density", "robust", "unless", "An additional robustness check gave the same result."),
    ("vocabulary-excess", "seamless", "unless", "We used seamless cloning to fuse the two fragments."),
    ("vocabulary-density", "leverage", "unless", "Points with high leverage were removed from the fit."),
    ("vocabulary-density", "leverage", "unless", "The leverage scores of the rows are in Table 2."),
    ("vocabulary-excess", "harness", "unless", "The test harnesses were calibrated before each run."),
    ("vocabulary-density", "utilize", "unless", "Glucose utilization rose in the mutant."),
    ("vocabulary-density", "unlock", "unless", "The unlocked nucleic acid probe bound the target."),
    ("vocabulary-density", "elevate", "unless", "Heat stress elevates calcium levels in the root."),
    ("vocabulary-excess", "empower", "unless", "Peaks were integrated in Empower 3 software."),
    ("vocabulary-excess", "myriad", "unless", "Myriad Genetics supplied the assay."),
    ("vocabulary-density", "synergy", "unless", "Synergy was scored with the Bliss model."),
    ("vocabulary-density", "streamline", "unless", "The streamlines of the flow field were plotted."),
    ("vocabulary-density", "streamline", "unless",
     "Above 6 cm per second, the streamlines broke into eddies that trailed behind the case."),
    ("vocabulary-density", "navigate", "unless", "Mice navigate the maze in a few minutes."),
    ("vocabulary-density", "facilitate", "unless", "Facilitated diffusion moves glucose across the membrane."),
    ("vocabulary-density", "foster", "unless", "Pups were cross-fostered to a foster dam at birth."),
    ("vocabulary-density", "foster", "unless", "Pups fostered within their own line gained a similar weight."),
    ("vocabulary-density", "foster", "unless", "Litters were fostered to a dam of the other line."),
    ("vocabulary-density", "paradigm", "unless", "Mice learned the task in a conditioning paradigm."),
    ("vocabulary-density", "paradigm", "unless", "In the open-field paradigm, a mouse is placed in a square arena."),
    ("vocabulary-excess", "transformative", "unless", "The grant came from the Transformative Research program."),
    ("vocabulary-excess", "state-of-the-art", "citation", "The method outperforms state-of-the-art tools " + CITE + "."),
    ("vocabulary-excess", "state-of-the-art", "unless", "The method reaches SOTA on state-of-the-art benchmarks."),
    ("vocabulary-density", "vital", "unless", "Vital signs were recorded every hour."),
    ("vocabulary-excess", "beacon", "unless", "A molecular beacon reports the cleavage."),
    ("vocabulary-excess", "supercharge", "unless", "The supercharged GFP resists aggregation."),
    ("figurative-load", "load-bearing", "unless", "The load-bearing bone of the limb is the femur."),
    ("figurative-load", "backbone", "unless", "The peptide backbone adopts a helical fold."),
    ("figurative-load", "backbone", "unless", "A ResNet backbone extracts features from each image."),
    ("figurative-load", "tapestry", "unless", "Tapestri profiling captured 5,000 cells."),
    ("figurative-load", "landscape", "unless", "Species richness shaped the landscape of the reserve."),
    ("figurative-load", "landscape", "unless", "The fitness landscape had two peaks."),
    ("figurative-load", "landscape", "unless", "We mapped the mutants to ask how rugged the local landscape is."),
    ("figurative-load", "ecosystem", "unless", "The marine ecosystem warmed by two degrees."),
    ("figurative-load", "ecosystem", "unless", "Plastic waste builds up in lake ecosystems."),
    ("binary-contrast", "is not X, it is Y", "unless", "The protein is not secreted, it is retained in the cell (p < 0.05)."),
    ("binary-contrast", "is not X, it is Y", "unless", "The protein is not secreted, it is retained in the cell (Fig. 2)."),
    ("binary-contrast", "is not X, it is Y", "unless", "The protein is not secreted, it is retained in the cell (n = 12)."),
    ("binary-contrast", "is not X, it is Y", "citation", "The protein is not secreted, it is retained in the cell " + CITE + "."),
    ("binary-contrast", "it's not X, it's Y", "unless", "It's not secreted, it's retained in the cell (Table 2)."),
    ("binary-contrast", "it's not X, it's Y", "citation", "It's not secreted, it's retained in the cell " + CITE + "."),
    ("binary-contrast", "is not X; it is Y", "unless", "The protein is not secreted; it is retained in the cell (p < 0.05)."),
    ("binary-contrast", "is not X; it is Y", "citation", "The protein is not secreted; it is retained in the cell " + CITE + "."),
    ("binary-contrast", "Not a X.", "unless", "Not a single mouse survived."),
    ("importance-puffery", "stands as a testament", "citation", "The record stands as a testament to long sampling " + CITE + "."),
    ("importance-puffery", "plays a pivotal role", "citation", "Marlin-2 plays a pivotal role in growth " + CITE + "."),
    ("importance-puffery", "plays a key role", "citation", "Marlin-2 plays a key role in growth " + CITE + "."),
    ("importance-puffery", "marks a turning point", "citation", "This result marks a turning point " + CITE + "."),
    ("importance-puffery", "solidifies its position", "citation", "The study solidifies its position " + CITE + "."),
    ("importance-puffery", "underscores its importance", "citation", "The assay underscores its importance " + CITE + "."),
    ("importance-puffery", "focal point", "unless", "The beam reached its focal point inside the sample chamber."),
    ("importance-puffery", "deeply rooted", "unless", "The deeply rooted lineages share one ancestor."),
    ("participial-benefit", "trailing participial clause", "unless", "Protein loading was checked, ensuring equal loading by a protein assay."),
    ("weasel-attribution", "studies show", "citation", "Studies show that Marlin-2 is expressed in the root " + CITE + "."),
    ("weasel-attribution", "many argue", "citation", "Many argue that the effect is small " + CITE + "."),
    ("weasel-attribution", "industry reports", "citation", "Industry reports suggest growth " + CITE + "."),
    ("weasel-attribution", "research suggests", "citation", "Research suggests that the effect is small " + CITE + "."),
    ("weasel-attribution", "vague quantity", "citation", "Most researchers use this assay " + CITE + "."),
    ("weasel-attribution", "vague quantity", "unless", "About 40% of cases improved (Fig. 2)."),
    ("weasel-attribution", "vague quantity", "unless", "Most researchers in the survey used this assay (n = 30 labs)."),
    ("assistant-residue", "sycophancy", "unless", "We thank the reviewer for this excellent catch."),
]

# (family id, label, sentence): the rule must stay quiet. The regex alone may not match.
QUIET = [
    ("weasel-attribution", "studies show", "These studies show a dose response."),
    ("weasel-attribution", "studies show", "The researchers say the sample was small."),
    ("throat-clearing", "in this article", "In this Article, we describe the cohort."),
    ("recap-opener", "recap opener", "Overall survival was 80% at 12 months."),
    ("em-dash", "em dash", "Growth rose from 10--20 mm."),
    ("em-dash", "em dash", "The rule has four hyphens: ----."),
    ("em-dash", "spaced dash", "Days 3 \u2013 5 were skipped."),
    ("em-dash", "spaced dash", "Pages 10 -- 20 hold the table."),
    ("colon-reveal", "found one reason", "We found three genes: Tavo, Marlin-2 and Vero."),
    ("colon-reveal", "The X is Y: z", "The samples were processed in three steps: lysis, digestion and cleanup."),
    ("colon-reveal", "The X is Y: z", "The strains were grown on three media: lysogeny broth, minimal medium and yeast extract."),
    ("colon-reveal", "The X is Y: z", "The primers were: forward, reverse and a probe."),
    ("colon-reveal", "The X is Y: z", "The results are: Marlin-2 rose and Tavo fell."),
    ("colon-reveal", "The X is Y: z", "The result for group A: 12 cells arrested."),
    ("colon-reveal", "The X is Y: z", "The result for the second group: 12 cells arrested."),
    ("colon-reveal", "The X is Y: z", "The samples were then processed in three steps: lysis, digestion and cleanup."),
    ("colon-reveal", "found one reason", "We observed three differences: size, shape and colour."),
    ("colon-reveal", "found one reason", "We identified two patterns: a fast one and a slow one."),
    ("assistant-residue", "placeholder", "The cost was XX dollars."),
    ("binary-contrast", "is not X, it is Y", "The rate is not known, it is likely to be small."),
    ("binary-contrast", "is not X, it is Y", "The delay isn't an artifact; it is a property of the cell cycle."),
    ("binary-contrast", "it's not X, it's Y", "It's not a technical artifact; it's a property of the cell cycle."),
    ("importance-puffery", "plays a key role", "Marlin-2 plays a pivotal role in drought tolerance."),
    ("importance-puffery", "plays a pivotal role", "Marlin-2 plays a key role in root growth."),
    ("binary-contrast", "is not X, it is Y", "These steps are not documented, it is not possible to tell."),
    ("binary-contrast", "it's not X, it's Y", "It's not clear, it's likely a small effect."),
    ("weasel-attribution", "research suggests", "Our research shows that the effect is small."),
    ("weasel-attribution", "vague quantity", "About 15% in the root tip carried the label."),
    ("importance-puffery", "sets the stage", "These changes may reflect broader changes in practice."),
    ("importance-puffery", "promotional words", "The design is exemplified by Figure 2."),
    ("importance-puffery", "underscores its importance", "We emphasize the importance of a control."),
    ("hedge-stack", "modal and adverb", "These data suggest that Marlin-2 may limit root growth."),
    ("hedge-stack", "modal and adverb", "Perhaps the mutant is unstable."),
]

# One plain sentence for each family with regex rules. Each is the plain form of a sentence in FIRES.
FAMILY_CLEAN = {
    "vocabulary-excess": "We examine how Marlin-2 expression changes after heat shock (n = 24 plants).",
    "vocabulary-density": "The two intervals overlap at one position.",
    "figurative-load": "This result is essential to our argument that Marlin-2 acts upstream of Tavo.",
    "binary-contrast": "The delay is a property of the cell cycle.",
    "importance-puffery": "Marlin-2 contributes to drought tolerance.",
    "participial-benefit": "Cells were sorted by flow cytometry. The sorted populations were 94% pure (Fig. 1B).",
    "weasel-attribution": "Sample size limits the precision of the estimate.",
    "fake-strong-verb": "Tavo binds the Marlin-2 promoter.",
    "throat-clearing": "Survival fell from 81% to 34% in the mutant.",
    "recap-opener": "These data suggest that Marlin-2 limits root growth.",
    "em-dash": "The mutant, which lacks the C-terminal domain, grows slowly.",
    "colon-reveal": "Marlin-2 limits root growth.",
    "assistant-residue": "Survival fell from 81% to 34%.",
    "hedge-stack": "These data suggest that Marlin-2 may limit root growth.",
}

# Plain science sentences. No family may flag any of them. They hold function words, the
# ordinary words that the corpus note says are not single-word flags, and the plain forms of
# the words that have exceptions.
CLEAN = [
    "Within each cell line, the signal rose across all time points.",
    "While the first approach failed, these findings suggest a potential role for Marlin-2.",
    "The pocket holds the ligand, and the loop stands apart from the helix.",
    "This protein serves a role in transport, and the mutant reveals a defect.",
    "The challenges of the assay involve low signal and high noise.",
    "Two strategies were compared, and the second approach gave cleaner traces.",
    "Cells were grown at 30 degrees for 24 h and then washed twice.",
    "Survival fell from 81% to 34% in the mutant (n = 60 per genotype).",
    "We measured growth, binding and expression in four lines.",
    "These data suggest that Marlin-2 may limit root growth.",
    "Overall survival was 80% at 12 months.",
    "The elevated level of calcium persisted for 10 min.",
    "Mice were tested on the elevated plus maze.",
    "The elevation of the site was 400 m.",
    "Particularly in the dark, the mutant grew slowly.",
    "The model was trained on 12,000 images and tested on a held-out set.",
    "Tavo binds the Marlin-2 promoter.",
    "Marlin-2 limited root growth in all four lines (Fig. 2).",
    "The primers were: forward, reverse and a probe.",
    "Enhancer activity rose in the mutant.",
    "The peptide backbone contains 12 residues.",
    "The mutant lacks the C-terminal domain, which explains the slow growth.",
    "The tissue was fixed in 4% paraformaldehyde and imaged on a confocal microscope.",
    "Fluorescence like that of the control was seen in the mutant.",
    "Marlin-2 is expressed in the root " + CITE + ".",
    "The reference sample serves as a loading control.",
    "Growth was robust to heat in all lines.",
    "A fitness landscape was built from 5,000 variants.",
    "The pivotal Phase 3 trial of the inhibitor enrolled 412 patients at 38 sites.",
    "Pups fostered within their own line gained a similar weight.",
    "In the open-field paradigm, a mouse is placed in a square arena.",
    "Above 6 cm per second, the streamlines broke into eddies that trailed behind the case.",
    "In order to test this idea, we crossed the lines.",
    "Furthermore, the signal was stable.",
    "Moreover, the signal was stable.",
    "Thus the mutant fails to bind Tavo.",
    "The difference (p < 0.05) held in both sexes.",
    "It is possible that the delay reflects the cell cycle.",
    "We found three genes: Tavo, Marlin-2 and Vero.",
    "Why was growth slower? We tested this in four lines.",
    "The intersection of the two intervals was empty.",
    "The data allow a comparison between groups.",
    "The authors used the standard buffer and a 10 mM stock.",
    "Table 2 lists the 12 lines, and Figure 3 shows their growth.",
    "The signal fell by 60% after 48 h, and cells arrested.",
    "A multivariate model explained 30% of the variance.",
]


# (note, phrase quoted in the note, family id, label, sentence with %s for the phrase). The test
# checks that the note holds the phrase, so the table cannot drift from the notes.
QUOTED = [
    ("guides", "stands as a testament", "importance-puffery", "stands as a testament", "The archive %s to long sampling."),
    ("guides", "plays a key role", "importance-puffery", "plays a key role", "Tavo %s in growth."),
    ("wikipedia", "setting the stage for", "importance-puffery", "sets the stage", "This work is a step, %s later work."),
    ("wikipedia", "evolving landscape", "importance-puffery", "sets the stage", "The paper enters an %s of methods."),
    ("wikipedia", "indelible mark", "importance-puffery", "sets the stage", "The record left an %s on the field."),
    ("wikipedia", "deeply rooted", "importance-puffery", "deeply rooted", "The belief is %s in the field."),
    ("wikipedia", "focal point", "importance-puffery", "focal point", "The %s of the talk is decay."),
    ("wikipedia", "diverse array", "importance-puffery", "promotional words", "The panel has a %s of species."),
    ("wikipedia", "nestled", "importance-puffery", "promotional words", "The lab is %s among many sites."),
    ("guides", "The stakes are high", "importance-puffery", "high stakes", "%s for every patient."),
    ("guides", "The implications are significant", "importance-puffery", "high stakes", "%s."),
    ("guides", "The future looks bright", "importance-puffery", "bright future", "%s for the method."),
    ("guides", "Despite these challenges", "importance-puffery", "despite challenges", "%s, the field continues to thrive."),
    ("wikipedia", "valuable insights", "participial-benefit", "valuable insights", "The data give %s into growth."),
    ("wikipedia", "Industry reports", "weasel-attribution", "industry reports", "%s suggest growth."),
    ("wikipedia", "Experts argue", "weasel-attribution", "studies show", "%s that the dose is high."),
    ("wikipedia", "Some critics argue", "weasel-attribution", "many argue", "%s that the dose is high."),
    ("guides", "Studies show", "weasel-attribution", "studies show", "%s that Tavo binds DNA."),
    ("guides", "Research suggests", "weasel-attribution", "research suggests", "%s that Tavo binds DNA."),
    ("wikipedia", "Certainly!", "assistant-residue", "chat opener", "%s"),
    ("wikipedia", "I hope this helps", "assistant-residue", "chat opener", "%s."),
    ("wikipedia", "as an AI language model", "assistant-residue", "as an AI", "%s, I cannot help."),
    ("wikipedia", "Delete this section before submission", "assistant-residue", "draft marker", "%s."),
    ("wikipedia", "You said:", "assistant-residue", "chat label", "%s write a summary."),
    ("wikipedia", "ChatGPT said:", "assistant-residue", "chat label", "%s here is a summary."),
    ("wikipedia", "as of my last knowledge update", "assistant-residue", "knowledge cutoff", "%s, the value was unknown."),
    ("wikipedia", "Up to my last training update", "assistant-residue", "knowledge cutoff", "%s, the value was unknown."),
    ("wikipedia", "contentReference", "assistant-residue", "tool marker", "The effect was large %s."),
    ("wikipedia", "oaicite", "assistant-residue", "tool marker", "The effect was large %s."),
    ("wikipedia", "grok_card", "assistant-residue", "tool marker", "The effect was large %s."),
    ("wikipedia", "[attached_file:1]", "assistant-residue", "tool marker", "The effect was large %s."),
    ("wikipedia", "[web:1]", "assistant-residue", "tool marker", "The effect was large %s."),
    ("wikipedia", "[cite: 1]", "assistant-residue", "tool marker", "The effect was large %s."),
    ("wikipedia", "[Your Name]", "assistant-residue", "placeholder", "Dear %s, thanks."),
    ("wikipedia", "2025-XX-XX", "assistant-residue", "placeholder", "Dated %s."),
    ("guides", "Insert Table 1 here", "assistant-residue", "placeholder", "%s."),
    ("guides", "Great question!", "assistant-residue", "sycophancy", "%s The answer follows."),
    ("wikipedia", "You're absolutely right!", "assistant-residue", "sycophancy", "%s"),
    ("authors", "I will now proceed", "assistant-residue", "meta-narration", "%s to the next step."),
    ("guides", "While details are limited", "assistant-residue", "source gap", "%s, the effect seems large."),
    ("guides", "Here's the thing", "throat-clearing", "chatty opener", "%s: the assay is noisy."),
    ("guides", "Let that sink in", "throat-clearing", "chatty opener", "%s."),
    ("guides", "It turns out", "throat-clearing", "chatty opener", "%s that the mutant is stable."),
    ("guides", "In this section, we'll", "throat-clearing", "in this section, we", "%s describe the cohorts."),
    ("guides", "At its core", "throat-clearing", "stock opener", "%s, the method counts reads."),
    ("guides", "It is important to note that", "throat-clearing", "it is worth noting that", "%s survival fell."),
    ("authors", "it is worth noting that", "throat-clearing", "it is worth noting that", "%s survival fell."),
    ("guides", "on the one hand", "throat-clearing", "on the one hand", "%s the mutant grows slowly, and on the other hand it survives."),
    ("authors", "In conclusion", "recap-opener", "recap opener", "%s, the mutant grows slowly."),
    ("authors", "Taken together", "recap-opener", "recap opener", "%s, the mutant grows slowly."),
    ("wikipedia", "In summary", "recap-opener", "recap opener", "%s, the mutant grows slowly."),
    ("guides", "It's not just a feature, it's a shift.", "binary-contrast", "not just X but Y", "%s"),
    ("guides", "Not because X, but because Y", "binary-contrast", "not because X, but because Y", None),
    ("guides", "could potentially", "hedge-stack", "modal and adverb", "The effect %s explain the delay."),
    ("corpus", "complex tapestry", "figurative-load", "tapestry", "The data form a %s of cues."),
    ("wikipedia", "deep dive", "figurative-load", "deep dive", "This section is a %s into data."),
    ("guides", "Lean into", "figurative-load", "lean into", "We %s the noise."),
    ("guides", "Game-changer", "figurative-load", "game-changer", "The kit is a %s."),
    ("authors", "load-bearing", "figurative-load", "load-bearing", "The result is %s for the argument."),
    ("corpus", "delves", "vocabulary-excess", "delve", "The study %s into the data."),
    ("corpus", "commendable", "vocabulary-excess", "commendable", "The effort is %s."),
    ("corpus", "garnered", "vocabulary-excess", "garner", "The tool %s attention."),
    ("corpus", "excels", "vocabulary-excess", "excels", "The tool %s at the task."),
    ("corpus", "surpassing", "vocabulary-density", "surpass", "The tool is %s the baseline."),
    ("corpus", "groundbreaking", "vocabulary-density", "groundbreaking", "The result is %s."),
    ("corpus", "invaluable", "vocabulary-density", "invaluable", "The data are %s."),
]


# Plain biology role statements. No family may flag them.
ROLE_SENTENCES = [
    "PKA acts as a negative regulator of the pathway.",
    "GFP serves as a reporter of promoter activity.",
    "This residue acts as a nucleophile in the first step.",
    "Fibronectin acts as a ligand for integrins.",
    "Tavo serves as a hub in the interaction network.",
    "GAPDH served as a loading control.",
    "The enzyme acts as a repressor of the pathway.",
    "The plasmid serves as a template for the reaction.",
    "Glucose serves as the substrate of the enzyme.",
    "CD4 functions as a marker of helper T cells.",
    "Marlin-2 acts as an activator of Tavo in the root.",
    "Tavo acts as a regulator of root growth.",
    "The protein operates as a dimer in the cell.",
]

# Ordinary sentences with generic words. No rule of an each family may flag them with severity flag.
GENERIC_WORD_SENTENCES = [
    "The transgene showed robust expression in leaves and weak expression in roots.",
    "Phosphorylation of Tavo facilitates its nuclear import [12].",
    "Fluorescence in the treated wells surpassed the background by day 3.",
    "A crucial control was the empty-vector line.",
    "We chose a comprehensive metabolic panel to screen all patients.",
    "Samples were utilized for RNA sequencing.",
    "Intravital imaging showed that vital dyes stained the same cells.",
    "The pretraining paradigm was the same for all models.",
    "We leveraged the existing cohort to estimate the effect size.",
    "The streamlined workflow reduced hands-on time from 6 h to 2 h.",
    "Robust cell growth was seen in all conditions.",
    "Mice navigate the maze in a few minutes.",
    "Heat stress elevates calcium levels in the root.",
]

# Pinned sentences for the `unless` regexes. Each entry is (family id, label, template, options, neutral).
# The template holds {} for one option. Every sentence of an entry holds the trigger of the rule and the
# option, so the regex matches and `unless` silences the rule. The neutral sentence has the trigger and no
# option, so the rule fires on it. A test removes each single option of each `unless` regex and checks that
# a pinned sentence then fires, so every option of every `unless` regex has a sentence here.
FIGURE_REFS = ["p < 0.05", "Fig. 2", "Figure 2", "Table 2"]
CONTEXT_WORDS = ["species", "ecology", "marine", "genome", "chromatin", "epigenomic", "microbiome", "habitat", "forest"]
WATER_WORDS = ["lake", "river", "ocean", "freshwater", "reef", "wetland", "soil", "coral", "plankton", "biodiversity",
               "wildlife", "aquatic", "terrestrial"]
UNLESS_PIN_SPECS = [
    ("vocabulary-excess", "underscore", "We replaced the underscore in each {}.",
     ["character", "filename", "identifier", "snake_case"], "We replaced the underscore in each sentence."),
    ("vocabulary-excess", "realm", "The realm Riboviria covers {} genomes.",
     ["virus", "viral", "virion", "ICTV", "taxonomic"], "The realm Riboviria covers plant genomes."),
    ("vocabulary-excess", "pivotal", "The pivotal {} enrolled 200 patients.",
     ["trial", "trials", "study", "studies"], "The pivotal result enrolled 200 patients."),
    ("vocabulary-excess", "pivotal", "The pivotal {} trial enrolled 412 patients.",
     ["Phase 3", "Phase III", "clinical", "registration", "registrational"], "This is a pivotal moment for the field."),
    ("vocabulary-excess", "seamless", "We used seamless {} to join the fragments.",
     ["cloning", "assembly", "ligation", "genome editing", "editing"], "We used seamless design to join the fragments."),
    ("vocabulary-excess", "harness", "The {} harnesses were calibrated before each run.",
     ["test", "animal", "safety", "body", "wiring", "cable", "rodent", "mouse", "rat"],
     "The new harnesses were calibrated before each run."),
    ("vocabulary-excess", "harness", "The harnesses {} was checked before each run.",
     ["system", "apparatus"], "The harnesses design was checked before each run."),
    ("vocabulary-excess", "empower", "Peaks were integrated in Empower {}.",
     ["3", "software", "data", "chromatography"], "Peaks were integrated in Empower later."),
    ("vocabulary-excess", "myriad", "Myriad {} supplied the assay.", ["Genetics"], "Myriad Labs supplied the assay."),
    ("vocabulary-excess", "transformative", "The grant came from the Transformative {} program.",
     ["Research"], "The grant came from the Transformative Impact program."),
    ("vocabulary-excess", "state-of-the-art", "The method reaches {} on state-of-the-art benchmarks.",
     ["SOTA"], "The method reaches parity on state-of-the-art benchmarks."),
    ("vocabulary-excess", "beacon", "A molecular {} reports the cleavage.", ["beacon", "beacons"],
     "A bright beacon reports the cleavage."),
    ("vocabulary-excess", "beacon", "The beacon follows the {} standard.", ["GA4GH"], "The beacon follows the open standard."),
    ("vocabulary-excess", "beacon", "We queried the Beacon {} of the archive.", ["protocol", "network", "API"],
     "We queried the beacon page of the archive."),
    ("vocabulary-excess", "supercharge", "The supercharged {} resists aggregation.", ["protein", "GFP"],
     "The supercharged tag resists aggregation."),
    ("vocabulary-excess", "supercharge", "The supercharging {} was added.", ["reagent"], "The supercharging step was added."),
    ("vocabulary-density", "comprehensive", "We used {}.",
     ["comprehensive two-dimensional gas chromatography", "Comprehensive Antibiotic Resistance Database",
      "Comprehensive R Archive Network"], "We used a comprehensive panel."),
    ("vocabulary-density", "robust", "We fitted robust {} to the counts.",
     ["regression", "statistics", "standard errors", "estimators", "linear models", "PCA"], "We fitted robust growth to the counts."),
    ("vocabulary-density", "robust", "The estimate is {} outliers.", ["robust to"], "The estimate is robust against outliers."),
    ("vocabulary-density", "robust", "The {} robustness fell after the knockout.",
     ["network", "genetic", "developmental", "phenotypic", "biological"], "The overall robustness fell after the knockout."),
    ("vocabulary-density", "robust", "We studied the robustness {} the {}.", [], "We studied the robustness of the estimate."),
    ("vocabulary-density", "robust", "An additional robustness {} gave the same result.",
     ["check", "analysis", "test"], "An additional robustness step gave the same result."),
    ("vocabulary-density", "leverage", "Points with {} were removed from the fit.", ["high leverage"],
     "Points with great leverage were removed from the fit."),
    ("vocabulary-density", "leverage", "The leverage {} of the rows are in Table 2.", ["scores", "points", "statistics"],
     "The leverage values of the rows are in Table 2."),
    ("vocabulary-density", "leverage", "The {} leverage was limited.", ["mechanical", "statistical", "financial"],
     "The overall leverage was limited."),
    ("vocabulary-density", "utilize", "{} utilization rose in the mutant.",
     ["Glucose", "Oxygen", "Nutrient", "Substrate", "Energy", "Resource", "CPU", "Memory", "GPU", "Drug", "Lipid"],
     "Overall utilization rose in the mutant."),
    ("vocabulary-density", "utilize", "The utilization {} rose in the mutant.", ["rate", "efficiency"],
     "The utilization level rose in the mutant."),
    ("vocabulary-density", "unlock", "The unlocked {} probe bound the target.", ["nucleic acid"], "The unlocked DNA probe bound the target."),
    ("vocabulary-density", "unlock", "The unlocked {} was stable.", ["conformation", "state", "form"], "The unlocked probe was stable."),
    ("vocabulary-density", "unlock", "Both {} probes bound the target.", ["locked and unlocked", "unlocked and locked"],
     "Both unlocked probes bound the target."),
    ("vocabulary-density", "elevate", "Heat stress elevates {} in the root.",
     ["levels", "concentrations", "pressure", "temperature", "expression", "risk", "rates"],
     "Heat stress elevates the root."),
    ("vocabulary-density", "synergy", "Synergy was scored with the {} model.", ["Bliss", "Loewe", "HSA", "ZIP"],
     "Synergy was scored with the additive model."),
    ("vocabulary-density", "synergy", "The synergy {} were high.", ["scores"], "The synergy values were high."),
    ("vocabulary-density", "synergy", "We scored drug {} in the panel.", ["synergy", "synergies"],
     "We scored the synergy in the panel."),
    ("vocabulary-density", "streamline", "The streamlines of the {} were plotted.", ["flow", "velocity", "fluid"],
     "The streamlines of the model were plotted."),
    ("vocabulary-density", "streamline", "The {} field has clear streamlines.", ["flow", "velocity", "fluid"],
     "The model field has clear streamlines."),
    ("vocabulary-density", "streamline", "The streamlines behind the case broke into {}.",
     ["eddies", "a vortex", "vortices", "turbulence"], "The streamlines behind the case broke into pieces."),
    ("vocabulary-density", "streamline", "The streamlines behind the case were {}.", ["laminar", "turbulent"],
     "The streamlines behind the case were short."),
    ("vocabulary-density", "streamline", "Near the case, {} appeared among the streamlines.",
     ["eddies", "a vortex", "vortices", "turbulence"], "Near the case, gaps appeared among the streamlines."),
    ("vocabulary-density", "streamline", "The {} region had clear streamlines.", ["laminar", "turbulent"],
     "The plain region had clear streamlines."),
    ("vocabulary-density", "streamline", "The streamlined {} reduced drag.", ["body", "bodies", "shape"],
     "The streamlined workflow reduced drag."),
    ("vocabulary-density", "navigate", "Mice navigate the {} in minutes.",
     ["maze", "mazes", "arena", "arenas", "gradient", "gradients"], "Mice navigate the field in minutes."),
    ("vocabulary-density", "navigate", "We studied {} navigation in the lab.",
     ["spatial", "animal", "visual", "olfactory", "chemotactic"], "We studied web navigation in the lab."),
    ("vocabulary-density", "navigate", "The {} was redesigned.", ["navigation menu", "navigation menus"],
     "The navigation page was redesigned."),
    ("vocabulary-density", "facilitate", "Facilitated {} moves glucose across the membrane.", ["diffusion", "transport"],
     "Facilitated uptake moves glucose across the membrane."),
    ("vocabulary-density", "facilitate", "{} rose after the burst.", ["Synaptic facilitation"], "Facilitation rose after the burst."),
    ("vocabulary-density", "facilitate", "{} rose after the burst.", ["Paired-pulse facilitation", "Paired pulse facilitation"],
     "Pulse facilitation rose after the burst."),
    ("vocabulary-density", "foster", "Animals were {} at birth.", ["cross-fostered"], "Animals were fostered at birth."),
    ("vocabulary-density", "foster", "The {} fostered at birth gained weight.",
     ["pups", "pup", "litters", "litter", "mice", "rats", "rat", "offspring"],
     "The program fostered a new collaboration."),
    ("vocabulary-density", "foster", "{} at birth.", ["Pups were fostered", "The litter was fostered"],
     "The program fostered a new collaboration."),
    ("vocabulary-density", "foster", "Newborns were fostered {} the dams of one line.", ["within", "to", "onto"],
     "The program fostered a new collaboration."),
    ("vocabulary-density", "foster", "Pups lived with a foster {}.",
     ["dam", "mother", "pup", "litter", "parent", "care", "home"], "Pups lived with a foster family."),
    ("vocabulary-density", "paradigm", "Mice learned the task in a {} paradigm.",
     ["experimental", "behavioral", "training", "conditioning", "task", "learning", "stimulation", "testing"],
     "Mice learned the task in a new paradigm."),
    ("vocabulary-density", "paradigm", "In the {} paradigm, a mouse is placed in a square arena.",
     ["open-field", "open field", "forced-choice", "forced choice", "two-choice", "two choice", "Pavlovian", "operant",
      "go/no-go", "oddball", "stop-signal"], "In the new paradigm, a mouse is placed in a square arena."),
    ("vocabulary-density", "vital", "Vital {} were recorded hourly.", ["signs", "dyes", "staining", "rates", "capacity"],
     "Vital measures were recorded hourly."),
    ("figurative-load", "load-bearing", "The load-bearing {} was fractured.",
     ["bone", "bones", "cartilage", "joint", "structure", "tissue", "wall", "limb", "surface", "region", "segment"],
     "The load-bearing role was fractured."),
    ("figurative-load", "backbone", "The {} backbone adopts a fold.",
     ["peptide", "protein", "polypeptide", "carbon", "sugar-phosphate", "phosphodiester", "DNA", "RNA", "amide",
      "polymer", "main-chain"], "The pipeline backbone adopts a fold."),
    ("figurative-load", "backbone", "The backbone {} were fixed.",
     ["atoms", "dihedrals", "RMSD", "torsions", "angles", "conformations"], "The backbone choices were fixed."),
    ("figurative-load", "backbone", "A {} extracts features from the backbone.",
     ["neural", "network", "networks", "architecture", "encoder", "ResNet", "transformer"],
     "A pipeline extracts features from the backbone."),
    ("figurative-load", "tapestry", "{} profiling captured 5,000 cells.", ["Tapestri"], "Tapestry profiling captured 5,000 cells."),
    ("figurative-load", "landscape", "A {} landscape had two peaks.",
     ["fitness", "energy", "adaptive", "epigenetic", "mutational", "conformational", "selection", "Waddington",
      "rugged", "local", "smooth", "neutral", "sequence", "functional", "molecular", "evolutionary", "regulatory"],
     "A scenic landscape had two peaks."),
    ("figurative-load", "landscape", "Set the landscape {} of the page.", ["mode", "orientation", "format"],
     "Set the landscape size of the page."),
    ("figurative-load", "landscape", "The landscape of the {} was mapped.", CONTEXT_WORDS, "The landscape of the reserve was mapped."),
    ("figurative-load", "ecosystem", "The {} ecosystem warmed.", CONTEXT_WORDS, "The software ecosystem warmed."),
    ("figurative-load", "ecosystem", "The {} ecosystem warmed.", WATER_WORDS, "The software ecosystem warmed."),
    ("binary-contrast", "is not X, it is Y", "The protein is not secreted, it is retained in the cell ({}).", FIGURE_REFS,
     "The protein is not secreted, it is retained in the cell (see below)."),
    ("binary-contrast", "it's not X, it's Y", "It's not secreted, it's retained in the cell ({}).", FIGURE_REFS,
     "It's not secreted, it's retained in the cell (see below)."),
    ("binary-contrast", "is not X; it is Y", "The protein is not secreted; it is retained in the cell ({}).", FIGURE_REFS,
     "The protein is not secreted; it is retained in the cell (see below)."),
    ("binary-contrast", "Not a X.", "Not a {} mouse survived.", ["single", "one"], "Not a mouse survived."),
    ("importance-puffery", "focal point", "The {} reached its focal point.",
     ["lens", "lenses", "objective", "microscope", "optics", "laser", "beam", "imaging", "image", "camera"],
     "The talk reached its focal point."),
    ("importance-puffery", "deeply rooted", "The deeply rooted {} share one ancestor.",
     ["plants", "roots", "trees", "phylogeny", "lineages", "clades", "taxa", "nodes"],
     "The deeply rooted beliefs share one ancestor."),
    ("participial-benefit", "trailing participial clause", "Loading was checked, ensuring equal loading {} a protein assay.",
     ["by", "using", "via", "through"], "Loading was checked, ensuring equal loading across lanes."),
    ("weasel-attribution", "vague quantity", "About 40% of cases improved ({}).", ["n = 12", "Fig. 2", "Figure 2", "Table 2"],
     "About 40% of cases improved (see below)."),
    ("assistant-residue", "sycophancy", "{} for this excellent catch.", ["We thank the reviewer"],
     "We are glad for this excellent catch."),
]
# The robustness-of alternative needs two options, so its sentences sit in a table of their own.
UNLESS_PIN_SENTENCES = {
    ("vocabulary-density", "robust"): [
        "We studied the robustness of the network.", "We studied the robustness in the network.",
        "We studied the robustness of the circuit.", "We studied the robustness of the pathway.",
        "We studied the robustness of development.",
    ],
}


def expand_unless_pins():
    """Return ({(family, label): [quiet sentence, ...]}, [(family, label, neutral sentence), ...])."""
    quiet, neutral = {}, []
    for family_id, label, template, options, neutral_sentence in UNLESS_PIN_SPECS:
        quiet.setdefault((family_id, label), []).extend(template.format(o) for o in options)
        neutral.append((family_id, label, neutral_sentence))
    for key, sentences in UNLESS_PIN_SENTENCES.items():
        quiet.setdefault(key, []).extend(sentences)
    return quiet, neutral


def split_top(rx):
    """Split a regex at the | characters that sit outside groups and character classes."""
    parts, depth, current, i, in_class = [], 0, "", 0, False
    while i < len(rx):
        char = rx[i]
        if char == "\\":
            current += rx[i:i + 2]
            i += 2
            continue
        if in_class:
            in_class = char != "]"
        elif char == "[":
            in_class = True
        elif char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
        elif char == "|" and depth == 0:
            parts.append(current)
            current = ""
            i += 1
            continue
        current += char
        i += 1
    parts.append(current)
    return parts


def group_bodies(rx):
    """Return (start, end) of the body of each group, including nested groups."""
    found, stack, i, in_class = [], [], 0, False
    while i < len(rx):
        char = rx[i]
        if char == "\\":
            i += 2
            continue
        if in_class:
            in_class = char != "]"
        elif char == "[":
            in_class = True
        elif char == "(":
            stack.append(i + 3 if rx.startswith("?:", i + 1) else i + 1)
        elif char == ")" and stack:
            found.append((stack.pop(), i))
        i += 1
    return found


def option_removals(rx):
    """Yield (description, regex) for each removal of one option of an alternation in the regex."""
    top = split_top(rx)
    for i in range(len(top)):
        rest = top[:i] + top[i + 1:]
        yield "top-level option %r" % top[i], "|".join(rest) if rest else "(?!)"
    for start, end in group_bodies(rx):
        options = split_top(rx[start:end])
        if len(options) > 1:
            for i in range(len(options)):
                rest = options[:i] + options[i + 1:]
                yield "option %r of the group %r" % (options[i], rx[start:end][:40]), rx[:start] + "|".join(rest) + rx[end:]


# (sentence, flags, infos): the reviewer's ordinary and risky sentences and a plain methods and results text.
# flags lists "family/label" of the rules of each families that flag the sentence with severity flag.
# infos lists the rules with severity info that fire. Density families are not listed.
# Every flag in this table is a decision: the sentence holds the pattern that the rule names.
RISKY = [
    ("The samples were processed in three steps: lysis, digestion and cleanup.", (), ()),
    ("The strains were grown on three media: lysogeny broth, minimal medium and yeast extract.", (), ()),
    ("The drug not only reduced tumor volume but also prolonged survival in the xenograft model.", (), ('binary-contrast/not only X but also Y',)),
    ("These cells are not stem cells; they are committed progenitors.", (), ('binary-contrast/is not X; it is Y',)),
    ("The mutation is not lethal; it is viable in the homozygous state.", (), ('binary-contrast/is not X; it is Y',)),
    ("The variant is a missense change, not a deletion.", (), ('binary-contrast/a X, not a Y',)),
    ("Marlin-2 plays a key role in root growth.", (), ('importance-puffery/plays a key role',)),
    ("Tavo serves as a hub in the interaction network.", (), ()),
    ("PKA acts as a negative regulator of the pathway.", (), ()),
    ("GFP serves as a reporter of promoter activity.", (), ()),
    ("Fibronectin acts as a ligand for integrins.", (), ()),
    ("This residue acts as a nucleophile in the first step.", (), ()),
    ("The tank was drained daily, allowing fresh medium to enter.", (), ('participial-benefit/mild participial clause',)),
    ("Expression peaked at day 3, reflecting the timing of germination.", (), ('participial-benefit/mild participial clause',)),
    ("The sequence was codon-optimized, enhancing expression in yeast.", (), ('participial-benefit/mild participial clause',)),
    ("Mice were housed in groups of four, making cage effects likely.", (), ('participial-benefit/mild participial clause',)),
    ("Researchers have shown that Tavo binds the promoter.", ('weasel-attribution/studies show',), ()),
    ("Reports suggest that the strain carries a second mutation.", ('weasel-attribution/studies show',), ()),
    ("Foster et al. described the first mutant in 1998.", (), ()),
    ("Garner and colleagues sequenced the locus.", (), ()),
    ("Samples were utilized for RNA sequencing.", (), ()),
    ("We chose a comprehensive metabolic panel to screen all patients.", (), ()),
    ("A crucial control was the empty-vector line.", (), ()),
    ("Intravital imaging showed that vital dyes stained the same cells.", (), ()),
    ("The paradigm of three-dimensional genome organization has changed over the past decade.", (), ()),
    ("The pretraining paradigm was the same for all models.", (), ()),
    ("Robust cell growth was seen in all conditions.", (), ()),
    ("The streamlined workflow reduced hands-on time from 6 h to 2 h.", (), ()),
    ("We leveraged the existing cohort to estimate the effect size.", (), ()),
    ("The enzyme exhibits nuanced substrate preferences.", ('vocabulary-excess/nuance',), ()),
    ("Interestingly, the effect was absent in females.", (), ()),
    ("It is important to note that the dose was lower in the second cohort.", (), ()),
    ("The reality is that sample size limited the analysis.", (), ()),
    ("When it comes to dosing, the two studies differed.", (), ()),
    ("Overall, the results are consistent with a model in which Marlin-2 limits growth.", (), ()),
    ("In conclusion, Marlin-2 limits root growth.", (), ()),
    ("Why did the double mutant grow normally? Because the two genes act in the same pathway.", (), ()),
    ("Is the effect specific to roots? We tested shoots and found no change.", (), ()),
    ("What explains the delay? The cells arrest in G1.", (), ()),
    ("Growth slowed. Cells arrested. Death followed.", (), ()),
    ("Mutant seedlings are small. They are pale. They die early.", (), ()),
    ("The phenotype was mild. The phenotype was variable. The phenotype was heritable.", (), ()),
    ("The effect could potentially be explained by auxin transport.", ('hedge-stack/modal and adverb',), ()),
    ("We cannot verify the raw values.", (), ()),
    ("Further work is needed. It may possibly help.", ('hedge-stack/modal and adverb',), ()),
    ("Cells were grown in DMEM with 10% fetal bovine serum at 37 degrees C and 5% CO2.", (), ()),
    ("We lysed the cells in RIPA buffer and cleared the lysate by centrifugation at 14,000 g for 15 minutes.", (), ()),
    ("Equal amounts of protein were loaded in each lane, and GAPDH served as a loading control.", (), ()),
    ("In order to reduce batch effects, we processed all samples on the same day.", (), ()),
    ("Band intensities were quantified in ImageJ and normalized to the control lane.", (), ()),
    ("We fitted a linear model with robust standard errors clustered by site.", (), ()),
    ("The pivotal trial enrolled 1,204 patients at 38 centers.", (), ()),
    ("The pivotal Phase 3 trial of the inhibitor enrolled 412 patients at 38 sites.", (), ()),
    ("This is a pivotal moment for the field.", ('vocabulary-excess/pivotal',), ()),
    ("The study maps the landscape of root growth.", (), ('figurative-load/landscape',)),
    ("We measured three traits: root length, shoot mass and flowering time.", (), ()),
    ("We define the growth index as the ratio of final to initial root length.", (), ()),
    ("Cells were sorted by flow cytometry, yielding 94% pure populations (Fig. 1B).", (), ('participial-benefit/mild participial clause',)),
    ("Does loss of Marlin-2 slow growth?", (), ()),
    ("The mutant seedlings grew 34% slower than wild type over 14 days (n = 60 per genotype).", (), ()),
    ("Root length did not differ between genotypes at day 3 (Fig. 2A).", (), ()),
    ("Expression of Tavo rose 2.4-fold in the mutant (p = 0.003).", (), ()),
    ("Overall survival at 24 months was 61% in the treated group and 48% in the control group.", (), ()),
    ("The lake ecosystem showed a clear seasonal cycle in chlorophyll a (Fig. 3).", (), ()),
    ("Mutations moved the protein across a rugged fitness landscape with several local optima.", (), ()),
    ("The transgene showed robust expression in leaves and weak expression in roots.", (), ()),
    ("Phosphorylation of Tavo facilitates its nuclear import " + CITE + ".", (), ()),
    ("Fluorescence in the treated wells surpassed the background by day 3.", (), ()),
    ("Taken together, these results suggest that Marlin-2 limits root growth.", (), ()),
    ("Marlin-2 acts as a repressor of Tavo in root tissue (Fig. 4).", (), ()),
    ("The effect may reflect a change in cell division, although we did not test this directly.", (), ()),
    ("Furthermore, the double mutant showed an intermediate phenotype.", (), ()),
    ("Our data cannot rule out an indirect effect through auxin transport.", (), ()),
    ("The mutant grew slowly\u2014a result we did not expect.", (), ()),
    ("Several studies have reported similar growth defects in other species " + CITE + ".", (), ()),
    ("This is not a technical artifact, as the effect appeared with two independent guides (Fig. 3B).", (), ()),
    ("The key limitation of this study is its small sample size.", (), ()),
    ("More research is needed to test whether Tavo binds the promoter directly.", (), ()),
    ("The reaction was stopped after 30 min with 0.1 M HCl.", (), ()),
    ("Reads were aligned to the reference genome with STAR, and counts were summarized per gene.", (), ()),
    ("We used 12 mice per group, which gave 80% power to detect a 25% difference.", (), ()),
    ("A Western blot confirmed that the antibody detects a single band at 52 kDa.", (), ()),
    ("Notably, the effect was absent in female mice.", (), ()),
    ("These findings were consistent across three independent experiments.", (), ()),
    ("The authors of the earlier study used a different strain, so the results are not directly comparable.", (), ()),
    ("The difference is not explained by cell number, since counts were similar in both groups (Table 2).", (), ()),
    ("These results matter for crop breeding because root growth limits yield under drought.", (), ()),
    ("We thank the staff of the imaging core for technical help.", (), ()),
]

def word_probe(entry):
    """Return a word that the entry of a word rule must match."""
    return entry[:-1] if entry.endswith("*") else entry


# ---------------------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------------------

class SchemaTests(unittest.TestCase):
    def test_family_ids_follow_the_fixed_list_in_order(self):
        self.assertEqual([f.id for f in PATTERNS.families], FAMILY_IDS)

    def test_family_ids_are_unique(self):
        ids = [f.id for f in PATTERNS.families]
        self.assertEqual(len(ids), len(set(ids)))

    def test_as_of_date(self):
        self.assertEqual(PATTERNS.as_of, "2026-10-23")
        for family_id in VOCABULARY_FAMILIES:
            self.assertIn("2026-10-23", PATTERNS.family(family_id).title)

    def test_data_file_holds_only_ascii(self):
        with open(DATA_PATH, "rb") as handle:
            raw = handle.read()
        raw.decode("ascii")

    def test_data_file_top_level(self):
        with open(DATA_PATH, encoding="utf-8") as handle:
            data = json.load(handle)
        self.assertEqual(list(data.keys()), ["version", "as_of", "families"])
        self.assertEqual(data["version"], 1)

    def test_modes_and_thresholds(self):
        for family in PATTERNS.families:
            self.assertIn(family.mode, ("each", "density"), family.id)
            if family.mode == "density":
                self.assertTrue(family.max_per_1000 > 0, family.id)
            else:
                self.assertIsNone(family.max_per_1000, family.id)
        density = [f.id for f in PATTERNS.families if f.mode == "density"]
        self.assertEqual(
            sorted(density),
            sorted(["vocabulary-density", "throat-clearing", "recap-opener", "em-dash"]))

    def test_fixed_thresholds(self):
        self.assertEqual(PATTERNS.family("vocabulary-density").max_per_1000, 3)
        self.assertEqual(PATTERNS.family("em-dash").max_per_1000, 2.5)

    def test_each_family_has_title_strategy_and_delete_flag(self):
        for family in PATTERNS.families:
            self.assertTrue(family.title.strip(), family.id)
            self.assertTrue(family.strategy.strip(), family.id)
            self.assertIsInstance(family.delete_ok, bool, family.id)
            self.assertTrue(family.enabled, family.id)

    def test_structural_families(self):
        for family_id, check in STRUCTURAL.items():
            family = PATTERNS.family(family_id)
            self.assertEqual(family.check, check)
            self.assertEqual(family.rules, [])
            self.assertIn(family.tier, ("T1", "T2", "T3"))
            self.assertTrue(family.sources)
        for family in PATTERNS.families:
            if family.id not in STRUCTURAL:
                self.assertIsNone(family.check, family.id)
                self.assertTrue(family.rules, family.id)

    def test_structural_parameters(self):
        self.assertEqual(PATTERNS.family("repeated-openers").params,
                         {"run": 3, "ignore": ["the", "a", "an", "we", "in"], "ignored_compare_words": 2})
        self.assertEqual(PATTERNS.family("staccato-run").params, {"run": 3, "max_words": 5})
        self.assertEqual(
            PATTERNS.family("rhetorical-question").params,
            {"answers": ["this", "that", "the", "it", "we", "yes", "no", "because", "simply", "here", "our", "these"],
             "skip_paragraph_start": True})

    def test_rules_have_tier_sources_and_label(self):
        for family, rule in all_rules():
            where = "%s / %s" % (family.id, rule.label)
            self.assertIn(rule.tier, ("T1", "T2", "T3"), where)
            self.assertTrue(rule.sources, where)
            self.assertTrue(rule.label.strip(), where)

    def test_rule_labels_are_unique_in_a_family(self):
        for family in PATTERNS.families:
            labels = [rule.label for rule in family.rules]
            self.assertEqual(len(labels), len(set(labels)), family.id)

    def test_regexes_are_compiled_and_never_match_nothing_or_everything(self):
        for family, rule in all_rules():
            where = "%s / %s" % (family.id, rule.label)
            self.assertTrue(hasattr(rule.regex, "search"), where)
            self.assertIsNone(rule.regex.search(""), where)
            self.assertIsNone(rule.regex.search("plain text with no marker"), where)
            if rule.unless is not None:
                self.assertIsNone(rule.unless.search(""), where)

    def test_no_rule_matches_a_placeholder(self):
        text = " ".join(OPEN + str(i) + CLOSE for i in (0, 3, 12, 345))
        for family, rule in all_rules():
            self.assertIsNone(rule.regex.search(text), "%s / %s" % (family.id, rule.label))

    def test_family_notes_for_special_families(self):
        rq = PATTERNS.family("rhetorical-question")
        self.assertEqual(rq.tier, "T3")
        self.assertTrue(all(key.startswith("authors:") for key in rq.sources))
        self.assertIn("corpus:S16", rq.note)
        self.assertIn("essay", rq.note)
        em = PATTERNS.family("em-dash")
        self.assertEqual(em.rules[0].tier, "T1")
        self.assertIn("corpus:S6", em.rules[0].sources)
        self.assertIn("authors:S7", em.rules[0].sources)
        self.assertIn("threshold", em.rules[0].note)
        self.assertIn("2.5", em.rules[0].note)
        part = PATTERNS.family("participial-benefit").rules[0]
        self.assertEqual(part.tier, "T1")
        self.assertIn("corpus:S15", part.sources)
        self.assertIn("corpus:S17", part.sources)
        self.assertIn("all participial clauses", part.note)

    def test_prose_fields_follow_the_writing_rules(self):
        banned = re.compile(r"\b(?:leverage|robust|seamless|crucial|comprehensive|very|really)\b", re.I)
        fields = []
        for family in PATTERNS.families:
            fields.append((family.id + " title", family.title, 25))
            fields.append((family.id + " strategy", family.strategy, 20))
            if family.note:
                fields.append((family.id + " note", family.note, 25))
            for rule in family.rules:
                if rule.note:
                    fields.append(("%s / %s note" % (family.id, rule.label), rule.note, 25))
        for where, text, limit in fields:
            self.assertNotIn("\u2014", text, where)
            if where.endswith("title") or where.endswith("strategy"):
                self.assertIsNone(banned.search(text), where)
            for sentence in re.split(r"(?<=[.!?])\s+", text.strip()):
                self.assertLessEqual(len(sentence.split()), limit, "%s: %s" % (where, sentence))

    def test_unless_citation_and_case_flags_are_set_on_the_expected_rules(self):
        citation = {
            ("vocabulary-excess", "state-of-the-art"), ("binary-contrast", "is not X, it is Y"),
            ("binary-contrast", "it's not X, it's Y"), ("binary-contrast", "is not X; it is Y"),
            ("importance-puffery", "stands as a testament"),
            ("importance-puffery", "plays a pivotal role"), ("importance-puffery", "plays a key role"),
            ("importance-puffery", "marks a turning point"),
            ("importance-puffery", "solidifies its position"), ("importance-puffery", "underscores its importance"),
            ("weasel-attribution", "studies show"), ("weasel-attribution", "many argue"),
            ("weasel-attribution", "industry reports"), ("weasel-attribution", "research suggests"),
            ("weasel-attribution", "vague quantity"),
        }
        case = {
            ("binary-contrast", "Not a X."), ("throat-clearing", "sentence adverb"),
            ("throat-clearing", "Importantly,"), ("throat-clearing", "in this article"),
            ("recap-opener", "recap opener"), ("assistant-residue", "chat label"),
            ("colon-reveal", "The X is Y: z"), ("colon-reveal", "found one reason"),
        }
        self.assertEqual({(f.id, r.label) for f, r in all_rules() if r.unless_citation}, citation)
        self.assertEqual({(f.id, r.label) for f, r in all_rules() if r.case_sensitive}, case)

    def test_words_that_only_row_l3_names_take_the_tier_of_their_other_keys(self):
        # Row L3 of the corpus note lists review words with no per-word ratio.
        expected = {"vital": "T3", "holistic": "T3", "unprecedented": "T2"}
        for label, tier in expected.items():
            rule = rule_of(family_of(label), label)
            self.assertEqual(rule.tier, tier, label)
            self.assertFalse([k for k in rule.sources if k.startswith("corpus:")], label)

    def test_em_dash_note_states_the_limits_of_the_data(self):
        note = PATTERNS.family("em-dash").rules[0].note
        self.assertIn("P8", note)
        self.assertIn("LaTeX", note)

    def test_hedge_stack_follows_the_brief(self):
        family = PATTERNS.family("hedge-stack")
        self.assertEqual(family.mode, "each")
        self.assertFalse(family.delete_ok)
        for rule in family.rules:
            self.assertEqual(rule.tier, "T3")
            self.assertEqual(rule.sources, ["authors:S1"])

    def test_throat_clearing_never_uses_each_mode_or_tier_t1(self):
        family = PATTERNS.family("throat-clearing")
        self.assertEqual(family.mode, "density")
        for rule in family.rules:
            self.assertIn(rule.tier, ("T2", "T3"), rule.label)

    def test_importantly_rule_stays_at_the_author_tier(self):
        rule = rule_of("throat-clearing", "Importantly,")
        self.assertEqual(rule.tier, "T3")
        self.assertIn("corpus:S10", rule.note)

    def test_delete_ok_follows_the_craft_table(self):
        allowed = {"assistant-residue", "throat-clearing", "recap-opener", "rhetorical-question",
                   "importance-puffery", "weasel-attribution", "repeated-openers", "staccato-run"}
        for family in PATTERNS.families:
            self.assertEqual(family.delete_ok, family.id in allowed, family.id)


# ---------------------------------------------------------------------------------------
# Sources
# ---------------------------------------------------------------------------------------

def cited_keys():
    """Return {key: [where, ...]} for every key of the data file."""
    found = {}
    for family in PATTERNS.families:
        for key in family.sources or []:
            found.setdefault(key, []).append(family.id)
        for rule in family.rules:
            for key in rule.sources:
                found.setdefault(key, []).append("%s / %s" % (family.id, rule.label))
    return found


class SourceTests(unittest.TestCase):
    def test_every_note_has_a_source_section(self):
        for name in NOTE_NAMES:
            self.assertTrue(source_lines(name), name)

    def test_every_key_resolves_to_a_source_line(self):
        unresolved = []
        for key, where in sorted(cited_keys().items()):
            note, _, number = key.partition(":S")
            if note not in NOTE_NAMES or not number.isdigit() or int(number) not in source_lines(note):
                unresolved.append("%s (%s)" % (key, where[0]))
        self.assertEqual(unresolved, [], "unresolved keys: " + "; ".join(unresolved))

    def test_no_key_points_to_an_unverified_line(self):
        bad = []
        for key, where in sorted(cited_keys().items()):
            note, _, number = key.partition(":S")
            line = source_lines(note).get(int(number), "")
            if "UNVERIFIED" in line:
                bad.append("%s (%s)" % (key, where[0]))
        self.assertEqual(bad, [], "unverified keys: " + "; ".join(bad))

    def test_unverified_lines_exist_so_the_check_can_fail(self):
        unverified = [(name, n) for name in NOTE_NAMES for n, line in source_lines(name).items()
                      if "UNVERIFIED" in line]
        self.assertIn(("corpus", 26), unverified)
        self.assertIn(("wikipedia", 11), unverified)
        self.assertIn(("craft", 23), unverified)

    def test_t1_rules_cite_a_corpus_key(self):
        for family, rule in all_rules():
            if rule.tier == "T1":
                self.assertTrue(any(k.startswith("corpus:") for k in rule.sources),
                                "%s / %s" % (family.id, rule.label))
        for family in PATTERNS.families:
            if family.tier == "T1":
                self.assertTrue(any(k.startswith("corpus:") for k in family.sources), family.id)

    def test_t3_rules_cite_author_keys_only(self):
        for family, rule in all_rules():
            if rule.tier == "T3":
                self.assertTrue(all(k.startswith("authors:") for k in rule.sources),
                                "%s / %s: %s" % (family.id, rule.label, rule.sources))
        for family in PATTERNS.families:
            if family.tier == "T3":
                self.assertTrue(all(k.startswith("authors:") for k in family.sources), family.id)

    def test_tier_is_the_strongest_tier_of_the_cited_keys(self):
        tiers = key_tiers()
        wrong = []
        entries = [("%s / %s" % (f.id, r.label), r.tier, r.sources) for f, r in all_rules()]
        entries += [(f.id, f.tier, f.sources) for f in PATTERNS.families if f.tier]
        for where, tier, sources in entries:
            strongest = min((tiers[k] for k in sources), key=lambda t: TIER_RANK[t])
            if strongest != tier:
                wrong.append("%s: tier %s, keys give %s" % (where, tier, strongest))
        self.assertEqual(wrong, [], "; ".join(wrong))

    def test_keys_have_the_note_and_number_form(self):
        for key in cited_keys():
            self.assertRegex(key, r"^(corpus|wikipedia|guides|authors|craft):S[1-9][0-9]*$")

    def test_sources_hold_no_duplicate_key(self):
        for family, rule in all_rules():
            self.assertEqual(len(rule.sources), len(set(rule.sources)), "%s / %s" % (family.id, rule.label))


# ---------------------------------------------------------------------------------------
# Rules on made-up sentences
# ---------------------------------------------------------------------------------------

class RuleTests(unittest.TestCase):
    def test_seeded_sentences_fire(self):
        for family_id, label, sentence in FIRES:
            self.assertIn(label, hits(family_id, sentence), "%s / %s: %s" % (family_id, label, sentence))

    def test_phrases_quoted_in_the_notes_fire(self):
        for note, phrase, family_id, label, template in QUOTED:
            self.assertIn(phrase.lower(), read_note(note).lower(), "%s does not quote %r" % (note, phrase))
            if template is None:
                continue
            sentence = template % phrase
            self.assertIn(label, hits(family_id, sentence), "%s / %s: %s" % (family_id, label, sentence))

    def test_craft_examples_before_fires_and_after_stays_quiet(self):
        examples = craft_examples()
        self.assertEqual(len(examples), 30)
        self.assertEqual(sorted(set(e[0] for e in examples)), sorted(CRAFT_FAMILY_IDS.values()))
        for family_id, before, after in examples:
            family = PATTERNS.family(family_id)
            if before in CRAFT_BEFORE_QUIET:
                self.assertEqual(all_hits(before), [], before)
            elif family.rules:
                self.assertNotEqual(hits(family, before), [], "%s: %s" % (family_id, before))
            self.assertEqual(all_hits(after), [], "%s: %s" % (family_id, after))

    def test_every_regex_rule_has_a_seeded_sentence(self):
        seeded = set((f, l) for f, l, _ in FIRES)
        missing = []
        for family, rule in all_rules():
            if rule.words is None and (family.id, rule.label) not in seeded:
                missing.append("%s / %s" % (family.id, rule.label))
        self.assertEqual(missing, [])

    def test_every_seed_names_a_real_rule(self):
        for family_id, label, _ in FIRES + [(f, l, s) for f, l, _, s in EXCEPTIONS] + QUIET:
            rule_of(family_id, label)

    def test_each_word_entry_fires_on_itself(self):
        for family, rule in all_rules():
            if rule.words is None:
                continue
            for entry in rule.words:
                sentence = "The sample was %s." % word_probe(entry)
                self.assertIn(rule.label, hits(family, sentence), "%s / %s: %s" % (family.id, rule.label, entry))

    def test_word_stems_match_other_endings(self):
        rule = rule_of("vocabulary-excess", "delve")
        for form in ("delve", "delves", "delved", "delving"):
            self.assertIn("delve", hits("vocabulary-excess", "We %s into it." % form), form)
        self.assertEqual(hits("vocabulary-excess", "We develop the method and deliver the kit."), [])
        self.assertTrue(rule.words)

    def test_exceptions_silence_a_rule_that_would_match(self):
        for family_id, label, kind, sentence in EXCEPTIONS:
            rule = rule_of(family_id, label)
            where = "%s / %s / %s: %s" % (family_id, label, kind, sentence)
            self.assertTrue(rule.regex.search(sentence), "the regex must match: " + where)
            self.assertNotIn(label, hits(family_id, sentence), "must be quiet: " + where)
            if kind == "unless":
                self.assertIsNotNone(rule.unless, where)
                self.assertTrue(rule.unless.search(sentence), where)
                self.assertNotIn(OPEN, sentence, where)
            else:
                self.assertTrue(rule.unless_citation, where)
                self.assertIn(OPEN, sentence, where)
                if rule.unless is not None:
                    self.assertIsNone(rule.unless.search(sentence), where)

    def test_citation_exception_fails_without_the_placeholder(self):
        for family_id, label, kind, sentence in EXCEPTIONS:
            if kind == "citation":
                bare = sentence.replace(CITE, "").replace("  ", " ")
                self.assertIn(label, hits(family_id, bare), bare)

    def test_unless_exception_fails_without_the_exception_text(self):
        # The same rule fires on a sentence that holds no exception text.
        plain = {
            "underscore": "The paper underscores the gap.",
            "realm": "The paper explores a new realm of study.",
            "pivotal": "The result is pivotal.",
            "comprehensive": "We give a comprehensive account.",
            "robust": "We give a robust account.",
            "seamless": "The workflow is seamless.",
            "leverage": "We leverage the data.",
            "harness": "We harness the data.",
            "utilize": "We utilize the data.",
            "unlock": "We unlock the data.",
            "elevate": "We elevate the field.",
            "empower": "We empower the reader.",
            "myriad": "There are myriad options.",
            "synergy": "The synergy is clear.",
            "streamline": "We streamline the work.",
            "navigate": "We navigate the field.",
            "facilitate": "This will facilitate the work.",
            "foster": "We foster growth.",
            "paradigm": "This is a new paradigm.",
            "transformative": "This is a transformative result.",
            "state-of-the-art": "This is a state-of-the-art tool.",
            "vital": "This is vital.",
            "beacon": "This is a beacon.",
            "supercharge": "We supercharge the work.",
        }
        for label, sentence in plain.items():
            self.assertIn(label, hits(family_of(label), sentence), label)
        for label, sentence in {
            "load-bearing": "The result is load-bearing for the argument.",
            "backbone": "The model is the backbone of the work.",
            "tapestry": "The data form a tapestry.",
            "landscape": "The paper maps the landscape of the work.",
            "ecosystem": "The tool joins a wider ecosystem.",
        }.items():
            self.assertIn(label, hits("figurative-load", sentence), label)

    def test_no_rule_is_slow_on_a_long_sentence(self):
        import time
        texts = ["word " * 8000, "The delay is not " + "big " * 4000 + "but", "less about " + "x " * 4000,
                 "The " + "a-b " * 3000 + "c:", "is not " + ", " * 4000, "we found one " + "explanation " * 3000,
                 "It is not just a thing, it is x" * 1000]
        start = time.time()
        for text in texts:
            for family, rule in all_rules():
                rule.regex.search(text)
                if rule.unless is not None:
                    rule.unless.search(text)
        self.assertLess(time.time() - start, 20.0)

    def test_plain_biology_roles_stay_quiet(self):
        for sentence in ROLE_SENTENCES:
            self.assertEqual(all_hits(sentence), [], sentence)

    def test_generic_words_do_not_flag_in_each_mode(self):
        for sentence in GENERIC_WORD_SENTENCES:
            flagged = [(f, l) for f, l in all_hits(sentence)
                       if PATTERNS.family(f).mode == "each" and rule_of(f, l).severity == "flag"]
            self.assertEqual(flagged, [], sentence)

    def test_generic_words_sit_in_the_density_family(self):
        density = PATTERNS.family("vocabulary-density")
        labels = [rule.label for rule in density.rules]
        for label in ("robust", "crucial", "comprehensive", "facilitate", "utilize", "surpass", "foster",
                      "navigate", "paradigm", "leverage", "synergy", "streamline", "vital", "unlock", "elevate"):
            self.assertIn(label, labels)
            self.assertNotIn(label, [r.label for r in PATTERNS.family("vocabulary-excess").rules])

    def test_surnames_stay_quiet_for_lower_only_words(self):
        for label in ("foster", "garner"):
            self.assertTrue(rule_of(family_of(label), label).lower_only, label)
        for sentence in ("Foster et al. described the first mutant in 1998.", "Garner and colleagues sequenced the locus.",
                         "The paper of Foster appeared in 1998."):
            self.assertEqual(all_hits(sentence), [], sentence)
        self.assertIn("foster", hits("vocabulary-density", "The program will foster collaboration."))
        self.assertIn("foster", hits("vocabulary-density", "The program fosters collaboration."))
        self.assertIn("garner", hits("vocabulary-excess", "The tool will garner attention."))
        self.assertIn("garner", hits("vocabulary-excess", "The tool garnered attention."))

    def test_every_option_of_every_unless_regex_is_pinned(self):
        quiet, neutral = expand_unless_pins()
        undetected = []
        for family, rule in all_rules():
            if rule.unless is None:
                continue
            pins = quiet.get((family.id, rule.label), [])
            self.assertTrue(pins, "no pinned sentence for %s / %s" % (family.id, rule.label))
            for sentence in pins:
                where = "%s / %s: %s" % (family.id, rule.label, sentence)
                self.assertIsNotNone(rule.regex.search(sentence), "the regex must match: " + where)
                self.assertIsNotNone(rule.unless.search(sentence), "unless must match: " + where)
                self.assertFalse(rule.fires(sentence), where)
            for description, mutated in option_removals(rule.unless.pattern):
                weaker = re.compile(mutated, rule.unless.flags)
                if not any(rule.regex.search(s) and not weaker.search(s) for s in pins):
                    undetected.append("%s / %s: %s" % (family.id, rule.label, description))
        self.assertEqual(undetected, [], "options without a pinned sentence:\n" + "\n".join(undetected))

    def test_neutral_sentences_fire_so_unless_stays_narrow(self):
        quiet, neutral = expand_unless_pins()
        for family_id, label, sentence in neutral:
            self.assertTrue(rule_of(family_id, label).fires(sentence), "%s / %s: %s" % (family_id, label, sentence))

    def test_every_pinned_rule_exists_and_has_unless(self):
        quiet, neutral = expand_unless_pins()
        for family_id, label in quiet:
            self.assertIsNotNone(rule_of(family_id, label).unless, "%s / %s" % (family_id, label))

    def test_ordinary_and_risky_sentences_keep_their_decided_outcome(self):
        self.assertEqual(len(RISKY), 88)
        decided_flags = set()
        for sentence, flags, infos in RISKY:
            got_flags, got_infos = [], []
            for family in PATTERNS.families:
                for rule in family.rules:
                    if rule.fires(sentence, cited=OPEN in sentence):
                        key = "%s/%s" % (family.id, rule.label)
                        if family.mode == "each" and rule.severity == "flag":
                            got_flags.append(key)
                        elif rule.severity == "info":
                            got_infos.append(key)
            self.assertEqual(tuple(got_flags), flags, sentence)
            self.assertEqual(tuple(got_infos), infos, sentence)
            decided_flags.update(flags)
        self.assertEqual(decided_flags, {"weasel-attribution/studies show", "vocabulary-excess/nuance",
                                         "vocabulary-excess/pivotal", "hedge-stack/modal and adverb"})

    def test_info_rules_are_the_ones_that_the_review_named(self):
        info = {(f.id, r.label) for f, r in all_rules() if r.severity == "info"}
        self.assertEqual(info, {
            ("binary-contrast", "not only X but also Y"), ("binary-contrast", "a X, not a Y"),
            ("binary-contrast", "is not X; it is Y"), ("importance-puffery", "plays a key role"),
            ("participial-benefit", "mild participial clause"), ("fake-strong-verb", "serves as a figure"),
            ("figurative-load", "landscape"),
        })
        for family, rule in all_rules():
            self.assertIn(rule.severity, ("flag", "info"))

    def test_rules_that_the_review_kept_at_flag(self):
        for family_id, label in (("binary-contrast", "not just X but Y"), ("binary-contrast", "is not X, it is Y"),
                                 ("binary-contrast", "it's not X, it's Y"),
                                 ("binary-contrast", "less about X, more about Y"), ("binary-contrast", "not mainly about X"),
                                 ("participial-benefit", "trailing participial clause")):
            self.assertEqual(rule_of(family_id, label).severity, "flag", label)
        self.assertIn("highlighting", rule_of("participial-benefit", "trailing participial clause").regex.pattern)
        self.assertIn("paving the way", rule_of("participial-benefit", "trailing participial clause").regex.pattern)

    def test_the_stock_gap_rule_is_gone(self):
        self.assertNotIn("stock gap statement", [r.label for r in PATTERNS.family("weasel-attribution").rules])
        self.assertEqual(all_hits("More research is needed to test whether Tavo binds the promoter."), [])

    def test_no_note_uses_an_x_not_y_pair(self):
        pair = re.compile(r"\w, not (?:a|an|the|only|just|in|on|of)\b|\bnot only\b|\bnot just\b", re.I)
        for family in PATTERNS.families:
            texts = [(family.id + " note", family.note), (family.id + " strategy", family.strategy)]
            texts += [("%s / %s note" % (family.id, r.label), r.note) for r in family.rules]
            for where, text in texts:
                if text:
                    self.assertIsNone(pair.search(text), "%s: %s" % (where, text))

    def test_left_out_words_are_in_no_word_rule(self):
        for word in ORDINARY_WORDS + LEFT_OUT_WORDS:
            self.assertEqual(all_hits(word), [], word)
            self.assertEqual(all_hits("The sample was %s." % word), [], word)
        for family, rule in all_rules():
            for entry in rule.words or []:
                self.assertNotIn(entry.rstrip("*"), ORDINARY_WORDS + LEFT_OUT_WORDS, "%s / %s" % (family.id, rule.label))

    def test_every_word_is_in_the_rows_of_the_keys_that_the_rule_cites(self):
        unsupported = []
        for family, rule in all_rules():
            if rule.words is None:
                continue
            patterns = [word_row_regex(entry) for entry in rule.words]
            texts_by_key = dict((key, rows_citing(*_split_key(key))) for key in rule.sources)
            for key, texts in texts_by_key.items():
                if not any(rx.search(text) for text in texts for rx in patterns):
                    unsupported.append("%s / %s: key %s names no entry" % (family.id, rule.label, key))
            for entry, rx in zip(rule.words, patterns):
                if not any(rx.search(text) for texts in texts_by_key.values() for text in texts):
                    unsupported.append("%s / %s: entry %s is in no cited row" % (family.id, rule.label, entry))
        self.assertEqual(unsupported, [], "keys whose rows do not hold the word: " + "; ".join(unsupported))

    def test_the_word_support_check_can_fail(self):
        rx = word_row_regex("delv*")
        self.assertTrue(any(rx.search(t) for t in rows_citing("corpus", 1)))
        self.assertFalse(any(rx.search(t) for t in rows_citing("craft", 1)))
        self.assertFalse(any(word_row_regex("zzzword").search(t) for t in rows_citing("corpus", 1)))

    def test_quiet_sentences_stay_quiet(self):
        for family_id, label, sentence in QUIET:
            self.assertNotIn(label, hits(family_id, sentence), "%s / %s: %s" % (family_id, label, sentence))

    def test_clean_sentences_stay_quiet_in_every_family(self):
        for sentence in CLEAN:
            self.assertEqual(all_hits(sentence), [], sentence)

    def test_each_regex_family_has_a_flagged_and_a_clean_sentence(self):
        flagged = set(f for f, _, _ in FIRES)
        for family in PATTERNS.families:
            if family.rules:
                self.assertIn(family.id, flagged, family.id)
                self.assertIn(family.id, FAMILY_CLEAN, family.id)
                self.assertEqual(hits(family, FAMILY_CLEAN[family.id]), [], family.id)
                self.assertEqual(all_hits(FAMILY_CLEAN[family.id]), [], family.id)
        self.assertEqual(sorted(FAMILY_CLEAN), sorted(f.id for f in PATTERNS.families if f.rules))

    def test_function_words_and_ordinary_words_are_no_flags(self):
        for word in FUNCTION_WORDS + ORDINARY_WORDS:
            self.assertEqual(all_hits(word), [], word)
            self.assertEqual(all_hits("The sample was %s." % word), [], word)

    def test_k9_words_are_no_flags_unless_an_author_key_backs_the_rule(self):
        words = k9_words()
        self.assertGreater(len(words), 50)
        self.assertIn("potential", words)
        for word in words:
            for family, rule in all_rules():
                if rule.regex.search(word) and not any(k.startswith("authors:") for k in rule.sources):
                    self.fail("%s / %s matches the K9 word %r" % (family.id, rule.label, word))

    def test_k9_words_stay_out_of_the_density_rules_without_author_keys(self):
        for rule in PATTERNS.family("vocabulary-density").rules:
            if any(k.startswith("authors:") for k in rule.sources):
                continue
            for word in k9_words():
                self.assertIsNone(rule.regex.search(word), "%s matches %s" % (rule.label, word))

    def test_vocabulary_lists_are_short_enough_to_read(self):
        entries = [e for r in PATTERNS.family("vocabulary-excess").rules for e in (r.words or [r.label])]
        self.assertTrue(25 <= len(entries) <= 45, len(entries))
        dense = [e for r in PATTERNS.family("vocabulary-density").rules for e in (r.words or [r.label])]
        self.assertTrue(len(dense) <= 60, len(dense))

    def test_vocabulary_excess_holds_the_rare_k1_and_k2_stems(self):
        family = PATTERNS.family("vocabulary-excess")
        for word in ("delves", "underscores", "delved", "showcasing", "meticulously", "delve",
                     "intricacies", "underscoring", "intricate", "delving", "commendable",
                     "underscore", "excels", "garnered", "underscored"):
            self.assertNotEqual(hits(family, "The sample was %s." % word), [], word)
        # surpassing is a plain verb in a manuscript, so it flags by density only
        self.assertEqual(hits(family, "The sample was surpassing."), [])
        self.assertNotEqual(hits("vocabulary-density", "The sample was surpassing."), [])

    def test_each_rule_of_a_corpus_word_cites_a_corpus_row_key(self):
        for label in ("delve", "underscore", "showcase", "meticulous", "intricate", "surpass",
                      "commendable", "excels", "garner"):
            rule = rule_of(family_of(label), label)
            self.assertEqual(rule.tier, "T1", label)
            self.assertIn("corpus:S1", rule.sources, label)
            self.assertIn("corpus:S2", rule.sources, label)

    def test_merged_words_take_tier_t1_and_cite_both_notes(self):
        for label in ("pivotal", "crucial", "comprehensive", "seamless", "leverage", "harness", "realm"):
            rule = rule_of(family_of(label), label)
            self.assertEqual(rule.tier, "T1", label)
            self.assertTrue(any(k.startswith("corpus:") for k in rule.sources), label)
            self.assertTrue(any(k.startswith("authors:") for k in rule.sources), label)

    def test_author_only_words_stay_at_t3(self):
        for label in ("journey", "plethora", "paramount", "ever-evolving", "myriad", "embark"):
            rule = rule_of("vocabulary-excess", label)
            self.assertEqual(rule.tier, "T3", label)

    def test_figurative_rules_follow_the_notes(self):
        for label in ("load-bearing", "cornerstone", "backbone"):
            self.assertEqual(rule_of("figurative-load", label).tier, "T3", label)
            self.assertEqual(rule_of("figurative-load", label).sources, ["authors:S11"], label)
        self.assertEqual(rule_of("figurative-load", "landscape").tier, "T2")

    def test_ordinary_science_verbs_are_not_listed(self):
        for sentence in ("The sample was enhanced.", "Enhancers were mapped.", "The region encompasses 3 genes.",
                         "We emphasize that the sample was small.", "The kinase aligns with the helix."):
            self.assertEqual(all_hits(sentence), [], sentence)

    def test_overlapping_hits_are_possible_across_families(self):
        sentence = "Marlin-2 plays a pivotal role in drought tolerance."
        found = all_hits(sentence)
        self.assertIn(("importance-puffery", "plays a pivotal role"), found)
        self.assertIn(("vocabulary-excess", "pivotal"), found)


# ---------------------------------------------------------------------------------------
# Word notation
# ---------------------------------------------------------------------------------------

class WordNotationTests(unittest.TestCase):
    def regex(self, entries, case_sensitive=False):
        return pp.words_pattern(entries, case_sensitive)

    def test_star_means_a_stem_with_any_ending(self):
        rx = self.regex(["delv*"])
        for word in ("delve", "delves", "delving", "delved", "Delve", "DELVING"):
            self.assertTrue(rx.search(word), word)
        for word in ("develop", "delicate", "undelv"):
            self.assertIsNone(rx.search(word), word)

    def test_plain_entry_means_the_exact_word(self):
        rx = self.regex(["delve"])
        self.assertTrue(rx.search("to delve"))
        self.assertIsNone(rx.search("he delves"))
        self.assertIsNone(rx.search("undelve"))

    def test_leading_word_boundary(self):
        rx = self.regex(["pivot*"])
        self.assertTrue(rx.search("a pivotal step"))
        self.assertIsNone(rx.search("an unpivotal step"))

    def test_hyphen_and_space_join_words(self):
        rx = self.regex(["cutting-edge"])
        for text in ("cutting-edge", "cutting edge", "Cutting-Edge"):
            self.assertTrue(rx.search(text), text)
        self.assertIsNone(rx.search("cuttingedge"))

    def test_several_entries_make_one_pattern(self):
        rx = self.regex(["lean into", "leans into"])
        self.assertTrue(rx.search("She leans into it."))
        self.assertTrue(rx.search("We lean into it."))
        self.assertIsNone(rx.search("We leaned into it."))

    def test_case_sensitive_flag(self):
        rx = self.regex(["Delve"], case_sensitive=True)
        self.assertTrue(rx.search("Delve in"))
        self.assertIsNone(rx.search("delve in"))

    def test_lower_only_makes_the_first_letter_lower_case(self):
        rx = pp.words_pattern(["foster*", "garner*"], False, True)
        for text in ("to foster collaboration", "she fosters", "it garnered attention", "FOSTERED"[:0] + "fostering"):
            self.assertTrue(rx.search(text), text)
        for text in ("Foster et al.", "Garner and colleagues", "FOSTER", "A paper by Foster."):
            self.assertIsNone(rx.search(text), text)
        # the rest of the word stays case-insensitive
        self.assertTrue(rx.search("fOSTER"))

    def test_lower_only_needs_a_lower_case_entry(self):
        with self.assertRaises(pp.PatternError):
            pp.words_pattern(["Foster*"], False, True)

    def test_bad_entries_raise(self):
        for bad in ("*delv", "de*lv", "", "a b!", "x*y", "delv**", " ", "9lives"):
            with self.assertRaises(pp.PatternError, msg=repr(bad)):
                self.regex([bad])
        with self.assertRaises(pp.PatternError):
            self.regex([])


# ---------------------------------------------------------------------------------------
# The loader
# ---------------------------------------------------------------------------------------

def base_data():
    return {
        "version": 1,
        "as_of": "2026-10-23",
        "families": [
            {"id": "alpha", "title": "Alpha", "mode": "each", "max_per_1000": None,
             "strategy": "Fix it.", "delete_ok": False,
             "rules": [{"tier": "T3", "sources": ["authors:S1"], "label": "one", "regex": "\\bfoo\\b"}]},
            {"id": "beta", "title": "Beta", "mode": "density", "max_per_1000": 2,
             "strategy": "Fix it.", "delete_ok": True,
             "rules": [{"tier": "T2", "sources": ["guides:S1"], "label": "two", "words": ["bar*"],
                        "unless": "baz", "unless_citation": True, "note": "A note."}]},
            {"id": "gamma", "title": "Gamma", "mode": "each", "strategy": "Fix it.",
             "delete_ok": False, "check": "staccato", "params": {"run": 3, "max_words": 5},
             "tier": "T3", "sources": ["authors:S1"]},
        ],
    }


class LoaderTests(unittest.TestCase):
    def parse(self, mutate=None):
        data = base_data()
        if mutate:
            mutate(data)
        return pp.parse_data(data)

    def fails(self, mutate, *fragments):
        with self.assertRaises(pp.PatternError) as ctx:
            self.parse(mutate)
        message = str(ctx.exception)
        for fragment in fragments:
            self.assertIn(fragment, message)
        return message

    def test_base_data_loads(self):
        patterns = self.parse()
        self.assertEqual([f.id for f in patterns.families], ["alpha", "beta", "gamma"])
        self.assertEqual(patterns.as_of, "2026-10-23")
        self.assertEqual(patterns.disabled, [])
        beta = patterns.family("beta")
        self.assertEqual(beta.max_per_1000, 2)
        rule = beta.rules[0]
        self.assertEqual((rule.tier, rule.label, rule.sources), ("T2", "two", ["guides:S1"]))
        self.assertTrue(rule.unless_citation)
        self.assertEqual(rule.note, "A note.")
        self.assertEqual(rule.words, ["bar*"])
        self.assertTrue(rule.regex.search("Bars"))
        self.assertTrue(rule.unless.search("BAZ"))
        self.assertTrue(patterns.family("alpha").rules[0].regex.search("a foo b"))
        gamma = patterns.family("gamma")
        self.assertEqual((gamma.check, gamma.params, gamma.tier, gamma.sources),
                         ("staccato", {"run": 3, "max_words": 5}, "T3", ["authors:S1"]))

    def test_family_lookup(self):
        patterns = self.parse()
        self.assertEqual(patterns.family("alpha").title, "Alpha")
        with self.assertRaises(KeyError):
            patterns.family("missing")

    def test_bad_regex_names_family_and_rule(self):
        def mutate(d):
            d["families"][0]["rules"][0]["regex"] = "(unclosed"
        self.fails(mutate, "alpha", "one", "regex")

    def test_bad_unless_names_family_and_rule(self):
        def mutate(d):
            d["families"][1]["rules"][0]["unless"] = "[bad"
        self.fails(mutate, "beta", "two", "unless")

    def test_regex_that_matches_the_empty_string_is_refused(self):
        def mutate(d):
            d["families"][0]["rules"][0]["regex"] = "x*"
        self.fails(mutate, "alpha", "one", "empty")

    def test_unknown_tier(self):
        def mutate(d):
            d["families"][0]["rules"][0]["tier"] = "T4"
        self.fails(mutate, "alpha", "one", "tier")

    def test_missing_or_empty_sources(self):
        def missing(d):
            del d["families"][0]["rules"][0]["sources"]
        self.fails(missing, "alpha", "one", "sources")

        def empty(d):
            d["families"][0]["rules"][0]["sources"] = []
        self.fails(empty, "alpha", "one", "sources")

    def test_bad_source_key(self):
        for bad in ("corpus", "corpus:1", "corpus:S0", "other:S1", "corpus:S01", 5):
            def mutate(d, bad=bad):
                d["families"][0]["rules"][0]["sources"] = [bad]
            self.fails(mutate, "alpha", "one")

    def test_regex_and_words_together_or_neither(self):
        def both(d):
            d["families"][0]["rules"][0]["words"] = ["foo"]
        self.fails(both, "alpha", "one")

        def neither(d):
            del d["families"][0]["rules"][0]["regex"]
        self.fails(neither, "alpha", "one")

    def test_unknown_key_in_a_rule_and_a_family(self):
        def rule_key(d):
            d["families"][0]["rules"][0]["regexx"] = "x"
        self.fails(rule_key, "alpha", "one", "regexx")

        def family_key(d):
            d["families"][0]["modes"] = "x"
        self.fails(family_key, "alpha", "modes")

    def test_unknown_top_level_key(self):
        def mutate(d):
            d["extra"] = 1
        self.fails(mutate, "extra")

    def test_duplicate_family_id_and_rule_label(self):
        def family(d):
            d["families"][1]["id"] = "alpha"
        self.fails(family, "alpha")

        def label(d):
            d["families"][0]["rules"].append(copy.deepcopy(d["families"][0]["rules"][0]))
        self.fails(label, "alpha", "one")

    def test_density_needs_a_threshold_and_each_needs_none(self):
        def density(d):
            d["families"][1]["max_per_1000"] = 0
        self.fails(density, "beta", "max_per_1000")

        def missing(d):
            d["families"][1]["max_per_1000"] = None
        self.fails(missing, "beta", "max_per_1000")

        def each(d):
            d["families"][0]["max_per_1000"] = 3
        self.fails(each, "alpha", "max_per_1000")

        def boolean(d):
            d["families"][1]["max_per_1000"] = True
        self.fails(boolean, "beta", "max_per_1000")

    def test_bad_mode(self):
        def mutate(d):
            d["families"][0]["mode"] = "always"
        self.fails(mutate, "alpha", "mode")

    def test_bad_types(self):
        def delete_ok(d):
            d["families"][0]["delete_ok"] = "no"
        self.fails(delete_ok, "alpha", "delete_ok")

        def unless_citation(d):
            d["families"][1]["rules"][0]["unless_citation"] = "yes"
        self.fails(unless_citation, "beta", "two", "unless_citation")

        def strategy(d):
            d["families"][0]["strategy"] = ""
        self.fails(strategy, "alpha", "strategy")

        def families(d):
            d["families"] = []
        self.fails(families)

    def test_structural_family_checks(self):
        def check(d):
            d["families"][2]["check"] = "unknown"
        self.fails(check, "gamma", "check")

        def params(d):
            d["families"][2]["params"] = {"run": "three", "max_words": 5}
        self.fails(params, "gamma", "run")

        def extra_param(d):
            d["families"][2]["params"]["other"] = 1
        self.fails(extra_param, "gamma", "other")

        def missing_param(d):
            del d["families"][2]["params"]["max_words"]
        self.fails(missing_param, "gamma", "max_words")

        def with_rules(d):
            d["families"][2]["rules"] = d["families"][0]["rules"]
        self.fails(with_rules, "gamma")

        def no_tier(d):
            del d["families"][2]["tier"]
        self.fails(no_tier, "gamma", "tier")

        def neither(d):
            del d["families"][0]["rules"]
        self.fails(neither, "alpha")

    def test_case_sensitive_rules(self):
        def mutate(d):
            d["families"][0]["rules"][0]["regex"] = "Foo"
            d["families"][0]["rules"][0]["case_sensitive"] = True
        patterns = self.parse(mutate)
        rule = patterns.family("alpha").rules[0]
        self.assertTrue(rule.case_sensitive)
        self.assertTrue(rule.regex.search("Foo"))
        self.assertIsNone(rule.regex.search("foo"))

    def test_severity_defaults_to_flag_and_accepts_info(self):
        patterns = self.parse()
        self.assertEqual(patterns.family("alpha").rules[0].severity, "flag")

        def info(d):
            d["families"][0]["rules"][0]["severity"] = "info"
        self.assertEqual(self.parse(info).family("alpha").rules[0].severity, "info")

        def bad(d):
            d["families"][0]["rules"][0]["severity"] = "warn"
        self.fails(bad, "alpha", "one", "severity")

    def test_lower_only_rules(self):
        def good(d):
            d["families"][1]["rules"][0]["lower_only"] = True
        rule = self.parse(good).family("beta").rules[0]
        self.assertTrue(rule.lower_only)
        self.assertTrue(rule.regex.search("bars"))
        self.assertIsNone(rule.regex.search("Bars"))

        def with_regex(d):
            d["families"][0]["rules"][0]["lower_only"] = True
        self.fails(with_regex, "alpha", "one", "lower_only")

        def not_bool(d):
            d["families"][1]["rules"][0]["lower_only"] = "yes"
        self.fails(not_bool, "beta", "two", "lower_only")

        def upper_entry(d):
            d["families"][1]["rules"][0]["lower_only"] = True
            d["families"][1]["rules"][0]["words"] = ["Bar*"]
        self.fails(upper_entry, "beta", "two", "lower-case")

    def test_fires_applies_unless_and_the_citation_flag(self):
        patterns = self.parse()
        beta = patterns.family("beta").rules[0]
        self.assertTrue(beta.fires("a bar here"))
        self.assertFalse(beta.fires("a bar and baz here"))
        self.assertFalse(beta.fires("a bar here", cited=True))
        self.assertFalse(beta.fires("nothing to see"))
        alpha = patterns.family("alpha").rules[0]
        self.assertTrue(alpha.fires("a foo b", cited=True))
        self.assertTrue(alpha.fires("a foo b"))
        self.assertFalse(alpha.fires("a food b"))

    def test_new_structural_parameters(self):
        def repeated(d, **changes):
            d["families"][2]["check"] = "repeated_openers"
            params = {"run": 3, "ignore": ["the"], "ignored_compare_words": 2}
            params.update(changes)
            d["families"][2]["params"] = params
        patterns = self.parse(repeated)
        self.assertEqual(patterns.family("gamma").params["ignored_compare_words"], 2)
        for bad in (0, "2", True, 1.5, None):
            self.fails(lambda d, bad=bad: repeated(d, ignored_compare_words=bad), "gamma", "ignored_compare_words")

        def missing(d):
            repeated(d)
            del d["families"][2]["params"]["ignored_compare_words"]
        self.fails(missing, "gamma", "ignored_compare_words")

        def question(d, **changes):
            d["families"][2]["check"] = "question_answer"
            params = {"answers": ["the"], "skip_paragraph_start": True}
            params.update(changes)
            d["families"][2]["params"] = params
        self.assertTrue(self.parse(question).family("gamma").params["skip_paragraph_start"])
        for bad in ("yes", 1, None):
            self.fails(lambda d, bad=bad: question(d, skip_paragraph_start=bad), "gamma", "skip_paragraph_start")
        self.fails(lambda d: question(d, answers=[]), "gamma", "answers")
        self.fails(lambda d: question(d, answers="the"), "gamma", "answers")

    def test_messages_list_the_valid_choices(self):
        message = self.fails(lambda d: d["families"][0]["rules"][0].__setitem__("regexx", "x"), "regexx")
        self.assertIn("The valid keys are tier, sources, label, regex, words", message)
        message = self.fails(lambda d: d["families"][0].__setitem__("modes", "x"), "modes")
        self.assertIn("The valid keys are id, title, mode", message)
        for bad in ("blog:S1", "corpus", "corpus:1"):
            message = self.fails(lambda d, bad=bad: d["families"][0]["rules"][0].__setitem__("sources", [bad]), "alpha", "one")
            self.assertIn("corpus, wikipedia, guides, authors, craft", message)
        message = self.fails(lambda d: d["families"][0]["rules"][0].__setitem__("sources", ["blog:S1"]), "blog")
        self.assertIn("unknown note", message)

    def test_module_docstring_sentences_are_short(self):
        for block in re.split(r"\n\s*\n", pp.__doc__):
            for item in re.split(r"\n- ", block):
                flat = " ".join(item.split())
                for sentence in re.split(r"(?<=[.!?])\s+", flat):
                    self.assertLessEqual(len(sentence.split()), 25, sentence)

    def test_missing_and_bad_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(pp.PatternError):
                pp.load_patterns(data_path=os.path.join(tmp, "missing.json"))
            bad = os.path.join(tmp, "bad.json")
            with open(bad, "w", encoding="utf-8") as handle:
                handle.write("{not json")
            with self.assertRaises(pp.PatternError) as ctx:
                pp.load_patterns(data_path=bad)
            self.assertIn("bad.json", str(ctx.exception))
            good = os.path.join(tmp, "good.json")
            with open(good, "w", encoding="utf-8") as handle:
                json.dump(base_data(), handle)
            self.assertEqual([f.id for f in pp.load_patterns(data_path=good).families],
                             ["alpha", "beta", "gamma"])

    def test_pattern_error_is_a_value_error(self):
        self.assertTrue(issubclass(pp.PatternError, ValueError))

    def test_load_patterns_reads_the_real_data_file(self):
        patterns = pp.load_patterns()
        self.assertEqual([f.id for f in patterns.families], FAMILY_IDS)
        self.assertTrue(os.path.samefile(pp.DATA_FILE, DATA_PATH))


# ---------------------------------------------------------------------------------------
# The project file
# ---------------------------------------------------------------------------------------

class ProjectFileTests(unittest.TestCase):
    def merged(self, project, name="prose-style.yaml"):
        return pp.apply_project(pp.parse_data(base_data()), project, name)

    def fails(self, project, *fragments):
        with self.assertRaises(pp.PatternError) as ctx:
            self.merged(project)
        message = str(ctx.exception)
        for fragment in fragments:
            self.assertIn(fragment, message)

    def test_empty_project_changes_nothing(self):
        patterns = self.merged({})
        self.assertEqual([f.id for f in patterns.families], ["alpha", "beta", "gamma"])
        self.assertEqual(patterns.disabled, [])

    def test_enabled_false_removes_a_family(self):
        patterns = self.merged({"families": {"alpha": {"enabled": False}}})
        self.assertEqual([f.id for f in patterns.families], ["beta", "gamma"])
        self.assertEqual([f.id for f in patterns.disabled], ["alpha"])
        self.assertFalse(patterns.disabled[0].enabled)
        self.assertEqual(patterns.family("alpha").id, "alpha")

    def test_enabled_true_keeps_a_family(self):
        patterns = self.merged({"families": {"alpha": {"enabled": True}}})
        self.assertEqual([f.id for f in patterns.families], ["alpha", "beta", "gamma"])
        self.assertEqual(patterns.disabled, [])

    def test_max_per_1000_changes_the_threshold(self):
        patterns = self.merged({"families": {"beta": {"max_per_1000": 7.5}}})
        self.assertEqual(patterns.family("beta").max_per_1000, 7.5)

    def test_mode_changes_the_mode(self):
        patterns = self.merged({"families": {"beta": {"mode": "each"}}})
        self.assertEqual(patterns.family("beta").mode, "each")
        patterns = self.merged({"families": {"alpha": {"mode": "density", "max_per_1000": 4}}})
        self.assertEqual(patterns.family("alpha").mode, "density")
        self.assertEqual(patterns.family("alpha").max_per_1000, 4)

    def test_density_without_a_threshold_is_refused(self):
        self.fails({"families": {"alpha": {"mode": "density"}}}, "alpha", "max_per_1000")

    def test_the_input_patterns_stay_unchanged(self):
        base = pp.parse_data(base_data())
        pp.apply_project(base, {"families": {"beta": {"max_per_1000": 9}, "alpha": {"enabled": False}}}, "p.yaml")
        self.assertEqual(base.family("beta").max_per_1000, 2)
        self.assertEqual([f.id for f in base.families], ["alpha", "beta", "gamma"])

    def test_a_typo_in_a_family_id_names_the_id(self):
        self.fails({"families": {"alhpa": {"enabled": False}}}, "alhpa")
        self.fails({"families": {"Alpha": {"enabled": False}}}, "Alpha")

    def test_unknown_key_names_the_key(self):
        self.fails({"families": {"alpha": {"enabeld": False}}}, "enabeld", "alpha")
        self.fails({"famlies": {}}, "famlies")
        self.fails({"extra_patterns": [{"id": "x1", "title": "X", "regex": "x", "strategy": "s", "colour": 1}]},
                   "colour", "x1")

    def test_bad_types_name_the_key(self):
        self.fails({"families": {"alpha": {"enabled": "no"}}}, "enabled", "alpha")
        self.fails({"families": {"beta": {"max_per_1000": "3"}}}, "max_per_1000", "beta")
        self.fails({"families": {"beta": {"max_per_1000": 0}}}, "max_per_1000", "beta")
        self.fails({"families": {"beta": {"max_per_1000": True}}}, "max_per_1000", "beta")
        self.fails({"families": {"beta": {"mode": "often"}}}, "mode", "beta")
        self.fails({"families": ["alpha"]}, "families")
        self.fails({"families": {"alpha": "off"}}, "alpha")
        self.fails({"extra_patterns": {"id": "x1"}}, "extra_patterns")
        self.fails({"extra_patterns": ["x1"]}, "extra_patterns")
        self.fails(["alpha"], "mapping")

    def test_extra_pattern_gets_tier_t3_and_the_project_key(self):
        project = {"extra_patterns": [
            {"id": "my-phrase", "title": "My phrase", "regex": "\\bfoo bar\\b", "strategy": "Say it plainly."}]}
        patterns = self.merged(project, name="prose-style.yaml")
        family = patterns.family("my-phrase")
        self.assertEqual(patterns.families[-1].id, "my-phrase")
        self.assertEqual(family.mode, "each")
        self.assertIsNone(family.max_per_1000)
        self.assertEqual(family.strategy, "Say it plainly.")
        self.assertEqual(family.title, "My phrase")
        self.assertFalse(family.delete_ok)
        self.assertEqual(len(family.rules), 1)
        rule = family.rules[0]
        self.assertEqual(rule.tier, "T3")
        self.assertEqual(rule.sources, ["project:prose-style.yaml"])
        self.assertTrue(rule.regex.search("a Foo Bar here"))
        self.assertIsNone(rule.unless)
        self.assertFalse(rule.unless_citation)

    def test_extra_pattern_key_uses_the_file_name(self):
        project = {"extra_patterns": [{"id": "p1", "title": "P", "words": ["foo*"], "strategy": "s"}]}
        patterns = self.merged(project, name="other.yaml")
        self.assertEqual(patterns.family("p1").rules[0].sources, ["project:other.yaml"])

    def test_extra_pattern_with_words_unless_mode_and_threshold(self):
        project = {"extra_patterns": [
            {"id": "p2", "title": "P2", "words": ["foo*", "bar"], "strategy": "s", "mode": "density",
             "max_per_1000": 1.5, "unless": "baz"}]}
        family = self.merged(project).family("p2")
        self.assertEqual(family.mode, "density")
        self.assertEqual(family.max_per_1000, 1.5)
        rule = family.rules[0]
        self.assertTrue(rule.regex.search("Fooing"))
        self.assertIsNone(rule.regex.search("bars"))
        self.assertTrue(rule.unless.search("a baz"))

    def test_bad_extra_patterns_name_the_pattern(self):
        good = {"id": "p3", "title": "P3", "regex": "foo", "strategy": "s"}

        def variant(**changes):
            item = dict(good)
            item.update(changes)
            return {"extra_patterns": [item]}

        self.fails(variant(regex="(unclosed"), "p3", "regex")
        self.fails(variant(unless="[bad"), "p3", "unless")
        self.fails(variant(regex="x*"), "p3", "empty")
        self.fails(variant(words=["foo"]), "p3")
        self.fails(variant(mode="density"), "p3", "max_per_1000")
        self.fails(variant(mode="often"), "p3", "mode")
        self.fails(variant(id="alpha"), "alpha")
        self.fails(variant(id="Bad Id"), "Bad Id")
        self.fails({"extra_patterns": [good, good]}, "p3")
        for missing in ("id", "title", "strategy"):
            item = dict(good)
            del item[missing]
            self.fails({"extra_patterns": [item]}, missing)
        item = dict(good)
        del item["regex"]
        self.fails({"extra_patterns": [item]}, "p3", "regex")

    def two_rule_patterns(self):
        data = base_data()
        data["families"][0]["rules"].append(
            {"tier": "T3", "sources": ["authors:S1"], "label": "uno", "regex": "\\buno\\b"})
        return pp.parse_data(data)

    def test_disable_labels_turns_off_rules(self):
        patterns = self.two_rule_patterns()
        merged = pp.apply_project(patterns, {"families": {"alpha": {"disable_labels": ["one"]}}}, "p.yaml")
        alpha = merged.family("alpha")
        self.assertEqual([r.label for r in alpha.rules], ["uno"])
        self.assertEqual([r.label for r in alpha.disabled_rules], ["one"])
        self.assertEqual([r.label for r in patterns.family("alpha").rules], ["one", "uno"])
        self.assertEqual(patterns.family("alpha").disabled_rules, [])

    def test_disable_labels_errors_name_the_valid_labels(self):
        patterns = self.two_rule_patterns()

        def fails(spec, *fragments):
            with self.assertRaises(pp.PatternError) as ctx:
                pp.apply_project(patterns, {"families": spec}, "prose-style.yaml")
            for fragment in fragments:
                self.assertIn(fragment, str(ctx.exception))
        fails({"alpha": {"disable_labels": ["nope"]}}, "nope", "one, uno", "alpha")
        fails({"alpha": {"disable_labels": ["one", "uno"]}}, "every rule", "enabled")
        fails({"alpha": {"disable_labels": ["one", "one"]}}, "twice")
        fails({"alpha": {"disable_labels": "one"}}, "disable_labels")
        fails({"alpha": {"disable_labels": []}}, "disable_labels")
        fails({"alpha": {"disable_labels": [1]}}, "disable_labels")
        fails({"gamma": {"disable_labels": ["one"]}}, "gamma", "no rules")

    def test_disable_labels_works_on_the_real_data(self):
        project = {"families": {"vocabulary-density": {"disable_labels": ["robust"]}}}
        merged = pp.apply_project(PATTERNS, project, "prose-style.yaml")
        self.assertNotIn("robust", [r.label for r in merged.family("vocabulary-density").rules])
        self.assertIn("robust", [r.label for r in PATTERNS.family("vocabulary-density").rules])

    def test_an_override_that_changes_nothing_is_refused(self):
        self.fails({"families": {"alpha": {"max_per_1000": 3}}}, "alpha", "max_per_1000", "mode: density")
        self.fails({"families": {"beta": {"mode": "density"}}}, "beta", "already", "density")
        self.fails({"families": {"alpha": {"mode": "each"}}}, "alpha", "already")
        self.fails({"families": {"gamma": {"mode": "density", "max_per_1000": 2}}}, "gamma", "structural")
        self.fails({"families": {"gamma": {"mode": "each"}}}, "gamma", "structural")
        # the same keys do work when they change something
        self.assertEqual(self.merged({"families": {"alpha": {"mode": "density", "max_per_1000": 3}}}).family("alpha").max_per_1000, 3)
        self.assertEqual(self.merged({"families": {"beta": {"mode": "each"}}}).family("beta").mode, "each")
        self.assertEqual(self.merged({"families": {"beta": {"max_per_1000": 9}}}).family("beta").max_per_1000, 9)

    def test_unknown_family_message_lists_the_ids(self):
        with self.assertRaises(pp.PatternError) as ctx:
            self.merged({"families": {"alhpa": {"enabled": False}}})
        self.assertIn("The valid ids are alpha, beta, gamma", str(ctx.exception))
        with self.assertRaises(pp.PatternError) as ctx:
            self.merged({"families": {"alpha": {"enabeld": False}}})
        self.assertIn("The valid keys are enabled, max_per_1000, mode, disable_labels", str(ctx.exception))

    def test_files_are_read_through_load_patterns(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = os.path.join(tmp, "data.json")
            with open(data, "w", encoding="utf-8") as handle:
                json.dump(base_data(), handle)
            project_dir = os.path.join(tmp, "project")
            os.makedirs(os.path.join(project_dir, "docs"))
            with open(os.path.join(project_dir, "docs", "prose-style.yaml"), "w", encoding="utf-8") as handle:
                handle.write(
                    "families:\n  alpha:\n    enabled: false\n  beta:\n    max_per_1000: 6\n"
                    "extra_patterns:\n  - id: p4\n    title: P4\n    regex: '\\bfoo\\b'\n    strategy: Fix it.\n")
            patterns = pp.load_patterns(project_dir=project_dir, data_path=data)
            self.assertEqual([f.id for f in patterns.families], ["beta", "gamma", "p4"])
            self.assertEqual(patterns.family("beta").max_per_1000, 6)
            self.assertEqual(patterns.family("p4").rules[0].sources, ["project:prose-style.yaml"])
            self.assertEqual([f.id for f in patterns.disabled], ["alpha"])

    def test_a_project_file_with_a_typo_exits_through_pattern_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = os.path.join(tmp, "data.json")
            with open(data, "w", encoding="utf-8") as handle:
                json.dump(base_data(), handle)
            with open(os.path.join(tmp, "prose-style.yaml"), "w", encoding="utf-8") as handle:
                handle.write("families:\n  alhpa:\n    enabled: false\n")
            with self.assertRaises(pp.PatternError) as ctx:
                pp.load_patterns(project_dir=tmp, data_path=data)
            self.assertIn("alhpa", str(ctx.exception))
            self.assertIn("prose-style.yaml", str(ctx.exception))

    def test_bad_yaml_and_empty_yaml(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = os.path.join(tmp, "data.json")
            with open(data, "w", encoding="utf-8") as handle:
                json.dump(base_data(), handle)
            path = os.path.join(tmp, "prose-style.yaml")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write("families: [unclosed\n")
            with self.assertRaises(pp.PatternError):
                pp.load_patterns(project_dir=tmp, data_path=data)
            with open(path, "w", encoding="utf-8") as handle:
                handle.write("")
            patterns = pp.load_patterns(project_dir=tmp, data_path=data)
            self.assertEqual([f.id for f in patterns.families], ["alpha", "beta", "gamma"])

    def test_project_file_works_on_the_real_data(self):
        project = {"families": {"em-dash": {"max_per_1000": 5}, "vocabulary-excess": {"enabled": False}}}
        patterns = pp.apply_project(PATTERNS, project, "prose-style.yaml")
        self.assertEqual(patterns.family("em-dash").max_per_1000, 5)
        self.assertNotIn("vocabulary-excess", [f.id for f in patterns.families])
        self.assertEqual(len(patterns.families), len(FAMILY_IDS) - 1)
        self.assertEqual(PATTERNS.family("em-dash").max_per_1000, 2.5)


class FindProjectFileTests(unittest.TestCase):
    def touch(self, root, *parts):
        path = os.path.join(root, *parts)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("families: {}\n")
        return path

    def test_none_gives_none(self):
        self.assertIsNone(pp.find_project_file(None))

    def test_empty_folder_gives_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(pp.find_project_file(tmp))

    def test_search_order_is_current_folder_docs_then_claude(self):
        with tempfile.TemporaryDirectory() as tmp:
            claude = self.touch(tmp, ".claude", "prose-style.yaml")
            self.assertEqual(pp.find_project_file(tmp), claude)
            docs = self.touch(tmp, "docs", "prose-style.yaml")
            self.assertEqual(pp.find_project_file(tmp), docs)
            here = self.touch(tmp, "prose-style.yaml")
            self.assertEqual(pp.find_project_file(tmp), here)

    def test_other_names_are_ignored(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.touch(tmp, "prose-style.yml")
            self.touch(tmp, "docs", "style.yaml")
            os.makedirs(os.path.join(tmp, ".claude", "prose-style.yaml"))
            self.assertIsNone(pp.find_project_file(tmp))


if __name__ == "__main__":
    unittest.main()
