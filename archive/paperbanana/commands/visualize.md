---
allowed-tools:
  - Read
  - Write
  - Bash(paperbanana *)
  - Bash(pip install *)
  - Bash(which paperbanana)
  - Bash(echo *)
  - Bash(ls *)
  - Bash(cat *)
  - Bash(mkdir *)
description: Generate a publication-quality diagram from an idea, text description, or methodology section
argument-hint: ["idea text" or path/to/file.txt] [caption]
---

# Visualize — Turn Ideas into Diagrams

Generate a publication-quality methodology diagram from a text description or idea using PaperBanana's multi-agent pipeline (retrieval, planning, styling, rendering, and critic-driven refinement).

**Arguments:** `$ARGUMENTS`

Formats:
- `/visualize "My system has three stages: input, processing, output"` — inline idea
- `/visualize method.txt` — from a file
- `/visualize method.txt "Overview of our pipeline"` — file + explicit caption
- `/visualize` — no args: ask the user for their idea

## Steps

### Step 0: Check Environment

1. Check if `paperbanana` is installed:
   ```bash
   which paperbanana 2>/dev/null || echo "NOT_INSTALLED"
   ```

2. If NOT installed, install it:
   ```bash
   pip install paperbanana
   ```

3. Check for API key:
   ```bash
   echo "${GOOGLE_API_KEY:+SET}" || echo "NOT_SET"
   ```
   If not set, tell the user:
   > PaperBanana needs a Google API key (free tier). Run `paperbanana setup` or set `GOOGLE_API_KEY` in your `.env` file.
   > Get a free key at: https://aistudio.google.com/apikey

   Then stop and wait for the user to configure it.

### Step 1: Parse Arguments

Parse `$ARGUMENTS` to determine the input:

- **If the first argument is a file path** (ends in `.txt`, `.md`, or exists as a file): read it and use its contents as `source_context`.
- **If the first argument is a quoted string or plain text**: use it directly as `source_context`.
- **If no arguments**: ask the user: "What idea or system would you like to visualize? Describe the components, data flow, and relationships."

If a second argument exists, use it as the `caption`. Otherwise, generate a concise caption from the source text (one sentence summarizing what the diagram should show).

### Step 2: Prepare Input File

If the source text came from inline arguments (not a file), write it to a temporary file:

```bash
mkdir -p /tmp/paperbanana
```

Write the source text to `/tmp/paperbanana/input.txt`.

### Step 3: Generate Diagram

Run PaperBanana with optimization and iterative refinement:

```bash
paperbanana generate \
  --input <input_file> \
  --caption "<caption>" \
  --optimize \
  --iterations 3
```

Use `--optimize` by default because user-provided text is often unstructured.

### Step 4: Present Results

1. Read the output path from the command output.
2. Tell the user:
   - Where the final diagram is saved
   - That intermediate iterations are available in the run directory
   - How to refine: `/refine-diagram "Make the arrows thicker"` or run again with different caption

### Step 5: Offer Refinement

Ask if the user wants to:
- **Refine** the diagram with feedback (suggest `/refine-diagram`)
- **Regenerate** with a different caption or emphasis
- **Continue** with more iterations for higher quality

## Tips for Best Results

When helping the user formulate their idea, encourage them to mention:
- **Components/modules**: What are the key parts?
- **Data flow**: What goes in, what comes out, what connects to what?
- **Stages/phases**: Is there a sequential pipeline or parallel processing?
- **Groupings**: Are some components logically grouped?

A good source text looks like:
> "Our system has three stages: (1) A feature extractor CNN processes the input image, (2) an attention module fuses features from multiple scales, and (3) a classification head outputs predictions. The attention module receives skip connections from stages 1 and 3."

A vague source text like "a machine learning system" will produce poor results.
