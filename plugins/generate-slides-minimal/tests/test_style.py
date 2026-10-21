"""Tests for the style loader in scripts/style.py and for the YAML data it reads."""
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import yaml

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import design_color as dc  # noqa: E402
import style  # noqa: E402

PROJECT_FILE = "slide-style-minimal.yaml"

# Every key of the lint block that the linter of Task 5 reads.
LINT_KEYS = [
    "title_words", "words_per_slide", "take_home_words", "bullets_per_list",
    "lists_per_slide", "objects_per_slide", "lines_per_paragraph", "body_font",
    "title_font", "source_font", "fonts_per_slide", "text_contrast",
    "mark_contrast", "inside_slide", "margin", "aspect", "picture_ppi",
    "alt_text", "slide_count", "take_homes", "roadmap_sections", "notes",
    "title_unique", "red_green",
]

# The look values of the brief. Each row is a path in the loaded style and its value.
LOOK_VALUES = [
    ("typography.body_font", "Avenir Light"),
    ("typography.code_font", "PT Mono"),
    ("typography.title_size", 28),
    ("typography.body_size", 24),
    ("typography.callout_size", 20),
    ("typography.source_size", 12),
    ("typography.big_number_size", 96),
    ("typography.label_size", 24),
    ("layout.slide_width", 13.333),
    ("layout.slide_height", 7.5),
    ("layout.margin", 0.8),
    ("layout.title_top", 0.3),
    ("layout.title_height", 0.95),
    ("layout.content_top", 1.5),
    ("layout.content_bottom", 6.7),
    ("layout.evidence_width", 7.7),
    ("layout.evidence_height", 5.2),
    ("layout.callout_left", 8.95),
    ("layout.rule_width", 0.03),
    ("style.use_bold", False),
    ("colors.context", "#9CA3AF"),
]

# The lint block of the peers profile, as the brief gives it. Every profile
# starts from these numbers.
PEERS_LINT = {
    "title_words": {"min": 6, "max": 20, "tier": "T3"},
    "words_per_slide": {"warn": 25, "error": 40, "tier": "T3"},
    "bullets_per_list": {"max": 4, "tier": "T2"},
    "lists_per_slide": {"max": 1, "tier": "T2"},
    "objects_per_slide": {"max": 6, "tier": "T2"},
    "lines_per_paragraph": {"max": 2, "tier": "T2"},
    "body_font": {"error_below": 18, "warn_below": 24, "secondary_warn_below": 20, "tier": "T2"},
    "take_home_words": {"max_claim": 15, "max_baseline": 15, "tier": "T3"},
    "title_font": {"warn_below": 28, "tier": "T2"},
    "source_font": {"warn_below": 12, "tier": "T3"},
    "fonts_per_slide": {"families": 2, "sizes": 3, "tier": "T2"},
    "text_contrast": {"error_below": 3.0, "warn_below": 4.5, "large_text_pt": 18, "tier": "T1"},
    "mark_contrast": {"warn_below": 3.0, "tier": "T1"},
    "inside_slide": {"tier": "T3"},
    "margin": {"warn_below_in": 0.5, "tier": "T3"},
    "aspect": {"ratio": 1.7778, "tolerance": 0.01, "tier": "T2"},
    "picture_ppi": {"warn_below": 144, "tier": "T3"},
    "alt_text": {"tier": "T2"},
    "slide_count": {"per_minute": 1.0, "tier": "T2"},
    "take_homes": {"max": 3, "tier": "T2"},
    "roadmap_sections": {"max": 5, "tier": "T2"},
    "notes": {"redundancy_above": 0.8, "tier": "T3"},
    "title_unique": {"tier": "T2"},
    "red_green": {"tier": "T2"},
}

# The only numbers that a profile may change from the peers profile, with the
# values of the brief. A path starts at the top of the loaded style.
PROFILE_OVERRIDES = {
    "lab-meeting": {
        "lint.words_per_slide.warn": 40,
        "lint.words_per_slide.error": 60,
        "lint.body_font.warn_below": 18,
        "lint.body_font.secondary_warn_below": 18,
        "lint.slide_count.per_minute": 1.5,
    },
    "general": {
        "lint.words_per_slide.warn": 15,
        "lint.words_per_slide.error": 25,
        "lint.body_font.warn_below": 28,
        "lint.body_font.secondary_warn_below": 24,
        "lint.objects_per_slide.max": 4,
    },
}


# The numbers outside the lint block that a profile may change. The general profile raises the three sizes
# that the helpers read for body text, call-outs and the label of a big number, so that a deck built from it
# meets its font floors (28 pt for body text and labels, 24 pt for secondary text).
TYPOGRAPHY_OVERRIDES = {
    "general": {
        "typography.body_size": 28,
        "typography.callout_size": 24,
        "typography.label_size": 28,
    },
}


def lookup(data, path):
    """Return the value at a dotted path such as "lint.body_font.warn_below"."""
    for part in path.split("."):
        data = data[part]
    return data


def flatten(data, prefix=""):
    """Return {dotted path: (type name, value)} for every leaf of a nested dict."""
    leaves = {}
    for key, value in data.items():
        path = prefix + "." + key if prefix else key
        if isinstance(value, dict):
            leaves.update(flatten(value, path))
        else:
            leaves[path] = (type(value).__name__, value)
    return leaves


def write_yaml(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, default_flow_style=False), encoding="utf-8")


class TempDirCase(unittest.TestCase):
    def make_dir(self):
        holder = tempfile.TemporaryDirectory()
        self.addCleanup(holder.cleanup)
        return Path(holder.name)


class DataFolder(unittest.TestCase):
    def test_the_data_folder_is_styles_next_to_the_module(self):
        self.assertEqual(style.STYLES_DIR, SCRIPTS_DIR / "styles")
        self.assertTrue(style.STYLES_DIR.is_dir())

    def test_no_folder_shares_the_name_of_the_module(self):
        self.assertFalse((SCRIPTS_DIR / "style").exists())

    def test_every_profile_and_theme_has_a_file(self):
        self.assertTrue((style.STYLES_DIR / "default.yaml").is_file())
        for name in style.PROFILES:
            self.assertTrue((style.STYLES_DIR / "profiles" / (name + ".yaml")).is_file(), name)
        for name in style.THEMES:
            self.assertTrue((style.STYLES_DIR / "themes" / (name + ".yaml")).is_file(), name)

    def test_the_names_of_the_brief(self):
        self.assertEqual(style.PROFILES, ("peers", "lab-meeting", "general"))
        self.assertEqual(style.THEMES, ("light", "dark"))
        self.assertEqual(
            style.TOP_LEVEL_KEYS, ("typography", "colors", "layout", "style", "lint")
        )

    def test_each_theme_file_names_its_palette_in_a_comment_at_the_top(self):
        for name in style.THEMES:
            with self.subTest(theme=name):
                text = (style.STYLES_DIR / "themes" / (name + ".yaml")).read_text(encoding="utf-8")
                head = text.splitlines()[:6]
                self.assertTrue(head[0].startswith("#"), "the first line must be a comment")
                comment = " ".join(line for line in head if line.startswith("#"))
                self.assertIn("Biohub Purple", comment)
                self.assertIn("spec section 5", comment)


class MergeOrder(TempDirCase):
    def make_styles(self, layers):
        """Write a styles folder. `layers` maps default, theme, profile to a dict."""
        root = self.make_dir()
        if "default" in layers:
            write_yaml(root / "default.yaml", layers["default"])
        if "theme" in layers:
            write_yaml(root / "themes" / "light.yaml", layers["theme"])
        if "profile" in layers:
            write_yaml(root / "profiles" / "peers.yaml", layers["profile"])
        return root

    def load_with(self, root, project_dir=None):
        with mock.patch.object(style, "STYLES_DIR", root):
            return style.load_style("peers", "light", project_dir)

    def layer(self, value):
        return {"colors": {"order": value}}

    def test_the_theme_overrides_the_default(self):
        root = self.make_styles({"default": self.layer("default"), "theme": self.layer("theme"),
                                 "profile": {}})
        self.assertEqual(self.load_with(root)["colors"]["order"], "theme")

    def test_the_profile_overrides_the_theme(self):
        root = self.make_styles({"default": self.layer("default"), "theme": self.layer("theme"),
                                 "profile": self.layer("profile")})
        self.assertEqual(self.load_with(root)["colors"]["order"], "profile")

    def test_the_project_file_overrides_the_profile(self):
        root = self.make_styles({"default": self.layer("default"), "theme": self.layer("theme"),
                                 "profile": self.layer("profile")})
        project = self.make_dir()
        write_yaml(project / PROJECT_FILE, self.layer("project"))
        self.assertEqual(self.load_with(root, project)["colors"]["order"], "project")

    def test_a_key_from_each_layer_survives(self):
        root = self.make_styles({
            "default": {"colors": {"a": 1}},
            "theme": {"colors": {"b": 2}},
            "profile": {"layout": {"c": 3}},
        })
        project = self.make_dir()
        write_yaml(project / PROJECT_FILE, {"typography": {"d": 4}})
        result = self.load_with(root, project)
        self.assertEqual(result["colors"], {"a": 1, "b": 2})
        self.assertEqual(result["layout"], {"c": 3})
        self.assertEqual(result["typography"], {"d": 4})

    def test_a_profile_file_with_only_comments_adds_nothing(self):
        root = self.make_styles({"default": {"colors": {"a": 1}}, "theme": {"colors": {"b": 2}}})
        profile_file = root / "profiles" / "peers.yaml"
        profile_file.parent.mkdir(parents=True, exist_ok=True)
        profile_file.write_text("# The peers profile equals the baseline.\n", encoding="utf-8")
        self.assertEqual(self.load_with(root), {"colors": {"a": 1, "b": 2}})

    def test_a_profile_changes_one_number_and_inherits_the_rest(self):
        root = self.make_styles({
            "default": {"lint": {"rule": {"warn": 1, "error": 2, "tier": "T2"}}},
            "theme": {},
            "profile": {"lint": {"rule": {"warn": 10}}},
        })
        self.assertEqual(
            self.load_with(root)["lint"]["rule"], {"warn": 10, "error": 2, "tier": "T2"}
        )


class ProjectFile(TempDirCase):
    def test_a_project_file_overrides_the_theme_which_overrides_the_default(self):
        default = yaml.safe_load((style.STYLES_DIR / "default.yaml").read_text(encoding="utf-8"))
        dark_theme = yaml.safe_load(
            (style.STYLES_DIR / "themes" / "dark.yaml").read_text(encoding="utf-8")
        )
        self.assertNotEqual(default["colors"]["context"], dark_theme["colors"]["context"])
        project = self.make_dir()
        write_yaml(project / PROJECT_FILE, {"colors": {"background": "#ABCDEF"}})

        plain = style.load_style(theme="dark")
        with_project = style.load_style(theme="dark", project_dir=project)

        self.assertEqual(plain["colors"]["context"], dark_theme["colors"]["context"])
        self.assertEqual(plain["colors"]["background"], dark_theme["colors"]["background"])
        self.assertEqual(with_project["colors"]["background"], "#ABCDEF")
        self.assertEqual(with_project["colors"]["text"], dark_theme["colors"]["text"])

    def test_dicts_merge_deeply(self):
        project = self.make_dir()
        write_yaml(project / PROJECT_FILE, {"lint": {"words_per_slide": {"warn": 30}}})
        base = style.load_style()["lint"]["words_per_slide"]
        merged = style.load_style(project_dir=project)["lint"]["words_per_slide"]
        self.assertEqual(merged["warn"], 30)
        self.assertEqual(merged["error"], base["error"])
        self.assertEqual(merged["tier"], base["tier"])

    def test_lists_replace(self):
        project = self.make_dir()
        write_yaml(project / PROJECT_FILE, {"colors": {"data_palette": ["#111111", "#222222"]}})
        result = style.load_style(project_dir=project)
        self.assertEqual(result["colors"]["data_palette"], ["#111111", "#222222"])

    def test_the_file_is_found_in_the_project_dir(self):
        project = self.make_dir()
        write_yaml(project / PROJECT_FILE, {"layout": {"margin": 1.1}})
        self.assertEqual(style.load_style(project_dir=project)["layout"]["margin"], 1.1)

    def test_the_file_is_found_in_docs(self):
        project = self.make_dir()
        write_yaml(project / "docs" / PROJECT_FILE, {"layout": {"margin": 1.2}})
        self.assertEqual(style.load_style(project_dir=project)["layout"]["margin"], 1.2)

    def test_the_file_is_found_in_dot_claude(self):
        project = self.make_dir()
        write_yaml(project / ".claude" / PROJECT_FILE, {"layout": {"margin": 1.3}})
        self.assertEqual(style.load_style(project_dir=project)["layout"]["margin"], 1.3)

    def test_the_first_file_found_wins_and_the_others_are_ignored(self):
        project = self.make_dir()
        write_yaml(project / PROJECT_FILE, {"layout": {"margin": 1.1}})
        write_yaml(project / "docs" / PROJECT_FILE, {"layout": {"margin": 1.2, "title_top": 9.9}})
        write_yaml(project / ".claude" / PROJECT_FILE, {"layout": {"margin": 1.3}})
        result = style.load_style(project_dir=project)
        self.assertEqual(result["layout"]["margin"], 1.1)
        self.assertNotEqual(result["layout"]["title_top"], 9.9)

    def test_docs_comes_before_dot_claude(self):
        project = self.make_dir()
        write_yaml(project / "docs" / PROJECT_FILE, {"layout": {"margin": 1.2}})
        write_yaml(project / ".claude" / PROJECT_FILE, {"layout": {"margin": 1.3}})
        self.assertEqual(style.load_style(project_dir=project)["layout"]["margin"], 1.2)

    def test_a_project_dir_without_the_file_changes_nothing(self):
        project = self.make_dir()
        self.assertEqual(style.load_style(project_dir=project), style.load_style())

    def test_project_dir_may_be_a_string(self):
        project = self.make_dir()
        write_yaml(project / PROJECT_FILE, {"layout": {"margin": 1.4}})
        self.assertEqual(style.load_style(project_dir=str(project))["layout"]["margin"], 1.4)

    def test_an_empty_project_file_changes_nothing(self):
        project = self.make_dir()
        (project / PROJECT_FILE).write_text("", encoding="utf-8")
        self.assertEqual(style.load_style(project_dir=project), style.load_style())

    def test_a_project_file_that_is_not_a_mapping_raises_value_error(self):
        for text in ("- a\n- b\n", "- colors\n", "42\n", "just text\n"):
            with self.subTest(text=text):
                project = self.make_dir()
                (project / PROJECT_FILE).write_text(text, encoding="utf-8")
                with self.assertRaises(ValueError):
                    style.load_style(project_dir=project)

    def test_a_project_file_with_a_yaml_syntax_error_raises_value_error_with_its_path(self):
        project = self.make_dir()
        (project / PROJECT_FILE).write_text("colors: [unclosed\n", encoding="utf-8")
        with self.assertRaises(ValueError) as caught:
            style.load_style(project_dir=project)
        self.assertIn(PROJECT_FILE, str(caught.exception))

    def test_a_key_with_no_value_raises_value_error_with_the_file_and_the_key_path(self):
        cases = [
            ("colors:\n", "colors"),
            ("lint:\n  words_per_slide:\n", "lint.words_per_slide"),
            ("lint:\n  words_per_slide:\n    warn:\n", "lint.words_per_slide.warn"),
        ]
        for text, key_path in cases:
            with self.subTest(key_path=key_path):
                project = self.make_dir()
                (project / PROJECT_FILE).write_text(text, encoding="utf-8")
                with self.assertRaises(ValueError) as caught:
                    style.load_style(project_dir=project)
                message = str(caught.exception)
                self.assertIn(PROJECT_FILE, message)
                self.assertIn(key_path, message)

    def test_a_value_that_is_not_a_mapping_cannot_replace_a_mapping(self):
        cases = [
            ("colors: red\n", "colors"),
            ("colors: [red, blue]\n", "colors"),
            ("lint: {words_per_slide: 30}\n", "lint.words_per_slide"),
            ("lint: {body_font: {warn_below: 20}, notes: 0.5}\n", "lint.notes"),
        ]
        for text, key_path in cases:
            with self.subTest(text=text):
                project = self.make_dir()
                (project / PROJECT_FILE).write_text(text, encoding="utf-8")
                with self.assertRaises(ValueError) as caught:
                    style.load_style(project_dir=project)
                message = str(caught.exception)
                self.assertIn(PROJECT_FILE, message)
                self.assertIn(key_path, message)

    def test_a_scalar_may_still_replace_a_scalar_and_a_list_a_list(self):
        project = self.make_dir()
        write_yaml(project / PROJECT_FILE, {
            "lint": {"words_per_slide": {"warn": 31}},
            "colors": {"data_palette": ["#111111"]},
        })
        result = style.load_style(project_dir=project)
        self.assertEqual(result["lint"]["words_per_slide"]["warn"], 31)
        self.assertEqual(result["colors"]["data_palette"], ["#111111"])

    def test_a_project_file_that_is_not_utf8_raises_value_error_with_its_path(self):
        project = self.make_dir()
        (project / PROJECT_FILE).write_bytes(b"colors:\n  background: \xff\xfe\n")
        with self.assertRaises(ValueError) as caught:
            style.load_style(project_dir=project)
        self.assertIn(PROJECT_FILE, str(caught.exception))

    def test_a_project_file_that_cannot_be_read_raises_value_error_with_its_path(self):
        project = self.make_dir()
        path = project / PROJECT_FILE
        write_yaml(path, {"layout": {"margin": 1.1}})
        os.chmod(str(path), 0)
        self.addCleanup(os.chmod, str(path), 0o600)
        if os.access(str(path), os.R_OK):
            self.skipTest("this user can read a file with mode 0, for example root")
        with self.assertRaises(ValueError) as caught:
            style.load_style(project_dir=project)
        self.assertIn(PROJECT_FILE, str(caught.exception))

    def test_a_project_dir_that_does_not_exist_raises_value_error(self):
        missing = self.make_dir() / "no-such-folder"
        with self.assertRaises(ValueError) as caught:
            style.load_style(project_dir=missing)
        message = str(caught.exception)
        self.assertTrue(message.startswith("project directory not found:"), message)
        self.assertIn(str(missing), message)

    def test_a_project_dir_that_is_a_file_raises_value_error(self):
        some_file = self.make_dir() / "a-file.txt"
        some_file.write_text("x", encoding="utf-8")
        with self.assertRaises(ValueError) as caught:
            style.load_style(project_dir=some_file)
        self.assertIn("project directory not found", str(caught.exception))

    def test_no_project_dir_is_valid(self):
        self.assertEqual(style.load_style(project_dir=None), style.load_style())

    def test_the_result_does_not_share_data_between_calls(self):
        first = style.load_style()
        first["colors"]["data_palette"].append("#123456")
        first["lint"]["words_per_slide"]["warn"] = -1
        second = style.load_style()
        self.assertEqual(len(second["colors"]["data_palette"]), 8)
        self.assertNotEqual(second["lint"]["words_per_slide"]["warn"], -1)


class Errors(TempDirCase):
    def test_an_unknown_profile_raises_value_error_with_the_valid_names(self):
        with self.assertRaises(ValueError) as caught:
            style.load_style(profile="nope")
        message = str(caught.exception)
        self.assertIn("nope", message)
        for name in style.PROFILES:
            self.assertIn(name, message)

    def test_an_unknown_theme_raises_value_error_with_the_valid_names(self):
        with self.assertRaises(ValueError) as caught:
            style.load_style(theme="sepia")
        message = str(caught.exception)
        self.assertIn("sepia", message)
        for name in style.THEMES:
            self.assertIn(name, message)

    def test_a_name_with_a_path_part_is_unknown(self):
        with self.assertRaises(ValueError):
            style.load_style(profile="../default")
        with self.assertRaises(ValueError):
            style.load_style(theme="../default")

    def test_an_unknown_top_level_key_raises_value_error_with_the_valid_keys(self):
        project = self.make_dir()
        write_yaml(project / PROJECT_FILE, {"colours": {"background": "#FFFFFF"}})
        with self.assertRaises(ValueError) as caught:
            style.load_style(project_dir=project)
        message = str(caught.exception)
        self.assertIn("colours", message)
        for key in ("typography", "colors", "layout", "style", "lint"):
            self.assertIn(key, message)

    def test_an_unknown_top_level_key_in_a_data_file_raises_value_error(self):
        root = self.make_dir()
        write_yaml(root / "default.yaml", {"bogus": 1})
        write_yaml(root / "themes" / "light.yaml", {})
        write_yaml(root / "profiles" / "peers.yaml", {})
        with mock.patch.object(style, "STYLES_DIR", root):
            with self.assertRaises(ValueError) as caught:
                style.load_style()
        self.assertIn("bogus", str(caught.exception))


class Default(unittest.TestCase):
    def test_the_defaults_load_with_valid_top_level_keys_only(self):
        for profile in style.PROFILES:
            for theme in style.THEMES:
                with self.subTest(profile=profile, theme=theme):
                    result = style.load_style(profile, theme)
                    self.assertEqual(set(result), set(style.TOP_LEVEL_KEYS))

    def test_the_default_arguments_are_peers_and_light(self):
        self.assertEqual(style.load_style(), style.load_style("peers", "light"))

    def test_the_default_file_holds_the_typography_and_layout_keys(self):
        result = style.load_style()
        self.assertEqual(
            set(result["typography"]),
            {"body_font", "code_font", "title_size", "body_size", "callout_size",
             "source_size", "big_number_size", "label_size"},
        )
        self.assertEqual(
            set(result["layout"]),
            {"slide_width", "slide_height", "margin", "title_top", "title_height",
             "content_top", "content_bottom", "evidence_width", "evidence_height",
             "callout_left", "rule_width"},
        )
        self.assertIs(result["style"]["use_bold"], False)

    def test_the_data_palette_is_the_okabe_ito_list(self):
        self.assertEqual(style.load_style()["colors"]["data_palette"], dc.OKABE_ITO)

    def test_the_look_values_of_the_brief(self):
        result = style.load_style()
        for path, expected in LOOK_VALUES:
            with self.subTest(path=path):
                actual = lookup(result, path)
                self.assertEqual(actual, expected)
                self.assertIs(type(actual), type(expected))

    def test_the_peers_lint_numbers_of_the_brief(self):
        lint = style.load_style("peers")["lint"]
        self.assertEqual(set(lint), set(PEERS_LINT))
        for key, expected in PEERS_LINT.items():
            with self.subTest(key=key):
                self.assertEqual(flatten(lint[key]), flatten(expected))

    def test_the_peers_profile_adds_nothing_to_the_baseline_in_default_yaml(self):
        default = yaml.safe_load((style.STYLES_DIR / "default.yaml").read_text(encoding="utf-8"))
        self.assertEqual(style.load_style("peers")["lint"], default["lint"])


class Themes(unittest.TestCase):
    def colors(self, theme):
        return style.load_style(theme=theme)["colors"]

    def test_the_theme_holds_accent_and_accent_ink_and_no_accent_tint(self):
        for theme in style.THEMES:
            with self.subTest(theme=theme):
                colors = self.colors(theme)
                self.assertIn("accent", colors)
                self.assertIn("accent_ink", colors)
                self.assertNotIn("accent_tint", colors)

    def test_every_theme_color_is_valid_hex(self):
        for theme in style.THEMES:
            colors = self.colors(theme)
            for key in ("background", "text", "muted", "accent", "accent_ink", "context"):
                with self.subTest(theme=theme, key=key):
                    dc.parse_hex(colors[key])

    def test_the_data_palette_holds_eight_valid_hex_colors(self):
        for theme in style.THEMES:
            with self.subTest(theme=theme):
                palette = self.colors(theme)["data_palette"]
                self.assertEqual(len(palette), 8)
                for color in palette:
                    dc.parse_hex(color)

    def test_text_on_background_is_at_least_7_to_1(self):
        for theme in style.THEMES:
            with self.subTest(theme=theme):
                colors = self.colors(theme)
                self.assertGreaterEqual(dc.contrast_ratio(colors["text"], colors["background"]), 7.0)

    def test_muted_accent_and_accent_ink_on_background_are_at_least_4_5_to_1(self):
        for theme in style.THEMES:
            colors = self.colors(theme)
            for key in ("muted", "accent", "accent_ink"):
                with self.subTest(theme=theme, key=key):
                    ratio = dc.contrast_ratio(colors[key], colors["background"])
                    self.assertGreaterEqual(ratio, 4.5)

    def test_context_on_background_meets_the_floor_of_each_theme(self):
        floors = {"light": 2.5, "dark": 3.0}
        for theme in style.THEMES:
            with self.subTest(theme=theme):
                colors = self.colors(theme)
                ratio = dc.contrast_ratio(colors["context"], colors["background"])
                self.assertGreaterEqual(ratio, floors[theme])


class Profiles(unittest.TestCase):
    def lint(self, profile):
        return style.load_style(profile)["lint"]

    def test_the_lint_block_holds_every_key_the_linter_reads(self):
        for profile in style.PROFILES:
            with self.subTest(profile=profile):
                lint = self.lint(profile)
                for key in LINT_KEYS:
                    self.assertIn(key, lint)

    def test_every_lint_key_has_a_tier_of_t1_t2_or_t3(self):
        for profile in style.PROFILES:
            lint = self.lint(profile)
            for key in LINT_KEYS:
                with self.subTest(profile=profile, key=key):
                    self.assertIsInstance(lint[key], dict)
                    self.assertIn(lint[key]["tier"], ("T1", "T2", "T3"))

    def test_a_profile_differs_from_peers_only_in_the_numbers_it_may_change(self):
        peers = flatten(style.load_style("peers"))
        for profile, overrides in PROFILE_OVERRIDES.items():
            allowed = dict(overrides, **TYPOGRAPHY_OVERRIDES.get(profile, {}))
            other = flatten(style.load_style(profile))
            for path in sorted(set(peers) | set(other)):
                if path in allowed:
                    continue
                with self.subTest(profile=profile, path=path):
                    self.assertEqual(
                        other.get(path),
                        peers.get(path),
                        "{}: {} differs from peers and is not an allowed difference".format(
                            profile, path
                        ),
                    )

    def test_a_profile_sets_the_override_values_of_the_brief(self):
        peers = style.load_style("peers")
        for profile, overrides in PROFILE_OVERRIDES.items():
            overrides = dict(overrides, **TYPOGRAPHY_OVERRIDES.get(profile, {}))
            loaded = style.load_style(profile)
            for path, expected in overrides.items():
                with self.subTest(profile=profile, path=path):
                    actual = lookup(loaded, path)
                    self.assertEqual(actual, expected)
                    self.assertIs(type(actual), type(expected))
                    self.assertNotEqual(actual, lookup(peers, path))

    def test_only_the_general_profile_changes_the_typography(self):
        peers = style.load_style("peers")["typography"]
        for profile in style.PROFILES:
            with self.subTest(profile=profile):
                typography = style.load_style(profile)["typography"]
                changed = {key for key in peers if typography[key] != peers[key]}
                expected = {path.split(".")[1] for path in TYPOGRAPHY_OVERRIDES.get(profile, {})}
                self.assertEqual(changed, expected)

    def test_the_general_typography_meets_the_general_font_floors(self):
        loaded = style.load_style("general")
        self.assertEqual(loaded["typography"]["body_size"], loaded["lint"]["body_font"]["warn_below"])
        self.assertEqual(loaded["typography"]["callout_size"], loaded["lint"]["body_font"]["secondary_warn_below"])
        self.assertEqual(loaded["typography"]["label_size"], loaded["lint"]["body_font"]["warn_below"])

    def test_the_other_profiles_keep_the_default_sizes(self):
        for profile in ("peers", "lab-meeting"):
            typography = style.load_style(profile)["typography"]
            self.assertEqual((typography["body_size"], typography["callout_size"], typography["label_size"]),
                             (24, 20, 24))

    def test_words_per_slide_warn_orders_general_then_peers_then_lab_meeting(self):
        warn = {name: self.lint(name)["words_per_slide"]["warn"] for name in style.PROFILES}
        self.assertLess(warn["general"], warn["peers"])
        self.assertLess(warn["peers"], warn["lab-meeting"])

    def test_words_per_slide_error_is_above_warn_in_every_profile(self):
        for profile in style.PROFILES:
            with self.subTest(profile=profile):
                limits = self.lint(profile)["words_per_slide"]
                self.assertGreater(limits["error"], limits["warn"])

    def test_the_secondary_body_font_floor_is_at_most_the_main_floor(self):
        for profile in style.PROFILES:
            with self.subTest(profile=profile):
                body = self.lint(profile)["body_font"]
                self.assertLessEqual(body["secondary_warn_below"], body["warn_below"])

    def test_the_body_font_error_floor_is_at_most_the_warn_floor(self):
        for profile in style.PROFILES:
            with self.subTest(profile=profile):
                body = self.lint(profile)["body_font"]
                self.assertLessEqual(body["error_below"], body["warn_below"])


if __name__ == "__main__":
    unittest.main()
