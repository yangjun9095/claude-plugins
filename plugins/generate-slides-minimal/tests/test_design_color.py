"""Tests for the WCAG 2.1 color helpers in scripts/design_color.py."""
import sys
import unittest
from pathlib import Path

SCRIPTS = str(Path(__file__).resolve().parents[1] / "scripts")
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

import design_color as dc  # noqa: E402


class ParseHex(unittest.TestCase):
    def test_accepts_six_digits_with_or_without_the_hash(self):
        self.assertEqual(dc.parse_hex("#FF8000"), (255, 128, 0))
        self.assertEqual(dc.parse_hex("FF8000"), (255, 128, 0))

    def test_accepts_any_case(self):
        self.assertEqual(dc.parse_hex("#ff80aB"), (255, 128, 171))

    def test_rejects_text_that_is_not_six_hex_digits(self):
        bad_texts = ["#FFF", "#GGGGGG", "", "#", "##FFFFFF", "#FFFFFFF", " #FFFFFF", "#FFFFFF\n"]
        for text in bad_texts:
            with self.subTest(text=text):
                with self.assertRaises(ValueError):
                    dc.parse_hex(text)

    def test_rejects_a_value_that_is_not_text(self):
        for value in (None, 16777215, (255, 255, 255)):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    dc.parse_hex(value)


class RelativeLuminance(unittest.TestCase):
    def test_black_is_zero_and_white_is_one(self):
        self.assertAlmostEqual(dc.relative_luminance((0, 0, 0)), 0.0, places=9)
        self.assertAlmostEqual(dc.relative_luminance((255, 255, 255)), 1.0, places=9)

    def test_uses_the_linear_branch_at_or_below_0_04045(self):
        # 10 / 255 = 0.03922, so the channel is divided by 12.92.
        expected = (10 / 255) / 12.92
        self.assertAlmostEqual(dc.relative_luminance((10, 10, 10)), expected, places=9)

    def test_uses_the_power_branch_above_0_04045(self):
        # 11 / 255 = 0.04314, so the channel goes through the 2.4 power.
        expected = (((11 / 255) + 0.055) / 1.055) ** 2.4
        self.assertAlmostEqual(dc.relative_luminance((11, 11, 11)), expected, places=9)

    def test_weights_the_channels(self):
        self.assertAlmostEqual(dc.relative_luminance((255, 0, 0)), 0.2126, places=9)
        self.assertAlmostEqual(dc.relative_luminance((0, 255, 0)), 0.7152, places=9)
        self.assertAlmostEqual(dc.relative_luminance((0, 0, 255)), 0.0722, places=9)

    def test_accepts_a_hex_string(self):
        self.assertAlmostEqual(dc.relative_luminance("#FF0000"), 0.2126, places=9)


class ContrastRatio(unittest.TestCase):
    def test_white_on_black_is_21(self):
        self.assertEqual(round(dc.contrast_ratio("#FFFFFF", "#000000"), 2), 21.00)

    def test_grey_767676_on_white_is_4_54(self):
        self.assertEqual(round(dc.contrast_ratio("#767676", "#FFFFFF"), 2), 4.54)

    def test_grey_777777_on_white_is_4_48(self):
        self.assertEqual(round(dc.contrast_ratio("#777777", "#FFFFFF"), 2), 4.48)

    def test_the_ratio_is_not_rounded(self):
        self.assertLess(dc.contrast_ratio("#777777", "#FFFFFF"), 4.5)
        self.assertGreater(dc.contrast_ratio("#767676", "#FFFFFF"), 4.5)
        self.assertAlmostEqual(dc.contrast_ratio("#767676", "#FFFFFF"), 4.542224959605, places=9)

    def test_a_ratio_that_rounds_up_to_4_5_still_fails_a_floor_of_4_5(self):
        ratio = dc.contrast_ratio("#777773", "#FFFFFF")  # 4.49613
        self.assertEqual(round(ratio, 2), 4.5)
        self.assertLess(ratio, 4.5)

    def test_red_on_green_is_1_39(self):
        self.assertEqual(round(dc.contrast_ratio("#FF0000", "#00B050"), 2), 1.39)

    def test_yellow_on_blue_is_8_00(self):
        self.assertEqual(round(dc.contrast_ratio("#FFFF00", "#0000FF"), 2), 8.00)

    def test_yellow_on_navy_is_10_82(self):
        self.assertEqual(round(dc.contrast_ratio("#FFFF00", "#1F3864"), 2), 10.82)

    def test_the_ratio_is_symmetric(self):
        self.assertEqual(
            dc.contrast_ratio("#FFFF00", "#1F3864"),
            dc.contrast_ratio("#1F3864", "#FFFF00"),
        )

    def test_the_same_color_gives_1(self):
        self.assertEqual(dc.contrast_ratio("#6D4BD6", "#6D4BD6"), 1.0)

    def test_accepts_rgb_tuples_and_mixed_input(self):
        self.assertEqual(round(dc.contrast_ratio((255, 255, 255), (0, 0, 0)), 2), 21.00)
        self.assertEqual(round(dc.contrast_ratio("#FFFFFF", (0, 0, 0)), 2), 21.00)

    def test_rejects_a_bad_color(self):
        with self.assertRaises(ValueError):
            dc.contrast_ratio("#FFF", "#000000")
        with self.assertRaises(ValueError):
            dc.contrast_ratio((256, 0, 0), (0, 0, 0))
        with self.assertRaises(ValueError):
            dc.contrast_ratio((255, 255), (0, 0, 0))


class HueBand(unittest.TestCase):
    def test_names_the_bands_of_the_brief(self):
        self.assertEqual(dc.hue_band(dc.parse_hex("#FF2000")), "red")
        self.assertEqual(dc.hue_band(dc.parse_hex("#009E73")), "green")
        self.assertEqual(dc.hue_band(dc.parse_hex("#0072B2")), "other")
        self.assertEqual(dc.hue_band(dc.parse_hex("#808080")), "other")

    def test_red_covers_hue_below_15_and_from_345(self):
        self.assertEqual(dc.hue_band((255, 63, 0)), "red")  # hue 14.8
        self.assertEqual(dc.hue_band((255, 64, 0)), "other")  # hue 15.06
        self.assertEqual(dc.hue_band((255, 0, 63)), "red")  # hue 345.2
        self.assertEqual(dc.hue_band((255, 0, 64)), "other")  # hue 344.9

    def test_green_covers_hue_75_to_165(self):
        self.assertEqual(dc.hue_band((0, 255, 191)), "green")  # hue 164.9
        self.assertEqual(dc.hue_band((0, 255, 192)), "other")  # hue 165.2
        self.assertEqual(dc.hue_band((191, 255, 0)), "green")  # hue 75.06
        self.assertEqual(dc.hue_band((192, 255, 0)), "other")  # hue 74.8

    def test_black_white_and_greys_are_other(self):
        for color in [(0, 0, 0), (255, 255, 255), (128, 128, 128), (1, 1, 1), (254, 254, 254)]:
            with self.subTest(color=color):
                self.assertEqual(dc.hue_band(color), "other")

    def test_colors_with_blue_as_the_largest_channel_are_other(self):
        self.assertEqual(dc.hue_band((75, 0, 100)), "other")  # hue 285
        self.assertEqual(dc.hue_band((0, 75, 100)), "other")  # hue 195
        self.assertEqual(dc.hue_band((0, 0, 100)), "other")  # hue 240

    def test_saturation_must_be_at_least_0_4(self):
        self.assertEqual(dc.hue_band((190, 100, 100)), "red")  # saturation 0.409
        self.assertEqual(dc.hue_band((190, 105, 105)), "other")  # saturation 0.395
        self.assertEqual(dc.hue_band((100, 190, 100)), "green")  # saturation 0.409
        self.assertEqual(dc.hue_band((105, 190, 105)), "other")  # saturation 0.395
        self.assertEqual(dc.hue_band((160, 96, 96)), "other")  # saturation 0.25

    def test_saturation_of_exactly_0_4_counts_as_at_least_0_4(self):
        # (175, 75, 75) has saturation 100 / 250. Float arithmetic gives 0.39999999999999997.
        self.assertEqual(dc.hue_band((175, 75, 75)), "red")
        self.assertEqual(dc.hue_band((75, 175, 75)), "green")
        self.assertEqual(dc.hue_band((174, 74, 74)), "red")  # saturation 100 / 248 = 0.403
        self.assertEqual(dc.hue_band((175, 76, 76)), "other")  # saturation 99 / 251 = 0.394

    def test_a_hue_of_exactly_15_is_other_and_exactly_345_is_red(self):
        self.assertEqual(dc.hue_band((100, 25, 0)), "other")  # hue 15
        self.assertEqual(dc.hue_band((100, 24, 0)), "red")  # hue 14.4
        self.assertEqual(dc.hue_band((100, 0, 25)), "red")  # hue 345
        self.assertEqual(dc.hue_band((100, 0, 26)), "other")  # hue 344.4

    def test_a_hue_of_exactly_75_and_exactly_165_is_green(self):
        self.assertEqual(dc.hue_band((75, 100, 0)), "green")  # hue 75
        self.assertEqual(dc.hue_band((76, 100, 0)), "other")  # hue 74.4
        self.assertEqual(dc.hue_band((0, 100, 75)), "green")  # hue 165
        self.assertEqual(dc.hue_band((0, 100, 76)), "other")  # hue 165.6

    def test_lightness_must_be_from_0_15_to_0_85(self):
        self.assertEqual(dc.hue_band((75, 0, 0)), "other")  # lightness 0.147
        self.assertEqual(dc.hue_band((77, 0, 0)), "red")  # lightness 0.151
        self.assertEqual(dc.hue_band((255, 177, 177)), "red")  # lightness 0.847
        self.assertEqual(dc.hue_band((255, 179, 179)), "other")  # lightness 0.851
        self.assertEqual(dc.hue_band((38, 0, 0)), "other")  # lightness 0.075
        self.assertEqual(dc.hue_band((255, 204, 204)), "other")  # lightness 0.90

    def test_accepts_a_hex_string(self):
        self.assertEqual(dc.hue_band("#FF2000"), "red")


class RedGreenConflict(unittest.TestCase):
    def test_pure_red_and_the_office_green_conflict(self):
        self.assertTrue(dc.red_green_conflict("#FF0000", "#00B050"))

    def test_the_order_of_the_arguments_does_not_matter(self):
        self.assertTrue(dc.red_green_conflict("#00B050", "#FF0000"))

    def test_okabe_ito_vermillion_and_bluish_green(self):
        # Actual result: False. The ratio is 1.13, below 3.0, so contrast does
        # not clear the pair. The hue of #D55E00 is 26.5 degrees, above the red
        # limit of 15, so hue_band gives "other" and no conflict exists.
        self.assertEqual(round(dc.contrast_ratio("#D55E00", "#009E73"), 2), 1.13)
        self.assertEqual(dc.hue_band(dc.parse_hex("#D55E00")), "other")
        self.assertFalse(dc.red_green_conflict("#D55E00", "#009E73"))

    def test_a_red_and_green_pair_with_ratio_of_3_or_more_is_no_conflict(self):
        dark_red, light_green = "#8B0000", "#90EE90"
        self.assertEqual(dc.hue_band(dc.parse_hex(dark_red)), "red")
        self.assertEqual(dc.hue_band(dc.parse_hex(light_green)), "green")
        self.assertGreaterEqual(dc.contrast_ratio(dark_red, light_green), 3.0)
        self.assertFalse(dc.red_green_conflict(dark_red, light_green))

    def test_two_reds_and_two_greens_are_no_conflict(self):
        self.assertFalse(dc.red_green_conflict("#FF0000", "#FF2000"))
        self.assertFalse(dc.red_green_conflict("#00B050", "#009E73"))

    def test_a_red_and_a_blue_are_no_conflict(self):
        self.assertFalse(dc.red_green_conflict("#FF0000", "#0072B2"))


class OkabeIto(unittest.TestCase):
    def test_holds_the_eight_colors_of_the_brief(self):
        expected = ["#000000", "#E69F00", "#56B4E9", "#009E73",
                    "#F0E442", "#0072B2", "#D55E00", "#CC79A7"]
        self.assertEqual(dc.OKABE_ITO, expected)

    def test_holds_eight_distinct_valid_colors(self):
        self.assertEqual(len(dc.OKABE_ITO), 8)
        self.assertEqual(len(set(c.upper() for c in dc.OKABE_ITO)), 8)
        for color in dc.OKABE_ITO:
            with self.subTest(color=color):
                dc.parse_hex(color)
                self.assertTrue(color.startswith("#"))


if __name__ == "__main__":
    unittest.main()
