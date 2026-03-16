#!/usr/bin/env python3
"""
build_kg.py — Build an interactive knowledge graph from a folder of markdown files.

Scans for:
  - [[wikilinks]]
  - Standard markdown links [text](file.md)
  - #tags
  - Headings (to label nodes)
  - YAML frontmatter (title, tags, description)

Outputs:
  - Interactive HTML graph (PyVis)
  - Summary index markdown file

Usage:
    python build_kg.py /path/to/docs [--output /path/to/output] [--depth 5]
"""

import argparse
import json
import os
import re
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import networkx as nx
from pyvis.network import Network


# ── Regex patterns ──────────────────────────────────────────────────────────

RE_WIKILINK = re.compile(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]")
RE_MD_LINK = re.compile(r"\[([^\]]*)\]\(([^)]+\.md(?:#[^)]*)?)\)")
RE_TAG = re.compile(r"(?:^|\s)#([a-zA-Z][a-zA-Z0-9_/-]{1,50})\b")
RE_HEADING = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)
RE_FRONTMATTER = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


# ── Frontmatter parsing (lightweight, no pyyaml dependency required) ────────

def parse_frontmatter(text):
    """Extract simple YAML frontmatter key-value pairs."""
    match = RE_FRONTMATTER.match(text)
    if not match:
        return {}, text
    fm_text = match.group(1)
    body = text[match.end():]
    meta = {}
    for line in fm_text.split("\n"):
        if ":" in line:
            key, _, val = line.partition(":")
            key = key.strip().lower()
            val = val.strip().strip('"').strip("'")
            if key == "tags":
                # Handle YAML list on same line: tags: [a, b] or tags: a, b
                val = val.strip("[]")
                meta[key] = [t.strip().strip('"').strip("'") for t in val.split(",") if t.strip()]
            else:
                meta[key] = val
    return meta, body


# ── File scanning ───────────────────────────────────────────────────────────

def scan_md_files(root, max_depth=10):
    """Find all .md files under root, respecting max depth."""
    root = Path(root).resolve()
    md_files = []
    for path in sorted(root.rglob("*.md")):
        rel = path.relative_to(root)
        depth = len(rel.parts) - 1
        if depth <= max_depth:
            md_files.append(path)
    return md_files


def parse_md_file(filepath, root):
    """Parse a single markdown file and extract graph-relevant info."""
    filepath = Path(filepath)
    root = Path(root).resolve()
    rel_path = str(filepath.relative_to(root))

    try:
        text = filepath.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return None

    meta, body = parse_frontmatter(text)

    # Extract headings
    headings = [(len(m.group(1)), m.group(2).strip()) for m in RE_HEADING.finditer(body)]
    title = meta.get("title") or (headings[0][1] if headings else filepath.stem)

    # Extract wikilinks
    wikilinks = RE_WIKILINK.findall(body)

    # Extract standard markdown links to .md files
    md_links = [(text, target) for text, target in RE_MD_LINK.findall(body)]

    # Extract tags (from body and frontmatter)
    body_tags = set(RE_TAG.findall(body))
    fm_tags = set(meta.get("tags", []))
    all_tags = body_tags | fm_tags

    # Word count (rough content size indicator)
    word_count = len(body.split())

    # Extract description from frontmatter or first paragraph
    description = meta.get("description", "")
    if not description and body.strip():
        first_para = body.strip().split("\n\n")[0].replace("\n", " ").strip()
        if len(first_para) > 200:
            first_para = first_para[:200] + "..."
        description = first_para

    return {
        "path": rel_path,
        "abs_path": str(filepath),
        "title": title,
        "headings": headings,
        "wikilinks": wikilinks,
        "md_links": md_links,
        "tags": all_tags,
        "word_count": word_count,
        "description": description,
        "meta": meta,
    }


# ── Graph construction ──────────────────────────────────────────────────────

def resolve_link(link_target, source_path, root, file_index):
    """Resolve a link target to a known file in the index."""
    # Try exact match by stem (for wikilinks)
    target_lower = link_target.lower().replace(" ", "-")
    for rel_path, info in file_index.items():
        stem = Path(rel_path).stem.lower().replace(" ", "-")
        if stem == target_lower:
            return rel_path

    # Try relative path resolution (for md_links)
    source_dir = Path(root) / Path(source_path).parent
    resolved = (source_dir / link_target.split("#")[0]).resolve()
    try:
        rel_resolved = str(resolved.relative_to(Path(root).resolve()))
        if rel_resolved in file_index:
            return rel_resolved
    except ValueError:
        pass

    return None


def build_graph(file_infos, root):
    """Build a NetworkX graph from parsed file info."""
    G = nx.DiGraph()
    file_index = {info["path"]: info for info in file_infos}

    # Collect all tags for coloring
    all_tags = set()
    for info in file_infos:
        all_tags.update(info["tags"])

    # Color palette for tags
    tag_colors = {}
    palette = [
        "#4e79a7", "#f28e2b", "#e15759", "#76b7b2", "#59a14f",
        "#edc948", "#b07aa1", "#ff9da7", "#9c755f", "#bab0ac",
        "#86bcb6", "#8cd17d", "#b6992d", "#499894", "#d37295",
    ]
    for i, tag in enumerate(sorted(all_tags)):
        tag_colors[tag] = palette[i % len(palette)]

    # Add document nodes
    for info in file_infos:
        node_id = info["path"]
        primary_tag = sorted(info["tags"])[0] if info["tags"] else None
        color = tag_colors.get(primary_tag, "#97c2fc") if primary_tag else "#97c2fc"

        # Scale node size by word count (min 15, max 50)
        size = min(50, max(15, 10 + info["word_count"] // 100))

        G.add_node(
            node_id,
            label=info["title"],
            title=_make_tooltip(info),
            color=color,
            size=size,
            group=primary_tag or "untagged",
            shape="dot",
        )

    # Add tag nodes (smaller, diamond-shaped)
    for tag in sorted(all_tags):
        tag_id = f"##{tag}"
        G.add_node(
            tag_id,
            label=f"#{tag}",
            title=f"Tag: #{tag}",
            color=tag_colors[tag],
            size=10,
            group=tag,
            shape="diamond",
        )

    # Add edges: document → document (via wikilinks and md_links)
    for info in file_infos:
        src = info["path"]

        for wl in info["wikilinks"]:
            target = resolve_link(wl, src, root, file_index)
            if target and target != src:
                G.add_edge(src, target, title=f"[[{wl}]]", color="#999999")

        for link_text, link_target in info["md_links"]:
            target = resolve_link(link_target, src, root, file_index)
            if target and target != src:
                label = link_text[:30] if link_text else link_target
                G.add_edge(src, target, title=label, color="#999999")

    # Add edges: document → tag
    for info in file_infos:
        for tag in info["tags"]:
            G.add_edge(info["path"], f"##{tag}", color=tag_colors[tag], width=0.5)

    return G, tag_colors


def _make_tooltip(info):
    """Create an HTML tooltip for a node."""
    lines = [
        f"<b>{info['title']}</b>",
        f"<i>{info['path']}</i>",
        f"Words: {info['word_count']}",
    ]
    if info["tags"]:
        lines.append(f"Tags: {', '.join(f'#{t}' for t in sorted(info['tags']))}")
    if info["description"]:
        desc = info["description"][:150]
        lines.append(f"<br>{desc}")
    if info["headings"]:
        toc = " | ".join(h[1] for h in info["headings"][:5])
        if len(info["headings"]) > 5:
            toc += f" ... (+{len(info['headings'])-5} more)"
        lines.append(f"<br>Sections: {toc}")
    return "<br>".join(lines)


# ── Visualization ───────────────────────────────────────────────────────────

def render_html(G, output_path, title="Knowledge Graph"):
    """Render the graph as an interactive HTML file using PyVis."""
    net = Network(
        height="100vh",
        width="100%",
        directed=True,
        bgcolor="#1a1a2e",
        font_color="#e0e0e0",
        select_menu=False,
        filter_menu=False,
    )

    net.from_nx(G)

    # Physics configuration for good layout
    net.set_options(json.dumps({
        "physics": {
            "forceAtlas2Based": {
                "gravitationalConstant": -80,
                "centralGravity": 0.01,
                "springLength": 120,
                "springConstant": 0.08,
                "damping": 0.4,
                "avoidOverlap": 0.5,
            },
            "solver": "forceAtlas2Based",
            "stabilization": {
                "enabled": True,
                "iterations": 200,
            },
        },
        "interaction": {
            "hover": True,
            "tooltipDelay": 100,
            "navigationButtons": True,
        },
        "edges": {
            "smooth": {
                "type": "continuous",
            },
            "arrows": {
                "to": {"enabled": True, "scaleFactor": 0.5},
            },
        },
        "nodes": {
            "font": {"size": 12},
            "borderWidth": 2,
        },
    }))

    net.save_graph(str(output_path))

    # Inject custom title into the HTML
    html = Path(output_path).read_text()
    html = html.replace("<head>", f"<head><title>{title}</title>")
    Path(output_path).write_text(html)


# ── Summary index ───────────────────────────────────────────────────────────

def generate_summary(file_infos, G, root, tag_colors):
    """Generate a markdown summary index."""
    lines = [
        f"# Knowledge Graph Summary",
        f"",
        f"**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"**Source**: `{root}`",
        f"**Documents**: {sum(1 for n in G.nodes if not n.startswith('##'))}",
        f"**Tags**: {sum(1 for n in G.nodes if n.startswith('##'))}",
        f"**Links**: {G.number_of_edges()}",
        "",
    ]

    # Tag summary
    tag_counts = defaultdict(list)
    for info in file_infos:
        for tag in info["tags"]:
            tag_counts[tag].append(info["title"])

    if tag_counts:
        lines.append("## Tags")
        lines.append("")
        for tag in sorted(tag_counts, key=lambda t: -len(tag_counts[t])):
            lines.append(f"- **#{tag}** ({len(tag_counts[tag])} docs): {', '.join(tag_counts[tag][:5])}")
            if len(tag_counts[tag]) > 5:
                lines[-1] += f" ... (+{len(tag_counts[tag])-5} more)"
        lines.append("")

    # Most connected docs (hubs)
    doc_nodes = [n for n in G.nodes if not n.startswith("##")]
    if doc_nodes:
        degree_sorted = sorted(doc_nodes, key=lambda n: G.degree(n), reverse=True)
        lines.append("## Most Connected Documents")
        lines.append("")
        for node in degree_sorted[:10]:
            info = next((f for f in file_infos if f["path"] == node), None)
            title = info["title"] if info else node
            deg = G.degree(node)
            lines.append(f"- **{title}** (`{node}`) — {deg} connections")
        lines.append("")

    # Orphan docs (no links in or out to other docs)
    orphans = [n for n in doc_nodes if G.degree(n) <= 1]  # only self or tag link
    if orphans:
        lines.append("## Isolated Documents (no cross-references)")
        lines.append("")
        for node in orphans:
            info = next((f for f in file_infos if f["path"] == node), None)
            title = info["title"] if info else node
            lines.append(f"- {title} (`{node}`)")
        lines.append("")

    # Document index
    lines.append("## All Documents")
    lines.append("")
    lines.append("| Document | Path | Words | Tags |")
    lines.append("|----------|------|------:|------|")
    for info in sorted(file_infos, key=lambda f: f["path"]):
        tags = ", ".join(f"#{t}" for t in sorted(info["tags"])) if info["tags"] else "-"
        lines.append(f"| {info['title']} | `{info['path']}` | {info['word_count']} | {tags} |")
    lines.append("")

    return "\n".join(lines)


# ── Main ────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Build an interactive knowledge graph from markdown files"
    )
    parser.add_argument("docs_path", help="Path to the docs directory")
    parser.add_argument(
        "--output", "-o",
        help="Output directory (default: same as docs_path)",
        default=None,
    )
    parser.add_argument(
        "--depth", "-d",
        type=int, default=10,
        help="Max directory depth to scan (default: 10)",
    )
    parser.add_argument(
        "--no-tags",
        action="store_true",
        help="Exclude tag nodes from the graph",
    )
    parser.add_argument(
        "--title", "-t",
        default=None,
        help="Title for the knowledge graph",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Also output graph data as JSON",
    )

    args = parser.parse_args()

    root = Path(args.docs_path).resolve()
    if not root.is_dir():
        print(f"Error: '{root}' is not a directory", file=sys.stderr)
        sys.exit(1)

    output_dir = Path(args.output).resolve() if args.output else root
    output_dir.mkdir(parents=True, exist_ok=True)

    title = args.title or f"Knowledge Graph: {root.name}"

    # Scan and parse
    print(f"Scanning {root} ...")
    md_files = scan_md_files(root, max_depth=args.depth)
    if not md_files:
        print("No .md files found.", file=sys.stderr)
        sys.exit(1)

    print(f"Found {len(md_files)} markdown files")

    file_infos = []
    for f in md_files:
        info = parse_md_file(f, root)
        if info:
            file_infos.append(info)

    print(f"Parsed {len(file_infos)} files successfully")

    # Build graph
    G, tag_colors = build_graph(file_infos, root)

    if args.no_tags:
        tag_nodes = [n for n in G.nodes if n.startswith("##")]
        G.remove_nodes_from(tag_nodes)

    doc_count = sum(1 for n in G.nodes if not n.startswith("##"))
    tag_count = sum(1 for n in G.nodes if n.startswith("##"))
    print(f"Graph: {doc_count} documents, {tag_count} tags, {G.number_of_edges()} edges")

    # Render HTML
    html_path = output_dir / "knowledge_graph.html"
    render_html(G, html_path, title=title)
    print(f"HTML graph: {html_path}")

    # Generate summary
    summary = generate_summary(file_infos, G, str(root), tag_colors)
    summary_path = output_dir / "knowledge_graph_summary.md"
    summary_path.write_text(summary)
    print(f"Summary:    {summary_path}")

    # Optional JSON export
    if args.json:
        graph_data = {
            "nodes": [
                {
                    "id": n,
                    "label": G.nodes[n].get("label", n),
                    "group": G.nodes[n].get("group", ""),
                    "size": G.nodes[n].get("size", 15),
                }
                for n in G.nodes
            ],
            "edges": [
                {"source": u, "target": v, "title": d.get("title", "")}
                for u, v, d in G.edges(data=True)
            ],
            "stats": {
                "documents": doc_count,
                "tags": tag_count,
                "edges": G.number_of_edges(),
                "generated": datetime.now().isoformat(),
            },
        }
        json_path = output_dir / "knowledge_graph.json"
        json_path.write_text(json.dumps(graph_data, indent=2))
        print(f"JSON data:  {json_path}")

    print("Done!")


if __name__ == "__main__":
    main()
