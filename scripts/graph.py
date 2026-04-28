#!/usr/bin/env python3
# scripts/graph.py
# Export knowledge graph
# Usage: python3 scripts/graph.py [brand] [--format dot|json|html]

import json, sys
from pathlib import Path
from datetime import datetime

BASE  = Path(__file__).parent.parent
MEMORY = BASE / "memory"

def load_triples():
    tfile = MEMORY / "triples.jsonl"
    if not tfile.exists():
        return []
    triples = []
    with open(tfile, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                triples.append(json.loads(line))
            except:
                pass
    return triples

def load_hot_cache():
    hfile = MEMORY / "hot-cache.json"
    if not hfile.exists():
        return {}
    with open(hfile, encoding="utf-8") as f:
        return json.load(f)

def export_dot(triples, brand_filter=None):
    lines = ["digraph KnowledgeGraph {", "  rankdir=LR;", "  node [shape=box];", ""]
    nodes = set()
    for t in triples:
        if brand_filter and brand_filter not in [t.get("subject",""), t.get("object","")]:
            continue
        s, p, o = t.get("subject",""), t.get("predicate",""), t.get("object","")
        if not s or not p or not o:
            continue
        nodes.add(s); nodes.add(o)
        lines.append('  "{0}" -> "{1}" [label="{2}"];'.format(s, o, p))
    for n in nodes:
        lines.append('  "{0}";'.format(n))
    lines.append("}")
    return "\n".join(lines)

def export_json(triples, brand_filter=None):
    out = []
    for t in triples:
        if brand_filter:
            if brand_filter not in [t.get("subject",""), t.get("object","")]:
                continue
        out.append(t)
    return json.dumps({"triples": out, "count": len(out), "exported_at": datetime.now().isoformat()}, ensure_ascii=False, indent=2)

def export_html(triples, brand_filter=None):
    # Minimal HTML with a node-link diagram using JS
    html = """<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Knowledge Graph</title>
<style>body{{font-family:sans-serif;background:#1a1a2e;color:#eee;}}
{{.node{{fill:#0f3460;stroke:#e94560;stroke-width:1.5;}}
.edge{{stroke:#e94560;stroke-width:1;fill:none;}}
text{{fill:#eee;font-size:12px;}}</style>
<script src="https://cdnjs.cloudflare.com/ajax/libs/d3/7.8.5/d3.min.js"></script>
</head><body>
<h2>Knowledge Graph — {count} triples</h2>
<div id="graph"></div>
<script>
const data={triples_json};
const svg=d3.select("#graph").append("svg").attr("width",800).attr("height",600);
const sim=d3.forceSimulation().force("link",d3.forceLink().id(d=>d.id)).force("charge",d3.forceManyBody(-200)).force("center",d3.forceCenter(400,300));
const link=svg.append("g").selectAll("line").data(data.triples).enter().append("line").attr("class","edge");
const node=svg.append("g").selectAll("text").data(data.nodes||[]).enter().append("text").text(d=>d.id);
link.append("title").text(d=>d.predicate);
sim.nodes(data.nodes||[]).on("tick",()=>{{link.attr("x1",d=>d.source.x).attr("y1",d=>d.source.y).attr("x2",d=>d.target.x).attr("y2",d=>d.target.y);node.attr("x",d=>d.x).attr("y",d=>d.y);}});
sim.force("link").links(data.triples.map(t=>({{source:t.subject,target:t.object,predicate:t.predicate}}))));
</script></body></html>"""
    nodes = list({t["subject"] for t in triples if brand_filter is None or brand_filter in [t["subject"], t["object"]]})
    triples_filtered = [t for t in triples if brand_filter is None or brand_filter in [t["subject"], t["object"]]]
    return html.format(count=len(triples_filtered), triples_json=json.dumps({"nodes": [{"id":n} for n in nodes], "triples": triples_filtered}))

def main():
    brand_filter = None
    fmt = "text"
    args = sys.argv[1:]
    if "--format" in args:
        idx = args.index("--format")
        if idx + 1 < len(args):
            fmt = args[idx + 1]
            args = args[:idx] + args[idx+2:]
    if args:
        brand_filter = args[0].lower()

    triples = load_triples()
    hot = load_hot_cache()

    if not triples and not hot:
        print("No triples in knowledge base.")
        return

    print("Knowledge Graph — {0} triples".format(len(triples)))
    print()

    if brand_filter:
        print("Filter: {0}".format(brand_filter))

    if fmt == "dot":
        print(export_dot(triples, brand_filter))
    elif fmt == "json":
        print(export_json(triples, brand_filter))
    elif fmt == "html":
        outpath = BASE / "wiki" / "graph.html"
        content = export_html(triples, brand_filter)
        outpath.write_text(content, encoding="utf-8")
        print("HTML graph saved: {0}".format(outpath))
    else:
        # Text summary
        for t in triples[:20]:
            if brand_filter and brand_filter not in [t.get("subject",""), t.get("object","")]:
                continue
            print("  {0} —{1}→ {2}".format(t.get("subject","?"), t.get("predicate","?"), t.get("object","?")))
        if len(triples) > 20:
            print("  ... and {0} more".format(len(triples) - 20))
        if hot:
            print()
            print("Hot cache keys: {0}".format(len(hot.get("keys", []))))

if __name__ == "__main__":
    main()
