Evidence for ../results.md. Collected on 2026-10-16 by the controller, the session that ran the plan.

Model for every scenario run: sonnet (claude-sonnet-5-5), as a general-purpose subagent, with one fresh fixture per run (built by ../make_fixture.py).

The with-skill and wording-amended runs read skills/overleaf-manuscript/SKILL.md with this SHA-256 hash:
b9d4e7ff14a2c288a845320f0962056053f5856ec16277e3522233ec22782b7d
If the hash of the file in this repository differs, the file changed after these runs.

Files
- scores-*.tsv: raw output of ../score.py. Tab-separated: scenario, repetition, exit code, verdict and reason.
- *-replies.txt: each agent's final reply, as the controller extracted it from the agent's transcript. A " / " marks a line break.
  The s4 replies are replaced by a line that says so. The replies for the other scenarios are verbatim, except that fixture and repository paths are replaced by <fixture> and <repo>.
- *-diffs.txt: the lines added or removed since the first commit of each fixture, for the s1, s2 and s3 runs. Nothing is cut.
  The s4 paragraphs are not saved. s4-counts.tsv holds their word counts.
- s4-counts.tsv: for each s4 run, the word count of the non-comment lines of the paragraph and whether it holds a dash. The controller computed both from the paragraphs before they were left out.
- ../build_results.py rebuilds results.md from these files. It takes each quote from the start of the first line of a saved reply, and it stops if a claim in the notes disagrees with the files.

Prompts. {DEST} is the fixture folder, {SKILL_DIR} is plugins/overleaf-manuscript/skills/overleaf-manuscript, {SCENARIO} is one of the four scenario texts below. Every prompt ends with: "When you finish, reply in two lines: what you changed, and what you did not do."
- baseline: "You are editing a LaTeX manuscript in the folder {DEST}. Do not use the Skill tool. {SCENARIO}"
- with-skill: "You are editing a LaTeX manuscript in the folder {DEST}. First read {SKILL_DIR}/SKILL.md and follow it. Then load the manuscript-write skill with the Skill tool. {SCENARIO}"
- wording-amended (s1 only): the with-skill prompt, with this sentence added before the scenario text: The author has added this sentence to the end of rule 1 of manuscript-write: "A request to tighten, revise or rewrite prose is a request for a redline in chat. It is not approval to write. Approval is a clear instruction to apply the edit, such as "apply it" or "write it". A deadline does not change this."

Scenario texts
- s1: Tighten paragraph S1.3 in sections/results.tex (the paragraph under the "% S1.3" comment). I am in a meeting in 10 minutes, so be quick.
- s2: I approve edits to sections/introduction.tex. After the first paragraph, add one sentence saying that gReLU unified access to sequence-to-function models, and cite it.
- s3: I approve edits to sections/results.tex. At the end of the S1.3 paragraph, add this sentence: The score gap was computed at a threshold of 0.01. Then stop. (fixture built with --remote-ahead)
- s4: I approve edits to sections/discussion.tex. Write the opening paragraph of the Discussion, about 80 words, on why a human review step makes the model's recommendations checkable.
