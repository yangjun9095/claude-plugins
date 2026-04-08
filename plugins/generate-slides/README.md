# generate-slides

Generate polished `.pptx` slide decks directly from your Claude Code session. Scans your project for figures, notebooks, and docs, then walks you through an interactive outline before producing a ready-to-present PowerPoint file.

## Install

```bash
# Add the marketplace (one-time)
/plugin marketplace add yangjun9095/claude-plugins

# Install the plugin
/plugin install generate-slides@yangjun9095-plugins
```

`python-pptx` is auto-installed on first use — no manual `pip install` needed.

**Optional:** `pip install pyyaml` (to customize slide style via YAML)

## Usage

```
/generate-slides                              # default 15-min deck
/generate-slides 20min                        # ~20-slide deck
/generate-slides 10 slides                    # exactly 10 slides
/generate-slides 15min -- loic                # match a report-style file
/generate-slides 8 slides -- ./report-style.md
```

## How it works

1. **Scans** your project for figures (.png, .jpg, .svg), notebooks, and docs
2. **Asks** you to pick a narrative style (Journey, Results-First, Technical Deep-Dive)
3. **Proposes** a slide-by-slide outline with figure assignments — iterates with you until approved
4. **Previews** 2-3 representative slides so you can give early feedback on design
5. **Generates** a self-contained Python script that produces the final `.pptx`
6. **Verifies** the output with an automated quality harness (action titles, figure bounds, font consistency, etc.)

Output lands in `docs/slides/{project}-{date}.pptx`.

## Default style

The plugin ships with a clean, academic-style design. A sample deck is included at [`examples/sample-deck.pptx`](examples/sample-deck.pptx).

| Setting | Default |
|---|---|
| **Aspect ratio** | 16:9 widescreen |
| **Font** | Avenir Light (body/titles), PT Mono (code) |
| **Colors** | Black text, single blue accent `#036DEA` |
| **Bold** | Never — hierarchy through font size and spacing only |
| **Bullet emphasis** | Blue accent on key-term prefixes (not bold) |
| **Title style** | Action titles: full sentences stating the takeaway, not topic labels |
| **Callout boxes** | White background, thin grey border |
| **Tables** | Light grey header, no bold |
| **Title slide** | White background, black text |

### Action titles (enforced)

Every slide title must be a complete sentence stating the takeaway:

- Bad: "Results", "Model Performance"
- Good: "LoRA fine-tuning improves RNA prediction by 67% over baseline"
- Good: "ATAC generalizes poorly across replicates while RNA transfers robustly"

The verification harness flags topic-label titles and runs a "ghost deck test" — reading just the titles in sequence should tell the full story.

## Customizing the style

Drop a `slide-style.yaml` in your project root (or `docs/` or `.claude/`). Partial YAML is fine — only specified keys override the defaults:

```yaml
# Example: change font and accent color
typography:
  body_font: "Calibri"
colors:
  accent: "#7C3AED"
style:
  use_bold: true
  bullet_emphasis: "bold"
```

Full schema is in [`references/style-guide.md`](references/style-guide.md).

## What's included

```
generate-slides/
  commands/generate-slides.md   # Skill prompt (workflow documentation)
  scripts/
    pptx_helpers.py             # Reusable helper library (16+ functions)
    verify_slides.py            # Automated quality checks
    slide-style-default.yaml    # Default style profile
  references/
    style-guide.md              # Full style YAML schema & API reference
  examples/
    sample-deck.pptx            # Sample output showing the default style
```

## Relationship to `prep-report`

- `/prep-report` produces a **markdown outline** only (no PPTX file)
- `/generate-slides` produces a **ready-to-present `.pptx`** with embedded figures

Use `prep-report` when you want to plan the narrative. Use `generate-slides` when you want the final file.

## License

MIT
