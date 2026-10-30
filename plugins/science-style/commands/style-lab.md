---
description: Run the style lab of science-style for one or more people (discover, sample, fetch, extract, profile)
argument-hint: "<person ids | all> [--pilot]"
allowed-tools: Bash, Read, Write, Edit, Agent
---

# /style-lab

Run the style lab for the people named in `$ARGUMENTS`. The design is in `docs/superpowers/specs/2026-10-29-science-style-lab-design.md` of the plugin repository.

## Before you start

- `STYLE_LAB_DATA` must name a scratch folder outside the repository. Every full text goes there. If it is not set, ask the author for a folder.
- Run each step with `python3 -I ${CLAUDE_PLUGIN_ROOT}/lab/style_lab.py <step>`. Add `--pilot` to every step of a pilot.
- Give every subagent its model in the dispatch. This command uses Sonnet subagents and the session's own model. It gives no task to any other model.

## Steps

1. **Registry.** For a new person, run `style_lab.py candidates "<name>"`. Pick the OpenAlex records whose ORCID, institutions and titles match the person, and add an entry to `data/people.json`. When two people cannot be told apart, stop and ask the author.
2. **Discovery.** Run `style_lab.py discover <ids>`. The sample needs the works file of every person in the registry.
3. **Sample.** Run `style_lab.py sample <ids>`. Read every row of each new manifest: title, venue, tier and group. Fix a wrong rule with a failing test first.
4. **Fetch.** Run `style_lab.py fetch <ids>`. One process fetches for all people, because each host allows only a few requests per second. An exit with the message `network error` stops the run. Run the same command again to resume it. After a reader changes, run `style_lab.py normalize <ids>`.
5. **Surface.** Run `style_lab.py surface --all`. The distinctive word lists need at least 4 people.
6. **Extraction.** Split the fetched papers of each person into batches of at most 5. For each batch, dispatch one subagent with `model: sonnet` and this brief: read `${CLAUDE_PLUGIN_ROOT}/prompts/extract.md` first; then the checklist path, each paper path with its output path, group and run `main`, and the attempt number 1.
7. **Agreement.** Run `style_lab.py select agreement <ids>`. For each listed paper, dispatch a fresh subagent with `model: sonnet` and the same brief, with the run `agreement`.
8. **Quote check.** Run `style_lab.py check-quotes <ids>` and `style_lab.py check-quotes <ids> --run agreement`. Each command ends the output of every person with the line `<person>: N papers checked`. In the main run, N is the number of fetched papers of that person. When N is 0, the command checked nothing and still exits with 0; find out why before you go on. For each paper marked `redo`, dispatch a fresh subagent with `model: sonnet` and the attempt number 2, then check again.
9. **Spot check.** Run `style_lab.py select spot <ids>`. Read every answer of each listed paper against the paper file, and write the marks to `$STYLE_LAB_DATA/spot/<id>.json`.
10. **Profiles.** Run `style_lab.py aggregate <ids>`.
11. **Cards.** For each person, dispatch one subagent with `model: sonnet` and this brief: read `${CLAUDE_PLUGIN_ROOT}/prompts/card.md` first; then the paths of the profile data, the digest and the card. Run `style_lab.py check-card <id>`. Send a failed card to a fresh writer with the failures, once. Stop and report a second failure.
12. **Principles and quality.** Write `profiles/principles.md` yourself, following `prompts/principles.md`. Run `style_lab.py check-card principles`, then `style_lab.py quality`.
13. **Commit.** Commit the registry, the manifests and the files in `profiles/`. Never commit anything from `STYLE_LAB_DATA`.

Run `style_lab.py status` at any point to see the state of each person.
