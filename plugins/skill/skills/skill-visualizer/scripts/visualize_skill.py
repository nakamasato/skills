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


def as_list(value: object) -> list:
    return value if isinstance(value, list) else []


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
        evidence = "inferred" if edge.get("evidence") == "inferred" else "explicit"
        edges.append({"from": source, "to": target, "kind": str(edge.get("kind", "related")), "reason": str(edge.get("reason", "")), "evidence": evidence})
    diff, diff_note = git_diff(root, files)

    tabs = [{"id": "overview", "label": "overview", "kind": "overview"}]
    for i, detail in enumerate(analysis["details"]):
        if not isinstance(detail, dict) or not detail.get("title"):
            continue
        label = str(detail.get("tab_label") or f"Part {i + 1}")
        if len(label) > 24:
            label = label[:21].rstrip() + "…"
        tabs.append({
            "id": f"detail-{i}", "label": label, "title": str(detail["title"]), "kind": "detail",
            "summary": str(detail.get("summary", "")), "brief": str(detail.get("brief", "")),
            "cards": [c for c in as_list(detail.get("cards")) if isinstance(c, dict) and c.get("title")],
            "notes": [n for n in as_list(detail.get("notes")) if isinstance(n, dict) and n.get("text")],
            "files": [f for f in as_list(detail.get("files")) if f in known_files],
        })
    tabs += [{"id": "structure", "label": "structure", "kind": "structure"}, {"id": "code", "label": "code", "kind": "code"}]

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
    data = {"tabs": tabs, "files": source_items, "edges": edges, "diff": diff, "diffNote": diff_note, "description": str(analysis.get("summary") or description), "appliesWhen": as_list(analysis.get("applies_when")), "notes": [n for n in as_list(analysis.get("notes")) if isinstance(n, dict) and n.get("text")], "sections": sections, "name": title, "lang": str(analysis.get("lang", "en")), "sourceRoot": source_label or str(root)}
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
    return TEMPLATE.read_text(encoding="utf-8").replace("__DATA__", payload)


TEMPLATE = Path(__file__).resolve().parent.parent / "assets" / "template.html"


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
