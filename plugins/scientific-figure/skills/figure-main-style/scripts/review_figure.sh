#!/usr/bin/env bash
# Referee one composed main figure with Codex (gpt-6-astra), as a second pair of eyes.
#
# The panel reviewer (scientific-figure/scripts/codex_review.sh) judges one panel. This one
# judges the PAGE: how the panels sit together, what the reader sees first, and what belongs
# in the legend instead of the figure. It is not told the measured house taste, so it judges
# as a referee would. The checker (check_main_figure.py) holds the measured taste.
#
# Usage:  bash review_figure.sh <figure.png> <brief-file> <width-mm> [extra-instruction]
# Prints one JSON object on stdout:
#   {"score": 0-100, "verdict": "...", "issues": [{"severity","where","what_i_see","fix"}],
#    "works": [...]}
set -uo pipefail

PNG="${1:?usage: review_figure.sh <figure.png> <brief-file> <width-mm> [extra]}"
BRIEF="${2:?missing brief file}"
WIDTH="${3:?missing printed width in mm}"
EXTRA="${4:-}"

[[ -f "$PNG" ]]   || { echo "{\"score\":0,\"verdict\":\"render missing: $PNG\",\"issues\":[],\"works\":[]}"; exit 0; }
[[ -f "$BRIEF" ]] || { echo "{\"score\":0,\"verdict\":\"brief missing: $BRIEF\",\"issues\":[],\"works\":[]}"; exit 0; }

PROMPT=$(cat <<EOF
You are the referee and the art editor for one main figure of a journal paper.
You did not make this figure and you owe it nothing.

The figure is attached as an image. It prints ${WIDTH} mm wide. Judge it at that size:
mentally shrink it to ${WIDTH} mm and ask what stops working.

WHAT THE FIGURE IS SUPPOSED TO SHOW:
$(cat "$BRIEF")

$EXTRA

Judge the figure as a page, hardest first:

1. DOES ANYTHING READ FALSE? A legend mark that does not match the marks it names, a panel
   letter that sits nearer the wrong panel, one colour meaning two things in two panels.
2. ORDER. Can a reader find the panels in order and tell where each panel ends?
3. SPACING. Is the white between panels clearly wider than the white inside a panel? Are the
   gaps between panels equal where they should be equal?
4. TYPE. How many type sizes do you see? Do the panel letters share one size, weight and
   baseline? Name any text too small to read at ${WIDTH} mm.
5. TEXT THAT BELONGS IN THE LEGEND. Footnotes, method details, sample sizes, seeds and
   sentences printed inside the figure. Name each and where it should go.
6. AREA. Name any panel that is larger than its content needs, any large empty region, and
   any panel too cramped to read. Say what share of the page carries data.
7. COLOUR. How many hues carry meaning? Does each hue keep one meaning across panels?
8. ALIGNMENT. Panel edges, axis lines and baselines that almost align but do not.

Reply with ONLY a JSON object, no prose before or after, no markdown fence:

{
  "score": <integer 0-100: would this figure pass a journal art editor as composed? 90+
            means you would let it through untouched>,
  "verdict": "<one sentence: the single most damaging thing about this figure>",
  "issues": [
    {"severity": "blocker|major|minor",
     "where": "<panel letter and position, for example 'b, lower left'>",
     "what_i_see": "<what you literally see>",
     "fix": "<the concrete change>"}
  ],
  "works": ["<what is good and must not be lost in the next revision>"]
}

Order issues worst first. At most 8. A criticism without a location is not actionable.
EOF
)

# Effort "high", not the account default "max": at max one review ran past ten minutes,
# and a review is a judgement about a picture, not a derivation.
OUT=$(printf '%s' "$PROMPT" | timeout 900 codex exec \
        --model gpt-6-astra \
        -c model_reasoning_effort="high" \
        --sandbox read-only \
        --skip-git-repo-check \
        -i "$PNG" 2>/dev/null)

# codex exec echoes the header and the prompt, then prints the reply twice. Take the LAST
# balanced JSON object that carries a "score" key.
python3 - "$OUT" <<'PY'
import json, sys
raw = sys.argv[1] if len(sys.argv) > 1 else ""
best = None
for start in [i for i, ch in enumerate(raw) if ch == "{"]:
    depth = 0
    for j in range(start, len(raw)):
        if raw[j] == "{":
            depth += 1
        elif raw[j] == "}":
            depth -= 1
            if depth == 0:
                try:
                    obj = json.loads(raw[start:j + 1])
                except ValueError:
                    break
                if isinstance(obj, dict) and "score" in obj:
                    best = obj
                break
if best is None:
    best = {"score": 0, "verdict": "codex returned no parseable verdict",
            "issues": [], "works": []}
best.setdefault("issues", [])
best.setdefault("works", [])
print(json.dumps(best, indent=1))
PY
