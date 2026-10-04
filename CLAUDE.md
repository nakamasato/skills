# Agent Skills

A plugin marketplace for Claude Code and Codex (`nakamasato`). See `README.md` for its structure and installation instructions.

## Adding Skills and Plugins

- Place skills in `plugins/<plugin>/skills/<skill>/SKILL.md`.
- When adding a plugin, register it in the `plugins` array in `.claude-plugin/marketplace.json`.
- Reference files from another skill using paths relative to the referencing file, not `~/.claude/skills/...`. Plugin-installed skills are not placed under `~/.claude/skills/`.

## Validation

Run both commands after making changes:

```
claude plugin validate .
claude plugin validate plugins/<plugin>
```
