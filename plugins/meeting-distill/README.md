# meeting-distill

Distill a long meeting note (Zoom AI summary, Otter transcript, hand notes) into a one-screen view: TL;DR + action items by owner + chronological timeline.

## Install

```
/plugin marketplace add yangjun9095/claude-plugins
/plugin install meeting-distill@yangjun9095-plugins
```

## Usage

```
/meeting-distill                              # use the note pasted in this conversation
/meeting-distill notes/2026-05-12.txt         # read from a file
/meeting-distill --for yang                   # filter to one person's items
/meeting-distill --mode timeline              # chronological view only
/meeting-distill --save                       # also archive to meetings/{date}_{slug}.md
```

## What it produces

```markdown
# {{Meeting topic}} — {{date}}

**TL;DR:** {{one sentence}}

## Action items

### Yang (4)
- Condense main methods to 3 paragraphs _(by Wed)_
- Mask out PSNR / N in Figure 1
- Share manuscript with Loic _(by Fri)_
- Clean up GitHub repo — remove unused notebooks

### Mathias (2)
- Review track changes _(weekend)_
- Final review _(before May 22 pre-print)_

## Timeline

| Date | What | Who |
|------|------|-----|
| Wed  | Methods condensed | Yang |
| Fri  | Share with Loic | Yang |
| Sat–Sun | Review track changes | Mathias |
| Mon  | Feedback due | Mathias |
| May 22 | Pre-print posting | (deadline) |
```

## Inputs it handles

- **Zoom AI meeting summaries** (Quick recap / Next steps / Summary) — primary target
- **Otter / Fathom transcripts** — speaker labels + timestamps, action items inferred
- **Free-form notes** — extracts owners and deadlines heuristically; flags items with no owner

## Flags

| Flag | Default | Effect |
|------|---------|--------|
| `--for <name>` | none | Filter action items and timeline to one person (case-insensitive substring) |
| `--mode bullets\|timeline\|both` | `both` | Drop a section if you only want one |
| `--save` | off | Archive to `meetings/{YYYY-MM-DD}_{slug}.md` |

## License

MIT
