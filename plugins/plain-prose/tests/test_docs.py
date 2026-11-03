"""Tests for the documents of plain-prose: the references, the example, the spec, the command and the READMEs.

All text in this file is made up. The tests check these groups of facts. The class names are
ReferenceTests, ExampleTests, SpecTests, CommandTests, OwnTextTests, ReadmeTests and PrivacyTests.

References. `references/rewrite-rules.md` has one section for each family id of the data and
the two sections "Rules for every rewrite" and "Hedges". `references/model-checks.md` holds
one check on each list line. A rule line is a list line of the sections "Rules for every
rewrite" and "Hedges", a line "Strategy: ..." of a family section, and a list line of the
model checks. Each rule line ends with a tag `(T<n>, <note>:S<n>)`. The key resolves to a line
`- S<n> ` of the note. The tier tag is equal to or weaker than the strongest tier that the
notes state for the key. No cited key points to a line that holds UNVERIFIED.
Each family section holds one strategy line, one line "Delete when", one line "Keep" and two
before-and-after examples in code spans. The strategy line holds the strategy of the data. The
"after" text of an example holds no flagged finding of any family. The "before" text holds a
flagged finding of its own family. Each pair passes the ten guards of `prose_verify.py` as one
proposal that covers the whole "before" text, unless a named exception says why not. Both references
pass the detector with zero flagged findings.
They hold no em dash, no banned word, no "not just" and no sentence of more than 25 words.

Example. The expected file equals the output of `prose_lint.py` on the made-up manuscript, run
in the plugin folder. The manuscript holds flagged findings of at least 10 families, a figure,
display math, a table and two citations. The clean sentences stay quiet.

Spec. The spec says "implemented", names every script file, lists every family id and holds no
`family` where a proposal field is meant. The lines on the verifier command line, on the proposals
and on the approval carry their fixed text.

Command. The front matter of `commands/plain-prose.md` parses as YAML. Each `allowed-tools` entry is
used by the text, and each command that the text runs is covered by an entry. The extraction rule:
a command is a non-blank line of a fenced `bash` block, or an inline code span that starts with
`python3`, `git` or `mkdir`. A `Bash(...)` entry is a glob in which `*` stands for any text. A tool
without `Bash` is used when the text names it in a code span. The command names the seven steps in
order, and it holds one pinned phrase for each statement that the spec asks for. Each `scripts/`,
`references/`, `data/` and `examples/` path that the command or the README names exists.

Own text. The README and the command pass `prose_lint.py` with zero flagged findings. They hold no
em dash, no banned word outside a code span and no "not just". The README and the references hold no
description of more than 25 words and no instruction of more than 20 words. An instruction starts
with a word of INSTRUCTION_STARTS. A code span counts as one word. A table cell of the README follows
the same limit. The command holds no sentence of more than 20 words. The command, the README and the
references hold no passive form (a form of be with a participle).
No user-facing text claims that the plugin evades or beats a detector, makes text undetectable, detects
text that a model wrote or tells who wrote a text. FORBIDDEN_CLAIMS lists the patterns of such claims.
The command and the README keep one term for each thing (author, finding, series).

README. The sections come in a fixed order. The families table is the table that a script builds
from `data/patterns.json`. The guards table lists the ten guards in the order of the code. Each
limit has one pinned phrase. The claims about the guards and the hedge list hold in the code. The
numbers that the README takes from the corpus note stand in that note. The plugin version equals
the version of the manifest. The root README has a section for the plugin.

Privacy. No reference, no example file, no README and no command text holds an absolute home path,
an e-mail address, a DOI or a handle of the author. The name of the marketplace and the slug of the
repository are the two allowed handles.
"""
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest

import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
PLUGIN_DIR = os.path.dirname(HERE)
REPO_DIR = os.path.dirname(os.path.dirname(PLUGIN_DIR))
sys.path.insert(0, os.path.join(PLUGIN_DIR, "scripts"))
sys.path.insert(0, HERE)

import prose_lint  # noqa: E402
import prose_mask  # noqa: E402
import prose_patterns  # noqa: E402
import prose_text  # noqa: E402
import prose_verify  # noqa: E402
from test_patterns import key_tiers, note_rows, source_lines  # noqa: E402

DATA_PATH = os.path.join(PLUGIN_DIR, "data", "patterns.json")
SCRIPTS_DIR = os.path.join(PLUGIN_DIR, "scripts")
REFERENCES_DIR = os.path.join(PLUGIN_DIR, "references")
EXAMPLES_DIR = os.path.join(PLUGIN_DIR, "examples")
REWRITE_RULES = os.path.join(REFERENCES_DIR, "rewrite-rules.md")
MODEL_CHECKS = os.path.join(REFERENCES_DIR, "model-checks.md")
MANUSCRIPT = os.path.join(EXAMPLES_DIR, "made-up-manuscript.tex")
EXPECTED = os.path.join(EXAMPLES_DIR, "made-up-manuscript.expected.txt")
SPEC = os.path.join(REPO_DIR, "docs", "superpowers", "specs", "2026-10-23-plain-prose-design.md")
COMMAND = os.path.join(PLUGIN_DIR, "commands", "plain-prose.md")
README = os.path.join(PLUGIN_DIR, "README.md")
ROOT_README = os.path.join(REPO_DIR, "README.md")
PLUGIN_JSON = os.path.join(PLUGIN_DIR, ".claude-plugin", "plugin.json")
MARKETPLACE_JSON = os.path.join(REPO_DIR, ".claude-plugin", "marketplace.json")
NOTES_DIR = os.path.join(REFERENCES_DIR, "research-notes")

SECTION_RULES = "Rules for every rewrite"
SECTION_HEDGES = "Hedges"
NOTE_NAMES = ("corpus", "wikipedia", "guides", "authors", "craft")
TIER_RANK = {"T1": 1, "T2": 2, "T3": 3}
EM_DASH = "\u2014"

# A rule line ends with this tag: the tier, a comma, a space and the source key.
TAG = re.compile(r"\((T[123]), (corpus|wikipedia|guides|authors|craft):S([1-9][0-9]*)\)$")

# The words of the author's ban list (C1 and C2), as plain words. The test looks for them as
# whole words in the masked text, so a code span may quote them.
BANNED_WORDS = (
    "delve", "leverage", "utilize", "robust", "seamless", "seamlessly", "holistic", "unlock", "elevate",
    "empower", "harness", "navigate", "landscape", "journey", "realm", "tapestry", "testament", "crucial",
    "pivotal", "vital", "comprehensive", "cutting-edge", "state-of-the-art", "game-changer", "paradigm",
    "ecosystem", "synergy", "streamline", "myriad", "plethora", "meticulous", "nuanced", "intricate",
    "boasts", "showcase", "very", "really", "truly", "incredibly", "remarkably", "extremely", "quite",
    "dramatically",
)
BANNED = re.compile(r"\b(?:%s)\b" % "|".join(re.escape(w) for w in BANNED_WORDS), re.I)
MAX_WORDS = 25

PATTERNS = prose_patterns.load_patterns()


# ---------------------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------------------

def read_text(path):
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def family_data():
    """Return the list of family dicts of data/patterns.json."""
    with open(DATA_PATH, encoding="utf-8") as handle:
        return json.load(handle)["families"]


def split_sections(text):
    """Return a list of (heading, lines) for each line that starts with "## ".

    The lines of a section run up to the next heading. The text before the first heading is dropped.
    """
    sections, heading, lines = [], None, []
    for line in text.split("\n"):
        if line.startswith("## "):
            if heading is not None:
                sections.append((heading, lines))
            heading, lines = line[3:].strip(), []
        elif heading is not None:
            lines.append(line)
    if heading is not None:
        sections.append((heading, lines))
    return sections


def rewrite_sections():
    return split_sections(read_text(REWRITE_RULES))


def rule_lines():
    """Return (where, line) for each rule line of the two references. See the module text."""
    found = []
    for heading, lines in rewrite_sections():
        for line in lines:
            if heading in (SECTION_RULES, SECTION_HEDGES) and line.startswith("- "):
                found.append((heading, line))
            elif heading not in (SECTION_RULES, SECTION_HEDGES) and line.startswith("Strategy: "):
                found.append((heading, line))
    for line in read_text(MODEL_CHECKS).split("\n"):
        if line.startswith("- "):
            found.append(("model-checks", line))
    return found


def craft_tiers():
    """Return {"craft:S<n>": strongest tier} as the two tables of craft.md state it.

    The note keeps its tiers in two tables. Section 1 (principles) has a last cell with segments such
    as "T1, 709,577 abstracts, S3. T2, guide, S4". A segment that starts with a tier gives that tier
    to every key of the segment. A segment that starts with UNVERIFIED gives no tier. Section 2
    (rewrite strategy) has a tier cell and a key cell in each row. Every key of the row takes the tier
    that the tier cell names first, as in "T2 for the rule; T1 for the rate". A key that several rows
    name keeps the strongest tier.
    """
    tiers = {}

    def add(number, tier):
        key = "craft:S%s" % number
        if key not in tiers or TIER_RANK[tier] < TIER_RANK[tiers[key]]:
            tiers[key] = tier

    for cells in note_rows("craft"):
        if len(cells) == 4 and re.match(r"^P[0-9]+$", cells[0]):
            for segment in re.split(r"\.\s+(?=(?:T[123]|UNVERIFIED))", cells[3]):
                head = re.match(r"(T[123]|UNVERIFIED)\b", segment)
                if head and head.group(1) != "UNVERIFIED":
                    for number in re.findall(r"\bS([1-9][0-9]*)\b", segment):
                        add(number, head.group(1))
        elif len(cells) == 6 and cells[0] != "Family":
            first = re.match(r"(T[123])\b", cells[4])
            if first:
                for number in re.findall(r"\bS([1-9][0-9]*)\b", cells[5]):
                    add(number, first.group(1))
    return tiers


def key_tier(note, number):
    """Return the strongest tier that the notes state for the key, or None."""
    key = "%s:S%d" % (note, number)
    if note == "craft":
        return craft_tiers().get(key)
    return key_tiers().get(key)


def parse_tag(line):
    """Return (tier, note, number) from the tag at the end of the line, or None."""
    match = TAG.search(line.rstrip())
    if match is None:
        return None
    return match.group(1), match.group(2), int(match.group(3))


def code_spans(line):
    return re.findall(r"`([^`]*)`", line)


def example_texts(lines):
    """Return {(n, "before" or "after"): text} from the lines "Example <n> before: `...`"."""
    found = {}
    for line in lines:
        match = re.match(r"^Example ([12]) (before|after): `(.*)`$", line)
        if match:
            found[(int(match.group(1)), match.group(2))] = match.group(3).replace("&mdash;", EM_DASH)
    return found


def flagged(text, fmt="text"):
    """Return the flagged findings of the text, with every family of the data."""
    return [f for f in prose_lint.lint_text(text, fmt, PATTERNS).findings if f.severity == "flag"]


PLACEHOLDER = re.compile("\ue000[0-9]+\ue001")


def word_count(sentence):
    """Return the length of a masked sentence: its words plus one for each masked span.

    A code span, a citation or a table row stands in the masked text as a placeholder. A reader reads a
    code span as a word, so a placeholder counts as one word.
    """
    return len(prose_text.words(sentence)) + len(PLACEHOLDER.findall(sentence))


def long_sentences(text, fmt="markdown", limit=MAX_WORDS):
    """Return the sentences of the text that have more than `limit` words (MAX_WORDS by default).

    Extraction rule: mask the text, then take the ranges of `prose_text.split_sentences` with the hard
    breaks of the detector. So each list item and each heading is a sentence of its own. Count words with
    `word_count`: the words of `prose_text.words`, and one more for each code span or other masked span.
    """
    masked = prose_mask.mask(text, fmt)
    breaks = prose_lint.hard_breaks(masked)
    found = []
    for start, end in prose_text.split_sentences(masked.text, breaks):
        sentence = masked.text[start:end]
        count = word_count(sentence)
        if count > limit:
            found.append((count, sentence))
    return found


# A sentence that starts with one of these words is an instruction. An instruction has at most 20 words and
# any other sentence has at most 25. The list is closed, so the test stays exact. It holds the first words of
# the instructions of the command, the README and the two references.
INSTRUCTION_STARTS = frozenset((
    "add answer apply ask change check copy count cover create delete do escape find flag give group keep leave "
    "list make mark merge move name never open pick propose put read redo remove repeat replace report run say "
    "search send set show state stop take tell try use verify wait write").split())
INSTRUCTION_LIMIT = 20


def long_instructions(text, fmt="markdown"):
    """Return (count, limit, sentence) for each sentence that exceeds the limit of its kind.

    An instruction starts with a word of INSTRUCTION_STARTS and has at most INSTRUCTION_LIMIT words. Any
    other sentence has at most MAX_WORDS. The extraction and the count are those of `long_sentences`.
    """
    masked = prose_mask.mask(text, fmt)
    found = []
    for start, end in prose_text.split_sentences(masked.text, prose_lint.hard_breaks(masked)):
        sentence = masked.text[start:end]
        first = [w for _, _, w in prose_text.words(sentence)[:1]]
        limit = INSTRUCTION_LIMIT if first and first[0].lower() in INSTRUCTION_STARTS else MAX_WORDS
        count = word_count(sentence)
        if count > limit:
            found.append((count, limit, sentence))
    return found


def table_cell_faults(text, limit=MAX_WORDS):
    """Return (count, sentence) for each sentence of a table cell that has more than `limit` words.

    The masker hides a table row as one span, so the sentence tests never see a cell. This check splits each
    row at the bars, replaces each code span by one word and splits each cell at a full stop.
    """
    found = []
    for line in text.split("\n"):
        if not line.startswith("|") or re.match(r"^\|[-| :]+\|$", line):
            continue
        for cell in line.strip().strip("|").split("|"):
            for sentence in re.split(r"(?<=[.!?])\s+", re.sub(r"`[^`]*`", "X", cell.strip())):
                count = len(re.findall(r"[A-Za-z0-9%'-]+", sentence))
                if count > limit:
                    found.append((count, sentence[:60]))
    return found


def family_section_checks(heading, lines):
    """Return a list of problems with one family section."""
    problems = []
    fields = {"Strategy: ": [], "Delete when: ": [], "Keep: ": []}
    for line in lines:
        for prefix in fields:
            if line.startswith(prefix):
                fields[prefix].append(line)
    for prefix, found in fields.items():
        if len(found) != 1:
            problems.append("%s: %d lines that start with %r" % (heading, len(found), prefix))
    if len(example_texts(lines)) != 4:
        problems.append("%s: needs the four example lines" % heading)
    return problems


# ---------------------------------------------------------------------------------------
# References
# ---------------------------------------------------------------------------------------

# A pair that cannot pass the verifier because it deletes whole sentences goes here as
# {(family id, example number): reason}. Only a family that allows deletion can have an entry. The list is
# empty today: every pair of rewrite-rules.md passes. A pair that fails for another reason needs a new text.
PAIR_EXCEPTIONS = {}


def verify_pair(family_id, before, after):
    """Return the Result of the ten guards for one proposal that rewrites the whole text `before` into `after`.

    The proposal names the family of the section, uses format text and has no voice profile.
    """
    proposal = {"id": "p1", "file": "pair.txt", "start": 0, "end": len(before), "before": before, "after": after,
                "families": [family_id], "reason": "test"}
    return prose_verify.check_proposals([proposal], PATTERNS, read=lambda path: before, fmt="text")[0]


class ReferenceTests(unittest.TestCase):
    def test_rewrite_rules_has_a_section_for_every_family_id(self):
        ids = [family["id"] for family in family_data()]
        self.assertEqual(len(ids), 17)
        headings = [heading for heading, _ in rewrite_sections()]
        for family_id in ids:
            with self.subTest(family=family_id):
                self.assertEqual(headings.count(family_id), 1)

    def test_rewrite_rules_has_only_the_known_sections(self):
        ids = [family["id"] for family in family_data()]
        headings = [heading for heading, _ in rewrite_sections()]
        self.assertEqual(sorted(headings), sorted(ids + [SECTION_RULES, SECTION_HEDGES]))
        self.assertEqual(headings[:2], [SECTION_RULES, SECTION_HEDGES])

    def test_hedges_section_states_the_four_rules(self):
        body = " ".join(dict(rewrite_sections())[SECTION_HEDGES]).lower()
        for phrase in ("never flag a hedge from a word list alone",
                       "keep a hedge that qualifies an inference",
                       "propose an edit for stacked hedges only",
                       "never change a past-tense result to present tense",
                       "keep every quantifier"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, body)

    def test_rules_section_states_the_seven_rules(self):
        body = " ".join(dict(rewrite_sections())[SECTION_RULES]).lower()
        for phrase in ("state the claim", "add no fact", "keep a hedge that carries real doubt",
                       "keep every number, citation and name", "minimum effective edit",
                       "delete a sentence that has no content", "leave a strong human sentence alone"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, body)

    def test_model_checks_state_the_required_checks(self):
        body = " ".join(read_text(MODEL_CHECKS).split()).lower()
        for phrase in ("the meaning is kept", "the portability test", "real doubt",
                       "the voice matches the profile", "rule-of-three padding", "synonym cycling",
                       "fake-profound closer", "no new fact",
                       "still supports the same claim", "its quantifier and its noun", "manual edit"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, body)

    def test_rule_lines_are_found(self):
        # A scan that finds nothing would pass every test below, so pin the counts.
        where = [w for w, _ in rule_lines()]
        self.assertGreaterEqual(where.count(SECTION_RULES), 7)
        self.assertGreaterEqual(where.count(SECTION_HEDGES), 4)
        self.assertEqual(sum(1 for w in where if w not in (SECTION_RULES, SECTION_HEDGES, "model-checks")), 17)
        self.assertGreaterEqual(where.count("model-checks"), 11)

    def test_every_rule_and_check_ends_with_a_tag(self):
        bad = [(w, line[:60]) for w, line in rule_lines() if parse_tag(line) is None]
        self.assertEqual(bad, [], "lines with no tag of the form (T2, craft:S4)")

    def test_every_key_resolves_to_a_line_of_its_note(self):
        bad = []
        for where, line in rule_lines():
            tag = parse_tag(line)
            if tag and tag[2] not in source_lines(tag[1]):
                bad.append("%s: %s:S%d" % (where, tag[1], tag[2]))
        self.assertEqual(bad, [])

    def test_no_cited_key_points_to_an_unverified_line(self):
        bad = []
        for where, line in rule_lines():
            tag = parse_tag(line)
            if tag and "UNVERIFIED" in source_lines(tag[1]).get(tag[2], ""):
                bad.append("%s: %s:S%d" % (where, tag[1], tag[2]))
        self.assertEqual(bad, [])

    def test_the_tier_reader_finds_the_tiers_of_the_craft_note(self):
        # Pin the reader on keys that the note states, so an empty result cannot pass.
        self.assertEqual(key_tier("craft", 3), "T1")
        self.assertEqual(key_tier("craft", 4), "T2")
        self.assertEqual(key_tier("craft", 10), "T1")
        self.assertEqual(key_tier("craft", 17), "T1")
        self.assertIsNone(key_tier("craft", 24))
        self.assertEqual(key_tier("authors", 3), "T3")

    def test_each_tier_tag_is_equal_to_or_weaker_than_the_tier_of_its_key(self):
        # The tier of a key is the strongest tier that the notes state for it (see craft_tiers and
        # test_patterns.key_tiers). A weaker tag is allowed. A stronger tag is a claim without a source.
        bad = []
        for where, line in rule_lines():
            tag = parse_tag(line)
            if tag is None:
                continue
            tier = key_tier(tag[1], tag[2])
            if tier is None or TIER_RANK[tag[0]] < TIER_RANK[tier]:
                bad.append("%s: %s on %s:S%d, the note gives %s" % (where, tag[0], tag[1], tag[2], tier))
        self.assertEqual(bad, [])

    def test_a_t1_tag_has_a_key_that_the_notes_state_as_t1(self):
        # So no T1 rule rests on a guide.
        for where, line in rule_lines():
            tag = parse_tag(line)
            if tag and tag[0] == "T1":
                with self.subTest(where=where, key=tag[2]):
                    self.assertEqual(key_tier(tag[1], tag[2]), "T1")

    def test_a_t3_tag_has_an_author_key(self):
        for where, line in rule_lines():
            tag = parse_tag(line)
            if tag and tag[0] == "T3":
                with self.subTest(where=where, key=tag[2]):
                    self.assertEqual(tag[1], "authors")

    def test_each_family_section_has_the_same_lines(self):
        ids = [family["id"] for family in family_data()]
        problems = []
        for heading, lines in rewrite_sections():
            if heading in ids:
                problems.extend(family_section_checks(heading, lines))
        self.assertEqual(problems, [])

    def test_the_strategy_line_holds_the_strategy_of_the_data(self):
        sections = dict(rewrite_sections())
        for family in family_data():
            with self.subTest(family=family["id"]):
                strategy = [l for l in sections[family["id"]] if l.startswith("Strategy: ")]
                self.assertEqual(len(strategy), 1)
                self.assertTrue(strategy[0].startswith("Strategy: " + family["strategy"] + " (T"), strategy[0])

    def test_the_deletion_statement_follows_the_delete_ok_flag(self):
        sections = dict(rewrite_sections())
        for family in family_data():
            with self.subTest(family=family["id"]):
                body = " ".join(sections[family["id"]])
                allows = "The family allows a deleted sentence." in body
                refuses = "The family does not allow a deleted sentence." in body
                self.assertTrue(allows != refuses, "one statement is needed")
                self.assertEqual(allows, family["delete_ok"])

    def test_the_after_text_of_every_example_holds_no_flagged_finding(self):
        # Lint each text as plain text with every family of the data. A density family flags a short
        # text at once, so the after text must hold no hit of a density family either.
        sections = dict(rewrite_sections())
        for family in family_data():
            examples = example_texts(sections[family["id"]])
            self.assertEqual(sorted(examples), [(1, "after"), (1, "before"), (2, "after"), (2, "before")])
            for number in (1, 2):
                text = examples[(number, "after")]
                with self.subTest(family=family["id"], example=number):
                    found = [(f.family, f.text) for f in flagged(text)]
                    self.assertEqual(found, [], text)

    def test_the_before_text_of_every_example_holds_a_flagged_finding_of_its_family(self):
        sections = dict(rewrite_sections())
        for family in family_data():
            examples = example_texts(sections[family["id"]])
            for number in (1, 2):
                text = examples[(number, "before")]
                with self.subTest(family=family["id"], example=number):
                    self.assertIn(family["id"], [f.family for f in flagged(text)], text)

    def test_examples_do_not_hold_a_real_em_dash(self):
        text = read_text(REWRITE_RULES)
        self.assertNotIn(EM_DASH, text)
        self.assertIn("&mdash;", text)

    def test_both_references_pass_the_detector_with_no_flagged_finding(self):
        for path in (REWRITE_RULES, MODEL_CHECKS):
            with self.subTest(path=os.path.basename(path)):
                found = [(f.line, f.family, f.text) for f in flagged(read_text(path), "markdown")]
                self.assertEqual(found, [])
                out = io.BytesIO()
                self.assertEqual(prose_lint.main([path, "--project-dir", PLUGIN_DIR], out=out, err=io.BytesIO()), 0)

    def test_references_hold_no_em_dash(self):
        for path in (REWRITE_RULES, MODEL_CHECKS):
            with self.subTest(path=os.path.basename(path)):
                self.assertNotIn(EM_DASH, read_text(path))

    def test_references_hold_no_banned_word_outside_a_code_span(self):
        for path in (REWRITE_RULES, MODEL_CHECKS):
            with self.subTest(path=os.path.basename(path)):
                masked = prose_mask.mask(read_text(path), "markdown").text
                self.assertEqual([m.group(0) for m in BANNED.finditer(masked)], [])

    def test_references_hold_no_not_just(self):
        for path in (REWRITE_RULES, MODEL_CHECKS):
            with self.subTest(path=os.path.basename(path)):
                masked = prose_mask.mask(read_text(path), "markdown").text.lower()
                self.assertNotIn("not just", masked)

    def test_references_hold_no_sentence_of_more_than_25_words(self):
        for path in (REWRITE_RULES, MODEL_CHECKS):
            with self.subTest(path=os.path.basename(path)):
                self.assertEqual(long_sentences(read_text(path)), [])

    def test_every_example_pair_passes_the_verifier_as_a_proposal(self):
        # Each pair is one proposal that covers the whole "before" text, in format text, with no profile.
        failures = []
        sections = dict(rewrite_sections())
        for family in family_data():
            examples = example_texts(sections[family["id"]])
            for number in (1, 2):
                if (family["id"], number) in PAIR_EXCEPTIONS:
                    continue
                result = verify_pair(family["id"], examples[(number, "before")], examples[(number, "after")])
                if not result.ok:
                    failures.append("%s example %d: %s" % (family["id"], number, result.detail))
        self.assertEqual(failures, [])

    def test_a_pair_exception_names_a_family_that_allows_deletion_and_gives_a_reason(self):
        allows = dict((family["id"], family["delete_ok"]) for family in family_data())
        for (family_id, number), reason in PAIR_EXCEPTIONS.items():
            with self.subTest(pair=(family_id, number)):
                self.assertTrue(allows[family_id])
                self.assertIn(number, (1, 2))
                self.assertTrue(reason.strip())

    def test_the_pair_check_finds_a_failing_pair(self):
        # Guard the guard: a rewrite that drops a quantifier, one that adds a number and a good rewrite.
        self.assertIn("numbers", verify_pair("binary-contrast", "It rose by about 40%.", "It rose.").failed)
        self.assertIn("numbers", verify_pair("binary-contrast", "It rose.", "It rose by 40%.").failed)
        self.assertTrue(verify_pair("vocabulary-excess", "We delve into the data.", "We examine the data.").ok)

    def test_the_rules_widen_a_series_and_never_widen_a_deletion(self):
        sections = dict((heading, normalized(" ".join(lines))) for heading, lines in rewrite_sections())
        self.assertEqual(missing_phrases(sections["repeated-openers"], (
            "A series of four or more openers has one window for each sentence from the third on",
            "Set `start` to the first sentence and `end` to the end of the last window",
            "Never widen a deletion: it covers one window")), [])
        self.assertEqual(missing_phrases(sections["staccato-run"], (
            "Cover the series in one proposal",
            "Never widen a deletion: it covers one window")), [])
        self.assertEqual(missing_phrases(sections["rhetorical-question"], (
            "Keep: a question that opens a Results paragraph or states a tested hypothesis. Leave such a question alone and write no proposal",
            "Otherwise one proposal covers the question and its answer",
            "The window holds the question, so keep `start` and set `end` and `before` to span both sentences",
            "Never widen a deletion: it covers the question alone")), [])
        # The kept question gets no proposal, so the line does not also ask to cover it.
        self.assertNotIn("cover both sentences in one proposal", sections["rhetorical-question"])

    def test_the_hedge_stack_rule_matches_the_hedge_guard(self):
        # The guard passes a hedge-stack proposal when `after` keeps 1 to the count of `before` (prose_verify).
        section = normalized(" ".join(dict(rewrite_sections())["hedge-stack"]))
        self.assertIn("`after` keeps at least one hedge word and no more than `before` has", section)

    def test_the_references_name_the_repository_owner_for_tier_t3(self):
        for path in (REWRITE_RULES, MODEL_CHECKS):
            with self.subTest(path=os.path.basename(path)):
                text = read_text(path)
                self.assertIn("T3 (the repository owner's own list)", text)
                self.assertNotIn("the author's own", text)

    def test_the_references_keep_one_term_for_each_thing(self):
        # A series is a run of sentences, a finding is a detector result and meaning is the sense of a text.
        for path in (REWRITE_RULES, MODEL_CHECKS):
            with self.subTest(path=os.path.basename(path)):
                masked = prose_mask.mask(read_text(path), "markdown").text.lower()
                self.assertNotRegex(masked, r"\b(?:the|a|each|whole|one) run\b")
                self.assertNotRegex(masked, r"\bhits?\b")
                self.assertNotRegex(masked, r"\bsense\b")
        self.assertIn("These checks test its meaning.", read_text(MODEL_CHECKS))

    def test_a_delete_when_line_uses_remove_for_words_and_delete_for_a_sentence(self):
        sections = dict(rewrite_sections())
        for family in family_data():
            line = [l for l in sections[family["id"]] if l.startswith("Delete when: ")][0]
            body = line[len("Delete when: "):]
            with self.subTest(family=family["id"]):
                if not family["delete_ok"]:
                    self.assertNotRegex(body, r"\bDelete\b")
                    self.assertRegex(body, r"\b(?:Remove|Replace)\b")
                else:
                    self.assertNotRegex(body, r"\bDelete (?:the|that)\b")

    def test_the_weasel_rule_states_a_hedged_claim_and_adds_no_mark(self):
        section = normalized(" ".join(dict(rewrite_sections())["weasel-attribution"]))
        for phrase in ("With no source, state the claim as a hedged claim about the subject, with `may` or `could`, never as a certain claim",
                       "Add no mark to the manuscript",
                       "Say in `reason` that the claim needs a source",
                       "Set `delete` to true only then"):
            with self.subTest(phrase=phrase):
                self.assertIn(normalized(phrase), section)
        for text in ("[citation needed", "citation needed from the author"):
            self.assertNotIn(text, read_text(REWRITE_RULES))
        self.assertNotIn("common knowledge", section)

    def test_a_sentence_with_no_content_goes_only_when_every_family_allows_deletion(self):
        rules = normalized(" ".join(dict(rewrite_sections())[SECTION_RULES]))
        ordered = ("a sentence has content when it holds an observation, a number, a citation, a figure reference or a name from this study",
                   "when a flagged word is the only fault of the sentence, swap the style words",
                   "otherwise delete a sentence that has no content when every family of its window allows deletion",
                   "leave the window alone when the sentence has no content and a family forbids deletion")
        self.assertEqual(missing_phrases(rules, ordered), [])
        # The swap comes first, so a sentence of style words alone gets the swap and not the window left alone.
        self.assertEqual([rules.index(p) for p in ordered], sorted(rules.index(p) for p in ordered))
        self.assertNotIn("otherwise swap the style words and keep the sentence", rules)
        self.assertNotIn("holds a claim, a number or a citation", rules)

    def test_the_delete_when_line_of_a_family_wins_over_the_deletion_of_the_content_rule(self):
        # The sentence stands in the same rule line as the deletion that it limits.
        line = [l for h, l in rule_lines() if h == SECTION_RULES and "has no content when every family" in l]
        self.assertEqual(len(line), 1)
        self.assertIn('The "Delete when" line of a family wins over this deletion, which applies only when every family '
                      "of the window allows a deleted sentence.", line[0])

    def test_the_hedge_check_restores_a_hedge_of_real_doubt_and_marks_nothing(self):
        line = [l for l in read_text(MODEL_CHECKS).split("\n") if "real doubt" in l]
        self.assertEqual(len(line), 1)
        self.assertIn("- A hedge that states real doubt stays. When the rewrite removes such a hedge, restore it. "
                      "Set `hedge_reason` only when the doubt is not real.", line[0])
        self.assertNotIn("mark the proposal", normalized(read_text(MODEL_CHECKS)))

    def test_a_merge_keeps_each_time_and_each_quantity_with_its_own_verb(self):
        section = normalized(" ".join(dict(rewrite_sections())["staccato-run"]))
        self.assertIn("each time and each quantity stays with its own verb", section)
        examples = example_texts(dict(rewrite_sections())["staccato-run"])
        self.assertEqual(examples[(2, "after")], "The signal rose and peaked, then fell by 60%.")

    def test_the_model_checks_define_new_fact_and_the_portability_test(self):
        checks = normalized(read_text(MODEL_CHECKS))
        for phrase in ("no claim, example, number, name or opinion that the sentence itself lacks",
                       "The paragraph around the sentence does not count",
                       "Each time and each quantity stays with its own verb",
                       'it holds content, as the section "Rules for every rewrite" of `rewrite-rules.md` defines it',
                       "A sentence without content passes when the proposal follows the rule of that section for it",
                       "Never add a name or a number to pass the test, because the guards reject it",
                       "A weasel attribution without a source becomes a hedged claim"):
            with self.subTest(phrase=phrase):
                self.assertIn(normalized(phrase), checks)
        self.assertNotIn("it names this subject", checks)
        self.assertNotIn("that the original lacks", checks)

    def test_one_file_defines_content_and_the_other_refers_to_it(self):
        # The rules file holds the one definition of content, and the model checks refer to its section.
        definition = "an observation, a number, a citation, a figure reference or a name from this study"
        self.assertIn(definition, normalized(" ".join(dict(rewrite_sections())[SECTION_RULES])))
        self.assertEqual(normalized(read_text(REWRITE_RULES)).count(definition), 1)
        checks = normalized(read_text(MODEL_CHECKS))
        self.assertNotIn(definition, checks)
        self.assertIn('the section "%s" of `rewrite-rules.md`' % SECTION_RULES.lower(), checks)
        self.assertNotIn("leave the window alone or swap only the style words", checks)
        self.assertNotIn("a claim, a number or a citation", normalized(read_text(REWRITE_RULES)))

    def test_a_missing_source_goes_in_reason_and_no_mark_enters_the_manuscript(self):
        checks = normalized(read_text(MODEL_CHECKS))
        for phrase in ("The missing source goes in `reason`, and no mark enters the manuscript",
                       "The section `weasel-attribution` of `rewrite-rules.md` holds the rule"):
            with self.subTest(phrase=phrase):
                self.assertIn(normalized(phrase), checks)
        self.assertIn("weasel-attribution", [heading for heading, _ in rewrite_sections()])
        for name, path in (("model-checks.md", MODEL_CHECKS), ("rewrite-rules.md", REWRITE_RULES),
                           ("plain-prose.md", COMMAND), ("README.md", README)):
            with self.subTest(file=name):
                self.assertNotIn("gets a mark", normalized(read_text(path)))

    def test_the_assistant_residue_rule_puts_the_check_of_the_sentences_after_it_in_reason(self):
        section = normalized(" ".join(dict(rewrite_sections())["assistant-residue"]))
        for phrase in ("Say in `reason` that the author must check the sentences after the span and the source of their numbers",
                       "Step 5 of the command shows the `reason` to the author"):
            with self.subTest(phrase=phrase):
                self.assertIn(normalized(phrase), section)
        self.assertNotIn("flag any number", section)
        self.assertIn("the columns are `id`, `file:line`, `before`, `after` and `reason`", command_section(5))

    def test_the_assistant_residue_rule_cites_the_authors_note_at_tier_t3(self):
        line = [l for l in dict(rewrite_sections())["assistant-residue"] if l.startswith("Strategy: ")][0]
        self.assertTrue(line.endswith("(T3, authors:S1)"), line)

    def test_references_hold_no_instruction_of_more_than_20_words(self):
        # An instruction starts with a word of INSTRUCTION_STARTS. A code span counts as one word.
        for path in (REWRITE_RULES, MODEL_CHECKS):
            with self.subTest(path=os.path.basename(path)):
                self.assertEqual(long_instructions(read_text(path)), [])

    def test_the_sentence_check_finds_a_long_sentence(self):
        # Guard the guard: a made-up sentence of 26 words must show up.
        self.assertEqual(len(long_sentences(" ".join(["word"] * 26) + ".")), 1)
        self.assertEqual(long_sentences(" ".join(["word"] * 25) + "."), [])
        self.assertEqual(long_sentences("A short sentence. Another short one."), [])

    def test_the_banned_word_check_finds_a_banned_word_and_skips_a_code_span(self):
        masked = prose_mask.mask("We utilize a `robust` method.", "markdown").text
        self.assertEqual([m.group(0) for m in BANNED.finditer(masked)], ["utilize"])


# ---------------------------------------------------------------------------------------
# Example
# ---------------------------------------------------------------------------------------

def run_detector():
    """Run `python3 scripts/prose_lint.py examples/made-up-manuscript.tex` in the plugin folder."""
    done = subprocess.run(
        [sys.executable, "-B", os.path.join("scripts", "prose_lint.py"), os.path.join("examples", "made-up-manuscript.tex")],
        cwd=PLUGIN_DIR, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return done.returncode, done.stdout.decode("utf-8"), done.stderr.decode("utf-8")


# Sentences of the example that a human would write. No finding of severity flag may touch them.
CLEAN_MARKERS = (
    "Colonies were collected", "The plates were kept", "Shoot length was measured", "Tissue was frozen",
    "Expression was quantified", "These data suggest that Tavo may limit growth", "A second explanation is that light",
    "The mutant is small---about half", "so the loss in the field probably has another cause",
    "Earlier work measured its growth", "The rate in bright light was almost four times",
)


class ExampleTests(unittest.TestCase):
    def test_the_expected_file_equals_the_output_of_the_detector(self):
        code, out, err = run_detector()
        self.assertEqual(err, "")
        self.assertEqual(code, 1)
        self.assertEqual(out, read_text(EXPECTED))

    def test_the_expected_file_names_the_manuscript_by_its_relative_path(self):
        first = read_text(EXPECTED).split("\n")[0]
        self.assertTrue(first.startswith("examples/made-up-manuscript.tex:"), first)

    def test_the_manuscript_holds_flagged_findings_of_at_least_10_families(self):
        text = read_text(MANUSCRIPT)
        families = sorted(set(f.family for f in flagged(text, "latex")))
        self.assertGreaterEqual(len(families), 10, families)

    def test_the_expected_file_shows_the_same_families(self):
        shown = set(re.findall(r"^[^:\n]+:\d+:\d+: ([a-z-]+): T[123]: flag:", read_text(EXPECTED), re.M))
        text = read_text(MANUSCRIPT)
        self.assertEqual(sorted(shown), sorted(set(f.family for f in flagged(text, "latex"))))

    def test_the_manuscript_has_the_required_parts(self):
        text = read_text(MANUSCRIPT)
        self.assertIn("\\begin{figure}", text)
        self.assertIn("\\includegraphics", text)
        self.assertIn("\\begin{equation}", text)
        self.assertIn("\\begin{table}", text)
        self.assertIn("\\begin{tabular}", text)
        self.assertEqual(len(re.findall(r"\\cite\{", text)), 2)

    def test_the_manuscript_has_about_600_words(self):
        # Count as the detector does: after masking, with prose_text.words.
        masked = prose_mask.mask(read_text(MANUSCRIPT), "latex")
        count = len(prose_text.words(masked.text))
        self.assertTrue(500 <= count <= 700, count)

    def test_the_manuscript_has_one_em_dash(self):
        text = read_text(MANUSCRIPT)
        self.assertEqual(text.count("---") + text.count(EM_DASH), 1)

    def test_the_human_em_dash_is_not_flagged(self):
        findings = prose_lint.lint_text(read_text(MANUSCRIPT), "latex", PATTERNS).findings
        dashes = [f for f in findings if f.family == "em-dash"]
        self.assertEqual([(f.text, f.severity) for f in dashes], [("---", "info")])

    def test_the_clean_sentences_stay_quiet(self):
        text = read_text(MANUSCRIPT)
        for marker in CLEAN_MARKERS:
            self.assertIn(marker, text, marker)
        touched = []
        for finding in flagged(text, "latex"):
            sentence = text[finding.sentence_start:finding.sentence_end]
            for marker in CLEAN_MARKERS:
                if marker in sentence:
                    touched.append((marker, finding.family, finding.text))
        self.assertEqual(touched, [])

    def test_the_passive_methods_paragraph_has_no_finding(self):
        text = read_text(MANUSCRIPT)
        start = text.index("\\section{Methods}")
        end = text.index("\\section{Results}")
        inside = [f for f in prose_lint.lint_text(text, "latex", PATTERNS).findings if start <= f.start < end]
        self.assertEqual(inside, [])

    def test_the_manuscript_names_no_real_item(self):
        text = read_text(MANUSCRIPT)
        self.assertIn("Zorbian moss", text)
        self.assertIn("\\author{Anonymous}", text)


# ---------------------------------------------------------------------------------------
# Spec
# ---------------------------------------------------------------------------------------

def voice_profile_minimum():
    """Return the minimum number of words that `voice_profile.py` needs."""
    import voice_profile
    return voice_profile.MIN_WORDS


def spec_section(number):
    """Return the text of the spec section "## <number>. ..." up to the next section."""
    text = read_text(SPEC)
    match = re.search(r"^## %d\. .*?(?=^## |\Z)" % number, text, re.M | re.S)
    return match.group(0)


class SpecTests(unittest.TestCase):
    def test_the_status_line_says_implemented(self):
        status = [l for l in read_text(SPEC).split("\n") if l.startswith("Status:")]
        self.assertEqual(len(status), 1)
        self.assertIn("implemented", status[0])

    def test_the_spec_names_every_script_file(self):
        text = read_text(SPEC)
        names = sorted(n for n in os.listdir(SCRIPTS_DIR) if n.endswith(".py"))
        self.assertIn("prose_text.py", names)
        self.assertIn("prose_mask_core.py", names)
        self.assertIn("prose_mask_md.py", names)
        for name in names:
            with self.subTest(script=name):
                self.assertIn(name, spec_section(4))
        self.assertIn("prose_text.py", text)

    def test_the_spec_has_no_family_field_in_the_proposal_section(self):
        section = spec_section(9)
        self.assertNotIn("`family`", section)
        self.assertNotIn('"family"', section)
        self.assertIn("`families`", section)

    def test_section_6_lists_every_family_id(self):
        section = spec_section(6)
        ids = [family["id"] for family in family_data()]
        self.assertEqual(len(ids), 17)
        for family_id in ids:
            with self.subTest(family=family_id):
                self.assertIn("`%s`" % family_id, section)
        self.assertIn("17 families", section)

    def test_section_6_describes_severity_and_tiers_and_tool_tags(self):
        section = spec_section(6)
        for phrase in ("`severity`", "`flag`", "`info`", "T1 is a measurement in a corpus",
                       "T2 is a rule that a named guide states", "T3 is the repository owner's own list",
                       "`oaicite`", "`contentReference`", "`utm_source=chatgpt.com`", "`mode: each`"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, section)

    def test_section_3_names_the_third_party_source_and_the_license_rule(self):
        section = spec_section(3)
        self.assertIn("petergyang/no-ai-slop", section)
        self.assertIn("family names and short examples", section)

    def test_section_5_describes_unmask_the_placeholder_and_the_span_kinds(self):
        section = spec_section(5)
        self.assertIn("`prose_mask.unmask(masked)` is the inverse", section)
        self.assertIn('"\\ue000" + str(i) + "\\ue001"', section)
        for kind in ("comment", "math", "env", "command", "cite", "ref", "url", "code", "markup"):
            with self.subTest(kind=kind):
                self.assertIn("`%s`" % kind, section)
        self.assertIn("unknown command hides its text", section)
        self.assertIn("text of the argument stays visible", section)

    def test_the_verifier_command_line_matches_the_code(self):
        section = spec_section(9)
        self.assertIn("python3 prose_verify.py PROPOSALS.json", section)
        self.assertNotIn("ORIGINAL", section)
        for option in ("--voice FILE", "--project-dir DIR", "--json", "--format"):
            self.assertIn(option, section)

    def test_the_verifier_output_is_described(self):
        section = spec_section(9)
        for phrase in ("`id: pass`", "`id: FAIL`", "`(warning: ...)`", "`passed: P failed: F`", "`results`", "`passed`", "`failed`"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, section)

    def test_the_windows_output_is_one_list(self):
        section = spec_section(7)
        self.assertIn("`--windows` prints one JSON list", section)
        self.assertNotIn("one window as JSON for each sentence", section)

    def test_approval_and_edits_happen_in_the_same_turn(self):
        section = " ".join(spec_section(9).split())
        self.assertIn("Approval does not carry over between turns", section)
        self.assertIn("in the same turn as the approval", section)
        self.assertIn("never applies an approval that the author gave in an earlier turn", section)

    def test_the_allowed_tools_sentence_has_one_pattern_for_each_script(self):
        section = " ".join(spec_section(9).split())
        self.assertIn("one `Bash` pattern for each of the three scripts", section)
        self.assertIn("the options of the script do not change the pattern", section)
        self.assertIn('Bash(python3 "${CLAUDE_PLUGIN_ROOT}/scripts/prose_lint.py" *)', section)

    def test_one_proposal_can_cover_several_windows(self):
        section = " ".join(spec_section(9).split())
        self.assertIn("A staccato window holds the third fragment of its series", section)
        self.assertIn("So one proposal can cover several windows.", section)
        self.assertNotIn("covers all hits of one sentence. Proposals do not overlap.", section)

    def test_the_grouping_in_step_5_uses_families(self):
        section = spec_section(9)
        self.assertIn("grouped by the first entry of `families`", section)

    def test_section_3_no_longer_calls_the_rows_unverified(self):
        section = " ".join(spec_section(3).split())
        self.assertNotIn("Treat each row as unverified", section)
        self.assertIn("The notes exist now. Where a row and a note differ, the note decides.", section)

    def test_section_7_describes_the_text_output_and_the_sentence_breaks(self):
        section = " ".join(spec_section(7).split())
        for phrase in ("`path: N words, F flagged, I info`", "family: N hits, X per 1000 words`",
                       "`flagged: N info: N`", "A paragraph break also ends a sentence",
                       "So do a heading, a list item and the token of an environment, except a math environment",
                       "The walk skips hidden folders, `node_modules` and `docs/prose`"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, section)
        self.assertNotIn("A summary per file gives", section)

    def test_section_8_states_the_3_word_rule_and_the_200_word_minimum(self):
        section = " ".join(spec_section(8).split())
        self.assertIn("over the sentences of at least 3 words", section)
        self.assertIn("A profile needs at least 200 words in all samples together", section)
        self.assertIn("the script exits with code 2 and writes nothing", section)
        self.assertEqual(voice_profile_minimum(), 200)

    def test_the_no_empty_row_states_the_blank_rule_and_the_empty_families_rule(self):
        row = [l for l in spec_section(9).split("\n") if l.startswith("| `no-empty` |")]
        self.assertEqual(len(row), 1)
        self.assertIn("`after` is not blank (white space only counts as blank)", row[0])
        self.assertIn("A proposal with an empty `families` list cannot delete.", row[0])

    def test_section_11_says_that_an_author_key_resolves_to_a_file_path(self):
        section = " ".join(spec_section(11).split())
        self.assertIn("or for the note `authors` a local file path", section)
        self.assertNotIn("resolves to a URL in the research notes", section)

    def test_section_13_lists_only_the_open_items(self):
        section = " ".join(spec_section(13).split())
        self.assertNotIn("The research task decides them", section)
        self.assertNotIn("The plan checks it", section)
        self.assertIn("Two items of the draft are closed", section)
        self.assertEqual(len([l for l in spec_section(13).split("\n") if l.startswith("- ")]), 3)
        self.assertIn("The precision pilot, the rewrite pilot, the voice check and the discovery check of section 11",
                      section)
        self.assertIn("They stay open until a person runs each pilot and records the result", section)
        self.assertIn("Agent sessions ran the precision pilot, the rewrite pilot and the discovery check on 2026-10-23 "
                      "and 2026-10-24. The author has not run one of them. The author ran the blind sample of the voice "
                      "check on invented text on 2026-10-28. The check on the author's writing samples is open.", section)

    def test_the_status_line_names_the_pilots_that_agent_sessions_ran(self):
        # The record in results.md publishes the three runs, so the status line no longer calls every pilot open.
        status = [l for l in read_text(SPEC).split("\n") if l.startswith("Status:")][0]
        self.assertIn("implemented", status)
        self.assertIn("Agent sessions ran the precision pilot, the rewrite pilot and the discovery check "
                      "(`tests/verification/evidence/results.md`). No person has run the other three. The author ran the voice check "
                      "on invented text on 2026-10-28. The check on the author's writing is open.", status)
        self.assertNotIn("The pilots of section 11 are open", status)
        self.assertTrue(os.path.isfile(os.path.join(PLUGIN_DIR, "tests", "verification", "evidence", "results.md")))

    def test_section_6_says_that_the_data_holds_no_rule_for_a_tag_inside_a_url(self):
        section = " ".join(spec_section(6).split())
        self.assertIn("The family `assistant-residue` also covers tool-citation tags such as `oaicite` and `contentReference`", section)
        self.assertIn("The data holds no rule for `utm_source=chatgpt.com`, because the masker hides URLs.", section)
        self.assertNotIn("`contentReference` and `utm_source=chatgpt.com`", section)
        regexes = [rule.get("regex", "") for family in family_data() for rule in family.get("rules", [])]
        self.assertFalse(any("utm_source" in regex for regex in regexes))

    def test_section_12_leaves_the_plugin_root_limit_to_the_readme(self):
        section = " ".join(spec_section(12).split())
        self.assertIn("whether Claude Code expands `${CLAUDE_PLUGIN_ROOT}` inside the `allowed-tools` lines. The README states the limit.",
                      section)
        self.assertNotIn("interactive try of generate-slides-minimal", section)

    def test_section_1_quotes_its_patterns_in_code_spans(self):
        section = spec_section(1)
        self.assertIn("carries patterns such as `load-bearing` and `this is X, not Y`.", section)
        self.assertEqual([(f.family, f.text) for f in flagged(section, "markdown")], [])

    def test_the_allowed_tools_sentence_lists_the_tools_that_the_command_lists(self):
        sentence = [s for s in " ".join(spec_section(9).split()).split(". ") if s.startswith("The command's `allowed-tools`")]
        self.assertEqual(len(sentence), 1)
        spans = inline_spans(sentence[0])
        named = sorted(span for span in spans if span in TOOL_NAMES)
        listed = sorted(entry for entry in command_data()["allowed-tools"] if not entry.startswith("Bash("))
        self.assertEqual(named, listed)
        self.assertNotIn("Grep", named)
        bash = [e for e in command_data()["allowed-tools"] if e.startswith("Bash(") and "/scripts/" not in e]
        for entry in bash:
            with self.subTest(entry=entry):
                if entry.startswith("Bash(git "):
                    # The sentence names a git command without its star, as in `git commit -m`.
                    self.assertIn("`%s`" % re.sub(r" \*\)$", "", entry[len("Bash("):] + ""), sentence[0])
                else:
                    self.assertIn("`%s`" % entry, sentence[0])
        self.assertEqual(len([e for e in command_data()["allowed-tools"] if "/scripts/" in e]), 3)
        self.assertIn("one `Bash` pattern for each of the three scripts", sentence[0])

    def test_step_5_of_the_spec_approves_by_group_with_a_numbered_fallback(self):
        step = " ".join(spec_section(9).split())
        for phrase in ("Ask the author to approve by group",
                       "all passing proposals of one family (every passing proposal whose first `families` entry is that family)",
                       "all deletions, or none",
                       "The question allows several answers, and none overrides the other options",
                       "so a numbered table lists the families when they exceed the options",
                       "A choice by proposal id works only in a text reply",
                       "`git status --short -- <file>` shows whether the original of a deleted sentence stays in git history"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, step)
        self.assertNotIn("offers chosen ids", step)

    def test_step_3_of_the_spec_covers_inner_windows_deletions_and_repeated_sentences(self):
        step = " ".join(spec_section(9).split())
        for phrase in ("It covers every inner window of the series and carries the union of their `families`, in the order of the windows, first window first",
                       "A proposal with `delete: true` covers one window and is never widened",
                       "When `before` occurs more than once, the proposal adds a neighbor sentence to `before` and `after`",
                       "`start` or `end` moves by the length of the neighbor and the blank between",
                       "with `--out docs/prose-voice.json` (a folder that the scripts search)"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, step)

    def test_step_6_of_the_spec_says_when_the_original_stays_in_git_history(self):
        step = " ".join(spec_section(9).split())
        self.assertIn("the original stays in git history once a commit holds the file", step)

    def test_step_0_of_the_spec_reads_the_six_paths_and_the_tool_list_has_no_glob(self):
        step = " ".join(spec_section(9).split())
        self.assertIn("then use `Read` on the six candidate paths of `prose-style.yaml` and `prose-voice.json` (`./`, `docs/` and `.claude/` of the working folder, joined into absolute paths)", step)
        self.assertIn("A `Read` error for a missing file is no error of the command", step)
        self.assertNotIn("Glob", step)

    def test_step_1_of_the_spec_takes_the_counts_from_the_family_lines_and_the_totals(self):
        step = " ".join(spec_section(9).split())
        for phrase in ("1. Detect: run `prose_lint.py` with its text output (section 7)",
                       "Show one table for each file: the tiers of each family from its finding lines, and its count and rate from the line `family: N hits, X per 1000 words`, which counts flagged and info findings together",
                       "Then give the totals of the line `flagged: N info: N`",
                       "The model does not count the findings of a family by severity"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, step)
        self.assertNotIn("Show the summary.", step)
        self.assertNotIn("run `prose_lint.py --json`", step)
        self.assertNotIn("`density`", step)
        # Section 7 describes the two lines that step 1 names.
        for line in ("family: N hits, X per 1000 words", "flagged: N info: N"):
            self.assertIn(line, spec_section(7))

    def test_the_no_new_names_row_of_the_spec_names_a_common_word(self):
        row = [l for l in spec_section(9).split("\n") if l.startswith("| `no-new-names` |")][0]
        self.assertIn("The result lists such a word as a warning, unless it is a common word.", row)
        self.assertNotIn("function word", row)

    def test_step_6_of_the_spec_gives_the_hook_notice_before_the_first_edit(self):
        step = " ".join(spec_section(9).split())
        self.assertIn("A hook may ask for each `Edit`, so before the first `Edit` the command tells the author to expect the prompts, and it never bypasses them", step)

    def test_step_3_of_the_spec_names_the_file_shape_the_families_and_the_left_alone_windows(self):
        step = " ".join(spec_section(9).split())
        for phrase in ("The file holds one JSON list, and `<name>` is the file name of the first path without its extension",
                       "The `families` of a window names the flagged families only",
                       "An info finding in the sentence stays out of the proposal, and step 7 counts it",
                       "`prose_lint.py --windows` exits with code 1 when it lists windows",
                       "and `id`, `occurrences` and `hits` from its first window",
                       "A window can get no proposal, for example a strong human sentence or a term of art",
                       "Step 5 lists it as left alone, with the reason"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, step)

    def test_step_4_of_the_spec_shares_the_budget_and_names_the_labels(self):
        step = " ".join(spec_section(9).split())
        for phrase in ("a check that says no also asks for a rewrite",
                       "Each rewrite after a failed guard or a no uses one try, and the tries stop after `--max-rounds` rewrites (default 2)",
                       "After the last try the proposal shows as failed guard when the verifier failed it last, and as failed check otherwise"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, step)
        self.assertNotIn("sends the proposal back once more", step)
        self.assertNotIn("for up to `--max-rounds` more tries", step)

    def test_step_5_of_the_spec_approves_all_except_deletions_and_lists_windows_left_alone(self):
        step = " ".join(spec_section(9).split())
        self.assertIn("approve by group: all passing except deletions, all passing proposals of one family", step)
        self.assertIn("then the proposals that failed a guard or a check, then the windows left alone", step)

    def test_step_6_of_the_spec_never_uses_an_empty_new_text(self):
        step = " ".join(spec_section(9).split())
        for phrase in ("with `before` as the old text and `after` as the new text, except for a deletion",
                       "The `Edit` tool removes the line break after the old text when the new text is empty, so a deletion never uses an empty new text",
                       "Its old text is the previous sentence, the blank and `before`, and its new text is the previous sentence",
                       "When the window opens its paragraph, the old text is `before`, the blank and the next sentence, and the new text is the next sentence",
                       "A paragraph of one sentence stays for the author"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, step)

    def test_step_7_of_the_spec_names_flagged_and_info_counts(self):
        step = " ".join(spec_section(9).split())
        self.assertIn("7. Report: run the detector again with its text output", step)
        self.assertIn("Show the totals and the count of each family before and after, and the remaining flagged findings from the finding lines with severity `flag`", step)
        self.assertIn("Name each family whose count rose", step)
        self.assertNotIn("flagged or info count rose", step)
        self.assertIn("A density family can drop from flag to info when the density of the file falls", step)

    def test_section_3_rows_state_the_counts_of_the_notes(self):
        section = " ".join(spec_section(3).split())
        guides = " ".join(read_text(os.path.join(NOTES_DIR, "guides.md")).split())
        corpus = " ".join(read_text(os.path.join(NOTES_DIR, "corpus.md")).split())
        for spec_phrase, note_phrase, note in (
                ("26 patterns in 6 sections at version 3.1.0", "26 patterns in 6 sections at version 3.1.0", guides),
                ("76 phrase entries in 8 sections, 48 structure rows in 11 sections",
                 "76 phrase entries in 8 sections and 48 structure rows in 11 sections", guides),
                ("Its README names 6 phrase categories", "Its README names 6 phrase categories", guides),
                ("15.1 million English abstracts of 2010 to 2024", "15.1 M English abstracts 2010 to 2024", corpus),
                ("Four vendored folders carry their own license", "Four vendored folders", guides)):
            with self.subTest(phrase=spec_phrase):
                self.assertIn(spec_phrase, section)
                self.assertIn(note_phrase, note)
        self.assertNotIn("40+ banned phrases", section)
        self.assertNotIn("24 to 29 patterns", section)
        self.assertNotIn("about 14 million", section)

    def test_the_spec_keeps_one_term_for_each_thing_and_names_no_task(self):
        # The repository owner owns the plugin and the author owns the text. A finding is a detector result and a
        # series is a run of sentences. The public repository does not hold the plan, so no text names a task.
        text = read_text(SPEC)
        masked = prose_mask.mask(text, "markdown").text
        self.assertNotRegex(masked, r"\bhits?\b")
        self.assertNotRegex(masked, r"\buser\b")
        self.assertNotRegex(masked, r"\b(?:a|the|each|whole|one|its|of) run\b")
        self.assertNotIn("Task 9", text)
        self.assertNotIn("Author, 2026", text)
        self.assertEqual(text.count("| Repository owner, 2026-10-2"), 5)
        for place in ("| D7 |",):
            row = [l for l in text.split("\n") if l.startswith(place)][0]
            self.assertIn("T3 (the repository owner's own list)", row)
        self.assertNotIn("the author's own", text)
        self.assertNotIn("the author's machine", text)

    def test_section_12_closes_the_license_check_by_the_notes(self):
        section = " ".join(spec_section(12).split())
        self.assertIn("The notes `guides.md` (section 6) and `authors.md` (section 5) record the license of each source", section)
        self.assertIn("so the check is closed for version 1", section)
        self.assertNotIn("The plan checks each source", section)


# ---------------------------------------------------------------------------------------
# Command
# ---------------------------------------------------------------------------------------

FENCE = re.compile(r"^```([A-Za-z]*)\n(.*?)^```$", re.M | re.S)
RUN_WORDS = ("python3", "git", "mkdir")
# The names of the tools that a text can mention in a code span. A name in the text needs an entry.
TOOL_NAMES = ("Read", "Write", "Edit", "Glob", "Grep", "AskUserQuestion", "WebFetch", "WebSearch", "NotebookEdit",
              "Agent", "Task")
STEP_TITLES = ("Preflight", "Detect", "Voice", "Propose", "Verify", "Show", "Apply", "Report")
USAGE = ("/plain-prose <path...> [--report-only] [--voice <sample...>] "
         "[--format auto|latex|markdown|text] [--max-rounds N]")
# A path that starts with one of the four folders of the plugin, with an optional plugin root before it.
NAMED_PATH = re.compile(
    r"(?<![\w/.-])(?:\$\{CLAUDE_PLUGIN_ROOT\}/)?((?:scripts|references|data|examples)/[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)*)")
SCRIPT_NAME = re.compile(r"\b([A-Za-z_]+\.py)\b")


def normalized(text):
    """Return the text in lower case, with each run of white space as one space."""
    return " ".join(text.lower().split())


def front_matter(text):
    """Return (front matter, body) of a text that starts with a line "---" and has a closing "---"."""
    match = re.match(r"---\n(.*?)\n---\n(.*)\Z", text, re.S)
    assert match is not None, "no front matter"
    return match.group(1), match.group(2)


def command_data():
    """Return the parsed front matter of the command."""
    return yaml.safe_load(front_matter(read_text(COMMAND))[0])


def command_body():
    return front_matter(read_text(COMMAND))[1]


def outside_fences(body):
    """Return the body with each fenced block removed."""
    return FENCE.sub("", body)


def inline_spans(text):
    return re.findall(r"`([^`\n]+)`", text)


def commands_run(body):
    """Return the commands that the text runs.

    Extraction rule. A command is a non-blank line of a fenced block whose info string is `bash`. It is
    also an inline code span, outside the fenced blocks, whose first word is `python3`, `git` or `mkdir`.
    A span that starts with another word, such as `sed` in "never use `sed`", is no command.
    """
    found = []
    for match in FENCE.finditer(body):
        if match.group(1) == "bash":
            found.extend(line.strip() for line in match.group(2).split("\n") if line.strip())
    for span in inline_spans(outside_fences(body)):
        if span.split(" ", 1)[0] in RUN_WORDS:
            found.append(span)
    return found


def bash_patterns(entries):
    """Return the glob of each `Bash(...)` entry. The glob `*` stands for any text."""
    found = []
    for entry in entries:
        match = re.match(r"^Bash\((.*)\)$", entry, re.S)
        if match:
            found.append(match.group(1))
    return found


def glob_matches(pattern, command):
    """Return True when the command matches the glob. Only `*` is special: it stands for any text."""
    regex = "^" + ".*".join(re.escape(part) for part in pattern.split("*")) + "$"
    return re.match(regex, command, re.S) is not None


def covered(command, entries):
    return any(glob_matches(pattern, command) for pattern in bash_patterns(entries))


def command_section(number):
    """Return the normalized text of the command section "Step <number>: ..."."""
    for heading, lines in split_sections(read_text(COMMAND)):
        if heading.startswith("Step %d:" % number):
            return normalized("\n".join(lines))
    raise AssertionError("no section for step %d" % number)


def command_section_raw(number):
    """Return the text of the command section "Step <number>: ..." with its case and its line breaks."""
    for heading, lines in split_sections(read_text(COMMAND)):
        if heading.startswith("Step %d:" % number):
            return "\n".join(lines)
    raise AssertionError("no section for step %d" % number)


def named_paths(text):
    """Return the paths of the four plugin folders that the text names."""
    return sorted(set(m.group(1).rstrip(".") for m in NAMED_PATH.finditer(text)))


def missing_phrases(text, phrases):
    """Return the phrases that the text lacks. The test lower-cases both and joins white space."""
    body = normalized(text)
    return [phrase for phrase in phrases if normalized(phrase) not in body]


def verify_text(text, start, end, after, families, delete=False, before=None):
    """Return the Result of the ten guards for one proposal on the made-up file `x.txt` that holds `text`.

    The proposal rewrites the text from `start` to `end`. The caller may give another `before` text.
    """
    proposal = {"id": "p1", "file": "x.txt", "start": start, "end": end,
                "before": text[start:end] if before is None else before, "after": after,
                "families": families, "reason": "test"}
    if delete:
        proposal["delete"] = True
    return prose_verify.check_proposals([proposal], PATTERNS, read=lambda path: text)[0]


def edit_tool(text, old, new):
    """Model the `Edit` tool as the fix round observed it, on a scratch file.

    The old text must occur once. With an empty new text the tool also removes the line break that follows the
    old text. With a non-empty new text it only replaces the old text.
    """
    assert text.count(old) == 1
    index = text.index(old)
    end = index + len(old)
    if new == "" and text[end:end + 1] == "\n":
        end += 1
    return text[:index] + new + text[end:]


def deletion_edit(text, start, end):
    """Return (old text, new text) of the `Edit` that deletes the window text[start:end], or None.

    The recipe of Step 6. A sentence of the same paragraph before the window gives the old text "sentence, blank,
    window" and the new text "sentence". Otherwise a sentence after the window gives the old text "window, blank,
    sentence" and the new text "sentence". A window that is its whole paragraph gives None.
    The paragraphs and the sentences come from `prose_text` on the plain text.
    """
    paragraph = [p for p in prose_text.paragraphs(text) if p[0] <= start and end <= p[1]][0]
    sentences = [s for s in prose_text.split_sentences(text) if paragraph[0] <= s[0] and s[1] <= paragraph[1]]
    index = [i for i, s in enumerate(sentences) if s[0] <= start and end <= s[1]][0]
    if index > 0:
        before = sentences[index - 1]
        return text[before[0]:end], text[before[0]:before[1]]
    if index + 1 < len(sentences):
        after = sentences[index + 1]
        return text[start:after[1]], text[after[0]:after[1]]
    return None


class CommandTests(unittest.TestCase):
    def test_the_front_matter_parses_as_yaml(self):
        data = command_data()
        self.assertEqual(sorted(data), ["allowed-tools", "description"])
        self.assertIsInstance(data["description"], str)
        self.assertTrue(data["description"].strip())
        self.assertIsInstance(data["allowed-tools"], list)
        self.assertTrue(all(isinstance(entry, str) for entry in data["allowed-tools"]))
        self.assertEqual(len(data["allowed-tools"]), len(set(data["allowed-tools"])))

    def test_every_tool_without_bash_is_named_in_the_text(self):
        spans = set(inline_spans(outside_fences(command_body())))
        for entry in command_data()["allowed-tools"]:
            if not entry.startswith("Bash("):
                with self.subTest(tool=entry):
                    self.assertIn(entry, spans)

    def test_the_text_names_no_tool_that_the_list_lacks(self):
        entries = command_data()["allowed-tools"]
        for span in inline_spans(outside_fences(command_body())):
            if span in TOOL_NAMES:
                with self.subTest(tool=span):
                    self.assertIn(span, entries)

    def test_every_bash_entry_matches_a_command_of_the_text(self):
        commands = commands_run(command_body())
        for pattern in bash_patterns(command_data()["allowed-tools"]):
            with self.subTest(pattern=pattern):
                self.assertTrue(any(glob_matches(pattern, command) for command in commands))

    def test_every_command_of_the_text_matches_an_entry(self):
        entries = command_data()["allowed-tools"]
        for command in commands_run(command_body()):
            with self.subTest(command=command):
                self.assertTrue(covered(command, entries))

    def test_the_scan_finds_the_commands_of_the_text(self):
        # A scan that finds nothing would pass the two tests above, so pin what it finds.
        commands = commands_run(command_body())
        self.assertGreaterEqual(len(commands), 9)
        for script in ("prose_lint.py", "voice_profile.py", "prose_verify.py"):
            self.assertTrue(any(script in command for command in commands), script)
        for start in ("mkdir -p docs/prose", "python3 -m pip install PyYAML", "git status", "git add", "git commit -m"):
            self.assertTrue(any(command.startswith(start) for command in commands), start)

    def test_the_script_patterns_end_in_a_star_and_name_a_script_that_exists(self):
        patterns = [p for p in bash_patterns(command_data()["allowed-tools"]) if "/scripts/" in p]
        self.assertEqual(len(patterns), 3)
        for pattern in patterns:
            with self.subTest(pattern=pattern):
                match = re.match(r'^python3 "\$\{CLAUDE_PLUGIN_ROOT\}/scripts/([a-z_]+\.py)" \*$', pattern)
                self.assertIsNotNone(match)
                self.assertTrue(os.path.isfile(os.path.join(SCRIPTS_DIR, match.group(1))))

    def test_the_patterns_match_in_both_directions(self):
        lint = 'python3 "${CLAUDE_PLUGIN_ROOT}/scripts/prose_lint.py" *'
        self.assertTrue(glob_matches(lint, 'python3 "${CLAUDE_PLUGIN_ROOT}/scripts/prose_lint.py" a.tex --json'))
        self.assertFalse(glob_matches(lint, 'python3 "${CLAUDE_PLUGIN_ROOT}/scripts/other.py" a.tex'))
        self.assertFalse(glob_matches(lint, 'python3 -c "print(1)"'))
        self.assertFalse(glob_matches(lint, 'sed -i s/a/b/ main.tex'))
        self.assertTrue(glob_matches("mkdir -p docs/prose", "mkdir -p docs/prose"))
        self.assertFalse(glob_matches("mkdir -p docs/prose", "mkdir -p docs/prose2"))
        self.assertTrue(glob_matches("python3 -m pip install PyYAML*", "python3 -m pip install PyYAML"))
        self.assertTrue(glob_matches("git commit -m *", 'git commit -m "style: edits"'))
        self.assertFalse(glob_matches("git commit -m *", "git push"))

    def test_the_extraction_reads_blocks_and_spans_and_skips_other_spans(self):
        body = "Run `git status --short` now. Never use `sed`.\n\n```bash\nls -a\n\npython3 x.py\n```\n\n```json\n{}\n```\n"
        self.assertEqual(commands_run(body), ["ls -a", "python3 x.py", "git status --short"])

    def test_every_path_that_the_command_names_exists(self):
        paths = named_paths(read_text(COMMAND))
        self.assertIn("references/rewrite-rules.md", paths)
        self.assertIn("scripts/prose_lint.py", paths)
        for path in paths:
            with self.subTest(path=path):
                self.assertTrue(os.path.exists(os.path.join(PLUGIN_DIR, path)), path)

    def test_every_script_name_in_the_command_exists(self):
        names = sorted(set(SCRIPT_NAME.findall(read_text(COMMAND))))
        self.assertGreaterEqual(len(names), 3)
        for name in names:
            with self.subTest(script=name):
                self.assertTrue(os.path.isfile(os.path.join(SCRIPTS_DIR, name)), name)

    def test_the_path_scan_finds_a_path_and_skips_a_nested_folder_name(self):
        text = "See `${CLAUDE_PLUGIN_ROOT}/scripts/a.py`, `data/b.json.` and docs/references/c.md."
        self.assertEqual(named_paths(text), ["data/b.json", "scripts/a.py"])

    def test_the_command_names_the_seven_steps_in_order(self):
        headings = [h for h, _ in split_sections(read_text(COMMAND)) if h.startswith("Step ")]
        self.assertEqual(headings, ["Step %d: %s" % (i, title) for i, title in enumerate(STEP_TITLES)])

    def test_the_usage_line_is_the_one_of_the_spec(self):
        self.assertIn(USAGE, command_body())
        self.assertIn(USAGE, spec_section(9))

    def test_the_words_of_the_author_change_only_inside_an_approved_proposal(self):
        self.assertEqual(missing_phrases(command_body(), (
            "Change the words of the author only inside a proposal that the author approves",)), [])

    def test_the_model_writes_after_and_reason_and_copies_every_other_field(self):
        self.assertEqual(missing_phrases(command_body(), (
            "Write `after` and `reason` in each proposal",
            "Add `hedge_reason` or `delete` only when they apply",
            "Copy every other field of the window from the output of `prose_lint.py --windows`",
            "A widened proposal and a neighbor sentence change some of them",
            "Step 3 shows how")), [])

    def test_a_run_needs_a_widened_proposal_with_the_text_of_the_file(self):
        # A question that the rules leave alone gets no proposal, so the command says what a proposal covers and
        # does not say that every finding needs one.
        self.assertNotIn("needs a proposal over the whole series", command_section(3))
        self.assertEqual(missing_phrases(command_section(3), (
            "A proposal for a finding of the family `staccato-run`, `repeated-openers` or `rhetorical-question` covers the whole series",
            "set `start` to the start of the first sentence of the series",
            "Set `end` to the end of the last window of the series",
            "For a question, set `end` to the end of the answer sentence",
            "Take the text between the new `start` and `end` from the `Read` output of the file",
            "Copy it as `before`",
            "Never retype it from memory",
            "The guard `exact-before` rejects a wrong copy or a wrong count")), [])

    def test_every_proposal_is_verified_before_it_is_shown(self):
        self.assertEqual(missing_phrases(command_section(4), (
            "Verify every proposal with `prose_verify.py` before you show it",
            "Each rewrite after a failed guard or a no uses one try",
            "The tries stop after `--max-rounds` rewrites, 2 by default",
            'the proposal shows as "failed guard"',
            "Change `after` and nothing else",
            "Do not adjust `before` to fit")), [])
        self.assertIn("never edit `before` to make a guard pass", normalized(command_body()))

    def test_the_references_are_read_before_step_3_writes_a_proposal(self):
        step = command_section(3)
        rules = "${claude_plugin_root}/references/rewrite-rules.md"
        checks = "${claude_plugin_root}/references/model-checks.md"
        self.assertIn("before the first proposal, `read` the file `%s` and the file `%s`" % (rules, checks), step)
        self.assertLess(step.index(rules), step.index("--windows"))
        self.assertLess(step.index(rules), step.index("write the proposals"))

    def test_the_model_checks_run_in_step_4_before_the_table_of_step_5(self):
        self.assertEqual(missing_phrases(command_section(4), (
            "run the checks of `model-checks.md` on each proposal that passes",
            'it shows as "failed check"')), [])
        self.assertIn("table", command_section(5))
        self.assertNotIn("table", command_section(4))

    def test_approval_and_edits_happen_in_the_same_turn(self):
        self.assertEqual(missing_phrases(command_body(), (
            "Apply only an approval that the author gives in the current turn",
            "Never apply an approval from an earlier turn")), [])
        self.assertEqual(missing_phrases(command_section(6), (
            "In the same turn as the approval, call `Edit` once for each approved id",
            "Set the old text to `before` and the new text to `after`")), [])

    def test_the_question_follows_the_limits_of_the_ask_tool(self):
        self.assertEqual(missing_phrases(command_section(5), (
            "Then ask the author to approve by group",
            "Use `AskUserQuestion`",
            "It allows 1 to 4 questions with 2 to 4 options each, so it cannot list every proposal",
            "all passing proposals except deletions, all proposals of one family, all deletions, and none",
            "One family means every passing proposal whose first `families` entry is that family",
            "After the author picks one family, ask which one in a second call",
            "With more families than the tool allows options, list them in a numbered table and ask in text",
            "A choice by proposal id works only in the text reply",
            "The reply of the author is the approval. Apply it in the turn that holds it")), [])
        self.assertNotIn("chosen ids work only there", command_section(5))

    def test_step_5_asks_one_multi_select_question_and_none_overrides_the_other_options(self):
        self.assertEqual(missing_phrases(command_section(5), (
            "Ask one question with `multiSelect` set to true",
            'The answer "none" overrides the other options')), [])

    def test_step_5_groups_by_the_first_family_and_marks_each_deletion(self):
        self.assertEqual(missing_phrases(command_section(5), (
            "Group the proposals by the first entry of `families`",
            'Mark every deletion with the word "delete"')), [])

    def test_a_deletion_is_a_plain_deletion_in_latex_too(self):
        self.assertEqual(missing_phrases(command_section(6), (
            "For `delete: true`, never set the new text to an empty string",
            "This holds in every format, LaTeX included",
            "The original stays in git history",
            "A `%` comment would hide the rest of a line when the sentence sits in the middle of it")), [])

    def test_the_hook_notice_comes_before_the_first_edit_and_no_script_writes(self):
        step = command_section(6)
        self.assertEqual(missing_phrases(step, (
            "A hook may ask for each `Edit`. Before the first `Edit`, tell the author to expect the prompts. Never bypass them",)), [])
        # The notice needs no test for an Overleaf folder, and it stands before the instruction that calls `Edit`.
        self.assertNotIn("overleaf", step)
        self.assertLess(step.index("a hook may ask for each `edit`"), step.index("call `edit` once for each approved id"))
        self.assertEqual(missing_phrases(command_body(), (
            "Write a manuscript file with `Edit` only",
            "Never use `sed`, `tee` or a script to write a file")), [])

    def test_the_report_runs_the_detector_again_and_states_what_it_did_not_check(self):
        step = command_section(7)
        self.assertEqual(missing_phrases(step, (
            "Run the detector again on the same paths",
            "Show the totals `flagged` and `info` before and after",
            "List each remaining flagged finding as `file:line:col`, family and text, from the finding lines with severity `flag`",
            "Say what the scripts did not check: rule-of-three padding, synonym cycling, meaning and voice",
            "The plugin makes no claim about AI detectors or about authorship")), [])
        self.assertIn("prose_lint.py", step)

    def test_the_preflight_checks_python_and_pyyaml_and_installs_only_after_consent(self):
        self.assertEqual(missing_phrases(command_section(0), (
            "Check that Python 3.6 or later and PyYAML work",
            "ask the author to agree to the install",
            "After the author agrees, run this command",
            "python3 -m pip install PyYAML")), [])
        self.assertEqual(missing_phrases(command_body(), (
            "Use no network, except the `pip` install that Step 0 describes",)), [])

    def test_the_proposal_folder_is_made_with_mkdir_before_the_first_write(self):
        self.assertEqual(missing_phrases(command_body(), (
            "Run `mkdir -p docs/prose` once, before the first write to that folder",)), [])

    def test_the_voice_samples_are_never_read_by_the_model(self):
        self.assertEqual(missing_phrases(command_body(), (
            "Never read, quote or copy a voice sample",
            "The profile holds numbers and one-word openers, and no sentence of a sample")), [])

    def test_a_json_string_escapes_backslashes_and_quotes(self):
        self.assertEqual(missing_phrases(command_section(3), (
            "Escape each backslash and each double quote in a JSON string",
            "A LaTeX `\\cite` becomes `\\\\cite` in `before` and in `after`",
            "Write a line break as `\\n`, and as `\\r\\n` in a CRLF file",
            "`Read` hides the CR, but the offsets of `--windows` count it")), [])
        self.assertIn("escape as in step 3", command_section(4))

    def test_step_4_has_a_branch_for_exit_code_2(self):
        self.assertEqual(missing_phrases(command_section(4), (
            "On code 2, read the message, fix the proposals file and run the verifier again",
            "A fix after code 2 does not count against `--max-rounds`",
            "It exits with code 2 when the check cannot run")), [])

    def test_a_repeated_sentence_gets_a_neighbor_and_the_offset_moves(self):
        self.assertEqual(missing_phrases(command_section(3), (
            "When `occurrences` is more than 1, `before` is not unique",
            "Add a neighbor sentence to `before` and to `after`, unchanged",
            "A neighbor before the window moves `start` back by its length plus the blank between",
            "A neighbor after the window moves `end` forward by the same count",
            "When two windows share one neighbor sentence, write one proposal that covers both windows and the neighbor")), [])

    def test_a_widened_proposal_covers_the_inner_windows_and_unites_their_families(self):
        self.assertEqual(missing_phrases(command_section(3), (
            "A widened proposal covers every inner window of the series",
            "It carries the union of the `families` of those windows, in the order of the windows, first window first",
            "No separate proposal exists for an inner window",
            "A series of repeated openers has one window for each opener from the third on",
            "A staccato series of more than three fragments gets one proposal for the first three")), [])

    def test_a_deletion_covers_one_window_and_is_never_widened(self):
        self.assertEqual(missing_phrases(command_section(3), (
            "Set `delete` to true only when every family of the proposal allows a deleted sentence",
            "Then set `after` to an empty string",
            "Never widen a `delete: true` proposal. It covers one window")), [])

    def test_a_deletion_never_uses_an_empty_new_text_and_replaces_the_neighbor_sentence(self):
        step = command_section(6)
        self.assertEqual(missing_phrases(step, (
            "The `Edit` tool then also removes the line break after the old text, and two paragraphs merge",
            "`Read` the paragraph again before each deletion, and copy the neighbor sentence exactly",
            "The blank is the space or the line break between two sentences",
            "If a sentence precedes the window in its paragraph, the old text is that sentence, the blank and `before`",
            "The new text is that sentence",
            "Otherwise, if a sentence follows, the old text is `before`, the blank and that sentence",
            "Otherwise leave the sentence to the author and say so",
            "For a rewrite, set the old text to `before` and the new text to `after`")), [])
        self.assertNotIn("adds the blank after the window to the old text", step)

    def test_the_deletion_recipe_keeps_the_paragraph_structure(self):
        # The `Edit` tool removes the line break after the old text when the new text is empty. The scratch
        # check of the fix round showed this on a file. edit_tool models that behavior and the recipe avoids it.
        text = ("Alpha one. Alpha two. Alpha three.\n\nBeta one. Beta two. Beta three.\n\n"
                "Gamma one. Gamma two. Gamma three.\n\nLast paragraph.\n")
        naive = edit_tool("First. Second. Third.\nNext paragraph.\n", " Third.", "")
        self.assertEqual(naive, "First. Second.Next paragraph.\n")
        for window, expected in (
                ("Alpha three.", "Alpha one. Alpha two.\n\nBeta one. Beta two. Beta three.\n\n"),
                ("Beta two.", "Alpha three.\n\nBeta one. Beta three.\n\nGamma one."),
                ("Gamma one.", "Beta three.\n\nGamma two. Gamma three.\n\nLast paragraph.\n")):
            start = text.index(window)
            old, new = deletion_edit(text, start, start + len(window))
            self.assertNotEqual(new, "")
            edited = edit_tool(text, old, new)
            self.assertIn(expected, edited)
            self.assertEqual(edited.count("\n\n"), text.count("\n\n"))
            self.assertNotIn(window, edited)
            self.assertNotIn("  ", edited)
        # A paragraph of one sentence stays for the author.
        self.assertIsNone(deletion_edit("One.\n\nOnly sentence.\n\nTwo.\n", 6, 20))
        # A line break between two sentences is a blank too.
        lined = "Alpha one.\nAlpha two.\n\nBeta.\n"
        start = lined.index("Alpha two.")
        old, new = deletion_edit(lined, start, start + len("Alpha two."))
        self.assertEqual(edit_tool(lined, old, new), "Alpha one.\n\nBeta.\n")

    def test_one_proposal_covers_two_windows_that_share_a_neighbor_sentence(self):
        text = ("Marlin-2 plays a pivotal role in drought tolerance. We measured growth in six colonies. "
                "Marlin-2 plays a pivotal role in drought tolerance.")
        after = ("Marlin-2 contributes to drought tolerance. We measured growth in six colonies. "
                 "Marlin-2 contributes to drought tolerance.")
        families = ["importance-puffery", "vocabulary-excess"]
        self.assertTrue(verify_text(text, 0, len(text), after, families).ok)
        # Two proposals that each add the shared neighbor overlap, so the later one fails.
        first = len("Marlin-2 plays a pivotal role in drought tolerance. We measured growth in six colonies.")
        second = text.index("We measured")
        proposals = [
            {"id": "a", "file": "x.txt", "start": 0, "end": first, "before": text[:first],
             "after": after[:after.index(" Marlin-2 contributes", 10)], "families": families, "reason": "t"},
            {"id": "b", "file": "x.txt", "start": second, "end": len(text), "before": text[second:],
             "after": after[after.index("We measured"):], "families": families, "reason": "t"}]
        results = prose_verify.check_proposals(proposals, PATTERNS, read=lambda path: text)
        self.assertIn("no-overlap", results[1].failed)

    def test_a_crlf_file_needs_the_crlf_break_in_before_and_the_json_escapes_it(self):
        text = "Growth slowed. We delve deeper.\r\nDeath followed at 48 h.\r\n"
        end = text.index("48 h.") + len("48 h.")
        after = "Growth slowed as we looked deeper, and death followed at 48 h."
        good = verify_text(text, 0, end, after, ["staccato-run", "vocabulary-excess"])
        self.assertTrue(good.ok, good.detail)
        bad = verify_text(text, 0, end, after, ["staccato-run", "vocabulary-excess"], before=text[:end].replace("\r\n", "\n"))
        self.assertIn("exact-before", bad.failed)
        dumped = json.dumps({"before": text[:end]})
        self.assertIn("\\r\\n", dumped)
        self.assertEqual(json.loads(dumped)["before"], text[:end])

    def test_a_hedge_reason_is_set_when_the_hedge_words_change(self):
        self.assertEqual(missing_phrases(command_section(3), (
            "Set `hedge_reason` when the rewrite changes the number of hedge words",
            "Say why in one sentence")), [])

    def test_the_count_starts_at_the_window_and_a_crlf_break_counts_two(self):
        self.assertEqual(missing_phrases(command_section(3), (
            "Count from the window start",
            "The offsets of the window already include the text before it",
            "A CRLF line break counts as two characters")), [])

    def test_a_window_that_spans_a_crlf_break_shows_it_in_before(self):
        self.assertEqual(missing_phrases(command_section_raw(3), (
            "A `before` of the windows output that spans a line break holds `\\r\\n` when the file uses CRLF",)), [])
        text = "The plants grew for six days.\r\nHere we delve\r\ninto the response of the shoots.\r\nWe delve into it.\r\n"
        found = prose_lint.windows(prose_lint.lint_text(text, "text", PATTERNS).findings, text, "x.txt", 1)
        befores = [w["before"] for w in found]
        self.assertIn("Here we delve\r\ninto the response of the shoots.", befores)
        self.assertIn("We delve into it.", befores)
        self.assertIn("\\r\\n", json.dumps(befores))

    def test_the_model_reads_the_profile_that_the_script_writes(self):
        self.assertEqual(missing_phrases(command_section(2), (
            "After the script writes the profile, `Read` it",
            "The model checks of Step 4 use its numbers")), [])

    def test_the_example_proposal_has_real_offsets_and_passes_the_guards(self):
        blocks = [m.group(2) for m in FENCE.finditer(command_body()) if m.group(1) == "json"]
        self.assertEqual(len(blocks), 1)
        proposals = json.loads(blocks[0])
        self.assertIsInstance(proposals, list)
        self.assertEqual(len(proposals), 1)
        proposal = proposals[0]
        for field in ("id", "file", "start", "end", "before", "occurrences", "families", "hits", "after", "reason"):
            self.assertIn(field, proposal)
        manuscript = read_text(MANUSCRIPT)
        window = [w for w in prose_lint.windows(
            prose_lint.lint_text(manuscript, "latex", PATTERNS).findings, manuscript, proposal["file"], 1)
            if w["id"] == proposal["id"]][0]
        for field in ("id", "file", "start", "end", "before", "occurrences", "families", "hits"):
            self.assertEqual(proposal[field], window[field], field)
        self.assertEqual(proposal["end"] - proposal["start"], len(proposal["before"]))
        self.assertEqual(manuscript[proposal["start"]:proposal["end"]], proposal["before"])
        self.assertEqual(proposal["file"], "examples/made-up-manuscript.tex")
        result = prose_verify.check_proposals([proposal], PATTERNS, read=lambda path: manuscript)[0]
        self.assertTrue(result.ok, result.detail)

    def test_the_question_before_a_deletion_names_the_git_history(self):
        self.assertEqual(missing_phrases(command_section(5), (
            "Before the table, run `git status --short -- <file>` for each file that holds a deletion",
            "If the output is not empty, the file is untracked or modified",
            "If git says that the folder is not a git repository, no history exists",
            "the question tells the author that the original text will not be in git history")), [])
        self.assertIn("the original stays in git history once a commit holds the file", command_section(6))

    def test_step_0_stops_for_an_old_python_and_an_unexpanded_plugin_root(self):
        self.assertEqual(missing_phrases(command_section(0), (
            "Stop in two cases and tell the author why",
            "the output can hold `SyntaxError`",
            "Then the command needs Python 3.6 or later",
            "The output can say `can't open file`",
            "Then Claude Code did not expand `${CLAUDE_PLUGIN_ROOT}`, and the script path does not exist")), [])

    def test_the_report_only_flag_stops_after_step_1_and_writes_no_file(self):
        self.assertIn("`--report-only` stops after Step 1 and changes nothing", command_body())
        self.assertEqual(missing_phrases(command_section(1), (
            "With `--report-only`, also list each flagged finding as `file:line:col`, family and text",
            "Then stop and write no file")), [])

    def test_the_commit_step_asks_once_and_never_pushes(self):
        self.assertEqual(missing_phrases(command_section(6), (
            "After at least one edit, run `git status --short`",
            "skip the commit",
            "ask once with `AskUserQuestion` whether to commit",
            "On yes, run `git add <file>` for each edited file",
            "Then run `git commit -m \"<message>\"`",
            "Never push")), [])

    def test_the_proposal_folder_command_stands_in_a_bash_block(self):
        # The rule names docs/prose and the proposals path writes there, so a fenced block must make the folder.
        # If the command stops writing to docs/prose, the allowed tool and the rule go together.
        blocks = [line.strip() for m in FENCE.finditer(command_body()) if m.group(1) == "bash"
                  for line in m.group(2).split("\n")]
        self.assertIn("mkdir -p docs/prose", blocks)
        self.assertIn("docs/prose/proposals-", command_body())
        self.assertIn("Bash(mkdir -p docs/prose)", command_data()["allowed-tools"])

    def test_the_table_takes_the_line_from_hits_and_the_group_from_families(self):
        step = normalized(command_section(5))
        self.assertIn("take the line from the first entry of `hits`", step)
        self.assertIn("group the proposals by the first entry of `families`", step)

    def test_the_usage_bullet_gives_the_default_of_max_rounds(self):
        body = normalized(command_body())
        self.assertIn("- `--max-rounds n` sets how many more tries a rejected proposal gets. the default is 2.", body)

    def test_step_0_reads_the_six_project_paths_and_names_no_glob_tool(self):
        step = command_section(0)
        for path in ("`prose-style.yaml`", "`docs/prose-style.yaml`", "`.claude/prose-style.yaml`",
                     "`prose-voice.json`", "`docs/prose-voice.json`", "`.claude/prose-voice.json`"):
            with self.subTest(path=path):
                self.assertIn(path, step)
        self.assertIn("use `read` on each project file in the working folder", step)
        self.assertIn("a `read` error for a missing file is no error of the command", step)
        self.assertNotIn("Glob", read_text(COMMAND))
        self.assertEqual([e for e in command_data()["allowed-tools"] if not e.startswith("Bash(")],
                         ["Read", "Write", "Edit", "AskUserQuestion"])

    def test_the_rules_join_the_working_folder_for_read(self):
        self.assertEqual(missing_phrases(command_body(), (
            "- `Read` takes an absolute path. Join the working folder and each relative path.",)), [])

    def test_steps_1_and_7_run_the_text_output_and_step_3_runs_the_windows(self):
        line = 'python3 "${CLAUDE_PLUGIN_ROOT}/scripts/prose_lint.py" <paths>'
        for number in (1, 7):
            with self.subTest(step=number):
                blocks = [m.group(2) for m in FENCE.finditer(command_section_raw(number)) if m.group(1) == "bash"]
                self.assertEqual([b.strip() for b in blocks], [line])
                self.assertNotIn("--json", command_section(number))
        self.assertIn(line + " --windows", command_section_raw(3))

    def test_step_1_describes_the_lines_of_the_text_output(self):
        self.assertEqual(missing_phrases(command_section(1), (
            "The output has one block for each file",
            'A block starts with one line for each finding: `file:line:col: family: tier: severity: "text" (strategy)`',
            "The severity is `flag` or `info`",
            "Then a line gives the words of the file and its flagged and info counts",
            "An indented line for each family follows: `family: N hits, R per 1000 words`",
            "N counts the flagged and info findings together",
            "The last line of the output reads `flagged: X info: Y`")), [])
        for old in ("`density`", "`files`", "top-level"):
            with self.subTest(old=old):
                self.assertNotIn(old, command_section(1))

    def test_the_table_of_step_1_takes_the_counts_from_the_family_lines_and_the_totals(self):
        self.assertEqual(missing_phrases(command_section(1), (
            "On code 1, show one table for each file, with its words",
            "Each row gives a family, its tiers, its count and its rate",
            "Take the count and the rate from the family line, and the tiers from the finding lines",
            "Then give the totals of the last line",
            "Do not count the findings of a family by severity")), [])
        for old in ("count the findings of each severity", "its flagged findings, its info findings",
                    "the flagged count of each file", "the rate times `words`"):
            with self.subTest(old=old):
                self.assertNotIn(old, command_section(1))

    def test_the_text_output_holds_the_lines_that_steps_1_and_7_read(self):
        # The facts that Steps 1 and 7 rest on, on two made-up files: a block for each file with its finding lines,
        # its file line and its family lines, then one totals line. A family line counts flag and info findings
        # together, and a clean file gives a file line with no family line.
        finding = re.compile(r'^(?P<file>[^:]+):\d+:\d+: (?P<family>[a-z-]+): (?P<tier>T[123]): (?P<severity>flag|info): ".*" \(.*\)$')
        file_line = re.compile(r"^(?P<file>[^:]+): \d+ words, (?P<flagged>\d+) flagged, (?P<info>\d+) info$")
        family_line = re.compile(r"^  (?P<family>[a-z-]+): (?P<count>\d+) hits, \d+\.\d\d per 1000 words$")
        totals = re.compile(r"^flagged: (?P<flagged>\d+) info: (?P<info>\d+)$")
        text = ("Marlin-2 plays a key role in the growth of the moss. Tavo plays a pivotal role in the growth of the "
                "root. We counted the shoots of each plant at noon and at dusk on each day of the test.\n")
        with tempfile.TemporaryDirectory() as folder:
            clean, puffed = os.path.join(folder, "clean.txt"), os.path.join(folder, "puffed.txt")
            with open(clean, "w", encoding="utf-8") as handle:
                handle.write("We counted the shoots of each plant at noon. The plants grew for six days.\n")
            with open(puffed, "w", encoding="utf-8") as handle:
                handle.write(text)
            out = io.BytesIO()
            code = prose_lint.main([clean, puffed, "--project-dir", PLUGIN_DIR], out=out, err=io.BytesIO())
            alone = io.BytesIO()
            clean_code = prose_lint.main([clean, "--project-dir", PLUGIN_DIR], out=alone, err=io.BytesIO())
        self.assertEqual(code, 1)
        self.assertEqual(clean_code, 0)
        clean_lines = alone.getvalue().decode("utf-8").splitlines()
        self.assertEqual(len(clean_lines), 2)
        self.assertRegex(clean_lines[0], r" 0 flagged, 0 info$")
        self.assertEqual(clean_lines[1], "flagged: 0 info: 0")
        lines = out.getvalue().decode("utf-8").splitlines()
        self.assertTrue(all(finding.match(l) or file_line.match(l) or family_line.match(l) or totals.match(l)
                            for l in lines), lines)
        self.assertTrue(totals.match(lines[-1]))
        self.assertEqual(sum(1 for l in lines if totals.match(l)), 1)
        findings = [finding.match(l) for l in lines if finding.match(l)]
        self.assertEqual(sorted(m.group("severity") for m in findings if m.group("family") == "importance-puffery"),
                         ["flag", "info"])
        last = totals.match(lines[-1])
        self.assertEqual(int(last.group("flagged")), sum(1 for m in findings if m.group("severity") == "flag"))
        self.assertEqual(int(last.group("info")), sum(1 for m in findings if m.group("severity") == "info"))
        self.assertEqual(set(m.group("tier") for m in findings if m.group("family") == "vocabulary-excess"), {"T1"})
        files = [file_line.match(l) for l in lines if file_line.match(l)]
        self.assertEqual([m.group("file") for m in files], [clean, puffed])
        self.assertEqual((files[0].group("flagged"), files[0].group("info")), ("0", "0"))
        families = [family_line.match(l) for l in lines if family_line.match(l)]
        self.assertTrue(families)
        self.assertTrue(finding.match(lines[lines.index(files[0].group(0)) + 1]), "the clean file has no family line")
        for m in families:
            with self.subTest(family=m.group("family")):
                self.assertEqual(int(m.group("count")), sum(1 for f in findings if f.group("family") == m.group("family")))

    def test_the_windows_call_exits_with_code_1_when_it_lists_windows(self):
        self.assertEqual(missing_phrases(command_section(3), (
            "The detector exits with code 1 when it lists windows",
            "Only code 2 is a failure")), [])
        code = prose_lint.main([MANUSCRIPT, "--windows", "--project-dir", PLUGIN_DIR], out=io.BytesIO(), err=io.BytesIO())
        self.assertEqual(code, 1)

    def test_the_proposals_file_is_a_list_named_by_the_file_name_without_its_extension(self):
        self.assertEqual(missing_phrases(command_section(3), (
            "The file holds one JSON list of proposals",
            "The name is the file name of the first path without its extension")), [])

    def test_a_window_names_flagged_families_only_and_an_info_finding_stays_out(self):
        self.assertEqual(missing_phrases(command_section(3), (
            "`families` names the flagged families only",
            "An info finding in the sentence stays out of the proposal, and Step 7 counts it")), [])
        text = "Marlin-2 plays a key role in growth, and we delve into it."
        found = prose_lint.lint_text(text, "text", PATTERNS).findings
        self.assertEqual(sorted((f.family, f.severity) for f in found),
                         [("importance-puffery", "info"), ("vocabulary-excess", "flag")])
        window = prose_lint.windows(found, text, "x.txt", 1)[0]
        self.assertEqual(window["families"], ["vocabulary-excess"])

    def test_the_hedge_list_of_step_3_is_the_list_of_the_guard(self):
        self.assertIn("The guard counts only these words: `%s`" % " ".join(prose_verify.HEDGE_WORDS),
                      command_section_raw(3))
        self.assertEqual(len(prose_verify.HEDGE_WORDS), 16)
        # The verifier counts "believe" as no hedge word, so a rewrite from believe to may changes the count.
        before = "Many researchers believe that nitrogen limits moss growth."
        result = guard_result(before, "Nitrogen may limit moss growth.")
        self.assertIn("hedge-kept", result.failed)
        waived = guard_result(before, "Nitrogen may limit moss growth.", hedge_reason="believe is no cue")
        self.assertNotIn("hedge-kept", waived.failed)

    def test_a_window_can_get_no_proposal_and_step_5_lists_it_as_left_alone(self):
        self.assertEqual(missing_phrases(command_section(3), (
            "A window can get no proposal, for example a strong human sentence or a term of art",
            "Leave it alone and say why in Step 5")), [])
        self.assertIn('list each window that got no proposal under "left alone", with its id and the reason',
                      command_section(5))

    def test_a_widened_proposal_takes_id_occurrences_and_hits_from_its_first_window(self):
        self.assertIn("it takes `id`, `occurrences` and `hits` from its first window", command_section(3))

    def test_the_staccato_note_of_the_detector_agrees_with_step_3(self):
        doc = " ".join(prose_lint.__doc__.split())
        self.assertIn("For a run of more than three fragments, the command proposes for the first three. "
                      "The detector run of Step 7 shows what remains.", doc)
        self.assertNotIn("runs the detector a second time", doc)
        self.assertIn("a staccato series of more than three fragments gets one proposal for the first three. "
                      "step 7 shows what remains.", command_section(3))

    def test_step_4_edits_the_proposals_file_and_names_the_labels_and_the_budget(self):
        step = command_section(4)
        self.assertEqual(missing_phrases(step, (
            "Use `Edit` on the proposals file, escape as in Step 3 and verify again",
            "After a no, rewrite `after`, verify it again and check it again",
            "Each rewrite after a failed guard or a no uses one try. The tries stop after `--max-rounds` rewrites, 2 by default",
            'After the last try, the proposal shows as "failed guard" if the verifier failed it last',
            'Otherwise it shows as "failed check"')), [])
        self.assertNotIn("Write the file again", step)
        # One rule sets the budget: no second rule allows one rewrite after a no or more tries after a guard.
        for old in ("rewrite `after` once", "allow `--max-rounds` more tries", "a rewrite after a failed check also uses one try"):
            with self.subTest(old=old):
                self.assertNotIn(old, step)
        self.assertEqual(step.count("`--max-rounds`"), 2)

    def test_the_new_names_guard_fails_inside_a_sentence_and_warns_at_its_start(self):
        self.assertEqual(missing_phrases(command_section(4), (
            "The guard `no-new-names` fails when `after` adds a name that `before` lacks",
            "A capitalized word that opens a sentence only gives a warning, printed as `(warning: ...)`",
            "A common word such as `They` gives no warning")), [])
        # Step 5 shows the warnings, so Step 4 does not say it again.
        self.assertIn("show each warning beside its proposal", command_section(5))
        self.assertNotIn("show each warning", command_section(4))
        before = "We delve into the data and Marlin-2 may possibly limit growth."
        inside = guard_result(before, "We study the data and Tarn may limit growth.", hedge_reason="x")
        self.assertIn("no-new-names", inside.failed)
        opening = guard_result(before, "We study the data. Tarn may limit growth.", hedge_reason="x")
        self.assertNotIn("no-new-names", opening.failed)
        self.assertTrue(any("Tarn" in w for w in opening.warnings))
        common = guard_result(before, "We study the data. They may limit growth.", hedge_reason="x")
        self.assertNotIn("no-new-names", common.failed)
        self.assertEqual(common.warnings, [])
        self.assertIn("they", prose_verify.COMMON_STARTS)

    def test_the_not_longer_guard_is_named_with_its_limit(self):
        self.assertEqual(missing_phrases(command_section_raw(4), (
            "The guard `not-longer` allows `after` at most 15 percent more words than `before`, or one more word, whichever is larger",)), [])
        result = guard_result("The assay is robust.", "The assay is sound and well suited to the study of the many samples.")
        self.assertIn("not-longer", result.failed)
        self.assertIn("the limit for 4 words is 5", result.detail["not-longer"])

    def test_step_7_names_flagged_and_info_counts_and_the_density_drop(self):
        # Step 7 compares the counts of Step 1, so it needs no count of a family by severity either.
        self.assertEqual(missing_phrases(command_section(7), (
            "Show the table of Step 1 again, with the count of each family before and after",
            "Name each family whose count rose",
            "A density family can drop from flag to info when the density of the file falls",
            "Its findings then stay in the text")), [])
        self.assertNotIn("flagged count rose", command_section(7))
        self.assertNotIn("info count rose", command_section(7))

    def test_the_command_says_approve_by_group_in_the_front_matter_the_intro_and_step_5(self):
        data = command_data()
        self.assertIn("approve by group", data["description"])
        body = normalized(command_body())
        self.assertIn("the author can approve by group, and no file changes before the approval", body)
        self.assertIn("ask the author to approve by group", command_section(5))

    def test_the_command_keeps_one_term_for_each_thing(self):
        # The author is the owner of the text, a finding is a detector result and a series is a run of
        # sentences. The words "user", "hit" and "run" as a noun stay out of the prose. A code span may hold them.
        masked = prose_mask.mask(command_body(), "markdown").text.lower()
        self.assertNotRegex(masked, r"\buser\b")
        self.assertNotRegex(masked, r"\bhits?\b")
        self.assertNotRegex(masked, r"\b(?:a|the|each|whole|one|of) run\b")
        self.assertNotIn("goes back", masked)

    def test_the_command_and_the_readme_name_the_same_voice_file(self):
        self.assertIn("--out docs/prose-voice.json", read_text(COMMAND))
        self.assertIn("writes `docs/prose-voice.json`", read_text(README))

    def test_the_command_makes_no_claim_about_detectors_or_authorship(self):
        self.assertEqual(missing_phrases(command_body(), (
            "Make no claim about artificial intelligence (AI) detectors or about authorship",)), [])


# ---------------------------------------------------------------------------------------
# Own text: the README and the command
# ---------------------------------------------------------------------------------------

OWN_TEXTS = (("README.md", README), ("plain-prose.md", COMMAND))
INSTRUCTION_WORDS = 20


# A form of "be" with a past participle marks a passive sentence. The scan reads the masked text, so a code
# span cannot match. A participle in PASSIVE_SKIP is an adjective here. Examples: a file with no history is
# untracked, a list with a fixed set of entries is closed, and a step that no run tried is untested.
# The form of "be" may take one of never, not, always or only and one adverb in ly before the participle.
# A participle is a word that ends in ed or en, or one of the closed list IRREGULAR_PARTICIPLES.
PASSIVE = re.compile(
    r"\b(?:is|are|was|were|be|been|being)\s+(?:(?:never|not|always|only)\s+)?(?:\w+ly\s+)?(\w+)\b", re.I)
IRREGULAR_PARTICIPLES = frozenset(
    "shown found seen done made given taken written run set built held used called known".split())
PASSIVE_SKIP = frozenset(("untracked", "closed", "untested", "open", "often", "even", "seven", "token", "green", "when", "then", "been",
                          "red", "need", "speed", "seed", "feed", "bed", "ten"))


def passive_forms(text):
    """Return the passive forms (a form of "be" and a participle) in the prose of a Markdown text."""
    masked = prose_mask.mask(text, "markdown").text
    found = []
    for match in PASSIVE.finditer(masked):
        word = match.group(1).lower()
        if word in PASSIVE_SKIP:
            continue
        if word.endswith(("ed", "en")) or word in IRREGULAR_PARTICIPLES:
            found.append(match.group(0))
    return found


# The passive scan reads the command, the README and the two references.
PASSIVE_TEXTS = OWN_TEXTS + (("rewrite-rules.md", REWRITE_RULES), ("model-checks.md", MODEL_CHECKS))


def style_faults(text, limit):
    """Return the style faults of a Markdown text as a list of strings.

    The faults are a flagged finding of any family, an em dash, a banned word outside a code span,
    "not just", and a sentence of more than `limit` words (see long_sentences).
    """
    faults = ["flagged %s: %s" % (f.family, f.text) for f in flagged(text, "markdown")]
    if EM_DASH in text:
        faults.append("em dash")
    masked = prose_mask.mask(text, "markdown").text
    faults.extend("banned word: %s" % m.group(0) for m in BANNED.finditer(masked))
    if "not just" in masked.lower():
        faults.append("not just")
    faults.extend("%d words: %s" % (count, sentence[:50]) for count, sentence in long_sentences(text, "markdown", limit))
    return faults


class OwnTextTests(unittest.TestCase):
    def test_both_pass_the_detector_with_no_flagged_finding(self):
        for name, path in OWN_TEXTS:
            with self.subTest(file=name):
                found = [(f.line, f.family, f.text) for f in flagged(read_text(path), "markdown")]
                self.assertEqual(found, [])

    def test_both_exit_with_code_0_on_the_command_line(self):
        for name, path in OWN_TEXTS:
            with self.subTest(file=name):
                code = prose_lint.main([path, "--project-dir", PLUGIN_DIR], out=io.BytesIO(), err=io.BytesIO())
                self.assertEqual(code, 0)

    def test_both_hold_no_em_dash(self):
        for name, path in OWN_TEXTS:
            with self.subTest(file=name):
                self.assertNotIn(EM_DASH, read_text(path))

    def test_both_hold_no_banned_word_outside_a_code_span(self):
        for name, path in OWN_TEXTS:
            with self.subTest(file=name):
                masked = prose_mask.mask(read_text(path), "markdown").text
                self.assertEqual([m.group(0) for m in BANNED.finditer(masked)], [])

    def test_both_hold_no_not_just(self):
        for name, path in OWN_TEXTS:
            with self.subTest(file=name):
                self.assertNotIn("not just", prose_mask.mask(read_text(path), "markdown").text.lower())

    def test_the_readme_holds_no_sentence_of_more_than_25_words(self):
        self.assertEqual(long_sentences(read_text(README)), [])

    def test_the_readme_holds_no_instruction_of_more_than_20_words(self):
        self.assertEqual(long_instructions(read_text(README)), [])

    def test_no_sentence_of_a_table_cell_of_the_readme_has_more_than_25_words(self):
        self.assertEqual(table_cell_faults(read_text(README)), [])

    def test_the_length_checks_count_a_code_span_as_one_word_and_tell_an_instruction_from_a_description(self):
        twenty = " ".join(["plain"] * 19)
        # "Keep" and 19 words are 20 words. A code span makes the 21st.
        self.assertEqual([c for c, _ in long_sentences("Keep `a` " + twenty + ".", "markdown", 20)], [21])
        self.assertEqual(long_sentences("Keep " + twenty + ".", "markdown", 20), [])
        self.assertEqual(len(long_instructions("Keep `a` " + twenty + ".")), 1)
        self.assertEqual(long_instructions("The tiers " + twenty + "."), [])
        self.assertEqual(len(long_instructions("The tiers " + " ".join(["plain"] * 24) + ".")), 1)
        self.assertEqual(len(table_cell_faults("| a | " + " ".join(["plain"] * 26) + ". |")), 1)
        self.assertEqual(table_cell_faults("| a | " + " ".join(["plain"] * 25) + ". |\n|---|---|"), [])
        self.assertEqual(table_cell_faults("| a | `" + " ".join(["plain"] * 40) + "` and two words. |"), [])

    def test_the_command_holds_no_sentence_of_more_than_20_words(self):
        # An instruction has at most 20 words. The test applies the limit to every sentence of the
        # command, because that is cheap and exact. The command keeps its descriptions short too.
        self.assertEqual(long_sentences(read_text(COMMAND), "markdown", INSTRUCTION_WORDS), [])

    def test_the_root_readme_section_of_the_plugin_passes_the_same_checks(self):
        section = root_readme_section()
        self.assertEqual(style_faults(section, MAX_WORDS), [])

    def test_no_sentence_claims_to_evade_or_beat_a_detector_or_to_tell_who_wrote_a_text(self):
        for name, text in claim_texts():
            with self.subTest(file=name):
                self.assertEqual(claim_faults(text), [])

    def test_the_claim_check_finds_made_up_claims_and_skips_denials_and_code_spans(self):
        for claim in ("The plugin evades AI detectors.", "The plugin helps you beat every detector.",
                      "Your text becomes undetectable.", "It makes the draft pass an AI detector.",
                      "The plugin detects text written by a model.", "A hit proves who wrote the paper.",
                      "The tool avoids detection by checkers.",
                      "The plugin detects text that a model wrote.", "The plugin spots drafts that ChatGPT generated.",
                      "The tool identifies text from ChatGPT.", "The plugin makes your text look human to a detector.",
                      "The plugin makes the manuscript sound natural.", "The plugin writes text that no detector flags.",
                      "The rewrite passes AI detectors.", "The draft passes detectors.",
                      "The plugin tells you which text a model wrote.", "The report shows which sentences ChatGPT produced."):
            with self.subTest(claim=claim):
                self.assertTrue(claim_faults(claim), claim)
        for fine in ("The plugin makes no claim about AI detectors.", "It scores no document.",
                     "Source S1 states that its method cannot identify single abstracts.",
                     "A finding is a style flag and carries no claim about authorship.",
                     "We write `evade detectors` in a span.", "It does not detect text that a model wrote.",
                     "The plugin never makes your text look human.", "A proposal passes when no guard fails.",
                     "Run the checks of `model-checks.md` on each proposal that passes.",
                     "A text without the listed words can still come from a model.",
                     "The plugin does not tell which text a model wrote."):
            with self.subTest(fine=fine):
                self.assertEqual(claim_faults(fine), [], fine)

    def test_the_command_the_readme_and_the_references_hold_no_passive_sentence(self):
        for name, path in PASSIVE_TEXTS:
            with self.subTest(file=name):
                self.assertEqual(passive_forms(read_text(path)), [])

    def test_the_passive_scan_finds_a_passive_form_and_skips_an_adjective(self):
        self.assertEqual(passive_forms("The file is committed."), ["is committed"])
        self.assertEqual(passive_forms("A rewrite was rejected by the guard."), ["was rejected"])
        self.assertEqual(passive_forms("The file is untracked or empty."), [])
        self.assertEqual(passive_forms("The list is closed. The step is untested."), [])
        self.assertEqual(passive_forms("The guard rejects the rewrite. We use `is committed` here."), [])
        # The scan also finds a form with never, not, always or only, and an irregular participle.
        self.assertEqual(passive_forms("A deletion is never widened."), ["is never widened"])
        self.assertEqual(passive_forms("The step is not run. The list is only shown."), ["is not run", "is only shown"])
        self.assertEqual(passive_forms("The count was always given."), ["was always given"])
        self.assertEqual(passive_forms("The text is written in a code span `is never widened`."), ["is written"])

    def test_the_style_checks_find_seeded_faults(self):
        # Guard the guards: each made-up text must show its fault, and a code span must hide it.
        self.assertTrue(style_faults("We delve into the data.", MAX_WORDS))
        self.assertIn("em dash", style_faults("A point " + EM_DASH + " and another.", MAX_WORDS))
        self.assertTrue(style_faults("A robust result.", MAX_WORDS))
        self.assertIn("not just", style_faults("It is not just large.", MAX_WORDS))
        self.assertEqual(len(style_faults(" ".join(["word"] * 21) + ".", 20)), 1)
        self.assertEqual(style_faults("We write `delve` and `robust` in a span.", MAX_WORDS), [])


# The plugin makes no claim about AI detectors or about authorship (decision D6 of the spec). No sentence
# of a user-facing text may say that the plugin evades, beats or fools a detector, makes text undetectable,
# passes a detector, detects text that a model wrote, identifies text from a named model or tool, makes text
# look human, writes text that no detector flags, or tells who wrote a text. Each pattern runs on the text
# without its code spans, so a sentence that quotes a claim in a code span does not match. A negation shortly
# before the match makes a denial (see claim_faults). The patterns stay narrow, so the real texts pass.
FORBIDDEN_CLAIMS = (
    r"\b(?:evade|evades|evading|beat|beats|beating|bypass|bypasses|bypassing|fool|fools|fooling|defeat|defeats|"
    r"defeating|trick|tricks|tricking)\b[^.]{0,60}\bdetect",
    r"\b(?:avoid|avoids|avoiding)\b[^.]{0,20}\bdetection\b",
    r"\bundetectable\b|\bundetected\b",
    r"\b(?:pass|passes|passing)\b[^.]{0,20}\b(?:AI|LLM)[ -]?(?:detector|detectors|check|checks)\b",
    r"\b(?:detect|detects|detecting|identify|identifies|identifying|find|finds|finding|flag|flags|flagging)\b[^.]{0,40}"
    r"\b(?:written|generated|produced|made) by (?:an? )?(?:AI|model|LLM|large language model|chatbot)\b",
    r"\b(?:proves?|shows?|tells?|reveals?|decides?)\b[^.]{0,30}\bwho (?:wrote|authored)\b",
    r"\bhuman[- ]like score\b|\bAI score\b",
    # The plugin detects text that a model wrote: a detect verb, a text noun and "that a model wrote".
    r"\b(?:detect|identif|spot|recogni[sz])\w*\b[^.]{0,40}\b(?:text|writing|prose|draft|sentence|passage)s?\b[^.]{0,30}"
    r"\b(?:that|which) (?:an? )?(?:AI|model|LLM|chatbot|ChatGPT|GPT)\w* (?:wrote|generated|produced|made|created)\b",
    # The plugin identifies text from ChatGPT or another named model or tool.
    r"\b(?:detect|identif|spot|recogni[sz])\w*\b[^.]{0,40}\b(?:text|writing|prose|draft|sentence|passage)s?\b[^.]{0,20}"
    r"\bfrom (?:an? )?(?:AI|LLM|chatbot|ChatGPT|GPT|Claude|Gemini|Copilot|Llama)\w*",
    # The plugin tells you which text a model wrote.
    r"\b(?:tells?|shows?|reveals?|says?|finds?)\b[^.]{0,30}\bwhich (?:text|sentence|passage|draft|paper|paragraph)s?\b[^.]{0,30}"
    r"\b(?:AI|model|LLM|chatbot|ChatGPT|GPT)\w* (?:wrote|generated|produced|made|created)\b",
    # The plugin makes your text look human.
    r"\bmakes?\b[^.]{0,30}\b(?:text|writing|prose|draft|manuscript|paper)s?\b[^.]{0,20}\b(?:look|sound|read|seem|appear)s?\b"
    r"[^.]{0,15}\b(?:human|natural|authentic)\b",
    # The plugin writes text that no detector flags, or passes detectors with no AI in the name.
    r"\bno (?:AI |LLM )?detectors? (?:flags?|finds?|catches|detects?|spots?)\b",
    r"\b(?:pass|passes|passing)\b[^.]{0,20}\bdetectors?\b",
)


NEGATION = re.compile(r"\b(?:no|not|never|cannot|without)\b|n't", re.I)


def claim_faults(text):
    """Return the forbidden claims that the text holds, as (pattern, sentence) pairs.

    The test masks the text, so a code span cannot match. It splits the masked text into sentences
    with `prose_text.split_sentences`. A negation (no, not, never, cannot, n't) in the 40 characters before
    the match makes a denial, and a denial is no claim.
    """
    masked = prose_mask.mask(text, "markdown")
    found = []
    for start, end in prose_text.split_sentences(masked.text, prose_lint.hard_breaks(masked)):
        sentence = masked.text[start:end]
        for pattern in FORBIDDEN_CLAIMS:
            match = re.search(pattern, sentence, re.I)
            if match and not NEGATION.search(sentence[max(0, match.start() - 40):match.start()]):
                found.append((pattern[:30], sentence[:60]))
    return found


def claim_texts():
    """Return (name, text) for each user-facing text: the READMEs, the command and the manifest description."""
    with open(PLUGIN_JSON, encoding="utf-8") as handle:
        description = json.load(handle)["description"]
    return (("README.md", read_text(README)), ("plain-prose.md", command_body()),
            ("root README section", root_readme_section()), ("plugin.json", description))


def root_readme_section():
    """Return the text of the section "### `plain-prose`" of the root README, without its heading."""
    text = read_text(ROOT_README)
    match = re.search(r"^### `plain-prose`\n(.*?)(?=^#{1,3} |\Z)", text, re.M | re.S)
    assert match is not None, "no section for plain-prose"
    return match.group(1)


# ---------------------------------------------------------------------------------------
# README
# ---------------------------------------------------------------------------------------

README_SECTIONS = ("Install", "Usage", "What it detects", "The flow", "The guards", "The voice profile",
                   "The project file", "Limits", "Decisions for the author", "Relation to other tools",
                   "Research notes", "Example and tests")

# One pinned phrase for each limit. The test lower-cases the README and joins white space first.
LIMIT_PHRASES = (
    ("no AI-detector claim", "The plugin makes no claim about AI detectors"),
    ("no authorship claim", "The plugin makes no claim about authorship"),
    ("no scientific judgment", "The plugin gives no scientific judgment"),
    ("false positives", "The detector has false positives on legitimate scientific phrasing"),
    ("a rewrite can change the meaning", "A rewrite can change the meaning"),
    ("a rewrite can flatten the voice", "A rewrite can flatten your voice"),
    ("the lists become outdated", "The pattern lists become outdated"),
    ("no corpus support", "have no corpus support"),
    ("masking can miss findings", "So the detector can miss findings"),
    ("constructs left visible", "The masker leaves some constructs visible"),
    ("a tool tag inside a URL", "The detector cannot find the tag `utm_source=chatgpt.com`, because the masker hides URLs"),
    ("Word files", "The plugin does not handle Word files"),
    ("the plugin root", "The repository owner did not test whether Claude Code expands `${CLAUDE_PLUGIN_ROOT}` in the `allowed-tools` lines of the command"),
    ("a widened proposal", "A widened proposal can need a retry"),
    ("the noun after a number", "The guard does not check the noun after a number"),
    ("number words", "Number words stop at twelve"),
    ("time units", "Time-unit abbreviations do not fold"),
    ("a quantifier swap", "A quantifier swap such as `about` to `roughly` fails by design"),
    ("a quantity word", "A quantity word used as an ordinary word counts"),
    ("the hedge list", "closed list of hedge words"),
    ("the month May", "such as the month May"),
    ("a name at the start", "cannot catch a new name at the start of a sentence"),
    ("lower-case gene names", "a gene name in lower case with no digit"),
    ("no-flag lints alone", "The guard `no-flag` lints the rewritten text alone"),
    ("a swap of two numbers", "The guard `numbers` counts each number and ignores its position. A rewrite that swaps two numbers passes."),
    ("the closed unit list", "The unit list is closed (see `_UNITS` in `prose_text.py`). A unit outside it gives the bare number, so `100 rpm` to `100 rcf` passes."),
    ("a dropped name", "The guard `no-new-names` checks the names that `after` adds. A name that `after` drops passes every guard, "
                       "unless it holds a digit that the guard `numbers` counts. No model check names the kept names, "
                       "and no pilot seeded a dropped name."),
    ("Edit on a CRLF file", "`Edit` on a file with CRLF line endings is untested."),
    ("a deletion with a number", "A sentence to delete that holds a number or a citation fails a guard, so the author edits it by hand."),
    ("precision for a manuscript", "The plugin gives no precision figure for a manuscript. The figures in "
                                   "`tests/verification/evidence/results.md` describe 60 invented paragraphs and nothing else."),
)


def family_json():
    """Return the parsed data file."""
    with open(DATA_PATH, encoding="utf-8") as handle:
        return json.load(handle)


def families_table(data):
    """Return the families table of the README, built from the data of `patterns.json`.

    The columns are the family id, the mode (with the threshold of a density family), the tiers of
    its rules (or of its check), the title and the strategy. The README holds this text. To update the
    README after a change of the data, run this function and paste its result.
    """
    lines = ["| Family | Mode | Tiers | What it finds | Rewrite strategy |", "|---|---|---|---|---|"]
    for family in data["families"]:
        tiers = set(rule["tier"] for rule in family.get("rules", []))
        if "tier" in family:
            tiers.add(family["tier"])
        mode = family["mode"]
        if mode == "density":
            mode = "density, above %g per 1000 words" % family["max_per_1000"]
        lines.append("| `%s` | %s | %s | %s | %s |" % (
            family["id"], mode, ", ".join(sorted(tiers)), family["title"], family["strategy"]))
    return "\n".join(lines)


def readme_headings():
    return [heading for heading, _ in split_sections(read_text(README))]


def readme_section(name):
    return normalized("\n".join(dict(split_sections(read_text(README)))[name]))


def guard_result(before, after, whole=None, hedge_reason=None):
    """Return the Result of `prose_verify.check_proposals` for a rewrite of `before` into `after`.

    The made-up file `x.txt` holds `whole`, which is `before` unless the caller gives more text. `before`
    must be the start of `whole`. The proposal names the family `vocabulary-excess`.
    """
    text = before if whole is None else whole
    proposal = {"id": "p1", "file": "x.txt", "start": 0, "end": len(before), "before": before, "after": after,
                "families": ["vocabulary-excess"], "reason": "test"}
    if hedge_reason is not None:
        proposal["hedge_reason"] = hedge_reason
    return prose_verify.check_proposals([proposal], PATTERNS, read=lambda path: text)[0]


def numbers_guard_fails(before, after):
    """Return True when the guard `numbers` fails for a rewrite of `before` into `after`."""
    return "numbers" in guard_result(before, after).failed


class ReadmeTests(unittest.TestCase):
    def test_the_sections_come_in_the_fixed_order(self):
        self.assertEqual(readme_headings(), list(README_SECTIONS))

    def test_the_families_table_is_the_table_of_the_data(self):
        self.assertIn(families_table(family_json()), read_text(README))

    def test_the_table_builder_gives_one_row_for_each_family(self):
        rows = families_table(family_json()).split("\n")
        self.assertEqual(len(rows), 2 + 17)
        self.assertTrue(rows[2].startswith("| `vocabulary-excess` | each | T1, T2, T3 |"))
        self.assertIn("| density, above 2.5 per 1000 words | T1, T2 |", rows[12])

    def test_the_readme_lists_every_family_id(self):
        text = read_text(README)
        for family in family_data():
            with self.subTest(family=family["id"]):
                self.assertIn("| `%s` |" % family["id"], text)

    def test_the_readme_names_the_number_of_families(self):
        self.assertIn("holds %d families" % len(family_data()), read_text(README))

    def test_the_readme_version_equals_the_manifest_version(self):
        versions = re.findall(r"^Version (\d+\.\d+\.\d+)\.$", read_text(README), re.M)
        self.assertEqual(len(versions), 1)
        with open(PLUGIN_JSON, encoding="utf-8") as handle:
            self.assertEqual(versions[0], json.load(handle)["version"])

    def test_the_guards_table_lists_the_ten_guards_in_the_order_of_the_code(self):
        rows = re.findall(r"^\| (\d+) \| `([a-z-]+)` \|", read_text(README), re.M)
        self.assertEqual([(int(n), name) for n, name in rows], list(enumerate(prose_verify.GUARDS, 1)))
        self.assertEqual(len(rows), 10)

    def test_the_usage_section_holds_the_usage_line_and_each_flag(self):
        section = "\n".join(dict(split_sections(read_text(README)))["Usage"])
        self.assertIn(USAGE, section)
        for flag in ("--report-only", "--voice", "--format", "--max-rounds"):
            with self.subTest(flag=flag):
                self.assertIn("- `%s" % flag, section)

    def test_every_limit_has_its_phrase(self):
        text = read_text(README)
        for label, phrase in LIMIT_PHRASES:
            with self.subTest(limit=label):
                self.assertEqual(missing_phrases(text, (phrase,)), [])

    def test_the_readme_lists_what_the_scripts_do_not_check(self):
        section = readme_section("Limits")
        self.assertIn("the scripts do not check four things", section)
        for label in ("rule-of-three padding", "synonym cycling", "meaning", "voice"):
            with self.subTest(label=label):
                self.assertIn("- %s: " % label, section)
        self.assertIn("you must read each changed passage", section)

    def test_a_rule_with_severity_info_always_shows_as_info(self):
        text = readme_section("What it detects")
        self.assertIn("a rule with severity `info`, which always shows as `info`, whatever the mode of its family", text)
        self.assertIn("a family in mode `density` flags its findings only when the file exceeds the threshold", text)

    def test_the_readme_says_approve_by_group(self):
        text = read_text(README)
        self.assertIn("you approve by group before any file changes", text)
        self.assertIn("5. Show. A table lists the proposals", text)
        self.assertIn("You approve by group.", text)
        self.assertIn("Approval by group.", "\n".join(dict(split_sections(text))["Decisions for the author"]))

    def test_the_install_section_gives_the_marketplace_and_install_lines(self):
        section = "\n".join(dict(split_sections(read_text(README)))["Install"])
        lines = [l for l in section.split("\n") if l.startswith("/plugin ")]
        self.assertEqual(lines, ["/plugin marketplace add " + repository_slug(),
                                 "/plugin install plain-prose@" + marketplace_name()])
        self.assertIn(lines[0], read_text(ROOT_README))

    def test_the_readme_lists_every_option_of_the_detector(self):
        options = [o for o in prose_lint._parser()._option_string_actions if o.startswith("--") and o != "--help"]
        self.assertEqual(sorted(options), ["--format", "--json", "--project-dir", "--windows"])
        section = "\n".join(dict(split_sections(read_text(README)))["What it detects"])
        for option in options:
            with self.subTest(option=option):
                self.assertIn("- `%s" % option, section)

    def test_the_readme_names_python_3_6_in_the_install_section_and_in_step_0(self):
        install = normalized("\n".join(dict(split_sections(read_text(README)))["Install"]))
        self.assertIn("the plugin needs python 3.6 or later and pyyaml", install)
        self.assertIn("0. Preflight. The command checks Python 3.6 or later and PyYAML", read_text(README))

    def test_the_usage_bullet_gives_the_default_of_max_rounds(self):
        section = "\n".join(dict(split_sections(read_text(README)))["Usage"])
        self.assertIn("- `--max-rounds N` sets how many more tries a rejected proposal gets. The default is 2.", section)

    def test_the_project_dir_option_also_searches_docs_and_the_claude_folder(self):
        section = normalized("\n".join(dict(split_sections(read_text(README)))["What it detects"]))
        self.assertIn("`--project-dir dir` names the folder to search for `prose-style.yaml`", section)
        self.assertIn("the detector also searches `docs/` and `.claude/` of that folder", section)

    def test_the_voice_limit_names_the_case_of_no_samples_and_no_saved_profile(self):
        limits = readme_section("Limits")
        self.assertIn("without samples and without a saved profile, no voice target exists", limits)
        self.assertIn("the model follows the plain-writing rules of `references/rewrite-rules.md`", limits)
        self.assertNotIn("without samples, no profile exists", limits)

    def test_the_readme_runs_the_detector_from_any_folder(self):
        text = normalized(read_text(README))
        self.assertIn("run the detector alone from the plugin folder with `python3 scripts/prose_lint.py <path>`", text)
        self.assertIn("from another folder, give the full path of the script", text)

    def test_the_hedge_kept_row_names_the_hedge_stack_waiver(self):
        row = [l for l in read_text(README).split("\n") if l.startswith("| 10 | `hedge-kept` |")]
        self.assertEqual(len(row), 1)
        # The code passes a hedge-stack proposal when `after` keeps 1 to the count of `before` (prose_verify).
        self.assertIn("A `hedge-stack` proposal also passes when `after` keeps at least one hedge word and no more than `before` has", row[0])
        self.assertIn("or the proposal gives a `hedge_reason`", row[0])

    def test_the_outdated_pattern_lists_bullet_varies_the_openers_of_its_sentences(self):
        bullet = [l for l in read_text(README).split("\n") if l.startswith("- The pattern lists become outdated.")]
        self.assertEqual(len(bullet), 1)
        masked = prose_mask.mask(bullet[0][2:], "markdown")
        firsts = []
        for start, end in prose_text.split_sentences(masked.text):
            words = prose_text.words(masked.text[start:end])[:1]
            firsts.append(words[0][2].lower() if words else "")
        self.assertGreaterEqual(len(firsts), 4)
        for i in range(len(firsts) - 2):
            self.assertNotEqual(len(set(firsts[i:i + 3])), 1, firsts)
        self.assertLessEqual(firsts.count("the"), 1, firsts)

    def test_the_readme_keeps_one_term_for_each_thing(self):
        # A finding is a detector result and a series is a run of sentences. The repository owner owns the
        # plugin. The word "user" and idioms stay out of the prose. A code span or a table row may hold them.
        masked = prose_mask.mask(read_text(README), "markdown").text.lower()
        self.assertNotRegex(masked, r"\buser\b")
        self.assertNotRegex(masked, r"\bhits?\b")
        self.assertNotRegex(masked, r"\b(?:the|a|each|whole|one) run\b")
        for idiom in ("goes back", "safe side", "pattern lists age"):
            with self.subTest(idiom=idiom):
                self.assertNotIn(idiom, masked)
        self.assertNotIn("the author's own", masked)

    def test_the_limits_name_both_families_without_corpus_support(self):
        limits = readme_section("Limits")
        self.assertIn("the families `binary-contrast` and `rhetorical-question` have no corpus support", limits)

    def test_the_limits_cite_the_corpus_note_and_its_keys(self):
        limits = readme_section("Limits")
        self.assertIn("`references/research-notes/corpus.md`", limits)
        for key in ("s1", "s5", "s6", "s16"):
            with self.subTest(key=key):
                self.assertIn("source %s" % key, limits)

    def test_the_numbers_that_the_readme_takes_from_the_corpus_note_stand_in_the_note(self):
        note = read_text(os.path.join(NOTES_DIR, "corpus.md"))
        for number in ("4.23%", "30 November 2022", "2.28", "5.55", "5.11", "2023 and 2024 text"):
            with self.subTest(number=number):
                self.assertIn(number, read_text(README))
                self.assertIn(number, note)

    def test_the_readme_states_the_date_of_the_data(self):
        with open(DATA_PATH, encoding="utf-8") as handle:
            as_of = json.load(handle)["as_of"]
        self.assertRegex(as_of, r"^\d{4}-\d{2}-\d{2}$")
        self.assertIn("`data/patterns.json` carries the date %s (`as_of`)" % as_of, read_text(README))

    def test_the_hedge_list_of_the_readme_is_the_list_of_the_code(self):
        # The README gives the closed list as one code span, as the spec does. The span equals the list of the code.
        self.assertEqual(len(prose_verify.HEDGE_WORDS), 16)
        self.assertIn("closed list of hedge words: `%s`." % " ".join(prose_verify.HEDGE_WORDS), read_text(README))

    def test_the_readme_describes_the_voice_profile_and_the_privacy_rule(self):
        self.assertEqual(missing_phrases(read_text(README), (
            "The privacy rule: the profile holds numbers and one-word openers and no sentence of a sample",
            "Never copy a sample into the repository",
            "The command never reads a sample itself",
            "the ten most common first words of a sentence, one word each")), [])

    def test_the_readme_names_the_project_file_and_its_keys(self):
        section = readme_section("The project file")
        for phrase in ("`prose-style.yaml`", "`./`, `docs/` and `.claude/`", "`enabled`", "`max_per_1000`", "`mode`",
                       "`disable_labels`", "`extra_patterns`"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, section)

    def test_the_project_file_example_of_the_readme_loads(self):
        blocks = [m.group(2) for m in FENCE.finditer(read_text(README)) if m.group(1) == "yaml"]
        self.assertEqual(len(blocks), 1)
        with tempfile.TemporaryDirectory() as folder:
            with open(os.path.join(folder, "prose-style.yaml"), "w", encoding="utf-8") as handle:
                handle.write(blocks[0])
            patterns = prose_patterns.load_patterns(folder)
        ids = [family.id for family in patterns.families]
        self.assertIn("lab-term", ids)
        self.assertNotIn("colon-reveal", ids)
        self.assertEqual([family.id for family in patterns.disabled], ["colon-reveal"])

    def test_the_decisions_for_the_author_name_the_deletion_difference_and_the_grouping(self):
        self.assertEqual(missing_phrases(readme_section("Decisions for the author"), (
            "A proposal with `delete: true` removes the sentence",
            "plain deletion in every format, LaTeX included",
            "The repository owner's skill `manuscript-write` prefers to comment out text",
            "The original stays in git history once a commit holds the file",
            "Approval by group. The proposals table groups proposals by the first entry of `families`",
            "You approve by group: all passing proposals except deletions, all passing proposals of one family, all deletions, or none",
            'You can pick several groups in one answer, and "none" overrides the others',
            "To pick single proposals, name their ids in a text reply")), [])
        self.assertNotIn("a numbered table gives chosen ids", readme_section("Decisions for the author"))

    def test_the_flow_counts_each_rewrite_after_a_guard_or_a_check_against_max_rounds(self):
        text = read_text(README)
        self.assertIn("After a failed guard or a failed check, the model rewrites the proposal, up to `--max-rounds` times in all.", text)
        self.assertNotIn("up to `--max-rounds` more times", text)

    def test_the_readme_says_that_a_deletion_never_uses_an_empty_new_text(self):
        text = readme_section("Decisions for the author")
        for phrase in ("The `Edit` tool removes the line break after the old text when the new text is empty",
                       "So the command never uses an empty new text: it replaces the neighbor sentence with itself, and the deleted sentence goes"):
            with self.subTest(phrase=phrase):
                self.assertIn(normalized(phrase), text)

    def test_the_readme_says_that_the_windows_call_exits_with_code_1(self):
        section = "\n".join(dict(split_sections(read_text(README)))["What it detects"])
        self.assertIn("- `--windows` prints one window for each sentence with a flagged finding. It exits with code 1 when it lists windows.", section)

    def test_the_relation_section_names_the_three_tools_and_the_paste_line(self):
        self.assertEqual(missing_phrases(readme_section("Relation to other tools"), (
            "`overleaf-manuscript`", "`manuscript-write`", "`no-ai-slop`",
            "paste this line into the text of the skill: `Run /plain-prose on the draft before you hand it over.`",
            "third-party repository", "found no license in the local copy",
            "copies only family names and short examples")), [])
        self.assertIn("Run `/plain-prose` on the draft before you hand it over.", spec_section(10))

    def test_the_readme_lists_the_five_research_notes_and_they_exist(self):
        section = dict(split_sections(read_text(README)))["Research notes"]
        listed = re.findall(r"^- `([a-z]+\.md)`:", "\n".join(section), re.M)
        self.assertEqual(listed, ["%s.md" % name for name in NOTE_NAMES])
        for name in listed:
            with self.subTest(note=name):
                self.assertTrue(os.path.isfile(os.path.join(NOTES_DIR, name)))

    def test_every_path_that_the_readme_names_exists(self):
        paths = named_paths(read_text(README))
        for expected in ("data/patterns.json", "scripts/prose_lint.py", "references/model-checks.md",
                         "references/rewrite-rules.md", "references/research-notes/corpus.md",
                         "examples/made-up-manuscript.tex", "examples/made-up-manuscript.expected.txt"):
            self.assertIn(expected, paths)
        for path in paths:
            with self.subTest(path=path):
                self.assertTrue(os.path.exists(os.path.join(PLUGIN_DIR, path)), path)

    def test_every_script_name_in_the_readme_exists(self):
        names = sorted(set(SCRIPT_NAME.findall(read_text(README))))
        self.assertGreaterEqual(len(names), 3)
        for name in names:
            with self.subTest(script=name):
                self.assertTrue(os.path.isfile(os.path.join(SCRIPTS_DIR, name)), name)

    def test_the_root_readme_has_a_section_for_the_plugin(self):
        section = root_readme_section()
        self.assertIn("plugins/plain-prose/README.md", section)
        self.assertIn("/plain-prose", section)
        with open(MARKETPLACE_JSON, encoding="utf-8") as handle:
            market = json.load(handle)["name"]
        self.assertIn("/plugin install plain-prose@%s" % market, section)

    def test_the_root_readme_section_says_approve_by_group(self):
        self.assertIn("you approve by group before any file changes", root_readme_section())

    def test_the_root_readme_keeps_the_sections_that_come_before(self):
        text = read_text(ROOT_README)
        names = re.findall(r"^### `([a-z-]+)`$", text, re.M)
        self.assertEqual(names[-2:], ["overleaf-manuscript", "plain-prose"])

    # The claims of the README about the guards hold in the code.

    def test_the_noun_after_a_number_is_not_checked(self):
        self.assertFalse(numbers_guard_fails("We counted 12 mice.", "We counted 12 rats."))

    def test_number_words_stop_at_twelve(self):
        self.assertTrue(numbers_guard_fails("We counted twelve mice.", "We counted eleven mice."))
        self.assertFalse(numbers_guard_fails("We counted thirteen mice.", "We counted sixty mice."))
        self.assertTrue(numbers_guard_fails("We counted thirty mice.", "We counted forty mice."))
        for word in ("hundred", "billion", "half", "twice", "double", "triple"):
            self.assertIn(word, prose_verify.NUMBER_WORDS)

    def test_time_unit_abbreviations_do_not_fold(self):
        self.assertTrue(numbers_guard_fails("Death followed at 48 h.", "Death followed at 48 hours."))
        self.assertFalse(numbers_guard_fails("Death followed at 3 weeks.", "Death followed at 3 week."))

    def test_a_quantifier_swap_fails(self):
        self.assertTrue(numbers_guard_fails("Growth fell by about 40%.", "Growth fell by roughly 40%."))

    def test_a_quantity_word_used_as_an_ordinary_word_counts(self):
        self.assertTrue(numbers_guard_fails("The cells grew over the plate.", "The cells grew on the plate."))

    def test_a_new_name_at_the_start_of_a_sentence_is_a_warning_and_no_failure(self):
        result = guard_result("The plants grew.", "Tavo slowed growth.")
        self.assertNotIn("no-new-names", result.failed)
        self.assertTrue(any("Tavo" in warning for warning in result.warnings), result.warnings)

    def test_the_readme_calls_the_stop_list_of_sentence_initial_words_common_words(self):
        # The list holds discourse adverbs such as "however" as well as function words, so the README says "common word".
        self.assertIn("It gives a warning for such a word unless the word is a common word.", read_text(README))
        self.assertNotIn("function word", read_text(README))
        self.assertIn("however", prose_verify.COMMON_STARTS)
        self.assertEqual(guard_result("The plants grew.", "The plants grew. However, growth slowed.").warnings, [])

    def test_the_new_limits_hold_in_the_code(self):
        # A swap of two numbers and a unit outside the list pass the guard `numbers`.
        self.assertFalse(numbers_guard_fails("Survival rose from 34% to 81% in the mutant.",
                                             "Survival rose from 81% to 34% in the mutant."))
        self.assertFalse(numbers_guard_fails("We spun the cells at 100 rpm for 5 min.", "We spun the cells at 100 rcf for 5 min."))
        self.assertNotIn("rpm", prose_text._UNITS)
        self.assertNotIn("rcf", prose_text._UNITS)
        self.assertIn("_UNITS = (", read_text(os.path.join(SCRIPTS_DIR, "prose_text.py")))
        # A dropped name passes every guard; the meaning check of the model checks is the only cover.
        dropped = guard_result("The Tavo and Brix mutants grew slowly in the dark.", "The Brix mutants grew slowly in the dark.")
        self.assertTrue(dropped.ok, dropped.detail)
        self.assertIn("- The meaning is kept:", read_text(MODEL_CHECKS))
        # A deletion of a sentence with a number or a citation fails a guard.
        text = "Survival fell in the mutant. As an AI model, I note that survival was 34% here. The roots grew."
        start = text.index("As an AI")
        end = text.index(" The roots")
        self.assertIn("numbers", verify_text(text, start, end, "", ["assistant-residue"], delete=True).failed)
        cited = "Survival fell in the mutant. As an AI model, I cite this (Smith et al., 2020). The roots grew."
        start, end = cited.index("As an AI"), cited.index(" The roots")
        self.assertIn("masked-spans", verify_text(cited, start, end, "", ["assistant-residue"], delete=True).failed)
        plain = "Survival fell in the mutant. As an AI model, I cannot help with that. The roots grew."
        start, end = plain.index("As an AI"), plain.index(" The roots")
        self.assertTrue(verify_text(plain, start, end, "", ["assistant-residue"], delete=True).ok)

    def test_the_record_names_who_labeled_the_rows_and_where_the_counts_come_from(self):
        record = normalized(read_text(os.path.join(PLUGIN_DIR, "tests", "verification", "evidence", "results.md")))
        for phrase in ("The assistant that built the plugin read every row and wrote the labels. The author has not read the rows.",
                       "The assistant read every row with its paragraph and labeled it before it looked at any figure.",
                       "This evidence folder holds the change lists of runs C and E. The other counts come from session logs outside the repository."):
            with self.subTest(phrase=phrase):
                self.assertIn(normalized(phrase), record)
        self.assertNotIn("i read every row", record)
        for name in ("rewrite-pilot-run-C-changes.txt", "rewrite-pilot-run-E-changes.txt"):
            self.assertTrue(os.path.isfile(os.path.join(PLUGIN_DIR, "tests", "verification", "evidence", name)))
        self.assertNotIn("because the precision pilot is open", read_text(README))

    def test_the_record_holds_the_choices_of_the_voice_check_and_they_match_the_key(self):
        # The record lists the ten choices of the author with the version chosen. The revised side of each item
        # is the side of ab-sample.md that does not occur word for word in the fixture paragraphs.
        evidence = os.path.join(PLUGIN_DIR, "tests", "verification", "evidence")
        record = read_text(os.path.join(evidence, "results.md"))
        sample = read_text(os.path.join(evidence, "ab-sample.md"))
        fixtures = " ".join(" ".join(p["text"].split()) for p in json.loads(
            read_text(os.path.join(PLUGIN_DIR, "tests", "verification", "fixtures", "paragraphs.json"))))
        items = re.findall(r"## Item (\d+)\n\nA\. (.+)\n\nB\. (.+)\n", sample)
        self.assertEqual([int(i[0]) for i in items], list(range(1, 11)))
        revised_side = {}
        for number, a_text, b_text in items:
            in_a, in_b = " ".join(a_text.split()) in fixtures, " ".join(b_text.split()) in fixtures
            self.assertNotEqual(in_a, in_b, "item %s: exactly one side must be the original" % number)
            revised_side[int(number)] = "B" if in_a else "A"
        rows = re.findall(r"^\| (\d+) \| ([AB]) \| (original|revised) \|$", record, re.M)
        self.assertEqual([int(r[0]) for r in rows], list(range(1, 11)))
        for number, choice, version in rows:
            with self.subTest(item=number):
                chose_revised = choice == revised_side[int(number)]
                self.assertEqual(version, "revised" if chose_revised else "original")
        key_a = [n for n, side in sorted(revised_side.items()) if side == "A"]
        key_b = [n for n, side in sorted(revised_side.items()) if side == "B"]
        self.assertIn("The revised version was A in items %s, and B in items %s." % (
            ", ".join(str(n) for n in key_a[:-1]) + " and " + str(key_a[-1]),
            ", ".join(str(n) for n in key_b[:-1]) + " and " + str(key_b[-1])), record)
        # The record gives the choices without a score.
        for phrase in ("out of 10", "out of ten", "of 10 pairs preferred", "preferred the rewrite in"):
            self.assertNotIn(phrase, record)

    def test_a_lower_case_gene_name_with_no_digit_is_not_caught(self):
        result = guard_result("The plants grew.", "The plants grew near tavo.")
        self.assertNotIn("no-new-names", result.failed)
        self.assertIn("Tavo", prose_text.protected_names("The Tavo mutant grew."))

    def test_the_month_may_fails_the_hedge_guard(self):
        result = guard_result("We sampled in May.", "We sampled in June.")
        self.assertIn("hedge-kept", result.failed)

    def test_a_hedge_reason_waives_the_hedge_guard(self):
        before = "We sampled in May."
        result = guard_result(before, "We sampled in June.", hedge_reason="May is a month")
        self.assertNotIn("hedge-kept", result.failed)

    def test_no_flag_lints_the_rewritten_text_alone(self):
        # The after text holds no hit alone, so the guard passes, although the file holds a hit elsewhere.
        first = "The plants grew."
        result = guard_result(first, "The plants grew fast.", whole=first + " Here we delve into the data.")
        self.assertNotIn("no-flag", result.failed)
        self.assertIn("no-flag", guard_result(first, "Here we delve into the data.").failed)


# ---------------------------------------------------------------------------------------
# Privacy
# ---------------------------------------------------------------------------------------

# Each pattern is written so that its own source text does not match it.
HOME_PATH = re.compile(r"(?<![\w.-])[/](?:home|Users|hpc|scratch|mnt|gpfs|projects|sc)[/]|C:[\\]Users[\\]", re.I)
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+")
# A digital object identifier (DOI) can name a real paper. Made-up text holds none.
DOI = re.compile(r"10\.\d{4,9}/\S+")
ALLOWED_DOMAINS = ("example.org", "example.com", "example.net")
# The handle patterns of the author are built from parts, so this file does not hold the name.
HANDLE = re.compile("|".join((
    "yang" + r"[-_. ]?" + "jo{1,2}" + "n",
    "yang" + "jun" + r"\d*",
    "czbio" + "hub",
    "gith" + "ub" + r"\.com/(?!example)",
)), re.I)


def marketplace_name():
    """Return the name of the marketplace. It is a public name, and the install line of the README holds it."""
    with open(MARKETPLACE_JSON, encoding="utf-8") as handle:
        return json.load(handle)["name"]


def repository_slug():
    """Return "owner/name" of the repository, from the manifest. The marketplace line of the README holds it."""
    with open(PLUGIN_JSON, encoding="utf-8") as handle:
        url = json.load(handle)["repository"]
    return url.split("github.com/", 1)[1]


def allowed_names():
    """Return the two strings that the privacy scan removes before it looks for a handle."""
    return (marketplace_name(), repository_slug())


def private_hits(text, allowed=()):
    """Return a list of (label, snippet) for each private item in the text.

    A string of `allowed` is removed from the text before the scan.
    """
    for name in allowed:
        text = text.replace(name, "")
    hits = [("home path", m.group(0)) for m in HOME_PATH.finditer(text)]
    for match in EMAIL.finditer(text):
        if match.group(0).split("@", 1)[1].lower() not in ALLOWED_DOMAINS:
            hits.append(("e-mail", match.group(0)))
    hits.extend(("handle", m.group(0)) for m in HANDLE.finditer(text))
    hits.extend(("doi", m.group(0)) for m in DOI.finditer(text))
    return hits


def private_files():
    """Return the files that the privacy test scans.

    They are references/*.md, every file of examples/, the README and the text of the command.
    """
    paths = [os.path.join(REFERENCES_DIR, n) for n in sorted(os.listdir(REFERENCES_DIR)) if n.endswith(".md")]
    paths += [os.path.join(EXAMPLES_DIR, n) for n in sorted(os.listdir(EXAMPLES_DIR))]
    return paths + [README, COMMAND]


class PrivacyTests(unittest.TestCase):
    def test_the_scan_reaches_the_documents(self):
        names = [os.path.basename(p) for p in private_files()]
        for name in ("rewrite-rules.md", "model-checks.md", "made-up-manuscript.tex", "made-up-manuscript.expected.txt",
                     "README.md", "plain-prose.md"):
            self.assertIn(name, names)

    def test_no_reference_and_no_example_holds_private_text(self):
        for path in private_files():
            with self.subTest(file=os.path.basename(path)):
                self.assertEqual(private_hits(read_text(path), allowed_names()), [])

    def test_the_readme_install_lines_hold_the_marketplace_name_and_the_repository_and_nothing_else_private(self):
        text = read_text(README)
        self.assertIn("@" + marketplace_name(), text)
        self.assertIn("/plugin marketplace add " + repository_slug(), text)
        self.assertNotEqual(private_hits(text), [])
        self.assertEqual(private_hits(text, allowed_names()), [])

    def test_the_patterns_find_made_up_private_text(self):
        slash = "/"  # Built from parts so this file does not match its own scan.
        samples = (
            ("home path", slash + "home" + slash + "someone/work"),
            ("home path", "see " + slash + "hpc" + slash + "projects/x"),
            ("home path", slash + "Users" + slash + "someone"),
            ("e-mail", "someone" + "@" + "university.edu"),
            ("handle", "by " + "yang" + "-" + "joon" + " here"),
            ("handle", "yang" + "jun" + "9095"),
            ("handle", "see https://" + "gith" + "ub.com/someone"),
            ("doi", "see " + "10" + ".1234/" + "abc.2020.5"),
        )
        for label, text in samples:
            with self.subTest(text=text):
                self.assertEqual([hit[0] for hit in private_hits(text)], [label])

    def test_the_patterns_stay_quiet_on_allowed_text(self):
        for text in ("Write to someone@example.org today.", "a relative path docs/data/x.csv",
                     "the word home and the word hpc", "https://example.org/page"):
            with self.subTest(text=text):
                self.assertEqual(private_hits(text), [])


if __name__ == "__main__":
    unittest.main()
