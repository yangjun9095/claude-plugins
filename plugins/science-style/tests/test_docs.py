"""Tests for the prompts, the command and the documents of science-style."""
import json
import os
import re
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "lab"))
sys.path.insert(0, HERE)

import lab_card_check as cc  # noqa: E402
import lab_checklist as lc  # noqa: E402
import lab_paths as lp  # noqa: E402
import style_lab  # noqa: E402

PLUGIN = lp.PLUGIN_ROOT
REPO = os.path.dirname(os.path.dirname(PLUGIN))
BANNED = ("delve", "leverage", "utilize", "robust", "seamless", "holistic", "crucial", "pivotal", "vital",
          "comprehensive", "cutting-edge", "state-of-the-art", "paradigm", "synergy", "streamline", "myriad",
          "plethora", "meticulous", "nuanced", "intricate", "showcase")


def read(*parts):
    with open(os.path.join(*parts), encoding="utf-8") as handle:
        return handle.read()


def json_blocks(text):
    return re.findall(r"```json\n(.*?)\n```", text, re.S)


def section(text, heading):
    """Return the body of the level-2 section with this heading."""
    match = re.search(r"^## {}\n(.*?)(?=^## |\Z)".format(re.escape(heading)), text, re.S | re.M)
    return match.group(1)


REVISED_SENTENCES = (
    "When no section has kind `intro`, the introduction is the first section, if its kind is `other` or `body`.",
    "When the first section has any other kind, for example `results`, the paper has no introduction.",
    "Leave `intro_roles` empty.",
    "Answer `none` to `gap_sentence` and `here_we`.",
    "Each section of kind `results` is one results section.",
    "When the paper has one section of kind `results` and it has subsections, each subsection is one results "
    "section instead.",
    "When the results are one section with no subsections, write one line for each new question that the text "
    "answers.",
    "A step that serves the same question gets no line of its own.",
    "Judge each results section by its first sentence that asks a question, states an aim, states a finding or "
    "describes a method.",
    "Skip sentences that give background, cite earlier work or state a hypothesis.",
    'A sentence that states the finding ("we begin by showing that X") is `result first`.',
    "`placement` is where most limits stand.",
    "When no place holds most, choose the first place in reading order.",
    "`inline in methods` means that the limits stand in the Methods.",
    "`inline in body` is for a paper with no results or discussion section.",
    "A limit is a weakness or boundary of this paper's own data, method or claims.",
    "A hypothesis, or a limit of earlier work, is not a limit.",
    "`specificity` is the most specific level that any limit reaches.",
    "These levels run from most to least specific.",
    "the claim with the widest scope, the one that carries the findings furthest beyond the systems the authors "
    "tested.",
    "Choose it over a narrower claim even when it is hedged.",
    "`mixed` means that each of these two patterns makes up at least one third of the figure and table citations "
    "outside the Methods.",
    "Otherwise choose the pattern that most citations follow.",
    "Quote only the recurring or unusual words, at most 12 words, not the sentence around them.",
    "analogies, and sentences that say in everyday words why or how something works, so that a reader outside "
    "the field can follow.",
    "Do not quote method steps written in field terms, or clauses that only pose a question.",
    'what earlier work has not done ("studied to date", "current models only"), or a stated need',
    "In a paper with no section of kind `results`, a sentence on what the paper covers or teaches is `approach`.",
    "In such a paper, a sentence on what the reviewed work found is `context`.",
    "In such a paper, an outlook or a recommendation is `implication`.",
    "Do not use `result` for such a paper.",
    "Choose the form that most headings take.",
    "Use the lowest heading level inside the results.",
    "That means the subsection headings when the results have subsections, and the section headings when they "
    "have none.",
    "`result preview` summarizes the findings of this paper before the results section",
)


VERSION_3_SENTENCES = (
    "A research paper with no section of kind `results` follows rule 13 instead.",
    "Its introduction is the opening paragraphs up to the end that rule 13 gives.",
    "These paragraphs can sit in a section of kind `intro` or `body` that runs on.",
    "When any section has kind `results`, fill `results_headings`, `results_openings` and `storyline`.",
    "An essay, a review or a tutorial reports no results of its own.",
    'For such a paper with no section of kind `results`, answer `{"not_applicable": true}` to these three items.',
    "Any other paper is a research paper.",
    "A research paper of group `senior` or `first` can have no section of kind `results`.",
    "In such a paper, the introduction ends just before the first paragraph that reports the paper's own work.",
    "The headed sections or subsections after it, before the discussion, are its results sections.",
    "Answer `results_headings`, `results_openings` and `storyline` from them.",
    "When the paper has no headings after the introduction, treat its paragraphs after the introduction as one "
    "results section.",
    "In a paper with a section of kind `results`, a section of any other kind is never a results section.",
    "A gap says what is not known, what earlier work has not done, or what is still needed.",
    "A broad challenge of the field is not a gap.",
    "When several sentences state a gap, choose the gap that the `here_we` sentence answers.",
    "If the `here_we` sentence answers none of them, choose the first.",
    "The paragraph that holds the `gap_sentence` quote has the role `gap`.",
    "The paragraph that holds the `here_we` quote has the role `here-we`, even when it also holds the gap.",
    "Quote wording habits, such as transitions, hedges, evaluative words and framing phrases.",
    "Never quote the name of a method, a model, a molecule, a quantity or a phenomenon that the paper studies, "
    "however often it recurs.",
    "When the widest claim stands in several places, quote it from the abstract.",
    "When the abstract does not hold it, quote it from the first place in reading order where it appears.",
    "In an essay or a review, a limit of the work that it reviews does not count.",
    "A workaround that the authors already applied is not a remedy.",
    "A sentence passes when a reader with school-level science can follow it.",
    "Do not quote a sentence that only announces an analogy, or a figure of speech that explains nothing.",
    "An empty list is a valid answer.",
    'A sentence such as "We evaluate X" or "We investigate X" is `aim`.',
    "A sentence that says how the authors did the work is `method first`.",
)


def one_line_card(sentence):
    return "# Ada\n\n## Sample\n\n{}\n".format(sentence)


class PromptTests(unittest.TestCase):
    def test_the_extraction_brief_names_every_item_and_its_example_is_valid(self):
        text = read(PLUGIN, "prompts", "extract.md")
        self.assertIn("Prompt version: {}".format(lc.PROMPT_VERSION), text)
        self.assertIn("40 words", text)
        checklist = lc.load_checklist()
        for item in checklist["items"]:
            self.assertIn("`{}`".format(item["id"]), text, item["id"])
        example = json.loads(json_blocks(text)[0])
        self.assertEqual(lc.validate_extraction(example, checklist, "senior"), [])
        self.assertEqual(example["prompt_version"], lc.PROMPT_VERSION)
        self.assertEqual(example["checklist_version"], checklist["version"])
        roles = example["answers"]["intro_roles"]["value"]
        for item_id, role in (("gap_sentence", "gap"), ("here_we", "here-we")):
            self.assertEqual(roles[example["answers"][item_id]["paragraph"] - 1], role, item_id)

    def test_the_extraction_brief_holds_the_revised_rules_in_short_sentences(self):
        text = " ".join(read(PLUGIN, "prompts", "extract.md").split())
        for sentence in REVISED_SENTENCES + VERSION_3_SENTENCES:
            self.assertIn(sentence, text)
            self.assertLessEqual(len(sentence.split()), 25, sentence)

    def test_the_introduction_rule_points_at_the_rule_for_a_paper_without_a_results_section(self):
        rules = section(read(PLUGIN, "prompts", "extract.md"), "Rules")
        by_number = dict(re.findall(r"^(\d+)\. (.*)$", rules, re.M))
        self.assertIn("follows rule 13 instead", by_number["7"])
        self.assertTrue(by_number["13"].startswith("A research paper of group `senior` or `first`"))

    def test_the_extraction_brief_numbers_its_rules_in_order(self):
        rules = section(read(PLUGIN, "prompts", "extract.md"), "Rules")
        numbers = [int(n) for n in re.findall(r"^(\d+)\. ", rules, re.M)]
        self.assertEqual(numbers, list(range(1, len(numbers) + 1)))

    def test_the_brief_lists_every_value_that_the_checklist_adds(self):
        text = read(PLUGIN, "prompts", "extract.md")
        meanings = section(text, "Meanings of the values")
        self.assertIn("`result preview`", meanings)
        self.assertIn("`inline in methods`", meanings)
        self.assertIn("`inline in body`", meanings)
        checklist = lc.load_checklist()
        marked = [i["id"] for i in checklist["items"] if lc.may_be_not_applicable(i)]
        rules = section(text, "Rules")
        for item_id in marked:
            self.assertIn("`{}`".format(item_id), rules, item_id)

    def test_the_prompt_version_of_the_extraction_brief_matches_the_code(self):
        text = read(PLUGIN, "prompts", "extract.md")
        versions = re.findall(r"^Prompt version: (\d+)$", text, re.M)
        self.assertEqual(versions, [str(lc.PROMPT_VERSION)])

    def test_the_card_brief_matches_the_card_check(self):
        text = read(PLUGIN, "prompts", "card.md")
        positions = [text.index("`## {}`".format(h)) for h in cc.CARD_HEADINGS]
        self.assertEqual(positions, sorted(positions))
        limits = cc.LIMITS["card"]
        for phrase in ("{} words".format(limits["words"]), "{} quotes".format(limits["quotes"]),
                       "{} quotes from one paper".format(limits["per_doi"]), "{} words or fewer".format(cc.MAX_QUOTE_WORDS),
                       "(doi:"):
            self.assertIn(phrase, text)

    def test_the_card_brief_states_the_stability_passive_and_ordinal_rules(self):
        text = " ".join(read(PLUGIN, "prompts", "card.md").split())
        for sentence in ("Storyline, explanations and signature_phrases have no stability entry; you may describe them.",
                         "The passive share is a lower bound: the pattern misses some passive forms. "
                         "Say so when you give it.",
                         "Do not name list sizes or ordinals, such as top 30 or 90th percentile; the check rejects "
                         "numbers that the profile does not hold."):
            self.assertIn(sentence, text)
        checklist = lc.load_checklist()
        closed = {i["id"] for i in lc.closed_items(checklist)}
        self.assertEqual(sorted(i["id"] for i in checklist["items"] if i["id"] not in closed),
                         ["explanations", "signature_phrases", "storyline"])

    def test_the_extraction_rules_name_every_item_that_has_evidence_rules(self):
        rules = section(read(PLUGIN, "prompts", "extract.md"), "Rules")
        with_evidence = [i["id"] for i in lc.load_checklist()["items"] if "evidence" in i]
        self.assertTrue(with_evidence)
        for item_id in with_evidence:
            self.assertIn("`{}`".format(item_id), rules, item_id)

    def test_the_number_words_that_the_card_brief_bans_fail_the_card_check(self):
        text = read(PLUGIN, "prompts", "card.md")
        named = re.search(r"number words such as ([^.]*)\.", text).group(1)
        banned = [w for w in re.findall(r"[a-z]+", named) if w != "or"]
        self.assertEqual(banned, ["two", "half", "quarter", "twice"])
        for word in banned:
            self.assertIn(word, cc.NUMBER_WORDS)
            failures = cc.check_text(one_line_card("The split is {} the size.".format(word)), "card", [])
            self.assertIn("write numbers as digits: " + word, failures)
        for phrase, sentence in (("3-fold", "The share is a 3-fold gain."), ("twofold", "The share is a twofold gain."),
                                 ("one of N", "The share is one of 7 papers."),
                                 ("one in N", "The share is one in 7 papers.")):
            self.assertIn(phrase, text)
            failures = cc.check_text(one_line_card(sentence), "card", [])
            self.assertTrue([f for f in failures if f.startswith("write numbers as digits")], phrase)

    def test_the_principles_brief_matches_the_check(self):
        text = read(PLUGIN, "prompts", "principles.md")
        for heading in cc.PRINCIPLES_HEADINGS:
            self.assertIn("`## {}`".format(heading), text)
        self.assertIn("1,200 words", text)
        self.assertIn("python3 -I lab/style_lab.py check-card principles", text)

    def test_the_principles_brief_models_no_number_word(self):
        failures = cc.check_text(read(PLUGIN, "prompts", "principles.md"), "principles", [])
        self.assertEqual([f for f in failures if f.startswith("write numbers as digits")], [])


TEAM_CARD_SENTENCE = ("A team card names its members in the title line, and its Caveats say that the card "
                      "describes the joint papers of those members.")
PRINCIPLES_TEAM_SENTENCE = "Use the profiles of individuals only and skip every team profile."
SKILL_TEAM_SENTENCE = "a person id or a team id from `<plugin>/data/people.json`"


class TeamDocumentTests(unittest.TestCase):
    def test_the_card_brief_says_how_a_team_card_differs(self):
        text = " ".join(read(PLUGIN, "prompts", "card.md").split())
        self.assertIn(TEAM_CARD_SENTENCE, text)
        self.assertLessEqual(len(TEAM_CARD_SENTENCE.split()), 25)

    def test_the_principles_brief_uses_individuals_only(self):
        text = " ".join(read(PLUGIN, "prompts", "principles.md").split())
        self.assertIn(PRINCIPLES_TEAM_SENTENCE, text)

    def test_the_skill_accepts_a_person_id_or_a_team_id(self):
        text = " ".join(read(PLUGIN, "skills", "science-write", "SKILL.md").split())
        self.assertIn(SKILL_TEAM_SENTENCE, text)

    def test_the_command_and_the_readme_describe_teams(self):
        for path in (("commands", "style-lab.md"), ("README.md",)):
            text = read(PLUGIN, *path)
            self.assertIn("team", text, path)
            self.assertIn("members", text, path)
        self.assertIn("shendure-trapnell", read(PLUGIN, "README.md"))


class CommandTests(unittest.TestCase):
    def setUp(self):
        self.text = read(PLUGIN, "commands", "style-lab.md")

    def test_the_command_has_front_matter_and_names_every_subcommand(self):
        self.assertTrue(self.text.startswith("---\ndescription: "))
        subparsers = [a for a in style_lab.build_parser()._actions if a.dest == "command"][0]
        for name in subparsers.choices:
            self.assertIn("style_lab.py {}".format(name), self.text, name)

    def test_the_command_states_the_data_layout_once_and_the_retry_rules(self):
        self.assertEqual(self.text.count("papers/<person>/<work>.json"), 1)
        for phrase in ("extract/<person>/<work>.json", "<work>.agreement.json", "digest/<person>.json", "pilot/",
                       "`network error`", "`<person>: N papers checked`", "`invalid`", "`extraction_failed`"):
            self.assertIn(phrase, self.text)
        self.assertNotIn("go on", self.text)

    def test_the_command_states_the_shape_of_a_spot_file(self):
        self.assertIn('`{"work_id": "...", "marks": {item_id: "correct" | "wrong" | "vague"}}`', self.text)
        for mark in style_lab.SPOT_MARKS:
            self.assertIn('"{}"'.format(mark), self.text)

    def test_every_subagent_has_an_explicit_model_and_haiku_has_no_task(self):
        self.assertGreaterEqual(self.text.count("model: sonnet"), 3)
        self.assertNotIn("haiku", self.text.lower())
        self.assertIn("STYLE_LAB_DATA", self.text)


class DocumentTests(unittest.TestCase):
    def test_the_readme(self):
        text = read(PLUGIN, "README.md")
        for phrase in ("STYLE_LAB_DATA", "python3 -B -m unittest discover -s tests", "outside the repository",
                       "/style-lab"):
            self.assertIn(phrase, text)

    def test_the_root_readme_lists_the_plugin(self):
        text = read(REPO, "README.md")
        self.assertIn("### `science-style`", text)
        self.assertLess(text.index("### `science-style`"), text.index("## Archived"))

    def test_no_banned_word_in_the_documents(self):
        paths = [os.path.join(PLUGIN, "README.md"), os.path.join(PLUGIN, "commands", "style-lab.md")]
        paths += [os.path.join(PLUGIN, "prompts", n) for n in ("extract.md", "card.md", "principles.md")]
        for path in paths:
            lower = read(path).lower()
            for word in BANNED:
                self.assertIsNone(re.search(r"\b" + re.escape(word) + r"\b", lower), "{} in {}".format(word, path))

    def test_committed_cards_pass_the_card_check(self):
        folder = os.path.join(PLUGIN, "profiles")
        names = sorted(n[:-3] for n in os.listdir(folder) if n.endswith(".md") and n != "quality.md") \
            if os.path.isdir(folder) else []
        for name in names:
            if name == "principles":
                profiles = [lp.read_json(os.path.join(folder, n)) for n in sorted(os.listdir(folder)) if n.endswith(".json")]
                kind = "principles"
            else:
                profiles = [lp.read_json(os.path.join(folder, name + ".json"))]
                kind = "card"
            self.assertEqual(cc.check_text(read(folder, name + ".md"), kind, profiles), [], name)


if __name__ == "__main__":
    unittest.main()
