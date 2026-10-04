# GitHub Sources

Use this procedure when the requested target is a GitHub URL. It creates a temporary, shallow local checkout so the agent can read the skill files and the renderer can collect source and diff data.

## Resolve the URL

- A repository URL identifies a repository; discover its `SKILL.md` files and use the only match when there is one. If several skills are present and the requested one is unclear, ask which one to visualize.
- A `/tree/<ref>/<path>` URL identifies a directory. A `/blob/<ref>/<path>/SKILL.md` URL identifies a skill directly; use its parent directory.
- Normalize either URL to `https://github.com/<owner>/<repo>.git`, the selected ref, and the skill directory path. Do not pass the web URL's `/tree/` or `/blob/` suffix to `git clone`.

## Prepare the checkout

Use a temporary directory and the caller's existing GitHub access (public access or configured credentials):

```bash
git clone --depth 1 --filter=blob:none --sparse [--branch <ref>] <repository.git-url> <temporary-checkout>
```

For a known skill directory, check out that directory's files:

```bash
git -C <temporary-checkout> sparse-checkout set <skill-directory>
```

For a repository URL without a directory, list candidate skill entrypoints from the Git tree (`git -C <temporary-checkout> ls-tree -r --name-only HEAD`). Then sparse-checkout the selected skill directory before reading its files.

Fetch `main` into `origin/main` when available so the renderer can show the requested comparison:

```bash
git -C <temporary-checkout> fetch --depth=1 origin main:refs/remotes/origin/main
```

If cloning, selecting the path, or fetching `main` fails, explain the specific access or ref issue. Continue without the diff only when the skill files themselves are available. Generate the HTML outside the temporary checkout, then remove the checkout. The page embeds source text and diff data; use `--source-label` with the original GitHub URL so its header retains the source identity.
