---
allowed-tools:
  - Read
  - Write
  - Bash(paperbanana *)
  - Bash(which paperbanana)
  - Bash(ls *)
  - Bash(find * -name)
  - Glob
description: Refine a previously generated PaperBanana diagram with feedback
argument-hint: "feedback text" [--run path/to/run_dir]
---

# Refine Diagram — Iterate on a Previous Generation

Continue refining a previously generated PaperBanana diagram with user feedback.

**Arguments:** `$ARGUMENTS`

Formats:
- `/refine-diagram "Make arrows thicker and add labels to each stage"` — refine most recent run
- `/refine-diagram "Use blue-green palette" --run outputs/run_20260318_abc` — refine specific run
- `/refine-diagram` — ask for feedback

## Steps

### Step 1: Parse Arguments

- **Feedback text**: The main argument — what to change about the diagram. If not provided, ask the user what they want to improve.
- **`--run` flag** (optional): Path to a specific run directory. If not provided, use the most recent run.

### Step 2: Find the Run to Continue

If no `--run` specified, find the most recent run:

```bash
ls -dt outputs/run_* 2>/dev/null | head -1
```

If no runs found, check common output locations:

```bash
find . -maxdepth 3 -type d -name "run_*" 2>/dev/null | head -5
```

If still no runs found, tell the user:
> "No previous PaperBanana runs found. Use `/visualize` first to generate a diagram, then `/refine-diagram` to iterate on it."

### Step 3: Show Current State

Read the run's metadata to remind the user what was generated:

```bash
ls <run_dir>/
```

Tell the user which run is being continued and what the original input/caption was (from metadata.json if available).

### Step 4: Refine

```bash
paperbanana generate --continue \
  --continue-run <run_dir> \
  --feedback "<feedback_text>" \
  --iterations 3
```

### Step 5: Present Results

1. Show where the refined diagram is saved.
2. Compare: "Iteration N (before feedback) vs Iteration N+3 (after feedback)."
3. Offer another round: "Want to refine further? Just run `/refine-diagram` again with new feedback."

## Common Refinement Prompts

These work well as feedback:
- "Make the arrows thicker and more prominent"
- "Use a blue-to-green color gradient instead of the current palette"
- "Add dimension annotations (e.g., 512, 1024) to each layer"
- "Simplify — remove the details inside each block, just show the flow"
- "Make it horizontal instead of vertical"
- "Add a legend explaining the color coding"
- "Increase contrast between the background and the components"
