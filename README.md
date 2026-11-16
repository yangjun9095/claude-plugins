# claude-plugins

Claude Code plugins for the daily work of a scientist: figures, slides, writing and status reports. By [Yang Joon Kim](https://github.com/yangjun9095).

## Install

Add the marketplace to Claude Code:

```
/plugin marketplace add yangjun9095/claude-plugins
```

Then install the plugins that you want:

```
/plugin install scientific-figure@yangjun9095-plugins
```

## Plugins

| Plugin | What it does |
|---|---|
| [`scientific-figure`](plugins/scientific-figure/README.md) | Builds a publication figure as a program and has a second model review it. |
| [`figure-style`](plugins/figure-style/README.md) | Applies a publication style to matplotlib figures and checks each figure before it saves. |
| [`generate-slides`](plugins/generate-slides/README.md) | Turns the figures and notes of a session into a `.pptx` deck. |
| [`science-style`](plugins/science-style/README.md) | Profiles how chosen scientists write, and drafts text with those profiles. |
| [`email-report`](plugins/email-report/README.md) | Emails a threaded status report from a long or unattended session. |

### `scientific-figure`

Builds or rebuilds a publication figure from a draft figure, a description or a results section. A script generates the figure and derives each number from the source data again at build time. A second model, which did not design the figure, reviews the rendered panel. The skill `figure-main-style` composes finished panels into one main figure.

```
/scientific-figure
```

The second-model review needs the Codex command-line tool. The `figure-main-style` tools need Python 3.8 or later with PyMuPDF and numpy.

### `figure-style`

Applies a publication style to matplotlib, seaborn and scanpy figures: small type, no top or right spine, color-blind-safe palettes. A verification script checks each figure for missing labels, small fonts, overlaps and low resolution before it saves.

```
/figure-style                    # activate for the session
/figure-style UMAP plots         # activate with a context hint
```

Use `figure-style` for one plot. Use `scientific-figure` for a complete figure of a paper. `scientific-figure` extends the style of `figure-style`.

### `generate-slides`

Scans the working directory for figures, reads the notes and notebooks, and proposes a slide outline. You approve the outline. The plugin then writes a Python script that builds a 16:9 `.pptx` deck with `python-pptx`.

```
/generate-slides                              # a deck for a talk of 15 minutes
/generate-slides 10 slides                    # exactly 10 slides
/generate-slides 8 slides -- ./report-style.md  # with a file of audience preferences
```

### `science-style`

The style lab finds open-access papers of chosen scientists through OpenAlex, reads the open full texts, and publishes one checked profile per person. The skill `science-write` drafts or revises text with the habits in a profile. Each profile quotes at most 25 words at a time and gives the DOI of each quote. The full texts stay outside the repository.

```
/style-lab <person ids> --pilot
```

### `email-report`

Sends a status report by email through a mail relay on the machine, with no OAuth and no API key. The reports of one session arrive as one thread. The plugin needs a mail transfer agent on `localhost:25`, which most HPC nodes have.

```
/email-report                    # report on this session
/email-report --check            # test whether this host can send mail
```

## License

MIT. See [LICENSE](LICENSE).
