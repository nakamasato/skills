#!/usr/bin/env python3
"""Render LLM-extracted analysis as a self-contained HTML guide for a local skill."""

from __future__ import annotations

import argparse
import html
import json
import re
import subprocess
import sys
from pathlib import Path

TEXT_SUFFIXES = {
    ".md", ".py", ".sh", ".js", ".ts", ".json", ".yaml", ".yml",
    ".toml", ".txt", ".xml", ".html", ".css", ".sql", ".go", ".rs",
}
MAX_SOURCE_BYTES = 300_000


def frontmatter(markdown: str) -> dict[str, str]:
    if not markdown.startswith("---\n"):
        return {}
    end = markdown.find("\n---", 4)
    if end < 0:
        return {}
    result = {}
    for line in markdown[4:end].splitlines():
        match = re.match(r"([\w-]+):\s*(.*)", line)
        if match:
            result[match.group(1)] = match.group(2).strip().strip("\"'")
    return result


def collect_files(root: Path) -> list[Path]:
    files = []
    for path in root.rglob("*"):
        if not path.is_file() or any(part.startswith(".") for part in path.relative_to(root).parts):
            continue
        if path.suffix.lower() in TEXT_SUFFIXES or path.name == "SKILL.md":
            files.append(path)
    return sorted(files, key=lambda p: (0 if p.name == "SKILL.md" else 1, str(p.relative_to(root)).lower()))


def git_diff(root: Path, files: list[Path]) -> tuple[str, str]:
    try:
        top = subprocess.run(["git", "-C", str(root), "rev-parse", "--show-toplevel"], capture_output=True, text=True, check=True).stdout.strip()
        subprocess.run(["git", "-C", top, "rev-parse", "--verify", "origin/main"], capture_output=True, check=True)
        rels = [p.relative_to(Path(top)).as_posix() for p in files if p.resolve().is_relative_to(Path(top).resolve())]
        if not rels:
            return "", "No tracked skill files were found in this repository."
        result = subprocess.run(["git", "-C", top, "diff", "--no-ext-diff", "origin/main", "--", *rels], capture_output=True, text=True, check=True)
        status = subprocess.run(["git", "-C", top, "status", "--short", "--", *rels], capture_output=True, text=True, check=True).stdout.strip()
        diff_text = result.stdout
        # `git diff` omits new untracked files; include them as additions so the
        # comparison still shows a newly created skill before it is staged.
        for rel in rels:
            tracked = subprocess.run(["git", "-C", top, "ls-files", "--error-unmatch", "--", rel], capture_output=True)
            if tracked.returncode == 0:
                continue
            source = Path(top, rel)
            try:
                content = source.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            lines = content.splitlines()
            diff_text += f"diff --git a/{rel} b/{rel}\nnew file mode 100644\n--- /dev/null\n+++ b/{rel}\n@@ -0,0 +1,{len(lines)} @@\n"
            diff_text += "".join("+" + line + "\n" for line in lines)
        note = "Compared the working tree with origin/main." + (" Working tree status: " + status if status else " No working tree changes detected.")
        return diff_text, note
    except (OSError, subprocess.CalledProcessError, ValueError):
        return "", "Git diff unavailable (the skill is not in a Git repository or origin/main is missing)."


def file_tree(root: Path, files: list[Path]) -> str:
    rows = []
    for path in files:
        rel = path.relative_to(root).as_posix()
        depth = rel.count("/")
        rows.append(f'<li style="--depth:{depth}"><span class="tree-line">{html.escape(path.name)}</span><small>{html.escape(rel)}</small></li>')
    return "".join(rows)


def read_analysis(source: str) -> dict[str, object]:
    try:
        raw = sys.stdin.read() if source == "-" else Path(source).expanduser().read_text(encoding="utf-8")
        analysis = json.loads(raw)
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Could not read analysis JSON: {exc}") from exc
    if not isinstance(analysis, dict):
        raise ValueError("Analysis JSON must be an object.")
    for key in ("sections", "details", "relationships"):
        if not isinstance(analysis.get(key), list):
            raise ValueError(f"Analysis JSON must contain a '{key}' array.")
    return analysis


def build_page(root: Path, analysis: dict[str, object], source_label: str | None = None) -> str:
    entry = root / "SKILL.md"
    if not entry.is_file():
        raise ValueError(f"No SKILL.md found in {root}")
    markdown = entry.read_text(encoding="utf-8")
    meta = frontmatter(markdown)
    title = meta.get("name", root.name)
    description = meta.get("description", "")
    files = collect_files(root)
    known_files = {"SKILL.md", *(p.relative_to(root).as_posix() for p in files)}
    edges = []
    for edge in analysis["relationships"]:
        if not isinstance(edge, dict):
            continue
        source, target = edge.get("from"), edge.get("to")
        if source not in known_files or target not in known_files:
            continue
        edges.append({"from": source, "to": target, "kind": str(edge.get("kind", "related")), "reason": str(edge.get("reason", ""))})
    diff, diff_note = git_diff(root, files)

    tabs = [{"id": "overview", "label": "Overview", "kind": "overview"}]
    for i, detail in enumerate(analysis["details"]):
        if not isinstance(detail, dict) or not detail.get("title"):
            continue
        label = str(detail.get("tab_label") or f"Part {i + 1}")
        if len(label) > 24:
            label = label[:21].rstrip() + "…"
        tabs.append({"id": f"detail-{i}", "label": label, "title": str(detail["title"]), "kind": "detail", "summary": str(detail.get("summary", ""))})
    tabs += [{"id": "code", "label": "Code", "kind": "code"}]

    source_items = []
    for path in files:
        try:
            raw = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        truncated = len(raw.encode("utf-8")) > MAX_SOURCE_BYTES
        if truncated:
            raw = raw[:MAX_SOURCE_BYTES] + "\n\n[Source truncated at 300 KB]"
        source_items.append({"path": path.relative_to(root).as_posix(), "content": raw})
    sections = [s for s in analysis["sections"] if isinstance(s, dict) and s.get("title")]
    applies_when = analysis.get("applies_when", [])
    data = {"tabs": tabs, "files": source_items, "edges": edges, "diff": diff, "diffNote": diff_note, "description": str(analysis.get("summary") or description), "appliesWhen": applies_when if isinstance(applies_when, list) else [], "tree": file_tree(root, files), "sections": sections, "name": title, "sourceRoot": source_label or str(root)}
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
    return PAGE.replace("__DATA__", payload)


PAGE = r'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Skill Visualizer</title>
<style>
:root{color-scheme:light;--ink:#172421;--muted:#61716b;--line:#dce5df;--paper:#f4f7f3;--card:#fff;--green:#176b54;--mint:#e4f4eb;--peach:#fff0df;--mono:ui-monospace,SFMono-Regular,Menlo,monospace}*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);font:15px/1.55 system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}header{padding:44px max(24px,calc((100vw - 1180px)/2));background:#153f35;color:#f4fbf6}header .eyebrow{font-size:12px;letter-spacing:.15em;text-transform:uppercase;color:#abd9c3}h1{font-size:clamp(30px,5vw,52px);line-height:1.05;margin:10px 0 14px}header p{max-width:850px;color:#d3e8dc;margin:0}.origin{font:12px var(--mono);color:#abd9c3;margin-top:22px;overflow-wrap:anywhere}main{max-width:1180px;margin:26px auto;padding:0 20px}.nav{display:flex;gap:8px;overflow:auto;padding:4px 0 14px;border-bottom:1px solid var(--line)}.nav button{white-space:nowrap;border:1px solid var(--line);border-radius:99px;background:white;padding:9px 15px;color:var(--muted);font:inherit;cursor:pointer}.nav button.active{background:var(--green);border-color:var(--green);color:white}.panel{display:none;padding:24px 0}.panel.active{display:block}.grid{display:grid;grid-template-columns:1.15fr .85fr;gap:18px}.card{background:var(--card);border:1px solid var(--line);border-radius:17px;padding:21px;box-shadow:0 4px 16px #153f3508}.card h2,.card h3{margin:0 0 12px}.card h2{font-size:19px}.card h3{font-size:15px}.muted{color:var(--muted)}.kicker{font-size:11px;letter-spacing:.12em;text-transform:uppercase;color:var(--green);font-weight:700}.outline,.tree{list-style:none;margin:12px 0 0;padding:0}.outline li,.tree li{padding:8px 0;border-bottom:1px solid #edf1ee}.outline b{font-size:12px;color:var(--green);margin-right:9px}.tree li{padding-left:calc(var(--depth)*18px);display:flex;justify-content:space-between;gap:16px}.tree small{color:var(--muted);font:11px var(--mono)}.map{display:flex;flex-direction:column;gap:8px;margin-top:12px}.node{border:1px solid var(--line);background:#fbfdfb;padding:10px 12px;border-radius:10px;font:12px var(--mono);overflow-wrap:anywhere}.edge{color:var(--muted);font-size:12px;padding-left:22px}.edge span{color:var(--green);font-weight:700}.step-card{margin-bottom:14px}.step-card p{margin:0;color:#40504a}.step-card .kicker{margin-bottom:6px}.empty{padding:18px;background:#f8faf8;border-radius:10px;color:var(--muted)}.source-layout{display:grid;grid-template-columns:260px 1fr;gap:15px}.filelist{display:flex;flex-direction:column;gap:5px;max-height:70vh;overflow:auto}.filelist button{text-align:left;overflow-wrap:anywhere;border:1px solid var(--line);border-radius:8px;background:white;padding:9px;font:12px var(--mono);cursor:pointer}.filelist button.active{border-color:var(--green);background:var(--mint)}.sourcebox{min-height:420px;max-height:70vh;overflow:auto;background:#101a17;border-radius:12px;color:#e2eee7;padding:18px}.sourcebox pre{margin:0;white-space:pre-wrap;overflow-wrap:anywhere;font:12px/1.6 var(--mono)}.source-head{display:flex;justify-content:space-between;gap:10px;align-items:center;margin-bottom:12px;color:#abd9c3;font:12px var(--mono)}.mode{display:flex;gap:6px}.mode button{background:#20362e;color:#d6e9dc;border:0;border-radius:6px;padding:5px 8px;cursor:pointer}.mode button.active{background:#579679}.badge{display:inline-block;background:var(--mint);color:var(--green);padding:3px 8px;border-radius:99px;font-size:11px;font-weight:700}.diffnote{margin-bottom:12px;color:var(--muted)}footer{color:var(--muted);font-size:12px;padding:30px 0;text-align:center}@media(max-width:760px){.grid,.source-layout{grid-template-columns:1fr}.filelist{max-height:200px}.tree li{display:block}.tree small{display:block;margin-top:3px}}
.section-row{padding:12px 0;border-bottom:1px solid #edf1ee}.section-row:last-child{border-bottom:0}.section-row h3{font-size:14px;margin:0 0 4px;color:var(--ink)}.section-row p{font-size:13px;line-height:1.5;margin:0;color:var(--muted)}.diagram{display:flex;flex-direction:column;gap:12px;margin-top:16px}.diagram-row{display:grid;grid-template-columns:minmax(120px,1fr) minmax(105px,150px) minmax(120px,1fr);align-items:center;gap:10px}.diagram-node{padding:12px 14px;border:1px solid #bdd8ca;background:#f5fbf7;border-radius:11px;font:12px/1.4 var(--mono);overflow-wrap:anywhere;box-shadow:0 2px 6px #153f3508}.diagram-node.entry{background:#e7f4ec;border-color:#87bea1}.connector{width:100%;height:48px;overflow:visible}.connector line{stroke:#43876b;stroke-width:2}.connector polygon{fill:#43876b}.connector text{fill:#52665c;font:11px system-ui,sans-serif}.diagram-legend{font-size:12px;color:var(--muted);margin-top:14px}@media(max-width:760px){.diagram-row{grid-template-columns:minmax(105px,1fr) 92px minmax(105px,1fr);gap:5px}.diagram-node{padding:10px;font-size:11px}}
+</style></head><body><header><div class="eyebrow">Skill field guide</div><h1 id="title"></h1><p id="description"></p><div class="origin" id="origin"></div></header><main><nav class="nav" id="nav"></nav><div id="panels"></div><footer>Generated locally · source content is displayed as text</footer></main>
<script>
const D=__DATA__;const esc=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
document.title=D.name+' · Skill Visualizer';document.getElementById('title').textContent=D.name;document.getElementById('description').textContent=D.description||'No description in SKILL.md.';document.getElementById('origin').textContent=D.sourceRoot;
const nav=document.getElementById('nav'),panels=document.getElementById('panels');
for(const t of D.tabs){const b=document.createElement('button');b.textContent=t.label;b.dataset.id=t.id;nav.appendChild(b);const p=document.createElement('section');p.className='panel';p.id=t.id;panels.appendChild(p);if(t.kind==='overview')p.innerHTML=overview();else if(t.kind==='detail')p.innerHTML=detail(t);else p.innerHTML=code();b.onclick=()=>activate(t.id)}
function activate(id){document.querySelectorAll('.nav button').forEach(x=>x.classList.toggle('active',x.dataset.id===id));document.querySelectorAll('.panel').forEach(x=>x.classList.toggle('active',x.id===id))}activate(D.tabs[0].id);
function overview(){const outline=D.sections.length?D.sections.map((s,i)=>`<li class="section-row"><h3>${String(i+1).padStart(2,'0')} · ${esc(s.title)}</h3><p>${esc(s.summary||'')}</p></li>`).join(''):'<li>No sections were identified.</li>';const edges=D.edges.length?D.edges.map(e=>`<div class="diagram-row"><div class="diagram-node ${e.from==='SKILL.md'?'entry':''}">${esc(e.from)}</div><svg class="connector" viewBox="0 0 150 48" role="img" aria-label="${esc(e.kind)} relationship" title="${esc(e.reason||e.kind)}"><line x1="4" y1="18" x2="143" y2="18"></line><polygon points="143,13 150,18 143,23"></polygon><text x="75" y="42" text-anchor="middle">${esc(e.kind)}</text></svg><div class="diagram-node">${esc(e.to)}</div></div>`).join('')+'<div class="diagram-legend">Arrows show relationships identified from the skill instructions and supporting files.</div>':'<div class="empty">No file relationships were identified.</div>';const applies=D.appliesWhen.length?D.appliesWhen.map(x=>`<li>${esc(x)}</li>`).join(''):'<li>Not specified in the analysis.</li>';return `<div class="grid"><article class="card"><div class="kicker">Structure</div><h2>Sections in SKILL.md</h2><ul class="outline">${outline}</ul></article><article class="card"><div class="kicker">Applicability</div><h2>When to use this skill</h2><ul class="outline">${applies}</ul></article><article class="card"><div class="kicker">Files</div><h2>Directory contents</h2><ul class="tree">${D.tree||'<li>No readable files found.</li>'}</ul></article><article class="card"><div class="kicker">Relationships</div><h2>Entrypoint and supporting files</h2><div class="diagram">${edges}</div></article></div>`}
function detail(t){const text=t.summary||'No explanation was provided for this detail.';return `<article class="card step-card"><div class="kicker">Skill detail</div><h2>${esc(t.title||t.label)}</h2><p>${esc(text)}</p></article><article class="card"><h3>Source files</h3><p class="muted">Open the Code tab to inspect SKILL.md and supporting files directly.</p></article>`}
let selected=0,showDiff=false;function code(){return `<div class="card"><div class="kicker">Source browser</div><h2>Skill files and Git diff</h2><p class="diffnote" id="diffnote"></p><div class="source-layout"><div class="filelist" id="filelist"></div><div class="sourcebox"><div class="source-head"><span id="filename"></span><div class="mode"><button id="sourcebtn" class="active">Source</button><button id="diffbtn">Diff</button></div></div><pre id="source"></pre></div></div></div>`}
const codeTab=D.tabs.find(x=>x.kind==='code');if(codeTab){const host=document.getElementById(codeTab.id);host.addEventListener('click',e=>{if(e.target.id==='sourcebtn'){showDiff=false;renderFile()}if(e.target.id==='diffbtn'){showDiff=true;renderFile()}});}
function initCode(){const list=document.getElementById('filelist');if(!list)return;document.getElementById('diffnote').textContent=D.diffNote;D.files.forEach((f,i)=>{const b=document.createElement('button');b.textContent=f.path;b.onclick=()=>{selected=i;showDiff=false;renderFile()};list.appendChild(b)});renderFile()}
function renderFile(){const list=document.getElementById('filelist');if(!list)return;[...list.children].forEach((b,i)=>b.classList.toggle('active',i===selected));const f=D.files[selected];document.getElementById('filename').textContent=showDiff?'origin/main diff':(f?.path||'No source');document.getElementById('source').textContent=showDiff?(D.diff||'No diff available for these files.'): (f?.content||'');document.getElementById('sourcebtn').classList.toggle('active',!showDiff);document.getElementById('diffbtn').classList.toggle('active',showDiff)}
initCode();
</script></body></html>'''


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("skill_path", type=Path, help="Skill directory or its SKILL.md")
    parser.add_argument("--output", type=Path, default=Path("skill-visualization.html"), help="Output HTML path (default: ./skill-visualization.html)")
    parser.add_argument("--analysis", required=True, help="LLM-extracted JSON file, or '-' to read JSON from stdin")
    parser.add_argument("--source-label", help="Display the original source URL instead of the local checkout path")
    args = parser.parse_args()
    root = args.skill_path.expanduser().resolve()
    if root.is_file() and root.name == "SKILL.md":
        root = root.parent
    output = args.output.expanduser().resolve()
    try:
        analysis = read_analysis(args.analysis)
        page = build_page(root, analysis, args.source_label)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(page, encoding="utf-8")
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    print(f"Wrote {output}")


if __name__ == "__main__":
    main()
