# Generic Agent Skills checklist

Use this checklist when the intended host is unknown or is not covered by a host-specific reference. It is based on the [Agent Skills specification](https://agentskills.io/specification); the [overview](https://agentskills.io/home) describes the discovery, activation and execution model. It checks format and general portability only. It cannot establish compatibility with an unidentified host.

## Package and frontmatter

- The skill directory contains a `SKILL.md` with YAML frontmatter followed by Markdown instructions.
- `name` is present, 1–64 characters, lowercase letters, numbers and hyphens only, has no leading/trailing or consecutive hyphens, and matches the parent directory name.
- `description` is present, 1–1024 characters, and says both what the skill does and when to use it. Specific task keywords help discovery.
- If `compatibility` is present, it is 1–500 characters and states real environment requirements such as intended product, packages or network access.
- `metadata`, if present, is a mapping of string keys to string values. `allowed-tools` is experimental and support varies by implementation; do not assume it grants permissions on an unknown host.

## Instructions and resources

- The body gives useful task instructions. The format does not require a particular heading structure; assess clarity and completeness for the described workflow rather than imposing one template.
- Check that referenced files exist and use paths relative to the skill root. Prefer direct references from `SKILL.md` and avoid deep reference chains.
- Scripts should be self-contained or document dependencies, provide helpful errors and handle expected edge cases. Supported languages and executables depend on the eventual host.
- Keep `SKILL.md` focused for progressive disclosure: the full body is loaded on activation and supporting resources should be loaded only when needed. The specification recommends under 500 lines and under 5,000 tokens for the body; treat these as guidance, not universal host limits.

## Validation boundary

- If available, `skills-ref validate <skill-dir>` checks frontmatter and naming conventions. Report what it validates; it does not prove runtime compatibility or workflow correctness.
- Do not infer that host-specific frontmatter, invocation controls, shell substitutions, tools or permissions are supported. Mark those as unverified until a target host is identified.
- Do not execute skill instructions or scripts during review. Static inspection does not prove the workflow succeeds at runtime.
