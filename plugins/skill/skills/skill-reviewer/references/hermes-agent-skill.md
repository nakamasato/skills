# Hermes Agent skill review

Apply these checks only to skills intended for Hermes Agent. Verify version-sensitive behavior against the [official Skills System documentation](https://hermes-agent.nousresearch.com/docs/user-guide/features/skills/) and [Creating Skills guide](https://hermes-agent.nousresearch.com/docs/developer-guide/creating-skills/).

## Discovery and activation

- Check the installation/discovery location for the stated use: profile skills, configured external directories, or project-local `.hermes/skills/` / `.agents/skills/`. Project skills require the repository to be trusted; do not assume that merely cloning a repository makes them active.
- Check `name` and `description` frontmatter. Hermes can resolve an omitted name in some install flows, but a portable, reliably discoverable skill should declare it. Description length and the recommended section order are authoring guidance; report violations as quality issues, not automatic load failures.
- Check `platforms` against the target OS and `metadata.hermes.requires_toolsets`, `requires_tools`, `fallback_for_toolsets`, and `fallback_for_tools` against the active toolsets/tools. These conditions hide the skill when unmet; they do not install or enable the required tool.
- Check `metadata.hermes.config`, `required_environment_variables`, and `required_credential_files` against the setup procedure and the environment where commands run. Do not expose secret values in the skill.

## Runtime and resources

- Resolve `${HERMES_SKILL_DIR}` and `${HERMES_SESSION_ID}` only as Hermes substitutions; verify referenced files exist. For shared skills, identify alternatives for hosts that do not implement these variables.
- Inspect every `` !`command` `` inline shell snippet. When `skills.inline_shell` is enabled, snippets run on the host while the skill is loaded, without an approval prompt. Review them as executable code, including failure behavior and possible data exposure. Do not execute them during review.
- Check that scripts, dependencies and tool names exist in the target deployment. Hermes recommends minimizing external dependencies and placing common workflows before edge cases; treat these as quality guidance unless they prevent the requested workflow from running.
- If the skill declares `metadata.hermes.blueprint`, review its schedule and delivery behavior as an automation proposal; installation registers a suggestion, while scheduling requires acceptance. Do not mistake the declaration for a harmless descriptive field.
- Inspect supporting-file references and any scripts for unsafe behavior. Hermes security scans apply to certain installed sources, but do not assume every local or external skill has been scanned.

## Portability

- `metadata.hermes` fields, Hermes template variables, inline-shell syntax and blueprint metadata are Hermes-specific. For multi-host skills, check for a functional alternative or clearly scoped host-specific instructions.
- Validate the skill in Hermes only when execution is explicitly requested and the environment is appropriate. Static review alone cannot prove that the skill is activated or that its workflow succeeds.
