---
allowed-tools:
  - Read
  - Write
  - Glob
  - Grep
  - AskUserQuestion
  - Bash(ls *)
  - Bash(find * -name)
  - Bash(find * -maxdepth)
  - Bash(date *)
  - Bash(mkdir *)
  - Bash(wc *)
  - Bash(pwd *)
description: Distill a Zoom (or generic) meeting note into TL;DR + action items by owner + chronological timeline
---

# Meeting Distill

Take a long meeting note (Zoom AI summary, Otter transcript, hand-written notes) and produce a compressed view: 1-line TL;DR, action items grouped by owner, and a chronological timeline.

**Arguments:** `$ARGUMENTS`

Format: `[file_or_paste] [--for <name>] [--mode bullets|timeline|both] [--save]`

Examples:
- `/meeting-distill` → assume the meeting note was pasted in this conversation; produce both views
- `/meeting-distill notes/2026-05-12-decima-sync.txt` → read from file
- `/meeting-distill --for yang` → show only Yang's action items
- `/meeting-distill --mode timeline` → chronological view only
- `/meeting-distill --save` → also write to `meetings/{YYYY-MM-DD}_{topic}.md`

---

## Instructions

### Step 1: Locate the meeting note

Check `$ARGUMENTS` for the input source:

1. **If a file path is present** (token that doesn't start with `--` and isn't a flag value): read the file with the Read tool.
2. **If no file path**: scan the recent conversation for the meeting note. Zoom AI notes typically contain markers like "Quick recap", "Next steps", "Summary", or "Action items". Otter transcripts contain speaker labels like "Yang  00:00:15".
3. **If neither**: ask the user via AskUserQuestion to either paste the note or point to a file.

Parse the remaining args:
- `--for <name>` — case-insensitive substring match against owner names; default: show all
- `--mode bullets|timeline|both` — default: `both`
- `--save` — also write to `meetings/{YYYY-MM-DD}_{slug}.md` in the cwd; default: print-only

### Step 2: Parse the meeting structure

Zoom AI notes have a predictable layout:
- **Quick recap** — 1 paragraph overview
- **Next steps** — bulleted action items, each starting with `<Owner>:` or `<Owner> will...`
- **Summary** — multi-section detailed recap with topical subheaders

If those markers are present, extract directly. Otherwise treat the whole note as free-form prose and infer action items from sentences containing imperative verbs ("send", "review", "share", "schedule", "finish") or attribution ("X will...", "X to...", "X promised...").

Build internal structures:

```
meeting_topic:      string (infer from content — first noun phrase / project name)
meeting_date:       date if present, else today
participants:       list of names (from owner prefixes)
action_items:       list of {owner, action, deadline?, dependency?}
timeline_events:    list of {when, what, who} (sorted chronologically)
```

For each action item, attempt to extract a deadline by scanning for date words: "by Friday", "next Monday", "weekend", "May 22", "end of week", etc. Convert relative dates to absolute using today as the anchor (e.g., "Friday" → next upcoming Friday).

### Step 3: Generate TL;DR

One sentence (≤25 words) that captures the meeting's primary outcome. Pattern: `<participants> <verbed> <main topic>; <key decision or next step>.`

Examples:
- "Yang and Mathias finalized the manuscript revision plan; Yang condenses methods and shares with Loic by Friday, target pre-print posting May 22."
- "Lab sync on binder pipeline; consensus to retire RFdiffusion in favor of BoltzGen; Yasin to benchmark by next Tuesday."

### Step 4: Group action items by owner

For each unique owner, list their action items as terse bullets. Aggressively compress: drop filler like "Yang planned to", "they agreed that". Keep the verb + object + deadline.

Format:

```markdown
### {{Owner}} ({{n}} items)
- {{action}} _(by {{deadline}})_
- {{action}} _(blocks: {{dependency}})_
- {{action}}
```

Group related items into sub-bullets when sensible (e.g., "Ask reviewers" with sub-bullets for Shayan / Avantika / Cheyenne). Don't fabricate groupings the source doesn't support.

### Step 5: Build chronological timeline

Collect all dated events (action deadlines + meeting milestones) and sort by date. Use absolute dates where possible. Format:

```markdown
| Date | What | Who |
|------|------|-----|
| {{date}} | {{event}} | {{owner}} |
```

If multiple items share a date, list them as separate rows. Mark events without a clear date as "TBD" in a separate trailing list, not in the table.

### Step 6: Apply filters and assemble output

If `--for <name>` is set, filter action items and timeline rows to that owner (case-insensitive substring match — `yang` matches "Yang", `mat` matches "Mathias"). The TL;DR stays in place but gets a `(filtered for {{name}})` annotation.

Assemble final output per `--mode`:
- `bullets`: TL;DR + action items only
- `timeline`: TL;DR + chronological table only
- `both` (default): TL;DR + action items + chronological table

Use this template:

```markdown
# {{meeting_topic}} — {{meeting_date}}

**TL;DR:** {{tl_dr}}

**Participants:** {{participants}}

---

## Action items {{(filtered for {{name}}) if applicable}}

### {{Owner1}} ({{n}})
- ...

### {{Owner2}} ({{n}})
- ...

---

## Timeline

| Date | What | Who |
|------|------|-----|
| ... | ... | ... |

_Undated:_
- {{item}}
- {{item}}
```

Keep the whole output **under one screen** when possible — that's the point of distillation. If a meeting truly has 20+ items and they all matter, output them all, but flag at the top: "Long meeting — consider running with `--for <yourname>` to focus."

### Step 7: Save (optional)

If `--save` is set:
1. Derive a topic slug from the meeting title (lowercase, hyphens, no spaces). Limit to 6 words.
2. Make a `meetings/` directory in the cwd if it doesn't exist.
3. Write the output to `meetings/{YYYY-MM-DD}_{slug}.md`.
4. Tell the user the file path. Don't auto-commit.

### Step 8: Suggest follow-ups (optional, light touch)

If the meeting note contains items that look like they should become GitHub issues, calendar events, or scheduled reminders, mention this in ONE line at the bottom — don't auto-create anything. Example:

> _Tip: 3 of these items have hard deadlines — consider `/schedule` to create reminders, or copy into your task tracker._

### Edge cases

- **No meeting note found**: Ask the user via AskUserQuestion whether to (a) point at a file, (b) paste the note now, or (c) cancel.
- **Multiple meeting notes pasted in one conversation**: Ask the user which one to distill.
- **Otter / Fathom transcripts (not Zoom AI)**: Speaker labels + timestamps instead of "Next steps". Treat as free-form and infer action items as in Step 2.
- **Hand-written notes without owners**: Group action items under "Unowned" and recommend the user assign owners.
- **No deadlines at all**: Skip the timeline section entirely; just produce the TL;DR + action items. Note this.
- **Note in a non-English language**: Output in the same language; same structure applies.
- **Note contains private/sensitive info** (legal review, personnel matters): Preserve verbatim — don't editorialize or sanitize. The user can redact when they share the output.
