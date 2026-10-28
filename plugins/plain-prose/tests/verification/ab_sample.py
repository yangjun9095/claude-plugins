"""Draw a blind A/B sample of reworded sentences for a human reader.

Command line: `python3 ab_sample.py ORIGINAL REVISED [--n 10] [--seed 7] --out DIR
[--format auto|latex|markdown|text]`.

The tool finds the reworded sentences with the same rules as `diff_report.py`. A reworded sentence
has a text in both files. A deleted sentence and an added sentence are no candidate. The tool
picks `n` of the candidates with a random generator that starts from `seed`, and keeps them in the
order of the manuscript. For each pick, it decides by chance which option holds the revised text.

Files in DIR.
- `ab-sample.md` shows each pick as two options, A and B. It does not say which option is revised.
  Give this file to the reader.
- `ab-key.json` tells for each item which option is the original and which is the revised text.
  Keep this file from the reader until the reader has answered.

The same inputs and the same seed give the same two files. A different seed gives a different
pick and a different order of the options.

Exit codes: 0 success, 2 the tool could not run. Code 2 covers fewer than `n` reworded sentences, a bad
`n`, an unreadable input and a DIR that already holds one of the two files. Then the tool writes
nothing, and the message goes to stderr.
"""
import argparse
import io
import json
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import diff_report as dr  # noqa: E402
from prose_mask import detect_format  # noqa: E402

PROG = "ab_sample.py"
SAMPLE_NAME = "ab-sample.md"
KEY_NAME = "ab-key.json"
DEFAULT_N = 10
DEFAULT_SEED = 7

INTRO = (
    "# A/B sample\n\n"
    "Each item shows one passage in two versions, A and B. Read both versions of each item.\n"
    "Write A, B or same for the version that reads better. Judge the sentence as prose.\n"
)


def pick(pairs, n, seed):
    """Return n items as dicts with `original`, `revised` and `revised_is`, in the order of the pairs.

    `revised_is` is "A" or "B": the option that holds the revised text.
    """
    rng = random.Random(seed)
    chosen = sorted(rng.sample(range(len(pairs)), n))
    items = []
    for number, index in enumerate(chosen, 1):
        swap = rng.random() < 0.5
        items.append({
            "item": number, "original": pairs[index]["before"], "revised": pairs[index]["after"],
            "revised_is": "A" if swap else "B"})
    return items


def sample_text(items):
    """Return the text of `ab-sample.md`. It holds no hint of the revised side."""
    blocks = [INTRO]
    for item in items:
        options = {"A": item["original"], "B": item["revised"]}
        if item["revised_is"] == "A":
            options = {"A": item["revised"], "B": item["original"]}
        blocks.append("## Item %d\n\nA. %s\n\nB. %s\n" % (item["item"], options["A"], options["B"]))
    return "\n".join(blocks)


def key_data(items, args):
    rows = []
    for item in items:
        rows.append({
            "item": item["item"], "A": "revised" if item["revised_is"] == "A" else "original",
            "B": "revised" if item["revised_is"] == "B" else "original",
            "original": item["original"], "revised": item["revised"]})
    return {"seed": args.seed, "n": args.n, "original_file": args.original, "revised_file": args.revised, "items": rows}


def _write(path, text):
    with io.open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def _parser():
    parser = argparse.ArgumentParser(prog=PROG, description="Draw a blind A/B sample of reworded sentences.")
    parser.add_argument("original", metavar="ORIGINAL")
    parser.add_argument("revised", metavar="REVISED")
    parser.add_argument("--n", type=int, default=DEFAULT_N, help="number of items (default %d)" % DEFAULT_N)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED, help="seed of the random generator (default %d)" % DEFAULT_SEED)
    parser.add_argument("--out", required=True, metavar="DIR")
    parser.add_argument("--format", choices=("auto",) + dr.FORMATS, default="auto", help="default: from the extension of ORIGINAL")
    return parser


def main(argv=None, err=None):
    """Run the command line. Return the exit code."""
    err = err or sys.stderr
    try:
        args = _parser().parse_args(argv)
    except SystemExit as stop:
        return stop.code
    try:
        if args.n < 1:
            raise dr.ToolError("--n must be at least 1.")
        original, revised = dr.read_text(args.original), dr.read_text(args.revised)
        fmt = detect_format(args.original) if args.format == "auto" else args.format
        pairs = dr.reworded(dr.changed_sentences(original, revised, fmt))
        if len(pairs) < args.n:
            raise dr.ToolError("only %d sentences changed. The sample needs %d." % (len(pairs), args.n))
        sample_path, key_path = os.path.join(args.out, SAMPLE_NAME), os.path.join(args.out, KEY_NAME)
        for path in (sample_path, key_path):
            if os.path.exists(path):
                raise dr.ToolError("%s exists. Remove it or choose another folder." % path)
        items = pick(pairs, args.n, args.seed)
        os.makedirs(args.out, exist_ok=True)
        _write(sample_path, sample_text(items))
        _write(key_path, json.dumps(key_data(items, args), ensure_ascii=False, indent=2) + "\n")
    except dr.ToolError as error:
        err.write("%s: error: %s\n" % (PROG, error))
        return 2
    except OSError as error:
        err.write("%s: error: cannot write %s: %s.\n" % (PROG, args.out, error.strerror or error))
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
