---
name: build-kg
description: Build an interactive knowledge graph from a folder of markdown documentation files. Use when the user wants to visualize, summarize, or understand relationships across multiple .md files.
argument-hint: [/path/to/docs]
---

# Build Knowledge Graph from Documentation

Generate an interactive HTML knowledge graph and summary index from a directory of markdown files.

## What This Does

1. Scans a directory for all `.md` files
2. Extracts: `[[wikilinks]]`, standard `[text](link.md)` links, `#tags`, headings, YAML frontmatter
3. Builds a NetworkX directed graph of document relationships
4. Renders an interactive HTML visualization (PyVis) with:
   - Documents as nodes (sized by word count, colored by primary tag)
   - Tags as diamond-shaped nodes
   - Edges showing cross-references between documents
   - Hover tooltips with title, path, tags, word count, and section outline
   - Dark theme, force-directed layout, navigation controls
5. Generates a `knowledge_graph_summary.md` with:
   - Tag frequency breakdown
   - Most connected (hub) documents
   - Isolated/orphan documents with no cross-references
   - Full document index table

## How to Run

The script is at `~/.claude/skills/build-kg/build_kg.py`.

**Basic usage:**
```bash
~/miniconda3/bin/python ~/.claude/skills/build-kg/build_kg.py $ARGUMENTS
```

**With options:**
```bash
# Output to a different directory
~/miniconda3/bin/python ~/.claude/skills/build-kg/build_kg.py /path/to/docs --output /path/to/output

# Also export graph as JSON
~/miniconda3/bin/python ~/.claude/skills/build-kg/build_kg.py /path/to/docs --json

# Custom title
~/miniconda3/bin/python ~/.claude/skills/build-kg/build_kg.py /path/to/docs --title "My Project Docs"

# Exclude tag nodes (show only document-to-document links)
~/miniconda3/bin/python ~/.claude/skills/build-kg/build_kg.py /path/to/docs --no-tags

# Limit scan depth
~/miniconda3/bin/python ~/.claude/skills/build-kg/build_kg.py /path/to/docs --depth 3
```

## Steps

1. Determine the target docs directory from `$ARGUMENTS`. If not provided, ask the user.
2. Run the script using the Bash tool with `~/miniconda3/bin/python`.
3. Report the results: number of documents, tags, links found.
4. Tell the user where the output files are (`knowledge_graph.html` and `knowledge_graph_summary.md`).
5. Read and present key findings from the summary (hub docs, orphans, tag breakdown).
6. If there are orphan documents or disconnected clusters, suggest improvements (add cross-references, tags, etc.).
