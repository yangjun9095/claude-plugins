#!/usr/bin/env python3
"""Verification harness for generated PPTX slide decks.

Performs deterministic quality checks on a .pptx file and reports
pass/fail for each criterion.  Designed to run as a post-generation
gate in the generate-slides skill.

Usage:
    python verify_slides.py output.pptx [--style slide-style.yaml]

Exit code 0 = all checks pass, 1 = one or more failures.
"""

import argparse
import re
import sys
from pathlib import Path

from pptx import Presentation
from pptx.util import Emu

# ── Helpers ──────────────────────────────────────────────────────────

SLIDE_W_EMU = 12192000  # 13.333" in EMU
SLIDE_H_EMU = 6858000   #  7.5"   in EMU

# Words that strongly suggest a topic-label title (not a sentence).
TOPIC_LABEL_PATTERNS = [
    r"^results?$", r"^methods?$", r"^background$", r"^introduction$",
    r"^discussion$", r"^overview$", r"^summary$", r"^conclusions?$",
    r"^motivation$", r"^outline$", r"^agenda$", r"^objectives?$",
    r"^approach$", r"^next steps$", r"^future work$",
    r"^data$", r"^analysis$", r"^evaluation$", r"^implementation$",
    r"^model performance$", r"^experimental setup$",
]

THANK_YOU_PATTERNS = [
    r"thank\s*you", r"thanks?[\!\.]?$", r"questions\??$",
    r"q\s*&\s*a\??$", r"any questions\??$",
]


def _get_slide_title(slide):
    """Return the first text box's text as the slide title, or None."""
    for shape in slide.shapes:
        if shape.has_text_frame:
            text = shape.text_frame.text.strip()
            if text:
                return text
    return None


def _is_topic_label(title):
    """Check if a title looks like a topic label instead of a sentence."""
    t = title.strip().rstrip(".!?").lower()
    # Very short titles (1-3 words) without a verb are likely labels
    for pat in TOPIC_LABEL_PATTERNS:
        if re.match(pat, t, re.IGNORECASE):
            return True
    return False


def _is_sentence(title):
    """Heuristic: a sentence has >3 words or contains a verb-like structure."""
    words = title.strip().split()
    if len(words) >= 5:
        return True
    # 3-4 word titles can be sentences if they have a verb
    # but we can't reliably detect verbs without NLP, so we're lenient
    return len(words) >= 4


# ── Checks ───────────────────────────────────────────────────────────

class CheckResult:
    def __init__(self, name, passed, details=""):
        self.name = name
        self.passed = passed
        self.details = details

    def __str__(self):
        status = "PASS" if self.passed else "FAIL"
        s = f"  [{status}] {self.name}"
        if self.details:
            s += f"\n         {self.details}"
        return s


def check_action_titles(prs):
    """Verify slide titles are action titles (sentences), not topic labels."""
    issues = []
    for i, slide in enumerate(prs.slides, 1):
        title = _get_slide_title(slide)
        if title is None:
            continue
        # Skip title slide (slide 1) — it's the presentation title, not an action title
        if i == 1:
            continue
        if _is_topic_label(title):
            issues.append(f"Slide {i}: \"{title}\" looks like a topic label, not an action title")
    if issues:
        return CheckResult("Action titles", False, "; ".join(issues))
    return CheckResult("Action titles", True)


def check_ghost_deck(prs):
    """Print all titles sequentially for the ghost deck test."""
    titles = []
    for i, slide in enumerate(prs.slides, 1):
        title = _get_slide_title(slide)
        if title:
            titles.append(f"  {i}. {title}")
    ghost = "\n".join(titles)
    # This is informational — always passes but prints the ghost deck
    return CheckResult(
        "Ghost deck test (informational)",
        True,
        f"Read these titles in sequence — do they tell a complete story?\n{ghost}"
    )


def check_figure_bounds(prs):
    """Verify no images overflow the slide edges."""
    issues = []
    for i, slide in enumerate(prs.slides, 1):
        for shape in slide.shapes:
            if shape.shape_type == 13:  # Picture
                right = shape.left + shape.width
                bottom = shape.top + shape.height
                if right > SLIDE_W_EMU:
                    overflow_in = (right - SLIDE_W_EMU) / 914400
                    issues.append(f"Slide {i}: image overflows right edge by {overflow_in:.2f}\"")
                if bottom > SLIDE_H_EMU:
                    overflow_in = (bottom - SLIDE_H_EMU) / 914400
                    issues.append(f"Slide {i}: image overflows bottom edge by {overflow_in:.2f}\"")
    if issues:
        return CheckResult("Figure bounds", False, "; ".join(issues))
    return CheckResult("Figure bounds", True)


def check_font_consistency(prs, expected_font=None):
    """Check that all text uses the expected font family."""
    if expected_font is None:
        expected_font = "Avenir Light"
    off_font = {}
    for i, slide in enumerate(prs.slides, 1):
        for shape in slide.shapes:
            if not shape.has_text_frame:
                continue
            for para in shape.text_frame.paragraphs:
                for run in para.runs:
                    font = run.font.name
                    if font and font != expected_font and font != "PT Mono":
                        key = f"Slide {i}: \"{font}\""
                        off_font[key] = off_font.get(key, 0) + 1
    if off_font:
        details = "; ".join(f"{k} ({v} runs)" for k, v in off_font.items())
        return CheckResult("Font consistency", False, f"Expected \"{expected_font}\", found: {details}")
    return CheckResult("Font consistency", True)


def check_no_thank_you_ending(prs):
    """Verify the last main slide is not 'Thank You' or 'Questions?'."""
    if len(prs.slides) == 0:
        return CheckResult("Conclusions ending", True, "No slides")
    last_title = _get_slide_title(prs.slides[-1])
    if last_title:
        for pat in THANK_YOU_PATTERNS:
            if re.search(pat, last_title, re.IGNORECASE):
                return CheckResult(
                    "Conclusions ending", False,
                    f"Last slide title is \"{last_title}\" — should end with Conclusions, not Thank You/Questions"
                )
    return CheckResult("Conclusions ending", True)


def check_content_density(prs, max_bullets=6):
    """Flag slides with too many bullets (>max_bullets)."""
    issues = []
    for i, slide in enumerate(prs.slides, 1):
        for shape in slide.shapes:
            if not shape.has_text_frame:
                continue
            bullet_count = sum(
                1 for p in shape.text_frame.paragraphs
                if p.text.strip().startswith("\u2022") or p.level > 0
            )
            if bullet_count > max_bullets:
                issues.append(f"Slide {i}: {bullet_count} bullets (max {max_bullets})")
    if issues:
        return CheckResult("Content density", False, "; ".join(issues))
    return CheckResult("Content density", True)


def check_slide_count(prs):
    """Report slide count (informational)."""
    n = len(prs.slides)
    return CheckResult("Slide count", True, f"{n} slides")


# ── Main ─────────────────────────────────────────────────────────────

def verify(pptx_path, expected_font=None):
    """Run all checks and return (results, all_passed)."""
    prs = Presentation(pptx_path)
    results = [
        check_slide_count(prs),
        check_action_titles(prs),
        check_ghost_deck(prs),
        check_figure_bounds(prs),
        check_font_consistency(prs, expected_font),
        check_no_thank_you_ending(prs),
        check_content_density(prs),
    ]
    all_passed = all(r.passed for r in results)
    return results, all_passed


def main():
    parser = argparse.ArgumentParser(description="Verify a generated PPTX slide deck.")
    parser.add_argument("pptx", help="Path to the .pptx file to verify")
    parser.add_argument("--font", default=None, help="Expected body font (default: Avenir Light)")
    args = parser.parse_args()

    if not Path(args.pptx).exists():
        print(f"ERROR: File not found: {args.pptx}")
        sys.exit(1)

    print(f"Verifying: {args.pptx}")
    print("=" * 60)

    results, all_passed = verify(args.pptx, expected_font=args.font)

    for r in results:
        print(r)

    print("=" * 60)
    if all_passed:
        print("ALL CHECKS PASSED")
    else:
        n_fail = sum(1 for r in results if not r.passed)
        print(f"{n_fail} CHECK(S) FAILED — fix issues above before presenting")

    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
