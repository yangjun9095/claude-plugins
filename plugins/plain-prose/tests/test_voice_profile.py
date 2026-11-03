"""Tests for scripts/voice_profile.py. All text in this file is made up."""
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from collections import OrderedDict
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.join(os.path.dirname(HERE), "scripts")
sys.path.insert(0, SCRIPTS)

import prose_text as pt  # noqa: E402
import voice_profile as vp  # noqa: E402

SCRIPT = os.path.join(SCRIPTS, "voice_profile.py")
EM = "\u2014"

# The main sample has 31 sentences in 5 paragraphs and 294 words.
# Each comment below gives the hand count of one sentence: the number of words, then the number
# of characters of its words. A flag follows for a hedge word (H), a passive (P), a semicolon (S)
# or an em dash (D).
SAMPLE_PARAGRAPHS = [
    [
        "We counted the snails in the south bed " + EM + " on every wet morning.",  # 12 words, 48, D
        "The count was recorded in a small blue book.",  # 9, 35, P
        "Rain fell.",  # 2, 8
        "The numbers may reflect the weather more than the garden.",  # 10, 47, H
        "We noted the same pattern in the north bed.",  # 9, 34
        "Slugs seem to prefer the lettuce; snails seem to prefer the beans.",  # 12, 53, H, S
    ],
    [
        "Two children helped on Saturday.",  # 5, 27
        "They were given a pencil and a clean page each.",  # 10, 37, P
        "The younger child drew a snail with a long tail " + EM + " a bold guess.",  # 13, 48, D
        "We might keep that drawing.",  # 5, 22, H
        "The older child was bored and left early.",  # 8, 33, P
    ],
    [
        "Perhaps the birds ate some of the snails.",  # 8, 33, H
        "A thrush visited the bed twice that week.",  # 8, 33
        "We saw it crack one shell on the path.",  # 9, 29
        "That fact is known to every gardener.",  # 7, 30, P
        "Still, the loss was small; most snails survived the week.",  # 10, 45, S
    ],
    [
        "By Friday the beans looked healthy.",  # 6, 29
        "The lettuce, in contrast, looked ragged and thin.",  # 8, 39
        "This could mean that snails like beans less than lettuce.",  # 10, 47, H
        "It is also likely that the slugs matter more.",  # 9, 36, H
        "We will count the slugs next month.",  # 7, 28
        "The results suggest only a weak link between snails and the weather, and they appeared late "
        "in the season " + EM + " so we hold the claim loosely.",  # 25, 109, H (two hedge words), D
        "Rain returned.",  # 2, 12
        "Our notes are short and plain, and they were checked twice by a second reader.",  # 15, 62, P
    ],
    [
        "On the last day we weighed every leaf the snails had touched.",  # 12, 49
        "The total was lower than we had hoped.",  # 8, 30
        "A cold night arrived and the garden went quiet.",  # 9, 38
        "Nothing moved in the beds.",  # 5, 21
        "The notebook was left open on the shed table for the whole winter and the pages were soaked "
        "by the first heavy snow.",  # 23, 93, P (was left is no match, were soaked is)
        "We hope to start again in spring with a better plan and a drier book.",  # 15, 54
        "That is all.",  # 3, 9
    ],
]
SAMPLE_TEXT = "\n\n".join(" ".join(paragraph) for paragraph in SAMPLE_PARAGRAPHS)

# Hand tally of the main sample.
# Words 294 and sentences 31. The words hold 1218 characters, so the mean length is 1218 / 294 = 4.143.
# 29 sentences hold 3 words or more, with 290 words in all. The mean is 290 / 29 = 10.0.
# Sorted, the lengths are 3, 5 x3, 6, 7 x2, 8 x5, 9 x5, 10 x4, 12 x3, 13, 15 x2, 23, 25.
# The value p10 is at rank ceil(2.9) = 3, which is 5.
# The value p50 is at rank ceil(14.5) = 15, which is 9.
# The value p90 is at rank ceil(26.1) = 27, which is 15.
# The first word is We in 6 of 31 sentences, so 6 / 31 = 0.194.
# 7 sentences hold a hedge word: 700 / 31 = 22.581. The sentence with two hedge words counts once.
# 6 sentences hold a passive: 600 / 31 = 19.355.
# The text holds 3 em dashes: 3000 / 294 = 10.204. It holds 2 semicolons: 2000 / 294 = 6.803.
SAMPLE_PROFILE = {
    "version": 1,
    "samples": 1,
    "words": 294,
    "sentences": 31,
    "sentence_length": {"mean": 10.0, "p10": 5, "p50": 9, "p90": 15},
    "we_share": 0.194,
    "hedge_rate": 22.581,
    "passive_rate": 19.355,
    "em_dash_per_1000": 10.204,
    "semicolon_per_1000": 6.803,
    "avg_word_length": 4.143,
    # The 8 openers "the", 6 "we", then three pairs, then single openers in the order of the word.
    "top_openers": [["the", 8], ["we", 6], ["a", 2], ["rain", 2], ["that", 2],
                    ["by", 1], ["it", 1], ["nothing", 1], ["on", 1], ["our", 1]],
}

# Neutral text. 20 sentences of 10 words in 4 paragraphs: 200 words and 43 characters of words in
# each sentence. No sentence holds a hedge word, a form of be or the word we.
PAD_SENTENCE = "Grey stones lined the old river path near the bridge."
PAD_TEXT = "\n\n".join([" ".join([PAD_SENTENCE] * 5)] * 4)
NEUTRAL = "grey stone path river bridge lamp field gate wall hill road cart".split()


def plain_sentences(lengths):
    """Return a text with one neutral sentence of each given length, in order."""
    found = []
    for k, size in enumerate(lengths):
        found.append(" ".join(NEUTRAL[(k + i) % len(NEUTRAL)] for i in range(size)).capitalize() + ".")
    return " ".join(found)


def profile_of(extra, fmt="text"):
    """Return the profile of the neutral text followed by the extra text."""
    return vp.build_profile([(PAD_TEXT + "\n\n" + extra, fmt)])


def sample_profile():
    return vp.build_profile([(SAMPLE_TEXT, "text")])


def tokens_of(text):
    return re.findall(r"[^\W\d_]+", text.lower())


def four_grams(tokens):
    return set(tuple(tokens[i:i + 4]) for i in range(len(tokens) - 3))


class MainSampleTests(unittest.TestCase):
    def test_the_sample_has_the_size_that_the_hand_count_assumes(self):
        self.assertEqual(sum(len(p) for p in SAMPLE_PARAGRAPHS), 31)
        self.assertEqual(pt.word_count(SAMPLE_TEXT), 294)

    def test_every_value_of_the_sample(self):
        self.assertEqual(sample_profile(), SAMPLE_PROFILE)

    def test_every_key_is_there(self):
        self.assertEqual(sorted(sample_profile()), sorted(vp.REQUIRED_KEYS))
        self.assertEqual(sorted(sample_profile()["sentence_length"]), ["mean", "p10", "p50", "p90"])

    def test_numbers_are_ints_or_floats_of_three_places(self):
        profile = sample_profile()
        for key in vp.COUNT_KEYS + ("version",):
            self.assertIs(type(profile[key]), int, key)
        floats = [(key, profile[key]) for key in vp.RATE_KEYS] + [("mean", profile["sentence_length"]["mean"])]
        for key, value in floats:
            self.assertIs(type(value), float, key)
            self.assertEqual(value, round(value, 3), key)
        for key in ("p10", "p50", "p90"):
            self.assertIs(type(profile["sentence_length"][key]), int, key)

    def test_the_json_has_sorted_keys_and_ends_with_a_line_feed(self):
        text = vp.profile_json(sample_profile())
        self.assertTrue(text.endswith("}\n"))
        parsed = json.loads(text, object_pairs_hook=OrderedDict)
        self.assertEqual(list(parsed), sorted(parsed))
        self.assertEqual(list(parsed["sentence_length"]), sorted(parsed["sentence_length"]))
        self.assertEqual(json.loads(text), SAMPLE_PROFILE)

    def test_a_crlf_file_gives_the_same_profile(self):
        crlf = SAMPLE_TEXT.replace("\n", "\r\n")
        self.assertEqual(vp.build_profile([(crlf, "text")]), SAMPLE_PROFILE)

    def test_a_sentence_with_no_word_is_no_sentence(self):
        # Arabic-Indic digits are a sentence for split_sentences and hold no word for words.
        digits = "\u0663\u0663\u0663"
        self.assertEqual(pt.split_sentences(digits), [(0, 3)])
        self.assertEqual(pt.words(digits), [])
        self.assertEqual(vp.build_profile([(SAMPLE_TEXT + "\n\n" + digits, "text")]), SAMPLE_PROFILE)


class SentenceLengthTests(unittest.TestCase):
    # The list holds 23 lengths of 3 words or more, with the lengths 1, 2 and 2 mixed in.
    # Sorted, the 23 lengths are:
    #   3 3 4 4 5 5 6 7 7 8 9 9 10 11 12 13 14 15 16 18 20 25 30
    # Their sum is 254, so the mean is 254 / 23 = 11.043. The text holds 259 words and 26 sentences.
    # The value p10 is at rank ceil(2.3) = 3, which is 4.
    # The value p50 is at rank ceil(11.5) = 12, which is 9.
    # The value p90 is at rank ceil(20.7) = 21, which is 20.
    LENGTHS = [7, 3, 15, 1, 9, 4, 12, 20, 2, 5, 8, 3, 11, 6, 14, 10, 25, 4, 2, 9, 13, 7, 18, 5, 16, 30]

    def test_percentiles_of_known_lengths(self):
        profile = vp.build_profile([(plain_sentences(self.LENGTHS), "text")])
        self.assertEqual(profile["words"], 259)
        self.assertEqual(profile["sentences"], 26)
        self.assertEqual(profile["sentence_length"], {"mean": 11.043, "p10": 4, "p50": 9, "p90": 20})

    def test_a_sentence_of_two_words_is_left_out_and_one_of_three_is_kept(self):
        # The text has 5 sentences of 3 words, 5 of 2 words and 37 of 5 words.
        # That makes 210 words in 47 sentences. 42 sentences hold 3 words or more, with 200 words.
        # The mean is 200 / 42 = 4.762.
        lengths = [3, 2, 3, 2, 3, 2, 3, 2, 3, 2] + [5] * 37
        profile = vp.build_profile([(plain_sentences(lengths), "text")])
        self.assertEqual(profile["sentence_length"]["mean"], 4.762)
        self.assertEqual(profile["sentence_length"]["p10"], 3)

    def test_no_sentence_of_three_words_gives_none(self):
        profile = vp.build_profile([(plain_sentences([2] * 100), "text")])
        self.assertEqual(profile["sentence_length"], {"mean": None, "p10": None, "p50": None, "p90": None})
        self.assertIn('"p90": null', vp.profile_json(profile))


class HedgeTests(unittest.TestCase):
    def test_the_list_is_the_one_of_the_brief(self):
        self.assertEqual(vp.HEDGE_WORDS, tuple(
            "may might could suggest suggests suggested appear appears appeared likely possibly perhaps "
            "seem seems seemed probably".split()))

    def test_each_hedge_word_counts(self):
        # 1 hedge sentence among 21 sentences: 100 / 21 = 4.762.
        for word in vp.HEDGE_WORDS:
            with self.subTest(word=word):
                self.assertEqual(profile_of("Rivers %s flood early." % word)["hedge_rate"], 4.762)

    def test_case_does_not_matter(self):
        self.assertEqual(profile_of("Perhaps rivers flood early.")["hedge_rate"], 4.762)
        self.assertEqual(profile_of("Rivers MAY flood early.")["hedge_rate"], 4.762)

    def test_two_hedge_words_in_one_sentence_count_once(self):
        self.assertEqual(profile_of("Rivers may seem to flood early.")["hedge_rate"], 4.762)

    def test_words_that_only_hold_a_hedge_word_do_not_count(self):
        near = "The mayor praised the suggestion, the appearance and the likelihood of seemly weather."
        self.assertEqual(profile_of(near)["hedge_rate"], 0.0)

    def test_no_hedge_gives_zero(self):
        self.assertEqual(vp.build_profile([(PAD_TEXT, "text")])["hedge_rate"], 0.0)


class PassiveTests(unittest.TestCase):
    BE_FORMS = "be am is are was were been being".split()
    IRREGULAR = "known shown found seen done made given taken written run set built held".split()

    def test_the_lists_are_the_ones_of_the_brief(self):
        self.assertEqual(sorted(vp.BE_FORMS), sorted(self.BE_FORMS))
        self.assertEqual(sorted(vp.IRREGULAR_PARTICIPLES), sorted(self.IRREGULAR))

    def test_each_form_of_be_counts_before_a_participle(self):
        for be in self.BE_FORMS:
            with self.subTest(be=be):
                self.assertEqual(profile_of("Rivers %s recorded." % be)["passive_rate"], 4.762)

    def test_each_irregular_participle_counts(self):
        for word in self.IRREGULAR:
            with self.subTest(word=word):
                self.assertEqual(profile_of("Rivers were %s." % word)["passive_rate"], 4.762)

    def test_case_does_not_matter(self):
        self.assertEqual(profile_of("Rivers Were recorded.")["passive_rate"], 4.762)
        self.assertEqual(profile_of("Rivers were Shown.")["passive_rate"], 4.762)

    def test_two_passives_in_one_sentence_count_once(self):
        self.assertEqual(profile_of("Rivers were recorded and were shown.")["passive_rate"], 4.762)

    def test_a_sentence_without_the_pattern_does_not_count(self):
        for sentence in ("The winner was Ed.",  # `ed` alone is no participle
                         "The jar was never opened.",  # the participle must come next
                         "The river was cold.",
                         "The river was needless.",  # the word must end in `ed`, not only hold it
                         "Rivers have recorded it.",  # have is no form of be
                         "The beings gathered."):
            with self.subTest(sentence=sentence):
                self.assertEqual(profile_of(sentence)["passive_rate"], 0.0)

    def test_a_participle_after_a_citation_still_follows_the_form_of_be(self):
        # The citation is no word, so `was` and `recorded` stand next to each other.
        self.assertEqual(profile_of("The jar was (Lee et al., 2020) recorded.")["passive_rate"], 4.762)


class OpenerTests(unittest.TestCase):
    def test_the_ten_most_common_in_order_of_count_then_word(self):
        # The words appear in reverse alphabetical order.
        # So the word must break a tie, and the order of appearance must not.
        counts = [("lima", 1), ("kilo", 1), ("juliet", 1), ("india", 2), ("hotel", 2), ("golf", 2),
                  ("foxtrot", 2), ("echo", 3), ("delta", 4), ("charlie", 3), ("bravo", 4), ("alpha", 3)]
        text = "\n\n".join(" ".join("%s grey stones lined the old river path." % word.capitalize()
                                    for _ in range(number)) for word, number in counts)
        profile = vp.build_profile([(text, "text")])
        self.assertEqual(profile["words"], 224)
        self.assertEqual(profile["top_openers"], [
            ["bravo", 4], ["delta", 4], ["alpha", 3], ["charlie", 3], ["echo", 3],
            ["foxtrot", 2], ["golf", 2], ["hotel", 2], ["india", 2], ["juliet", 1]])

    def test_openers_are_lower_case(self):
        profile = profile_of("The river rose.\n\nTHE river rose.\n\nthe river rose.")
        self.assertEqual(profile["top_openers"], [["grey", 20], ["the", 3]])

    def test_wealth_does_not_count_as_we(self):
        self.assertEqual(profile_of("Wealth grows slowly.")["we_share"], 0.0)
        self.assertEqual(profile_of("We left early.")["we_share"], 0.048)
        self.assertEqual(profile_of("we left early.")["we_share"], 0.048)

    def test_only_the_first_word_counts_for_we(self):
        self.assertEqual(profile_of("Then we left early.")["we_share"], 0.0)


class PunctuationTests(unittest.TestCase):
    FORMATS = ("text", "markdown", "latex")

    def test_the_em_dash_counts_in_every_format(self):
        # 203 words and 1 em dash: 1000 / 203 = 4.926.
        for fmt in self.FORMATS:
            with self.subTest(fmt=fmt):
                self.assertEqual(profile_of("Rivers rose " + EM + " slowly.", fmt)["em_dash_per_1000"], 4.926)

    def test_three_hyphens_count_in_latex_only(self):
        for fmt, expected in (("latex", 4.926), ("text", 0.0), ("markdown", 0.0)):
            with self.subTest(fmt=fmt):
                self.assertEqual(profile_of("Rivers rose --- slowly.", fmt)["em_dash_per_1000"], expected)

    def test_an_en_dash_is_no_em_dash(self):
        # 211 words, with two ranges that use U+2013 and one U+2014: 1000 / 211 = 4.739.
        sentence = "Rivers rose 10\u201320 cm and fell 30\u201340 cm " + EM + " slowly."
        for fmt in self.FORMATS:
            with self.subTest(fmt=fmt):
                profile = profile_of(sentence, fmt)
                self.assertEqual(profile["words"], 211)
                self.assertEqual(profile["em_dash_per_1000"], 4.739)

    def test_two_hyphens_do_not_count(self):
        self.assertEqual(profile_of("Rivers rose -- slowly.", "latex")["em_dash_per_1000"], 0.0)

    def test_semicolons_count_in_every_format(self):
        # 206 words and 2 semicolons: 2000 / 206 = 9.709.
        for fmt in self.FORMATS:
            with self.subTest(fmt=fmt):
                self.assertEqual(profile_of("Rivers rose; they fell; we slept.", fmt)["semicolon_per_1000"], 9.709)

    def test_hidden_text_holds_no_dash_and_no_semicolon(self):
        latex = "Rivers rose slowly $a --- b; c " + EM + " d$.\n% one; two --- three " + EM + " four\n"
        profile = profile_of(latex, "latex")
        self.assertEqual(profile["words"], 203)
        self.assertEqual(profile["em_dash_per_1000"], 0.0)
        self.assertEqual(profile["semicolon_per_1000"], 0.0)
        markdown = "Rivers rose slowly `a " + EM + " b; c`.\n"
        profile = profile_of(markdown, "markdown")
        self.assertEqual(profile["em_dash_per_1000"], 0.0)
        self.assertEqual(profile["semicolon_per_1000"], 0.0)

    def test_a_number_counts_as_a_word_in_the_mean_length(self):
        # Six words of 18 characters join the 200 words of 860 characters: 878 / 206 = 4.262.
        profile = profile_of("In 2020 we had 150 jars.")
        self.assertEqual(profile["words"], 206)
        self.assertEqual(profile["avg_word_length"], 4.262)

    def test_the_mean_word_length_of_the_neutral_text(self):
        self.assertEqual(vp.build_profile([(PAD_TEXT, "text")])["avg_word_length"], 4.3)


class FormatTests(unittest.TestCase):
    def test_a_plain_text_sample_hides_citations_and_urls(self):
        # The sentence holds 11 words once the citation, the number citation and the URL are hidden.
        # 211 words, 21 sentences. Hedge 100 / 21 = 4.762. We 1 / 21 = 0.048. One semicolon:
        # 1000 / 211 = 4.739. The mean length is (860 + 37) / 211 = 4.251.
        sentence = "We may see the effect (Lee et al., 2020) in rivers [12]; the data sit at https://example.org/data."
        profile = profile_of(sentence)
        self.assertEqual(profile["words"], 211)
        self.assertEqual(profile["sentences"], 21)
        self.assertEqual(profile["hedge_rate"], 4.762)
        self.assertEqual(profile["we_share"], 0.048)
        self.assertEqual(profile["semicolon_per_1000"], 4.739)
        self.assertEqual(profile["avg_word_length"], 4.251)
        self.assertEqual(profile["sentence_length"]["mean"], 10.048)

    # The masker hides the comment, the section command, the math and the citations.
    # The snippet then holds 4 sentences and 21 words:
    #   Rivers (1 word, 6 characters), the heading of the section command.
    #   We measured the rate of each plate. (7 words, 28 characters)
    #   The slow river trend was recorded twice. (7 words, 33 characters, a passive)
    #   It may rise again, or not. (6 words, 19 characters, a hedge, one `---`)
    # The comment holds the hedge words "may" and "suggest" and a semicolon. They stay hidden.
    # With the neutral text the profile holds 221 words and 24 sentences.
    # 23 sentences hold 3 words or more, with the lengths 6, 7, 7 and 20 times 10.
    # So the mean is 220 / 23 = 9.565, p10 is 7, and p50 and p90 are 10.
    # The share of We is 1 / 24 = 0.042. The hedge rate and the passive rate are 100 / 24 = 4.167.
    # The em dash rate is 1000 / 221 = 4.525. The mean word length is (860 + 86) / 221 = 4.281.
    LATEX_SNIPPET = (
        "% We may suggest hidden words in a comment; they do not count.\n"
        "\\section{Rivers}\n"
        "We measured the rate $r = 0.5 \\pm 0.1$ of each plate \\cite{lee2020}.\n"
        "The slow \\emph{river} trend was recorded twice \\cite{lee2020}.\n"
        "It may rise again --- or not.\n")
    LATEX_PLAIN = (
        "Rivers\n\n"
        "We measured the rate of each plate.\n"
        "The slow river trend was recorded twice.\n"
        "It may rise again " + EM + " or not.\n")

    def test_a_latex_sample_ignores_math_comments_and_citations(self):
        profile = profile_of(self.LATEX_SNIPPET, "latex")
        self.assertEqual(profile["words"], 221)
        self.assertEqual(profile["sentences"], 24)
        self.assertEqual(profile["sentence_length"], {"mean": 9.565, "p10": 7, "p50": 10, "p90": 10})
        self.assertEqual(profile["we_share"], 0.042)
        self.assertEqual(profile["hedge_rate"], 4.167)
        self.assertEqual(profile["passive_rate"], 4.167)
        self.assertEqual(profile["em_dash_per_1000"], 4.525)
        self.assertEqual(profile["semicolon_per_1000"], 0.0)
        self.assertEqual(profile["avg_word_length"], 4.281)
        self.assertEqual(profile["top_openers"], [["grey", 20], ["it", 1], ["rivers", 1], ["the", 1], ["we", 1]])

    def test_the_latex_sample_gives_the_profile_of_its_plain_text(self):
        self.assertEqual(profile_of(self.LATEX_SNIPPET, "latex"), profile_of(self.LATEX_PLAIN, "text"))

    def test_the_same_latex_read_as_plain_text_gives_other_counts(self):
        # A plain-text read counts the comment, the math and the citations as prose.
        self.assertNotEqual(profile_of(self.LATEX_SNIPPET, "text")["words"], 221)

    # The Markdown snippet holds a heading, two list items, a fenced block and a paragraph.
    #   Rivers (1 word, 6 characters), the heading.
    #   We measured the rate of each plate. (7 words, 28 characters), a list item.
    #   The river was checked twice, see the log. (8 words, 32 characters, a passive), a list item.
    #   The paragraph (13 words, 44 characters) holds a hedge, one em dash and two semicolons.
    # The inline code `we may suggest` stays hidden.
    # The fenced block holds a semicolon, an em dash and two hedge words. It stays hidden.
    # With the neutral text the profile holds 229 words and 24 sentences.
    # 23 sentences hold 3 words or more, with the lengths 7, 8, 10 times 20, and 13.
    # So the mean is 228 / 23 = 9.913. The share of We is 1 / 24 = 0.042.
    # The hedge rate and the passive rate are 100 / 24 = 4.167.
    # The em dash rate is 1000 / 229 = 4.367. The semicolon rate is 2000 / 229 = 8.734.
    # The mean word length is (860 + 110) / 229 = 4.236.
    MARKDOWN_SNIPPET = (
        "# Rivers\n\n"
        "- We measured the rate of each plate.\n"
        "- The river was checked twice, see [the log](https://example.org/log).\n\n"
        "```python\nx = 1; y = 2 " + EM + " We may suggest this is code\n```\n\n"
        "It may rise again " + EM + " or not; the notes say `we may suggest` a thing; ask again.\n")
    MARKDOWN_PLAIN = (
        "Rivers\n\n"
        "We measured the rate of each plate.\n\n"
        "The river was checked twice, see the log.\n\n"
        "It may rise again " + EM + " or not; the notes say a thing; ask again.\n")

    def test_a_markdown_sample_ignores_code_and_link_targets(self):
        profile = profile_of(self.MARKDOWN_SNIPPET, "markdown")
        self.assertEqual(profile["words"], 229)
        self.assertEqual(profile["sentences"], 24)
        self.assertEqual(profile["sentence_length"], {"mean": 9.913, "p10": 10, "p50": 10, "p90": 10})
        self.assertEqual(profile["we_share"], 0.042)
        self.assertEqual(profile["hedge_rate"], 4.167)
        self.assertEqual(profile["passive_rate"], 4.167)
        self.assertEqual(profile["em_dash_per_1000"], 4.367)
        self.assertEqual(profile["semicolon_per_1000"], 8.734)
        self.assertEqual(profile["avg_word_length"], 4.236)

    def test_the_markdown_sample_gives_the_profile_of_its_plain_text(self):
        self.assertEqual(profile_of(self.MARKDOWN_SNIPPET, "markdown"), profile_of(self.MARKDOWN_PLAIN, "text"))

    def test_an_unknown_format_raises_value_error(self):
        with self.assertRaises(ValueError):
            vp.build_profile([(SAMPLE_TEXT, "html")])


class CombineTests(unittest.TestCase):
    # The neutral text has 200 words and 20 sentences. The main sample has 294 words and 31 sentences.
    # Together they hold 494 words and 51 sentences.
    # The hedge rate is 700 / 51 = 13.725. The passive rate is 600 / 51 = 11.765.
    # The share of We is 6 / 51 = 0.118.
    # The em dash rate is 3000 / 494 = 6.073. The semicolon rate is 2000 / 494 = 4.049.
    # The mean word length is (1218 + 860) / 494 = 4.206.
    # 49 sentences hold 3 words or more, with 490 words in all, so the mean is 10.0.
    # 24 of the 49 have 10 words. The ranks for n = 49 are 5, 25 and 45.
    # They give p10 = 6, p50 = 10 and p90 = 13.
    # The top openers are grey 20, the 8 and we 6. Then come a, rain and that with 2 each.
    # Single openers follow in the order of the word.
    def test_two_samples_give_one_profile(self):
        profile = vp.build_profile([(PAD_TEXT, "text"), (SAMPLE_TEXT, "text")])
        self.assertEqual(profile["samples"], 2)
        self.assertEqual(profile["words"], 494)
        self.assertEqual(profile["sentences"], 51)
        self.assertEqual(profile["sentence_length"], {"mean": 10.0, "p10": 6, "p50": 10, "p90": 13})
        self.assertEqual(profile["we_share"], 0.118)
        self.assertEqual(profile["hedge_rate"], 13.725)
        self.assertEqual(profile["passive_rate"], 11.765)
        self.assertEqual(profile["em_dash_per_1000"], 6.073)
        self.assertEqual(profile["semicolon_per_1000"], 4.049)
        self.assertEqual(profile["avg_word_length"], 4.206)
        self.assertEqual(profile["top_openers"], [
            ["grey", 20], ["the", 8], ["we", 6], ["a", 2], ["rain", 2], ["that", 2],
            ["by", 1], ["it", 1], ["nothing", 1], ["on", 1]])

    def test_the_order_of_the_samples_does_not_matter(self):
        one = vp.build_profile([(PAD_TEXT, "text"), (SAMPLE_TEXT, "text")])
        two = vp.build_profile([(SAMPLE_TEXT, "text"), (PAD_TEXT, "text")])
        self.assertEqual(one, two)

    def test_each_sample_uses_its_own_format(self):
        # The `---` counts in the LaTeX sample only.
        text = PAD_TEXT + "\n\nRivers rose --- slowly.\n"
        both = vp.build_profile([(text, "latex"), (text, "markdown")])
        self.assertEqual(both["words"], 406)
        # 1 dash in 406 words: 1000 / 406 = 2.463.
        self.assertEqual(both["em_dash_per_1000"], 2.463)

    def test_a_generator_of_samples_works(self):
        profile = vp.build_profile(pair for pair in [(SAMPLE_TEXT, "text")])
        self.assertEqual(profile, SAMPLE_PROFILE)


class LimitTests(unittest.TestCase):
    def test_199_words_raise_and_200_words_pass(self):
        with self.assertRaises(ValueError) as caught:
            vp.build_profile([(plain_sentences([10] * 19 + [9]), "text")])
        self.assertEqual(str(caught.exception), "too little text for a profile (199 words; need 200)")
        self.assertEqual(vp.build_profile([(plain_sentences([10] * 20), "text")])["words"], 200)

    def test_the_words_of_all_samples_count(self):
        halves = [(plain_sentences([10] * 10), "text")] * 2
        self.assertEqual(vp.build_profile(halves)["words"], 200)
        with self.assertRaises(ValueError) as caught:
            vp.build_profile([(plain_sentences([10] * 9), "text")] * 2)
        self.assertIn("(180 words; need 200)", str(caught.exception))

    def test_no_sample_and_an_empty_sample_raise(self):
        for samples in ([], [("", "text")]):
            with self.assertRaises(ValueError) as caught:
                vp.build_profile(samples)
            self.assertEqual(str(caught.exception), "too little text for a profile (0 words; need 200)")

    def test_masked_text_does_not_count_toward_the_limit(self):
        # 150 words plus a long comment and long math.
        text = plain_sentences([10] * 15) + "\n% " + " ".join(["hidden"] * 100) + "\n$" + "x " * 100 + "$\n"
        with self.assertRaises(ValueError) as caught:
            vp.build_profile([(text, "latex")])
        self.assertIn("(150 words; need 200)", str(caught.exception))


class PrivacyTests(unittest.TestCase):
    def test_the_scan_finds_a_leaked_sentence(self):
        leak = json.dumps({"note": SAMPLE_PARAGRAPHS[0][1]})
        self.assertTrue(four_grams(tokens_of(leak)) & four_grams(tokens_of(SAMPLE_TEXT)))

    def test_the_output_holds_no_four_words_of_the_sample(self):
        sample_grams = four_grams(tokens_of(SAMPLE_TEXT))
        self.assertGreater(len(sample_grams), 200)
        for text in (SAMPLE_TEXT, SAMPLE_TEXT + "\n\n" + PAD_TEXT):
            output = vp.profile_json(vp.build_profile([(text, "text")]))
            self.assertFalse(four_grams(tokens_of(output)) & sample_grams)

    def test_every_string_of_the_output_is_one_word_or_a_key(self):
        profile = sample_profile()
        for word, number in profile["top_openers"]:
            self.assertRegex(word, r"^[^\W\d_]+$")
        self.assertEqual(sorted(profile), sorted(vp.REQUIRED_KEYS))


class Folder(object):
    """A temporary folder with a `write` helper."""

    def __enter__(self):
        self.dir = tempfile.TemporaryDirectory()
        self.root = self.dir.name
        return self

    def __exit__(self, *exc):
        self.dir.cleanup()

    def path(self, name):
        return os.path.join(self.root, name)

    def write(self, name, data):
        path = self.path(name)
        with open(path, "wb") as handle:
            handle.write(data if isinstance(data, bytes) else data.encode("utf-8"))
        return path


class LoadProfileTests(unittest.TestCase):
    def setUp(self):
        self.folder = Folder().__enter__()
        self.addCleanup(self.folder.__exit__)

    def load(self, data, name="prose-voice.json"):
        if not isinstance(data, bytes):
            data = json.dumps(data)
        return vp.load_profile(self.folder.write(name, data))

    def broken(self, **changes):
        profile = json.loads(json.dumps(SAMPLE_PROFILE))
        profile.update(changes)
        return profile

    def assert_rejected(self, data, *needles):
        with self.assertRaises(ValueError) as caught:
            self.load(data)
        for needle in needles:
            self.assertIn(needle, str(caught.exception))

    def test_a_good_profile_loads_unchanged(self):
        self.assertEqual(self.load(SAMPLE_PROFILE), SAMPLE_PROFILE)

    def test_a_written_profile_loads_unchanged(self):
        path = self.folder.write("out.json", vp.profile_json(SAMPLE_PROFILE))
        self.assertEqual(vp.load_profile(path), SAMPLE_PROFILE)

    def test_a_missing_key_names_the_key(self):
        for key in vp.REQUIRED_KEYS:
            with self.subTest(key=key):
                profile = self.broken()
                del profile[key]
                self.assert_rejected(profile, '"%s"' % key, "prose-voice.json")

    def test_a_string_where_a_number_belongs_names_the_key(self):
        for key in vp.RATE_KEYS:
            with self.subTest(key=key):
                self.assert_rejected(self.broken(**{key: "0.5"}), '"%s"' % key)

    def test_a_count_must_be_an_int(self):
        for key in vp.COUNT_KEYS:
            for value in ("12", 1.5, 12.0, None, [12]):
                with self.subTest(key=key, value=value):
                    self.assert_rejected(self.broken(**{key: value}), '"%s"' % key)

    def test_a_bool_is_no_number_and_no_count(self):
        for key in vp.COUNT_KEYS + vp.RATE_KEYS:
            for value in (True, False):
                with self.subTest(key=key, value=value):
                    self.assert_rejected(self.broken(**{key: value}), '"%s"' % key)
        spread = dict(SAMPLE_PROFILE["sentence_length"], p90=True)
        self.assert_rejected(self.broken(sentence_length=spread), "sentence_length.p90")

    def test_a_negative_number_names_the_key(self):
        for key in vp.COUNT_KEYS:
            with self.subTest(key=key):
                self.assert_rejected(self.broken(**{key: -1}), '"%s"' % key)
        for key in vp.RATE_KEYS:
            with self.subTest(key=key):
                self.assert_rejected(self.broken(**{key: -0.5}), '"%s"' % key)
        for key in vp.LENGTH_KEYS:
            with self.subTest(key=key):
                spread = dict(SAMPLE_PROFILE["sentence_length"], **{key: -8})
                self.assert_rejected(self.broken(sentence_length=spread), "sentence_length." + key)

    def test_the_share_of_we_lies_between_0_and_1(self):
        for value in (1.5, 1.001, 2, 100):
            with self.subTest(value=value):
                self.assert_rejected(self.broken(we_share=value), '"we_share"')
        for value in (0, 0.0, 1, 1.0, 0.5):
            with self.subTest(value=value):
                self.assertEqual(self.load(self.broken(we_share=value))["we_share"], value)

    def test_zero_is_a_good_value_everywhere(self):
        zero = dict((key, 0) for key in vp.COUNT_KEYS + vp.RATE_KEYS)
        spread = dict((key, 0) for key in vp.LENGTH_KEYS)
        loaded = self.load(self.broken(sentence_length=spread, **zero))
        self.assertEqual(loaded["sentence_length"], spread)
        self.assertEqual(vp.max_sentence_words(loaded), 0)

    def test_a_rate_may_be_an_int(self):
        self.assertEqual(self.load(self.broken(hedge_rate=0))["hedge_rate"], 0)

    def test_the_version_must_be_the_int_1(self):
        for value in (2, 0, "1", 1.0, True, None):
            with self.subTest(value=value):
                self.assert_rejected(self.broken(version=value), '"version"')

    def test_a_number_must_be_finite(self):
        for key, literal in (("we_share", "NaN"), ("hedge_rate", "Infinity"), ("passive_rate", "-Infinity"),
                             ("avg_word_length", "1e999"), ("em_dash_per_1000", "1" + "0" * 400)):
            with self.subTest(key=key, literal=literal):
                text = json.dumps(self.broken(**{key: 0})).replace('"%s": 0' % key, '"%s": %s' % (key, literal))
                self.assertIn(literal, text)
                self.assert_rejected(text.encode("utf-8"), '"%s"' % key)

    def test_sentence_length_needs_its_four_keys(self):
        for key in vp.LENGTH_KEYS:
            with self.subTest(key=key):
                spread = dict(SAMPLE_PROFILE["sentence_length"])
                del spread[key]
                self.assert_rejected(self.broken(sentence_length=spread), "sentence_length." + key)

    def test_sentence_length_takes_numbers_and_none_only(self):
        for key in vp.LENGTH_KEYS:
            with self.subTest(key=key):
                spread = dict(SAMPLE_PROFILE["sentence_length"], **{key: "12"})
                self.assert_rejected(self.broken(sentence_length=spread), "sentence_length." + key)
        none = dict((key, None) for key in vp.LENGTH_KEYS)
        self.assertEqual(self.load(self.broken(sentence_length=none))["sentence_length"], none)
        floats = {"mean": 10.5, "p10": 4.0, "p50": 9.5, "p90": 20.25}
        self.assertEqual(self.load(self.broken(sentence_length=floats))["sentence_length"], floats)
        self.assert_rejected(self.broken(sentence_length="x"), '"sentence_length"')
        self.assert_rejected(self.broken(sentence_length=[]), '"sentence_length"')

    def test_top_openers_must_be_a_list_of_word_count_pairs(self):
        for value in ("the", {"the": 5}, [["the", 5], "we"], [["the"]], [["the", 5, 1]], [["the", "5"]],
                      [[1, 5]], [["the", True]], [["the", 5], 7], None):
            with self.subTest(value=value):
                self.assert_rejected(self.broken(top_openers=value), '"top_openers"')
        self.assertEqual(self.load(self.broken(top_openers=[]))["top_openers"], [])

    def test_a_file_that_is_not_json_names_the_file(self):
        with self.assertRaises(ValueError) as caught:
            self.load(b"{ not json", name="bad-voice.json")
        self.assertIn("bad-voice.json", str(caught.exception))

    def test_a_file_that_is_not_utf8_names_the_file(self):
        with self.assertRaises(ValueError) as caught:
            self.load(b'{"version": 1, "x": "\xff\xfe"}', name="latin-voice.json")
        self.assertIn("latin-voice.json", str(caught.exception))

    def test_json_that_is_no_object_is_no_profile(self):
        for data in (b"[1, 2]", b"42", b'"text"', b"null", b"true"):
            with self.subTest(data=data):
                with self.assertRaises(ValueError) as caught:
                    self.load(data, name="list-voice.json")
                self.assertIn("list-voice.json", str(caught.exception))

    def test_a_missing_file_raises_value_error_with_the_name(self):
        path = self.folder.path("absent-voice.json")
        with self.assertRaises(ValueError) as caught:
            vp.load_profile(path)
        self.assertIn(path, str(caught.exception))

    def test_a_profile_with_an_extra_key_loads(self):
        self.assertEqual(self.load(self.broken(note="x"))["note"], "x")


class MaxSentenceWordsTests(unittest.TestCase):
    def profile(self, p90):
        return {"sentence_length": {"mean": 10.0, "p10": 4, "p50": 9, "p90": p90}}

    def test_p90_30_gives_38(self):
        self.assertEqual(vp.max_sentence_words(self.profile(30)), 38)

    def test_none_gives_35(self):
        self.assertEqual(vp.max_sentence_words(self.profile(None)), 35)

    def test_the_result_is_an_int_that_rounds_up(self):
        for p90, expected in ((24, 30), (25, 32), (15, 19), (20, 25), (1, 2), (30.0, 38)):
            with self.subTest(p90=p90):
                result = vp.max_sentence_words(self.profile(p90))
                self.assertEqual(result, expected)
                self.assertIs(type(result), int)

    def test_the_profile_of_the_main_sample(self):
        # p90 is 15 and 15 x 1.25 = 18.75.
        self.assertEqual(vp.max_sentence_words(SAMPLE_PROFILE), 19)


def run_script(args, env=None, binary=False):
    """Run `python3 voice_profile.py` in a child process. Return (exit code, stdout, stderr)."""
    options = {} if binary else {"universal_newlines": True}
    proc = subprocess.run([sys.executable, "-B", SCRIPT] + list(args), stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, env=env, **options)
    return proc.returncode, proc.stdout, proc.stderr


class CommandLineTests(unittest.TestCase):
    def setUp(self):
        self.folder = Folder().__enter__()
        self.addCleanup(self.folder.__exit__)
        self.sample = self.folder.write("sample.txt", SAMPLE_TEXT)

    def test_a_profile_goes_to_stdout_with_exit_0(self):
        code, out, err = run_script([self.sample])
        self.assertEqual((code, err), (0, ""))
        self.assertEqual(out, vp.profile_json(SAMPLE_PROFILE))

    def test_two_files_give_one_profile(self):
        pad = self.folder.write("pad.txt", PAD_TEXT)
        code, out, err = run_script([pad, self.sample])
        self.assertEqual((code, err), (0, ""))
        self.assertEqual(json.loads(out), vp.build_profile([(PAD_TEXT, "text"), (SAMPLE_TEXT, "text")]))
        self.assertEqual(json.loads(out)["samples"], 2)

    def test_out_writes_the_file_and_prints_nothing(self):
        target = self.folder.path("profile.json")
        code, out, err = run_script([self.sample, "--out", target])
        self.assertEqual((code, out, err), (0, "", ""))
        with open(target, "rb") as handle:
            self.assertEqual(handle.read().decode("utf-8"), vp.profile_json(SAMPLE_PROFILE))
        self.assertEqual(vp.load_profile(target), SAMPLE_PROFILE)

    def test_out_writes_utf8(self):
        path = self.folder.write("accent.txt", PAD_TEXT + "\n\n\u00c9cole grey stones lined the old river path.\n")
        target = self.folder.path("profile.json")
        self.assertEqual(run_script([path, "--out", target], env=dict(os.environ, LC_ALL="C"))[0], 0)
        with open(target, "rb") as handle:
            data = handle.read()
        self.assertIn("\u00e9cole".encode("utf-8"), data)
        self.assertEqual(json.loads(data.decode("utf-8"))["top_openers"][-1], ["\u00e9cole", 1])

    def test_out_replaces_an_old_file(self):
        target = self.folder.write("profile.json", "old " * 5000)
        self.assertEqual(run_script([self.sample, "--out", target])[0], 0)
        self.assertEqual(vp.load_profile(target), SAMPLE_PROFILE)

    def test_a_missing_file_gives_exit_2(self):
        absent = self.folder.path("absent.txt")
        code, out, err = run_script([self.sample, absent])
        self.assertEqual((code, out), (2, ""))
        self.assertIn(absent, err)
        self.assertNotIn("Traceback", err)

    def test_too_little_text_gives_exit_2_with_the_message(self):
        short = self.folder.write("short.txt", plain_sentences([10] * 15))
        code, out, err = run_script([short])
        self.assertEqual((code, out), (2, ""))
        self.assertIn("too little text for a profile (150 words; need 200)", err)

    def test_an_empty_file_gives_exit_2(self):
        empty = self.folder.write("empty.txt", b"")
        code, out, err = run_script([empty])
        self.assertEqual((code, out), (2, ""))
        self.assertIn("(0 words; need 200)", err)

    def test_a_file_that_is_not_utf8_gives_exit_2_without_a_traceback(self):
        bad = self.folder.write("latin.txt", b"We saw the caf\xe9 by the river.\n")
        code, out, err = run_script([bad])
        self.assertEqual((code, out), (2, ""))
        self.assertIn("latin.txt", err)
        self.assertIn("UTF-8", err)
        self.assertNotIn("Traceback", err)

    def test_a_file_that_is_not_utf8_leaves_the_out_file_alone(self):
        bad = self.folder.write("latin.txt", b"We saw the caf\xe9 by the river.\n")
        target = self.folder.path("profile.json")
        self.assertEqual(run_script([self.sample, bad, "--out", target])[0], 2)
        self.assertFalse(os.path.exists(target))

    def test_a_binary_file_gives_exit_2(self):
        binary = self.folder.write("data.txt", b"We saw\x00 the river.\n")
        code, out, err = run_script([binary])
        self.assertEqual((code, out), (2, ""))
        self.assertIn("data.txt", err)
        self.assertNotIn("Traceback", err)

    def test_a_folder_gives_exit_2(self):
        code, out, err = run_script([self.folder.root])
        self.assertEqual((code, out), (2, ""))
        self.assertNotIn("Traceback", err)

    def test_too_little_text_leaves_the_out_file_unwritten(self):
        short = self.folder.write("short.txt", plain_sentences([10] * 15))
        target = self.folder.path("profile.json")
        code, out, err = run_script([short, "--out", target])
        self.assertEqual((code, out), (2, ""))
        self.assertFalse(os.path.exists(target))

    def test_an_out_path_that_cannot_be_written_gives_exit_2(self):
        target = os.path.join(self.folder.root, "no-such-folder", "profile.json")
        code, out, err = run_script([self.sample, "--out", target])
        self.assertEqual((code, out), (2, ""))
        self.assertIn(target, err)
        self.assertNotIn("Traceback", err)

    def test_an_empty_out_path_gives_exit_2(self):
        code, out, err = run_script([self.sample, "--out", ""])
        self.assertEqual((code, out), (2, ""))
        self.assertIn("cannot write", err)

    def test_help_gives_exit_0(self):
        code, out, err = run_script(["--help"])
        self.assertEqual((code, err), (0, ""))
        self.assertIn("SAMPLE", out)

    def odd_file(self, base, data):
        """Write a file whose name holds a byte that is not UTF-8. Skip the test if the file system refuses."""
        try:
            return self.folder.write(os.fsdecode(b"caf\xe9-" + base), data)
        except OSError:
            raise unittest.SkipTest("the file system rejects a file name with a byte that is not UTF-8")

    def assert_clean_failure(self, args, name, env=None):
        """Run the command. Expect exit 2, no output, no traceback and the file name in the message.

        The child writes the original bytes of the name. The parent reads the bytes, so no decoding fails.
        """
        code, out, err = run_script(args, env=env, binary=True)
        self.assertEqual(code, 2, err)
        self.assertEqual(out, b"")
        self.assertNotIn(b"Traceback", err)
        self.assertIn(os.fsencode(name), err)
        return err

    def test_a_missing_file_with_a_name_that_is_not_utf8(self):
        name = os.fsdecode(b"caf\xe9-missing.txt")
        err = self.assert_clean_failure([name], name)
        self.assertIn(b"cannot read", err)

    def test_a_file_that_is_not_utf8_with_a_name_that_is_not_utf8(self):
        path = self.odd_file(b"bad.txt", b"x\xff")
        err = self.assert_clean_failure([path], path)
        self.assertIn(b"UTF-8", err)

    def test_an_out_path_that_is_not_utf8_and_cannot_be_written(self):
        target = os.path.join(self.folder.root, "no-such-folder", os.fsdecode(b"caf\xe9.json"))
        err = self.assert_clean_failure([self.sample, "--out", target], target)
        self.assertIn(b"cannot write", err)

    def test_a_format_value_that_is_not_utf8_gives_exit_2(self):
        code, out, err = run_script([self.sample, "--format", os.fsdecode(b"x\xe9")], binary=True)
        self.assertEqual((code, out), (2, b""))
        self.assertNotIn(b"Traceback", err)

    def test_a_utf8_name_in_the_c_locale(self):
        # The child reads the name as bytes that stand for the characters. It must write the same bytes back.
        name = "caf\u00e9-missing.txt"
        err = self.assert_clean_failure([name], name, env=dict(os.environ, LC_ALL="C"))
        self.assertIn(name.encode("utf-8"), err)

    def test_out_naming_a_sample_gives_exit_2_and_keeps_the_sample(self):
        victim = self.folder.write("victim.txt", SAMPLE_TEXT)
        other = self.folder.write("other.txt", PAD_TEXT)
        os.mkdir(self.folder.path("sub"))
        link = self.folder.path("link.txt")
        try:
            os.symlink(victim, link)
        except OSError:
            link = None
        spellings = [
            [victim, "--out", victim],
            [victim, "--out", os.path.join(self.folder.root, ".", "victim.txt")],
            [victim, "--out", os.path.join(self.folder.root, "sub", "..", "victim.txt")],
            [other, victim, "--out", victim],
            [victim, other, "--out", other],
        ]
        if link:
            spellings.append([victim, "--out", link])
            spellings.append([link, "--out", victim])
        for args in spellings:
            with self.subTest(args=args):
                code, out, err = run_script(args)
                self.assertEqual((code, out), (2, ""))
                self.assertIn(args[-1], err)
                self.assertIn("--out", err)
                self.assertNotIn("Traceback", err)
                with open(victim, "rb") as handle:
                    self.assertEqual(handle.read(), SAMPLE_TEXT.encode("utf-8"))
                with open(other, "rb") as handle:
                    self.assertEqual(handle.read(), PAD_TEXT.encode("utf-8"))

    def test_out_naming_a_hard_link_to_a_sample_gives_exit_2_and_keeps_the_sample(self):
        # A hard link has its own real path, so only the file identity shows that it is the sample.
        sample = self.folder.write("hard-sample.txt", SAMPLE_TEXT)
        self.assertGreaterEqual(len(SAMPLE_TEXT.split()), vp.MIN_WORDS)
        link = self.folder.path("hard-link.txt")
        try:
            os.link(sample, link)
        except OSError as error:
            self.skipTest("this file system cannot make a hard link: %s" % error)
        self.assertNotEqual(os.path.realpath(sample), os.path.realpath(link))
        out, err = io.BytesIO(), io.BytesIO()
        code = vp.main([sample, "--out", link], out, err)
        self.assertEqual((code, out.getvalue()), (2, b""))
        self.assertIn(b"would overwrite", err.getvalue())
        with open(sample, "rb") as handle:
            self.assertEqual(handle.read(), SAMPLE_TEXT.encode("utf-8"))
        self.assertFalse(vp._same_file(sample, self.folder.path("absent.json")))

    def test_out_naming_a_sample_with_a_name_that_is_not_utf8(self):
        victim = self.odd_file(b"victim.txt", SAMPLE_TEXT)
        err = self.assert_clean_failure([victim, "--out", victim], victim)
        self.assertIn(b"--out", err)
        with open(victim, "rb") as handle:
            self.assertEqual(handle.read(), SAMPLE_TEXT.encode("utf-8"))

    def test_out_next_to_a_sample_still_writes(self):
        # A name that extends the sample name, and a name that the sample name extends, are other files.
        for name in ("sample.txt.json", "sample", "sam"):
            with self.subTest(name=name):
                target = self.folder.path(name)
                self.assertEqual(run_script([self.sample, "--out", target])[0], 0)
                self.assertEqual(vp.load_profile(target), SAMPLE_PROFILE)
                with open(self.sample, "rb") as handle:
                    self.assertEqual(handle.read(), SAMPLE_TEXT.encode("utf-8"))

    def test_no_sample_gives_exit_2(self):
        code, out, err = run_script([])
        self.assertEqual((code, out), (2, ""))
        self.assertIn("SAMPLE", err)

    def test_a_bad_format_gives_exit_2(self):
        code, out, err = run_script([self.sample, "--format", "xml"])
        self.assertEqual((code, out), (2, ""))
        self.assertIn("xml", err)

    def test_the_format_option_applies_to_every_sample(self):
        # The `---` counts when the format is latex. 203 words and 1 dash: 1000 / 203 = 4.926.
        text = PAD_TEXT + "\n\nRivers rose --- slowly.\n"
        tex = self.folder.write("a.tex", text)
        txt = self.folder.write("b.txt", text)
        md = self.folder.write("c.md", text)
        odd = self.folder.write("d.unknown", text)

        def dash(args):
            code, out, err = run_script(args)
            self.assertEqual((code, err), (0, ""), args)
            return json.loads(out)["em_dash_per_1000"]

        self.assertEqual(dash([tex]), 4.926)
        self.assertEqual(dash([tex, "--format", "auto"]), 4.926)
        self.assertEqual(dash([txt]), 0.0)
        self.assertEqual(dash([md]), 0.0)
        self.assertEqual(dash([odd]), 0.0)
        self.assertEqual(dash([tex, "--format", "text"]), 0.0)
        self.assertEqual(dash([tex, "--format", "markdown"]), 0.0)
        self.assertEqual(dash([txt, "--format", "latex"]), 4.926)
        self.assertEqual(dash([md, "--format", "latex"]), 4.926)
        self.assertEqual(dash([odd, "--format", "latex"]), 4.926)
        # With two files and `latex`, both files count the dash: 2000 / 406 = 4.926.
        self.assertEqual(dash([txt, md, "--format", "latex"]), 4.926)
        # With `auto`, each file gets its own format. Only the .tex file counts the dash: 1000 / 406 = 2.463.
        self.assertEqual(dash([tex, md]), 2.463)
        self.assertEqual(dash([md, tex, txt]), 1.642)

    def test_a_non_ascii_opener_goes_out_as_utf8_in_the_c_locale(self):
        text = PAD_TEXT + "\n\n\u00c9cole grey stones lined the old river path.\n"
        path = self.folder.write("accent.txt", text)
        env = dict(os.environ, LC_ALL="C")
        env.pop("PYTHONIOENCODING", None)
        code, out, err = run_script([path], env=env, binary=True)
        self.assertEqual((code, err), (0, b""))
        self.assertIn("\u00e9cole".encode("utf-8"), out)
        self.assertNotIn(b"\\u00e9", out)

    def test_a_crash_gives_exit_2_and_not_a_profile(self):
        out, err = io.BytesIO(), io.BytesIO()
        with mock.patch.object(vp, "build_profile", side_effect=RuntimeError("boom")):
            code = vp.main([self.sample], out, err)
        self.assertEqual(code, 2)
        self.assertEqual(out.getvalue(), b"")
        self.assertIn(b"RuntimeError: boom", err.getvalue())

    def test_main_runs_in_this_process(self):
        out, err = io.BytesIO(), io.BytesIO()
        self.assertEqual(vp.main([self.sample], out, err), 0)
        self.assertEqual(out.getvalue().decode("utf-8"), vp.profile_json(SAMPLE_PROFILE))
        self.assertEqual(err.getvalue(), b"")


if __name__ == "__main__":
    unittest.main()
