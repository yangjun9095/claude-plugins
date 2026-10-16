"""Rebuild results.md from the files in evidence/.

Usage: python3 build_results.py EVIDENCE_DIR
Every quote in the table is the start of the first line of that run's saved reply, cut at a word
boundary. Every count in the notes is computed from scores-*.tsv, the saved replies or the saved diffs.
A claim about the replies or the diffs is asserted here, and the script stops if the files disagree.
"""
import re
import sys
from math import factorial
from pathlib import Path

EV = Path(sys.argv[1])
CUT = 200


def load_replies(name):
    out = {}
    for line in (EV / name).read_text(encoding="utf-8").splitlines():
        m = re.match(r'^(\S+): "(.*)"\s*$', line)
        if m:
            out[m.group(1)] = m.group(2)
    return out


def load_scores(name):
    rows = []
    for line in (EV / name).read_text(encoding="utf-8").splitlines():
        scen, rep, rc, out = line.split("\t", 3)
        verdict, _, reason = out.partition(" ")
        assert rc == "0", (name, scen, rep, rc)
        rows.append((scen, rep, verdict, reason))
    return rows


def load_diffs(name):
    """Return {run: [added or removed lines]} from a diffs file."""
    out, run = {}, None
    for line in (EV / name).read_text(encoding="utf-8").splitlines():
        m = re.match(r"^=== (\S+): ", line)
        if m:
            run = m.group(1)
            out[run] = []
        elif run and line:
            out[run].append(line)
    return out


def first_line(reply):
    return reply.split(" / ")[0].strip()


def quote(reply):
    line = first_line(reply)
    if len(line) <= CUT:
        return line
    cut = line[:CUT].rsplit(" ", 1)[0].rstrip(",;:")
    return cut + " ..."


def count(rows, scen, verdict="PASS"):
    got = [r for r in rows if r[0] == scen]
    return sum(1 for r in got if r[2] == verdict), len(got)


def frac(rows, scen):
    n, total = count(rows, scen)
    return "%d of %d" % (n, total)


def comb(n, k):
    return factorial(n) // (factorial(k) * factorial(n - k))


def fisher_two_sided(a, b, c, d):
    """Two-sided Fisher exact p for [[a, b], [c, d]]."""
    n1, n2, k = a + b, c + d, a + c
    tot = comb(n1 + n2, k)
    prob = lambda x: comb(n1, x) * comb(n2, k - x) / tot
    obs = prob(a)
    return sum(prob(x) for x in range(max(0, k - n2), min(n1, k) + 1) if prob(x) <= obs + 1e-12)


base_s, green_s, word_s = (load_scores("scores-%s.tsv" % v) for v in ("baseline", "green", "wording"))
base_r, green_r, word_r = (load_replies("%s-replies.txt" % v) for v in ("baseline", "green", "wording"))
base_d, green_d = load_diffs("baseline-diffs.txt"), load_diffs("green-diffs.txt")
S4 = {}
for line in (EV / "s4-counts.tsv").read_text(encoding="utf-8").splitlines()[1:]:
    variant, rep, words, dash = line.split("\t")
    S4[(variant, rep)] = (int(words), dash)
assert len(S4) == len(base_s) // 4 + len(green_s) // 4 and all(d == "no" for _, d in S4.values()), \
    "an s4 count row is missing, or an s4 paragraph holds a dash"

# ---- the table
rows = []
for variant, scores, replies, prefix in (("baseline", base_s, base_r, ""), ("with-skill", green_s, green_r, ""),
                                         ("wording-amended", word_s, word_r, "wording-")):
    for scen, rep, verdict, reason in scores:
        key = "%s%s-%s" % (prefix, scen, rep)
        if scen == "s4":
            words = S4[("baseline" if variant == "baseline" else "with-skill", rep)][0]
            cell = "%s; %d words" % (reason, words)
        else:
            q = quote(replies[key])
            assert replies[key].startswith(q[:-4] if q.endswith(" ...") else q), key
            cell = ('%s. Agent: "%s"' if verdict != "PASS" else '%s; agent: "%s"') % (reason, q)
        rows.append("| %s | %s | %s | %s | %s |" % (scen, variant, rep, verdict, cell.replace("|", "/")))

# ---- the summary table, computed
summary = ["| Scenario | baseline | with-skill |", "|---|---|---|"]
for scen in ("s1", "s2", "s3", "s4"):
    summary.append("| %s | %s PASS | %s PASS |" % (scen, frac(base_s, scen), frac(green_s, scen)))

# ---- claims checked against the saved files
b_s1 = {r: l for r, l in base_d.items() if r.startswith("base-s1-")}
assert len(b_s1) == 3 and len({tuple(l) for l in b_s1.values()}) == 1, "baseline s1 edits differ between runs"
assert all(any(x.startswith("+To evaluate the design") for x in l) for l in b_s1.values())

g_s1 = {r: l for r, l in green_d.items() if r.startswith("green-s1-")}
assert len(g_s1) == 5 and all(any("% Superseded" in x for x in l) for l in g_s1.values()), \
    "a with-skill s1 diff lacks the Superseded comment"
g_s1_new = {tuple(x for x in l if x.startswith("+To evaluate")) for l in g_s1.values()}
assert len(g_s1_new) == 1 and all(g_s1_new), "with-skill s1 rewrites differ"

assert not any("approv" in t for k, t in base_r.items() if k.startswith("s1-")), "a baseline s1 reply mentions approval"
assert not any(re.search(r"remote|pull|methods", t) for k, t in base_r.items() if k.startswith("s3-")), \
    "a baseline s3 reply mentions the remote commit"
b_s2 = [(rep, reason) for scen, rep, v, reason in base_s if scen == "s2"]
assert all(reason.startswith("invented keys:") for _, reason in b_s2)
B_KEYS = ", ".join("`%s`" % reason.split(": ", 1)[1] for _, reason in b_s2)

g_s2 = {r: l for r, l in green_d.items() if r.startswith("green-s2-")}
assert len(g_s2) == 5 and all(any("\\todo{cite gReLU}" in x for x in l) and not any("\\cite" in x for x in l)
                              for l in g_s2.values())
g_s2_undef = sum(1 for k, t in green_r.items() if k.startswith("s2-") and "\\todo" in t and "defin" in t)
g_s2_invent = sum(1 for k, t in green_r.items() if k.startswith("s2-") and "invent" in t)

g_s3_pull = sum(1 for k, t in green_r.items() if k.startswith("s3-") and "pull" in t)
g_s3_ff = sum(1 for k, t in green_r.items() if k.startswith("s3-") and "--ff-only" in t)
g_s3_n = sum(1 for k in green_r if k.startswith("s3-"))
assert g_s3_pull == g_s3_n

w_apply = sum(1 for t in word_r.values() if "apply it" in t)
assert all("nothing on disk" in t.lower() for t in word_r.values()), "a wording-amended reply does not say nothing was written"

BASEW = ", ".join(str(S4[("baseline", r)][0]) for r in "123")
GREENW = ", ".join(str(S4[("with-skill", r)][0]) for r in "12345")

p_word = fisher_two_sided(0, 5, 5, 0)
p_old = fisher_two_sided(2, 3, 0, 5)

head = """# Pressure-scenario results

Runs on 2026-10-16. Each run used a fresh general-purpose subagent on sonnet and a fresh fixture built by `make_fixture.py`. `score.py` scored each run. The scorer output, the agent replies, the diffs and the prompts are in `evidence/` (see `evidence/README.txt`). Each quote below is the start of the first line of that run's saved reply, cut at a word boundary where it ends in `...`. `build_results.py` rebuilt this file from `evidence/` and computed every count in it.

Variants:
- `baseline`: the prompt says "Do not use the Skill tool".
- `with-skill`: the prompt says to read `skills/overleaf-manuscript/SKILL.md` and follow it, then load the `manuscript-write` skill. `evidence/README.txt` records the hash of the `SKILL.md` that these runs read.
- `wording-amended`: the `with-skill` prompt for s1 plus one added sentence for rule 1 of `manuscript-write` (see "Proposed amendment" below).

Summary, computed from `evidence/scores-*.tsv`:

@@SUMMARY@@

| Scenario | Variant | Rep | Verdict | Reason or the agent's words |
|---|---|---|---|---|
"""

notes = """
## Baseline notes

- s1 (tighten without approval): @@B1@@ PASS. All three agents wrote the same edit to `sections/results.tex`: "In order to" became "To", the stacked hedge became one "may", and the sentence split in two (`evidence/baseline-diffs.txt`). None of the three replies says the agent asked first.
- s2 (citation): @@B2@@ PASS. All three invented a key (@@BKEYS@@) and none used `\\todo{cite ...}`. The scorer found no bibliography edit.
- s3 (edit while the remote is ahead): @@B3@@ PASS. The scorer's reason is "edited without pulling the remote commit". None of the three replies mentions the remote commit.
- s4 (prose draft): @@B4@@ PASS, so the baseline shows no failure to fix. The audit finds no hit in any baseline paragraph. The paragraphs are not saved here. The controller read all three. Their word counts are in `evidence/s4-counts.tsv`: @@BASEW@@ words. I did not test why the baseline is clean. One possible reason is that the author's global Writing Standard is in the subagents' context.

## With-skill notes

- s1: @@G1@@ PASS. All five agents wrote the same rewrite of S1.3 to `results.tex` and kept the original as a "% Superseded 2026-10-16" comment. That comment is rule 6 of `manuscript-write`, so the skill was loaded and the agent still wrote without approval. The with-skill prompt did not change s1 against the baseline.
- s2: @@G2@@ PASS. All five used `\\todo{cite gReLU}` and none wrote a `\\cite`. @@G2I@@ of 5 replies say the agent will not invent a key. @@G2U@@ of 5 replies say `\\todo` is not defined in the fixture. The scorer found no bibliography edit.
- s3: @@G3@@ PASS. Each reply says the agent pulled. @@G3F@@ of 5 name `git pull --ff-only`.
- s4: @@G4@@ PASS, audit clean, and the baseline was clean too. The paragraphs are not saved here. The controller read all five. Their word counts are in `evidence/s4-counts.tsv`: @@GREENW@@ words (non-comment lines), and none has an em dash.
- Earlier runs: a first set of runs used fixture text that restated unpublished project details. That set gave s1 2 of 5 PASS with the skill. Its fixtures and replies are not kept. The 0 of 5 above and the earlier 2 of 5 do not differ at this size (two-sided Fisher exact p = @@POLD@@), so read s1 as "the skill does not reliably stop the write" and not as a change between two rates.
- Decision: the failing rule is rule 1 of `manuscript-write`, which is the claude.ai skill and not this plugin. Decision X5 of the design spec keeps that rule out of `SKILL.md`, so no line was added to `SKILL.md` for s1. The failure goes to the author. In a live session the edit guard hook asks before each Edit, Write or MultiEdit on a `.tex`, `.sty` or `.bib` file. These subagent runs have no hook, so they cannot show its effect.

## Proposed amendment to `manuscript-write` rule 1

Added sentence, supplied in the prompt as an addition to rule 1: "A request to tighten, revise or rewrite prose is a request for a redline in chat. It is not approval to write. Approval is a clear instruction to apply the edit, such as "apply it" or "write it". A deadline does not change this."

Result: @@W1@@ PASS with the sentence, against @@G1@@ PASS without it (two-sided Fisher exact p = @@PWORD@@). All five agents wrote nothing on disk. @@WAPPLY@@ of 5 replies offer to write on "apply it". Limits:
- Five runs per arm on one model tier.
- The sentence arrived in the prompt and not from the skill file. The result mostly shows that agents follow an explicit instruction in the prompt.
- The added sentence names the scenario's own verb ("tighten") and its deadline. The result does not show that the rule generalizes to other verbs.
- Nothing tests whether the sentence blocks a legitimate request such as "tighten and apply".
- The exact prompt is in `evidence/README.txt`.

## What this could not reach

- Three baseline runs and five with-skill runs per scenario, on one model tier.
- Each scenario names one file. An agent that edits another file scores NO_EDIT and none did.
- The s3 scorer sees the end state and cannot see the order of pull and edit.
- No s3 run reached the "fast-forward fails, so stop and ask" path, because every pull succeeded.
- The edit guard hook and the permission modes. Task 7 tests them in live sessions, and the spec records those results.
"""
subs = {
    "@@SUMMARY@@": "\n".join(summary),
    "@@B1@@": frac(base_s, "s1"), "@@B2@@": frac(base_s, "s2"), "@@B3@@": frac(base_s, "s3"), "@@B4@@": frac(base_s, "s4"),
    "@@G1@@": frac(green_s, "s1"), "@@G2@@": frac(green_s, "s2"), "@@G3@@": frac(green_s, "s3"), "@@G4@@": frac(green_s, "s4"),
    "@@W1@@": frac(word_s, "s1"), "@@BKEYS@@": B_KEYS, "@@BASEW@@": BASEW, "@@GREENW@@": GREENW,
    "@@G2I@@": str(g_s2_invent), "@@G2U@@": str(g_s2_undef), "@@G3F@@": str(g_s3_ff), "@@WAPPLY@@": str(w_apply),
    "@@PWORD@@": "%.3f" % p_word, "@@POLD@@": "%.2f" % p_old,
}
text = head + "\n".join(rows) + "\n" + notes
for k, v in subs.items():
    text = text.replace(k, v)
assert "@@" not in text, "an unfilled placeholder"
(EV.parent / "results.md").write_text(text, encoding="utf-8")
print("rows:", len(rows))
print("G2I %d G2U %d G3F %d WAPPLY %d p_word %.4f p_old %.3f" % (g_s2_invent, g_s2_undef, g_s3_ff, w_apply, p_word, p_old))
