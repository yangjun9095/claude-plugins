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

The script ships with this plugin at `${CLAUDE_PLUGIN_ROOT}/build_kg.py`.

**Dependencies.** It needs `networkx` and `pyvis`, which are NOT in the standard library. Pick an
interpreter that has them, and check first rather than discovering it mid-run:

```bash
python3 -c "import networkx, pyvis; print('deps OK')" || echo "NEED: pip install networkx pyvis"
```

If the system `python3` lacks them, use one that has them (e.g. a conda env) or install them. Set
`KG_PYTHON` to that interpreter and use it throughout:

```bash
KG_PYTHON="${KG_PYTHON:-python3}"
```

**Basic usage:**
```bash
"$KG_PYTHON" "${CLAUDE_PLUGIN_ROOT}/build_kg.py" $ARGUMENTS
```

**With options:**
```bash
# Output to a different directory
"$KG_PYTHON" "${CLAUDE_PLUGIN_ROOT}/build_kg.py" /path/to/docs --output /path/to/output

# Also export graph as JSON
"$KG_PYTHON" "${CLAUDE_PLUGIN_ROOT}/build_kg.py" /path/to/docs --json

# Custom title
"$KG_PYTHON" "${CLAUDE_PLUGIN_ROOT}/build_kg.py" /path/to/docs --title "My Project Docs"

# Exclude tag nodes (show only document-to-document links)
"$KG_PYTHON" "${CLAUDE_PLUGIN_ROOT}/build_kg.py" /path/to/docs --no-tags

# Limit scan depth
"$KG_PYTHON" "${CLAUDE_PLUGIN_ROOT}/build_kg.py" /path/to/docs --depth 3
```

## Steps

1. Determine the target docs directory from `$ARGUMENTS`. If not provided, ask the user.
2. Verify `networkx` and `pyvis` are importable, then run the script with that interpreter.
   If they are missing, say so and give the `pip install networkx pyvis` line — do not fail silently.
3. Report the results: number of documents, tags, links found.
4. Tell the user where the output files are (`knowledge_graph.html` and `knowledge_graph_summary.md`).
5. Read and present key findings from the summary (hub docs, orphans, tag breakdown).
6. If there are orphan documents or disconnected clusters, suggest improvements (add cross-references, tags, etc.).
