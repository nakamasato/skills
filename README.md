# Agent Skills

A plugin marketplace for Claude Code and Codex.

## Skills

| Skill | Plugin | Purpose |
|---|---|---|
| `md-doc-update` | `doc` | Update Markdown documentation |
| `md-doc-refactor` | `doc` | Refactor Markdown structure without changing meaning |
| `skill-reviewer` | `skill` | Review skill structure |
| `skill-visualizer` | `skill` | Generate an HTML guide to explore a skill |

## Installation

### Claude Code

```
/plugin marketplace add nakamasato/cc-skills
/plugin install doc@nakamasato
/plugin install skill@nakamasato
```

To try the plugins from a local clone, use `/plugin marketplace add ./`.

### Codex

```bash
codex plugin marketplace add nakamasato/cc-skills
codex plugin add doc@nakamasato
codex plugin add skill@nakamasato
```

Add the marketplace, then install the plugins you want to use.
