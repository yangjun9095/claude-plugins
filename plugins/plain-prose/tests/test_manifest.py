"""Tests for the plugin manifest, the marketplace entry and the research notes.

All text in this file is made up. The tests check four groups of facts.

Manifest. The files plugin.json and marketplace.json parse. The file plugin.json
has exactly the eight keys of the other plugins. The marketplace keeps the nine
entries that existed before this plugin, in order. It holds one entry named
plain-prose, with the keys name, source, description and version. The version and
the description of that entry equal those of plugin.json.

Hashes. Each research note has a pinned SHA-256 value. A change to a note fails
the test until a person updates the pin on purpose. The file .gitattributes stops
a line-ending conversion that would change the hash.

Source keys. A note lists its sources in the section whose heading holds "Pages
opened" or "Files read". A line of that list that starts with "- S" and a number,
as in "- S12 ", defines a key. A defined line in corpus, wikipedia, guides and
craft holds an http or https URL. A defined line in authors holds a path in
backticks, because that note lists local files. A table row is any line that
starts with "|". The checker reads the table rows of every section, the source
list included. A key in a table row is a token S<n> with no leading zero, in any
cell of the row. The ids S01 to S04 in authors.md name rules, and the
leading-zero rule skips them. Every key that a table row uses must have a line in
the source list. A key that the list defines and no table uses is allowed.
Self-tests run the checker on made-up notes, so a broken pattern cannot pass
unseen.

Privacy. No file under plugins/plain-prose holds an absolute home or project
path. The path rule covers the root folders of Linux, macOS, Windows and cluster
file systems. No file holds an email address either, with three exceptions. One
is the Claude attribution address. Others are addresses at example.org,
example.com or example.net. The last kind has a one-letter local part and a
one-letter domain label, as in the made-up fixtures of the masker tests.
Self-tests run the patterns on made-up text that the test builds from parts.
"""
import hashlib
import json
import os
import re
import unittest
from collections import OrderedDict

HERE = os.path.dirname(os.path.abspath(__file__))
PLUGIN_DIR = os.path.dirname(HERE)
REPO_DIR = os.path.dirname(os.path.dirname(PLUGIN_DIR))
PLUGIN_JSON = os.path.join(PLUGIN_DIR, ".claude-plugin", "plugin.json")
MARKETPLACE_JSON = os.path.join(REPO_DIR, ".claude-plugin", "marketplace.json")
NOTES_DIR = os.path.join(PLUGIN_DIR, "references", "research-notes")
GITATTRIBUTES = os.path.join(PLUGIN_DIR, ".gitattributes")

PLUGIN_NAME = "plain-prose"
PLUGIN_KEYS = ["name", "version", "description", "author", "homepage",
               "repository", "license", "keywords"]
MARKET_KEYS = ["name", "source", "description", "version"]
OTHER_PLUGINS = (
    "prep-report", "generate-slides", "figure-style", "meeting-distill",
    "codeql-quality-review", "agent-board", "email-report", "build-kg",
    "overleaf-manuscript",
)
NOTE_NAMES = ("corpus", "wikipedia", "guides", "authors", "craft")

# SHA-256 of each research note, as copied byte for byte from the research run.
# Update a value only when you change the note on purpose. The authors note changed
# once on purpose: one row names the repository author by role instead of by name.
NOTE_HASHES = {
    "corpus": "5026fa01ad7f10a4e8cde34feaf1ac48019b78589521c8664fe8575fca4207d2",
    "wikipedia": "971da466e964f86ee868c6907c87d1d60c005fc335646b2a83ad78007bf172a2",
    "guides": "23d8864f136d1b1869ea40fe42df5e53edb04dde42378c1389134089beb5aee0",
    "authors": "7528582705043aa31f45e1c137111e69d052b0c463b655c5e43e79187326f1a3",
    "craft": "2a1a0120324eb3610ce2284f13cf191c3d73acdc5d2611ded9cbb480fccb6ac4",
}

SOURCE_TITLES = ("Pages opened", "Files read")
KEY_LINE = re.compile(r"^- (S[1-9][0-9]*) ")
TABLE_KEY = re.compile(r"\bS[1-9][0-9]*\b")
URL = re.compile(r"https?://")
PATH = re.compile(r"`[^`\n]*[/.][^`\n]*`")
PATH_NOTES = ("authors",)
SEMVER = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")

# Each pattern is written so that its own source text does not match it.
PRIVATE_PATTERNS = (
    ("home or project path",
     re.compile(r"(?<![\w.-])[/](?:home|Users|hpc|scratch|mnt|gpfs|projects|sc)[/]"
                r"|C:[\\]Users[\\]", re.IGNORECASE)),
    ("email address",
     re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+")),
)
ALLOWED_EMAILS = ("noreply@anthropic.com",)
EXAMPLE_DOMAINS = ("example.org", "example.com", "example.net")
ONE_LETTER_DOMAIN = re.compile(r"^[a-z]\.[a-z0-9.]+$", re.IGNORECASE)


def rel(path):
    return os.path.relpath(path, REPO_DIR)


def plugin_problems(data):
    """Return the problems of a parsed plugin.json as a list of short texts."""
    problems = []
    keys = list(data.keys())
    if keys != PLUGIN_KEYS:
        problems.append("keys are " + ", ".join(keys) + "; need " + ", ".join(PLUGIN_KEYS))
    if data.get("name") != PLUGIN_NAME:
        problems.append("name is not " + PLUGIN_NAME)
    version = data.get("version")
    if not (isinstance(version, str) and SEMVER.match(version)):
        problems.append("version is missing or has no n.n.n form")
    description = data.get("description")
    if not (isinstance(description, str) and description.strip()):
        problems.append("description is missing or empty")
    elif len(description.split()) > 25:
        problems.append("description has more than 25 words")
    author = data.get("author")
    if not (isinstance(author, dict) and author.get("name") and author.get("url")):
        problems.append("author needs a name and a url")
    for field in ("homepage", "repository", "license"):
        if not data.get(field):
            problems.append(field + " is missing")
    keywords = data.get("keywords")
    if not (isinstance(keywords, list) and keywords):
        problems.append("keywords is missing or empty")
    return problems


def link_form(name):
    """Return the link form that the source lines of a note must hold."""
    return "path" if name in PATH_NOTES else "url"


def has_link(line, form):
    """Return True when the line holds a link of the form "url" or "path"."""
    return bool((URL if form == "url" else PATH).search(line))


def analyze_note(text):
    """Return the source-list facts of one note.

    The result has four items. The first is the number of source-list sections.
    The second is the ordered dict of key to list line. The third is the list of
    repeated keys. The last is the set of keys that table rows use in any section.
    """
    sections = 0
    defined = OrderedDict()
    repeated = []
    table_keys = set()
    in_list = False
    for line in text.split("\n"):
        if line.startswith("## "):
            in_list = any(title in line for title in SOURCE_TITLES)
            if in_list:
                sections += 1
        elif line.startswith("|"):
            table_keys.update(TABLE_KEY.findall(line))
        elif in_list:
            match = KEY_LINE.match(line)
            if match:
                key = match.group(1)
                if key in defined:
                    repeated.append(key)
                else:
                    defined[key] = line
    return {"sections": sections, "defined": defined, "repeated": repeated,
            "table_keys": table_keys}


def allowed_email(address):
    """Return True for the attribution address and for a placeholder address."""
    local, domain = address.split("@", 1)
    if address.lower() in ALLOWED_EMAILS or domain.lower() in EXAMPLE_DOMAINS:
        return True
    return (len(local) == 1 and local.isalpha()
            and bool(ONE_LETTER_DOMAIN.match(domain)))


def private_hits(text):
    """Return a list of (label, snippet) for each private item in the text."""
    hits = []
    for label, pattern in PRIVATE_PATTERNS:
        for match in pattern.finditer(text):
            found = match.group(0)
            if label == "email address" and allowed_email(found):
                continue
            hits.append((label, found))
    return hits


def plugin_files():
    """Yield every file of the plugin folder, except compiled Python files."""
    for folder, dirs, names in os.walk(PLUGIN_DIR):
        dirs[:] = sorted(d for d in dirs if d != "__pycache__")
        for name in sorted(names):
            if not name.endswith(".pyc"):
                yield os.path.join(folder, name)


class FileCase(unittest.TestCase):
    def read_bytes(self, path):
        self.assertTrue(os.path.isfile(path), rel(path) + " is missing")
        with open(path, "rb") as handle:
            return handle.read()

    def read_text(self, path):
        data = self.read_bytes(path)
        try:
            return data.decode("utf-8")
        except UnicodeDecodeError:
            self.fail(rel(path) + " is not valid UTF-8")

    def read_json(self, path):
        try:
            return json.loads(self.read_text(path), object_pairs_hook=OrderedDict)
        except ValueError as error:
            self.fail(rel(path) + " is not valid JSON: " + str(error))


class ManifestTests(FileCase):
    def test_plugin_json_fields(self):
        self.assertEqual(plugin_problems(self.read_json(PLUGIN_JSON)), [])

    def test_marketplace_entry(self):
        plugin = self.read_json(PLUGIN_JSON)
        market = self.read_json(MARKETPLACE_JSON)
        entries = [e for e in market["plugins"] if e.get("name") == PLUGIN_NAME]
        self.assertEqual(len(entries), 1, "need exactly one plain-prose entry")
        entry = entries[0]
        self.assertEqual(entry.get("source"), "./plugins/" + PLUGIN_NAME)
        self.assertEqual(entry.get("version"), plugin.get("version"))
        self.assertEqual(entry.get("description"), plugin.get("description"))
        self.assertEqual(list(entry.keys()), MARKET_KEYS)

    def test_marketplace_keeps_other_entries(self):
        market = self.read_json(MARKETPLACE_JSON)
        names = [entry.get("name") for entry in market["plugins"]]
        self.assertEqual(tuple(names[:len(OTHER_PLUGINS)]), OTHER_PLUGINS)


GOOD_PLUGIN = OrderedDict([
    ("name", "plain-prose"),
    ("version", "0.1.0"),
    ("description", "A made-up description of a made-up plugin."),
    ("author", {"name": "A Writer", "url": "https://example.org/writer"}),
    ("homepage", "https://example.org/home"),
    ("repository", "https://example.org/repo"),
    ("license", "MIT"),
    ("keywords", ["writing", "style"]),
])


def plugin_variant(drop=(), **changes):
    """Return a copy of GOOD_PLUGIN with some keys dropped, set or added."""
    data = OrderedDict(GOOD_PLUGIN)
    for key in drop:
        del data[key]
    for key, value in changes.items():
        data[key] = value
    return data


class PluginFieldCheckerTests(unittest.TestCase):
    def test_made_up_plugin_passes(self):
        self.assertEqual(plugin_problems(GOOD_PLUGIN), [])

    def test_stray_key_is_found(self):
        for key in ("skills", "commands"):
            with self.subTest(key=key):
                problems = plugin_problems(plugin_variant(**{key: "./x"}))
                self.assertEqual(len(problems), 1)
                self.assertIn("keys are", problems[0])

    def test_changed_key_order_is_found(self):
        data = OrderedDict(reversed(list(GOOD_PLUGIN.items())))
        self.assertIn("keys are", plugin_problems(data)[0])

    def test_missing_field_is_found(self):
        for key in PLUGIN_KEYS:
            with self.subTest(key=key):
                self.assertTrue(plugin_problems(plugin_variant(drop=(key,))))

    def test_wrong_name_is_found(self):
        self.assertEqual(plugin_problems(plugin_variant(name="other")),
                         ["name is not plain-prose"])

    def test_bad_version_is_found(self):
        for version in ("1.0", "v1.0.0", "", 1):
            with self.subTest(version=version):
                self.assertTrue(plugin_problems(plugin_variant(version=version)))

    def test_bad_description_is_found(self):
        for description in ("", "   ", " ".join(["word"] * 26), 7):
            with self.subTest(description=description):
                self.assertTrue(plugin_problems(plugin_variant(description=description)))
        self.assertEqual(plugin_problems(plugin_variant(description=" ".join(["word"] * 25))), [])

    def test_bad_author_is_found(self):
        for author in ("A Writer", {"name": "A Writer"}, {"url": "https://example.org/w"}):
            with self.subTest(author=author):
                self.assertTrue(plugin_problems(plugin_variant(author=author)))

    def test_empty_keywords_are_found(self):
        self.assertTrue(plugin_problems(plugin_variant(keywords=[])))


class GitattributesTests(FileCase):
    def test_notes_are_not_converted(self):
        lines = self.read_text(GITATTRIBUTES).splitlines()
        self.assertIn("references/research-notes/*.md -text", lines)


class NoteTests(FileCase):
    def note_path(self, name):
        return os.path.join(NOTES_DIR, name + ".md")

    def test_hash_table_names_the_five_notes(self):
        self.assertEqual(tuple(sorted(NOTE_HASHES)), tuple(sorted(NOTE_NAMES)))

    def test_notes_match_their_pinned_hash(self):
        for name in NOTE_NAMES:
            with self.subTest(note=name):
                data = self.read_bytes(self.note_path(name))
                self.assertTrue(data.strip(), name + ".md is empty")
                self.assertEqual(
                    hashlib.sha256(data).hexdigest(), NOTE_HASHES[name],
                    name + ".md changed. Update its pinned hash only on purpose.")

    def test_every_table_key_has_a_source_line(self):
        for name in NOTE_NAMES:
            with self.subTest(note=name):
                facts = analyze_note(self.read_text(self.note_path(name)))
                self.assertEqual(facts["sections"], 1,
                                 "need one section titled Pages opened or Files read")
                self.assertTrue(facts["defined"], "the source list is empty")
                self.assertEqual(facts["repeated"], [], "a key has two lines")
                self.assertTrue(facts["table_keys"], "no table row uses a key")
                undefined = sorted(facts["table_keys"] - set(facts["defined"]),
                                   key=lambda key: int(key[1:]))
                self.assertEqual(undefined, [], "table keys with no source line")

    def test_every_source_line_has_its_link(self):
        for name in NOTE_NAMES:
            with self.subTest(note=name):
                facts = analyze_note(self.read_text(self.note_path(name)))
                form = link_form(name)
                bare = [key for key, line in facts["defined"].items()
                        if not has_link(line, form)]
                self.assertEqual(bare, [], "source lines with no " + form)


MADE_UP_NOTE = "\n".join([
    "# Made-up note",
    "",
    "## 1. Table",
    "",
    "| ID | Item | Source key |",
    "|---|---|---|",
    "| S01 | rule id | S1, S2 |",
    "| S02 | rule id | S2 |",
    "",
    "## 2. Pages opened",
    "",
    "- S1 https://example.org/one (made-up page)",
    "- S2 https://example.org/two (made-up page)",
    "",
    "## 3. License",
    "",
    "| Source | License |",
    "|---|---|",
    "| S2 | MIT |",
])


class SourceKeyCheckerTests(unittest.TestCase):
    def test_made_up_note_passes(self):
        facts = analyze_note(MADE_UP_NOTE)
        self.assertEqual(facts["sections"], 1)
        self.assertEqual(list(facts["defined"]), ["S1", "S2"])
        self.assertEqual(facts["repeated"], [])
        self.assertEqual(facts["table_keys"], {"S1", "S2"})
        self.assertTrue(all(has_link(l, "url") for l in facts["defined"].values()))

    def test_leading_zero_ids_are_skipped(self):
        self.assertNotIn("S01", analyze_note(MADE_UP_NOTE)["table_keys"])

    def test_undefined_key_in_a_table_is_found(self):
        facts = analyze_note(MADE_UP_NOTE.replace("S1, S2", "S1, S7"))
        self.assertEqual(facts["table_keys"] - set(facts["defined"]), {"S7"})

    def test_undefined_key_in_a_table_after_the_list_is_found(self):
        facts = analyze_note(MADE_UP_NOTE.replace("| S2 | MIT |", "| S9 | MIT |"))
        self.assertEqual(facts["table_keys"] - set(facts["defined"]), {"S9"})

    def test_undefined_key_in_a_table_inside_the_list_is_found(self):
        text = MADE_UP_NOTE.replace("\n\n## 3. License",
                                    "\n| S8 | stray row |\n\n## 3. License")
        facts = analyze_note(text)
        self.assertEqual(facts["table_keys"] - set(facts["defined"]), {"S8"})

    def test_dropped_source_line_is_found(self):
        text = MADE_UP_NOTE.replace("- S2 https://example.org/two (made-up page)\n", "")
        facts = analyze_note(text)
        self.assertEqual(facts["table_keys"] - set(facts["defined"]), {"S2"})

    def test_repeated_key_is_found(self):
        extra = "- S2 https://example.org/two\n\n## 3. License"
        text = MADE_UP_NOTE.replace("## 3. License", extra)
        self.assertEqual(analyze_note(text)["repeated"], ["S2"])

    def test_files_read_title_is_accepted(self):
        facts = analyze_note(MADE_UP_NOTE.replace("Pages opened", "Files read"))
        self.assertEqual(facts["sections"], 1)
        self.assertEqual(list(facts["defined"]), ["S1", "S2"])

    def test_missing_source_section_is_found(self):
        facts = analyze_note(MADE_UP_NOTE.replace("Pages opened", "Sources"))
        self.assertEqual(facts["sections"], 0)

    def test_note_without_table_keys_is_found(self):
        text = "## 1. Pages opened\n\n- S1 https://example.org/x\n"
        self.assertEqual(analyze_note(text)["table_keys"], set())


class LinkFormTests(unittest.TestCase):
    def test_url_form_accepts_http_and_https(self):
        self.assertTrue(has_link("- S1 https://example.org/one (page)", "url"))
        self.assertTrue(has_link("- S1 http://example.org/one (page)", "url"))

    def test_url_form_rejects_a_path_only_line(self):
        self.assertFalse(has_link("- S1 `README.md` (file)", "url"))
        self.assertFalse(has_link("- S1 `docs/two.md` (file)", "url"))

    def test_url_form_rejects_a_line_without_link(self):
        self.assertFalse(has_link("- S1 a page", "url"))

    def test_path_form_accepts_a_slash_or_a_dot(self):
        self.assertTrue(has_link("- S1 `docs/two` (file)", "path"))
        self.assertTrue(has_link("- S1 `README.md` (file)", "path"))

    def test_path_form_rejects_a_url_only_line(self):
        self.assertFalse(has_link("- S1 https://example.org/one (page)", "path"))

    def test_path_form_rejects_a_span_without_slash_or_dot(self):
        self.assertFalse(has_link("- S1 `README` (file)", "path"))

    def test_only_authors_uses_the_path_form(self):
        self.assertEqual(link_form("authors"), "path")
        for name in ("corpus", "wikipedia", "guides", "craft"):
            self.assertEqual(link_form(name), "url")


class PrivacyTests(FileCase):
    def test_no_private_text_in_the_plugin_folder(self):
        paths = list(plugin_files())
        shown = set(os.path.relpath(p, PLUGIN_DIR) for p in paths)
        for expected in ("tests/test_manifest.py",
                         os.path.join("references", "research-notes", "corpus.md")):
            self.assertIn(expected, shown, "the scan does not reach " + expected)
        for path in paths:
            with self.subTest(file=rel(path)):
                self.assertEqual(private_hits(self.read_text(path)), [])

    def test_patterns_find_made_up_private_text(self):
        slash = "/"  # Built from parts so this file does not match its own scan.
        samples = (
            ("home or project path", slash + "home" + slash + "someone/work"),
            ("home or project path", "see " + slash + "hpc" + slash + "projects/x"),
            ("home or project path", "`" + slash + "scratch" + slash + "x`"),
            ("home or project path", slash + "Users" + slash + "someone"),
            ("home or project path", "C:" + chr(92) + "Users" + chr(92) + "someone"),
            ("home or project path", "open " + slash + "mnt" + slash + "data/x.csv"),
            ("home or project path", "(" + slash + "gpfs" + slash + "lab/x)"),
            ("home or project path", "at " + slash + "projects" + slash + "lab/x"),
            ("home or project path", "\"" + slash + "sc" + slash + "lab/x\""),
            ("email address", "someone" + "@" + "university.edu"),
            ("email address", "someone" + "@" + "mail.example.org"),
            ("email address", "ab" + "@" + "cd.ef"),
            ("email address", "jane" + "@" + "t.co"),
            ("email address", "someone" + "@" + "g.co"),
        )
        for label, text in samples:
            with self.subTest(text=text):
                self.assertEqual([hit[0] for hit in private_hits(text)], [label])

    def test_patterns_stay_quiet_on_allowed_text(self):
        slash = "/"  # Built from parts so this file does not match its own scan.
        for text in (
            "Co-Authored-By: Claude <noreply@anthropic.com>",
            "Write to someone@example.org or someone@example.com today.",
            "Write to someone@example.net today.",
            "Masker fixtures a@b.c and a@b.1 and x@y.12 and a@b.co",
            "https://example.org" + slash + "home" + slash + "page",
            "a relative path docs" + slash + "scratch" + slash + "x",
            "a relative path docs/data/x.csv",
            "plain text with the word home and the word hpc",
        ):
            with self.subTest(text=text):
                self.assertEqual(private_hits(text), [])


if __name__ == "__main__":
    unittest.main()
