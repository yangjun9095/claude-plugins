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
