---
allowed-tools:
  - Read
  - Write
  - Bash(paperbanana *)
  - Bash(pip install *)
  - Bash(which paperbanana)
  - Bash(echo *)
  - Bash(ls *)
  - Bash(mkdir *)
description: Generate a publication-quality statistical plot from data
argument-hint: path/to/data.csv [intent]
---

# Plot — Generate Statistical Plots from Data

Generate a publication-quality statistical plot from CSV or JSON data using PaperBanana.

**Arguments:** `$ARGUMENTS`

Formats:
- `/plot results.csv "Grouped bar chart comparing accuracy across models"` — CSV + intent
- `/plot metrics.json "Line plot of loss over epochs"` — JSON + intent
- `/plot results.csv` — ask user for plot intent

## Steps

### Step 0: Check Environment

1. Check if `paperbanana` is installed:
   ```bash
   which paperbanana 2>/dev/null || echo "NOT_INSTALLED"
   ```

2. If NOT installed:
   ```bash
   pip install paperbanana
   ```

3. Check for API key:
   ```bash
   echo "${GOOGLE_API_KEY:+SET}" || echo "NOT_SET"
   ```
   If not set, tell the user to run `paperbanana setup` or set `GOOGLE_API_KEY`.

### Step 1: Parse Arguments

- **First argument** must be a path to a `.csv` or `.json` data file. If not provided, ask the user.
- **Second argument** (optional) is the plot intent — what kind of plot and what it should show.

If no intent is provided, read the data file to understand its columns and ask the user:
> "Your data has columns: [list columns]. What kind of plot would you like? For example: 'Bar chart comparing X across Y' or 'Scatter plot of X vs Y colored by Z'."

### Step 2: Verify Data File

Read the first few lines of the data file to confirm it's valid:
- For CSV: check it has headers and data rows
- For JSON: check it's valid JSON with column-keyed structure

If the data looks malformed, warn the user and suggest fixes.

### Step 3: Generate Plot

```bash
paperbanana plot \
  --data <data_file> \
  --intent "<intent>" \
  --iterations 3
```

### Step 4: Present Results

1. Show where the final plot is saved.
2. Offer to refine: "Want to adjust colors, labels, or chart type? Just describe the changes."

## Tips

- **Be specific with intent**: "Grouped bar chart with model names on x-axis, accuracy on y-axis, benchmarks as groups" is better than "bar chart of results"
- **Data format**: CSV with headers works best. JSON should be column-keyed: `{"col1": [...], "col2": [...]}`
- **Chart types**: bar, grouped bar, stacked bar, line, scatter, heatmap, box plot, violin plot
