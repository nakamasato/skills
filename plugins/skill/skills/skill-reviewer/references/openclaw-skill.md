# OpenClaw skill review

Apply these checks only to skills intended for OpenClaw. Verify version-sensitive behavior against the [official Skills documentation](https://docs.openclaw.ai/tools/skills) and [Creating Skills guide](https://docs.openclaw.ai/tools/creating-skills).

## Discovery and invocation

- Check that the skill is under a configured OpenClaw skill root and that its frontmatter has a non-empty `name` and `description`. Grouped layouts use the frontmatter name (or, where supported, the directory name); check name collisions and source precedence when multiple roots are in scope.
- Check `user-invocable`, `disable-model-invocation`, and any command dispatch fields against the intended entry point. In particular, `command-dispatch: tool` bypasses model interpretation and requires a valid registered `command-tool`; do not assume slash-command and ordinary prompt invocation behave identically.
- Check `metadata.openclaw` gating (`os`, `requires.bins`, `requires.anyBins`, `requires.env`, `requires.config`, `always`) against the actual host/runtime configuration. Missing a requirement can hide the skill. Do not confuse gating with installing a dependency or granting a tool permission.
- If a connected remote runtime is used, verify requirements against the effective runtime, not just the Gateway host. Check snapshot/refresh behavior if the skill or its dependencies changed during a session.

## Runtime, resources and secrets

- Resolve `{baseDir}` and all script/reference paths relative to the skill directory and verify the referenced files exist. Check installer metadata for supported installer kinds and that the declared binary matches the skill's commands.
- Inspect scripts and instructions for host-side effects. OpenClaw warns that third-party skills are untrusted. Review shell commands, downloads, file writes, external requests and prompt-injection risks; never execute a skill as part of this review.
- `skills.entries.*.env` and `apiKey` are injected into the host agent process for the turn, not automatically into the sandbox. If sandboxed commands need a secret, verify the documented sandbox passthrough path; do not recommend placing secret values in prompts or skill files.
- Check symlinked skill paths and referenced resources remain within the trusted skill root unless the deployment explicitly allows external targets.

## Portability

- OpenClaw-only keys under `metadata.openclaw` are host extensions, not portable AgentSkills fields. For multi-host skills, verify that other hosts have a working alternative for gating, invocation and path substitution.
- Confirm the tools named in the body exist and are enabled for the target agent. A skill's metadata does not itself install tools, grant permissions, or make an unavailable executable callable.
