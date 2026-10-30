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


class PromptTests(unittest.TestCase):
    def test_the_extraction_brief_names_every_item_and_its_example_is_valid(self):
        text = read(PLUGIN, "prompts", "extract.md")
        self.assertIn("Prompt version: 1", text)
        self.assertIn("40 words", text)
        checklist = lc.load_checklist()
        for item in checklist["items"]:
            self.assertIn("`{}`".format(item["id"]), text, item["id"])
        example = json.loads(json_blocks(text)[0])
        self.assertEqual(lc.validate_extraction(example, checklist, "senior"), [])
        self.assertEqual(example["prompt_version"], 1)

    def test_the_prompt_version_of_the_extraction_brief_matches_the_code(self):
        text = read(PLUGIN, "prompts", "extract.md")
        versions = re.findall(r"^Prompt version: (\d+)$", text, re.M)
        self.assertEqual(versions, [str(lc.PROMPT_VERSION)])
        example = json.loads(json_blocks(text)[0])
        self.assertEqual(example["prompt_version"], lc.PROMPT_VERSION)
        self.assertEqual(lc.validate_extraction(example, lc.load_checklist(), "senior"), [])

    def test_the_card_brief_matches_the_card_check(self):
        text = read(PLUGIN, "prompts", "card.md")
        positions = [text.index("`## {}`".format(h)) for h in cc.CARD_HEADINGS]
        self.assertEqual(positions, sorted(positions))
        limits = cc.LIMITS["card"]
        for phrase in ("{} words".format(limits["words"]), "{} quotes".format(limits["quotes"]),
                       "{} quotes from one paper".format(limits["per_doi"]), "{} words or fewer".format(cc.MAX_QUOTE_WORDS),
                       "(doi:"):
            self.assertIn(phrase, text)

    def test_the_principles_brief_matches_the_check(self):
        text = read(PLUGIN, "prompts", "principles.md")
        for heading in cc.PRINCIPLES_HEADINGS:
            self.assertIn("`## {}`".format(heading), text)
        self.assertIn("1,200 words", text)


class CommandTests(unittest.TestCase):
    def setUp(self):
        self.text = read(PLUGIN, "commands", "style-lab.md")

    def test_the_command_has_front_matter_and_names_every_subcommand(self):
        self.assertTrue(self.text.startswith("---\ndescription: "))
        subparsers = [a for a in style_lab.build_parser()._actions if a.dest == "command"][0]
        for name in subparsers.choices:
            self.assertIn("style_lab.py {}".format(name), self.text, name)

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
