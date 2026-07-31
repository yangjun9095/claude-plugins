"""Self-contained HTML export.

One file, no external anything. The invariant is about EXECUTION and FETCHING, not
about links: 0 `<script>`, 0 `on*=`, 0 `javascript:`, 0 `src=`, 0 `<link>`,
0 `@import`. An `href` to a PR, issue or commit is permitted and expected -- it runs
no code, fetches no asset, and degrades to a dead link offline. Treating href=0 as
the win renders every PR reference as inert text, which is worse.

No meta-refresh either: this is a shareable frozen snapshot, and auto-reloading a
static file cannot show new data.
"""
import html as _html

from agent_board.render import palette

# Node/edge geometry for the blocked_by graph.
NW, NH, HG, VG, PADX, PADY = 190, 44, 74, 22, 12, 14

SEV_CLASS = {"HIGH": "sev-high", "MEDIUM": "sev-med", "LOW": "sev-low"}


def esc(value):
    """Escape for text AND attribute context (quote=True covers both)."""
    return _html.escape("" if value is None else str(value), quote=True)


def _safe_href(url):
    """Only http(s). A `javascript:` or `data:` URL in a thread field is
    agent-writable input, and this file is meant to be shareable."""
    if not isinstance(url, str):
        return None
    low = url.strip().lower()
    if low.startswith("http://") or low.startswith("https://"):
        return url.strip()
    return None


# --- layered DAG for blocked_by ----------------------------------------------

def layer_nodes(nodes, edges):
    """Longest-path layering, bounded by len(nodes) so a cycle cannot hang.

    `edges` are (blocked, blocker) pairs: the blocker sits in an EARLIER layer, so
    the arrow reads "this must finish before that can".
    """
    layer = {n: 0 for n in nodes}
    for _ in range(len(nodes)):
        changed = False
        for blocked, blocker in edges:
            if blocked in layer and blocker in layer:
                want = layer[blocker] + 1
                if layer[blocked] < want:
                    layer[blocked] = want
                    changed = True
        if not changed:
            break
    return layer


def barycenter_order(nodes, edges, layer, sweeps=4):
    """Reduce crossings. Deterministic: ties break on the id, so the same board
    always exports the same SVG."""
    by_layer = {}
    for node in sorted(nodes):
        by_layer.setdefault(layer[node], []).append(node)
    neighbours = {n: set() for n in nodes}
    for blocked, blocker in edges:
        if blocked in neighbours and blocker in neighbours:
            neighbours[blocked].add(blocker)
            neighbours[blocker].add(blocked)
    for sweep in range(sweeps):
        keys = sorted(by_layer) if sweep % 2 == 0 else sorted(by_layer, reverse=True)
        pos = {n: i for depth in by_layer for i, n in enumerate(by_layer[depth])}
        for depth in keys:
            row = by_layer[depth]

            def key(node):
                mates = [pos[m] for m in neighbours[node] if m in pos]
                return (sum(mates) / float(len(mates)) if mates else 0.0, node)
            by_layer[depth] = sorted(row, key=key)
    return by_layer


def graph_svg(threads_by_id, columns):
    """Inline SVG of the blocked_by graph, or "" when there are no edges."""
    edges = []
    for tid, thread in sorted(threads_by_id.items()):
        for dep in thread.get("blocked_by") or []:
            if isinstance(dep, str) and dep in threads_by_id:
                edges.append((tid, dep))
    if not edges:
        return ""

    nodes = sorted({n for edge in edges for n in edge})
    layer = layer_nodes(nodes, edges)
    by_layer = barycenter_order(nodes, edges, layer)

    place = {}
    for depth in sorted(by_layer):
        for index, node in enumerate(by_layer[depth]):
            place[node] = (PADX + depth * (NW + HG), PADY + index * (NH + VG))
    width = PADX * 2 + (max(layer.values()) + 1) * (NW + HG) - HG
    height = PADY * 2 + max(len(v) for v in by_layer.values()) * (NH + VG) - VG

    parts = ['<svg class="dag" viewBox="0 0 %d %d" width="100%%" '
             'role="img" aria-label="thread dependency graph">' % (width, height),
             '<defs><marker id="ah" viewBox="0 0 10 10" refX="9" refY="5" '
             'markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
             '<path d="M0,0 L10,5 L0,10 z" class="ahead"/></marker></defs>']

    for blocked, blocker in edges:
        bx, by = place[blocker]
        tx, ty = place[blocked]
        x1, y1 = bx + NW, by + NH / 2.0
        x2, y2 = tx, ty + NH / 2.0
        mid = (x1 + x2) / 2.0
        parts.append('<path class="edge" d="M%.1f,%.1f C%.1f,%.1f %.1f,%.1f '
                     '%.1f,%.1f" marker-end="url(#ah)"/>'
                     % (x1, y1, mid, y1, mid, y2, x2, y2))

    for node in nodes:
        x, y = place[node]
        col = columns.get(node) or ""
        title = threads_by_id[node].get("title") or node
        parts.append(
            '<g class="node"><title>%s %s %s</title>'
            '<rect x="%d" y="%d" width="%d" height="%d" rx="8" class="%s"/>'
            '<text x="%d" y="%d">%s</text></g>'
            % (esc(node), "&#183;", esc(col or "?"),
               x, y, NW, NH, "n-" + (col.split()[0].lower() if col else "none"),
               x + 10, y + NH / 2 + 5, esc(_clip(title, 26))))
    parts.append("</svg>")
    return "\n".join(parts)


def _clip(text, limit):
    text = "" if text is None else str(text)
    return text if len(text) <= limit else text[:limit - 1] + "…"


# --- page --------------------------------------------------------------------

def _css():
    dark, light = palette.DARK, palette.LIGHT
    return """
:root{--bg:%(lbg)s;--txt:%(ltxt)s;--dim:%(ldim)s;--faint:%(lfaint)s;
--ok:%(lok)s;--warn:%(lwarn)s;--bad:%(lbad)s;--chrome:%(lchrome)s;
--card:#fbfaff;--line:#e3dff0}
@media (prefers-color-scheme:dark){:root{--bg:%(dbg)s;--txt:%(dtxt)s;
--dim:%(ddim)s;--faint:%(dfaint)s;--ok:%(dok)s;--warn:%(dwarn)s;--bad:%(dbad)s;
--chrome:%(dchrome)s;--card:#1c1830;--line:#2e2747}}
*{box-sizing:border-box}
body{margin:0;padding:24px;background:var(--bg);color:var(--txt);
font:14px/1.5 ui-monospace,SFMono-Regular,Menlo,Consolas,monospace}
h1{font-size:16px;margin:0 0 4px;color:var(--chrome)}
.meta{color:var(--dim);font-size:12px;margin-bottom:20px}
.meta b{color:var(--txt);font-weight:600}
h2{font-size:12px;letter-spacing:.14em;text-transform:uppercase;
color:var(--chrome);margin:26px 0 10px;padding-bottom:6px;
border-bottom:1px solid var(--line)}
.lane{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));
gap:12px}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;
padding:12px 14px}
.card .id{color:var(--chrome);font-weight:600}
.card .title{margin:2px 0 6px}
.card .goal{color:var(--dim)}
.card .next{margin-top:6px}
.card .next::before{content:"\\2192 ";color:var(--ok)}
.wt{color:var(--dim);font-size:12px;margin-top:6px;white-space:pre-wrap}
.badge{display:inline-block;margin-top:8px;padding:1px 8px;border-radius:20px;
font-size:12px;border:1px solid currentColor;color:var(--warn)}
.badge.jobs{color:var(--ok)}
.note{color:var(--bad);font-size:12px;margin-top:6px}
.ev{color:var(--faint);font-size:12px;margin-top:4px}
a{color:var(--chrome)}
table{border-collapse:collapse;width:100%%;font-size:13px}
th,td{text-align:left;padding:5px 10px;border-bottom:1px solid var(--line);
vertical-align:top}
th{color:var(--dim);font-weight:600;font-size:12px}
.sev-high{color:var(--bad);font-weight:600}
.sev-med{color:var(--warn)}
.sev-low{color:var(--dim)}
.files{color:var(--dim);font-size:12px}
details{margin-top:6px}
summary{cursor:pointer;color:var(--dim)}
.footer{margin-top:28px;padding-top:10px;border-top:1px solid var(--line);
color:var(--faint);font-size:12px}
.dag{max-width:100%%;height:auto;margin:6px 0 2px}
.dag .edge{fill:none;stroke:var(--dim);stroke-width:1.5}
.dag .ahead{fill:var(--dim)}
.dag rect{fill:var(--card);stroke:var(--chrome);stroke-width:1.5}
.dag rect.n-blocked{stroke:var(--bad)}
.dag rect.n-done{stroke:var(--faint)}
.dag text{fill:var(--txt);font:12px ui-monospace,Menlo,monospace}
.dag .node:hover rect{stroke-width:3}
@media print{.card{break-inside:avoid}body{padding:0}}
""" % {"lbg": light["bg"], "ltxt": light["txt"], "ldim": light["dim"],
       "lfaint": light["faint"], "lok": light["ok"], "lwarn": light["warn"],
       "lbad": light["bad"], "lchrome": light["chrome"],
       "dbg": dark["bg"], "dtxt": dark["txt"], "ddim": dark["dim"],
       "dfaint": dark["faint"], "dok": dark["ok"], "dwarn": dark["warn"],
       "dbad": dark["bad"], "dchrome": dark["chrome"]}


def _card_html(card):
    out = ['<div class="card">',
           '<div class="id">%s</div>' % esc(card.get("id")),
           '<div class="title">%s</div>' % esc(card.get("title") or "")]
    if card.get("goal"):
        out.append('<div class="goal">%s</div>' % esc(card["goal"]))
    if card.get("next_action"):
        out.append('<div class="next">%s</div>' % esc(card["next_action"]))
    for line in card.get("worktrees") or []:
        out.append('<div class="wt">%s</div>' % esc(line))
    for key, text in card.get("badges") or []:
        cls = "badge jobs" if key == "live_jobs" else "badge"
        out.append('<span class="%s">%s</span>' % (cls, esc(text)))
    pr = card.get("pr") or {}
    href = _safe_href(pr.get("url"))
    if href:
        label = "PR #%s" % pr.get("number") if pr.get("number") else "pull request"
        out.append('<div class="next"><a href="%s">%s</a></div>'
                   % (esc(href), esc(label)))
    for note in card.get("notes") or []:
        out.append('<div class="note">%s</div>' % esc(note))
    # The terminal card shows its last activity, so the shared snapshot must too --
    # it is the artifact a reader opens instead of the board.
    for ev in card.get("events") or []:
        from agent_board.render.layout import _event_text
        text = _event_text(ev)
        if text:
            out.append('<div class="ev">%s</div>' % esc(text))
    out.append("</div>")
    return "".join(out)


def export(board, threads_by_id=None, columns=None, generated_at=""):
    """The whole page as a string."""
    meta = board.get("meta") or {}
    signals = board.get("signals") or {}
    parts = ["<style>%s</style>" % _css(),
             "<h1>agent-board &#183; %s</h1>" % esc(meta.get("project") or "?")]
    bits = ["<b>%s</b> open" % esc(meta.get("open", 0)),
            "%s live job(s)" % esc(meta.get("live_jobs", 0)),
            "%s collision(s)" % esc(meta.get("collisions", 0)),
            "base <b>%s</b>@%s" % (esc(meta.get("branch") or "?"),
                                   esc(meta.get("head") or "?"))]
    if generated_at:
        bits.append("generated %s" % esc(generated_at))
    parts.append('<div class="meta">%s</div>' % " &#183; ".join(bits))

    for name in ("ACTIVE", "IN REVIEW", "BLOCKED", "PARKED"):
        cards = (board.get("columns") or {}).get(name) or []
        if not cards:
            continue
        parts.append("<h2>%s (%d)</h2>" % (esc(name), len(cards)))
        parts.append('<div class="lane">%s</div>'
                     % "".join(_card_html(c) for c in cards))

    done = (board.get("columns") or {}).get("DONE") or []
    if done:
        # Native <details>, so collapsing needs no script.
        rows = "".join("<div>%s &#183; %s</div>"
                       % (esc(c.get("id")), esc(c.get("title") or ""))
                       for c in done)
        parts.append("<h2>DONE (%d)</h2><details><summary>show %d finished "
                     "thread(s)</summary>%s</details>" % (len(done), len(done), rows))

    cols = board.get("collisions") or []
    if cols:
        parts.append("<h2>Collisions (%d)</h2><table><tr><th>severity</th>"
                     "<th>threads</th><th>files</th></tr>" % len(cols))
        for c in cols:
            files = ", ".join(c.get("files") or [])
            demoted = c.get("demoted_files") or []
            if demoted:
                files += " <em>(+%d ubiquitous demoted)</em>" % len(demoted)
            parts.append('<tr><td class="%s">%s</td><td>%s &#183; %s</td>'
                         '<td class="files">%s</td></tr>'
                         % (SEV_CLASS.get(c.get("severity"), "sev-low"),
                            esc(c.get("severity")), esc(c.get("a")), esc(c.get("b")),
                            files))
        parts.append("</table>")

    if threads_by_id:
        svg = graph_svg(threads_by_id, columns or {})
        if svg:
            parts.append("<h2>Dependencies</h2>" + svg)

    notes = []
    from agent_board.render.layout import footer_notes
    notes.extend(footer_notes(board))
    for tid, dep, why in signals.get("stale_blocks") or []:
        notes.append("%s is blocked by %s, which is %s"
                     % (tid, dep, "done" if why == "DONE" else "unknown"))
    if notes:
        parts.append('<div class="footer">%s</div>'
                     % "<br>".join(esc(n) for n in notes))
    return "\n".join(parts) + "\n"
