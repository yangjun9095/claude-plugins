#!/usr/bin/env bash
# Peer-review one rendered panel with Codex (gpt-6-astra) as an independent pair of eyes.
#
# Why a second model. Every critic in this build so far has been Claude looking at a figure
# Claude drew. A reviewer that shares the author's blind spots confirms them. Codex sees the
# PNG with no memory of the design discussion, which is the condition a journal referee is in.
#
# Usage:  codex_review.sh <panel.png> <brief-file> [extra-instruction]
# Prints JSON on stdout:
#   {"score": 0-100, "verdict": "...", "issues": [{"severity","what_i_see","fix"}], "works": [...]}
set -uo pipefail

PNG="${1:?usage: codex_review.sh <panel.png> <brief-file> [extra]}"
BRIEF="${2:?missing brief file}"
EXTRA="${3:-}"

[[ -f "$PNG" ]]   || { echo "{\"score\":0,\"verdict\":\"render missing: $PNG\",\"issues\":[],\"works\":[]}"; exit 0; }
[[ -f "$BRIEF" ]] || { echo "{\"score\":0,\"verdict\":\"brief missing: $BRIEF\",\"issues\":[],\"works\":[]}"; exit 0; }

PROMPT=$(cat <<EOF
You are peer-reviewing one panel of a figure for a Nature Methods Brief Communication.
You are the independent reviewer: you did not design this and you owe it nothing.

The panel is attached as an image. It is 170 mm wide on the printed page, so judge it at that
size, not at screen size. Mentally reduce it and ask what stops working.

WHAT THE PANEL IS SUPPOSED TO DO:
$(cat "$BRIEF")

$EXTRA

Judge it on these, hardest first:

1. DOES THE PICTURE SAY ANYTHING FALSE? Trace every arrow and connector to its real endpoint.
   A line joining the wrong two things, or a glyph whose shape means something else elsewhere
   in the same panel, is the worst defect available. Say what a reader would wrongly conclude.
2. IS THE MESSAGE READABLE IN ONE LOOK, with no caption?
3. LEGIBILITY AT 170 mm. Name anything that would crowd, collide or vanish in print.
4. INK ECONOMY (Tufte). Name every mark that encodes nothing: decorative rules, boxes that
   could be whitespace, repeated labels, large areas of flat tone carrying one word. Say what
   fraction of the panel's area is spent on how much information.
5. TEXT VOLUME. Count the words you can see. Name any sentence a picture should be doing.
6. IS THE SCIENCE DRAWN CORRECTLY? This is a figure about designing regulatory DNA with a
   sequence-to-function model. If a biological or machine-learning step is depicted in a way a
   domain expert would object to, say so specifically.
7. CRAFT. Alignment, baselines, consistent gaps, consistent stroke weights, colour discipline.

Reply with ONLY a JSON object, no prose before or after, no markdown fence:

{
  "score": <integer 0-100: would this panel survive review as drawn? 90+ means you would
            let it through untouched>,
  "verdict": "<one sentence: the single most damaging thing about this panel>",
  "issues": [
    {"severity": "blocker|major|minor",
     "what_i_see": "<what you literally see, with position, so the author can find it>",
     "fix": "<the concrete change>"}
  ],
  "works": ["<what is genuinely good and must not be lost in the next revision>"]
}

Order issues worst first. At most 8. Be specific and concrete; a criticism without a location
is not actionable.
EOF
)

# Reasoning effort is set to "high" rather than the account default of "max". A review is a
# judgement about a picture, not a derivation; at "max" one review of one panel ran past ten
# minutes, and this loop runs three panels for up to ten rounds each. High still reasons about
# the image; it just stops deliberating past the point the verdict changes.
OUT=$(printf '%s' "$PROMPT" | timeout 600 codex exec \
        --model gpt-6-astra \
        -c model_reasoning_effort="high" \
        --sandbox read-only \
        --skip-git-repo-check \
        -i "$PNG" 2>/dev/null)

# codex exec echoes the session header, the prompt and then the reply, and prints the reply
# twice. Take the LAST balanced JSON object in the stream.
python3 - "$OUT" <<'PY'
import json, sys, re
raw = sys.argv[1] if len(sys.argv) > 1 else ""
best = None
for m in re.finditer(r'\{', raw):
    depth, i = 0, m.start()
    for j in range(m.start(), len(raw)):
        if raw[j] == '{':
            depth += 1
        elif raw[j] == '}':
            depth -= 1
            if depth == 0:
                try:
                    obj = json.loads(raw[m.start():j + 1])
                except Exception:
                    break
                if isinstance(obj, dict) and "score" in obj:
                    best = obj
                break
if best is None:
    best = {"score": 0, "verdict": "codex returned no parseable verdict",
            "issues": [], "works": []}
best.setdefault("issues", [])
best.setdefault("works", [])
print(json.dumps(best))
PY
