# Contributing

Collaborative workflow for evolving this skill. If you're using the skill as a consumer, read `README.md` instead.

## Setup

```bash
# Clone directly into your Claude Code skills directory
git clone https://github.com/ideryang/pdf-to-pptx-clone.git \
  ~/.claude/skills/pdf-to-pptx-clone

# Install Python deps (one-time)
pip install --user PyMuPDF python-pptx Pillow fonttools
```

The skill auto-activates in Claude Code sessions when its description matches the user's request. To force-trigger during testing: *"use the pdf-to-pptx-clone skill on …"*.

## Day-to-day workflow

Always work on a branch, push, open a PR. No direct commits to `main` even when collaborating with just two people — the PR view makes the change reviewable, and `main` stays known-good.

```bash
cd ~/.claude/skills/pdf-to-pptx-clone
git checkout main && git pull           # sync to latest
git checkout -b your-name/short-topic   # branch
# … edit files …
git add . && git commit -m "Concise change summary"
git push -u origin your-name/short-topic
gh pr create   # or open the PR in the GitHub UI
```

When your PR merges, both of you `git pull` to update locally. Because the repo lives directly inside `~/.claude/skills/`, the new SKILL.md and scripts are picked up the next time the skill activates — no install step.

## What goes in a good change

This skill is a tool that runs against real PDFs. The bar for changes:

- **New behavior is documented.** New scripts get a docstring; new flags get mentioned in `SKILL.md`; new edge cases get a row in `references/pipeline.md` or `references/sibling_mode.md`.
- **Lessons learned go into the references.** When you debug a footgun (e.g., variable fonts don't render in Keynote, or PIL blur needs padding), capture the *why* in the relevant references file. Future runs of the skill — and future contributors — benefit.
- **`CHANGELOG.md` gets a line under the next version section.** Use semver-ish version numbers (`v0.5`, `v0.6`, ...). Bump the version when a release feels natural.

## Sanity-checks before opening a PR

1. **Validate SKILL.md format.** The skill-creator includes a validator:
   ```bash
   python3 -m scripts.quick_validate ~/.claude/skills/pdf-to-pptx-clone
   ```
   (You can find `skill-creator` in your local Claude Code skills directory if it isn't on PATH.)

2. **Run the pipeline on at least one real PDF** end-to-end and open the result. If you changed `extract_pdf.py`, `extract_design_tokens.py`, or `build_pptx.py`, also run on a second PDF with different typography/imagery to catch regressions.

3. **If you added a dependency**, update both `SKILL.md` (Dependencies section) and `CONTRIBUTING.md` (Setup section).

## Repo layout

```
pdf-to-pptx-clone/
├── SKILL.md                # entry point — what triggers, what it does
├── README.md               # consumer-facing — comparison vs. prompt + install
├── CHANGELOG.md            # human-readable history
├── CONTRIBUTING.md         # this file
├── .gitignore
├── scripts/                # the executable pipeline
└── references/             # docs Claude reads on demand
```

## When to ask vs. when to just do it

- **Just do it**: bug fixes, typo fixes, docstring improvements, new edge case notes in references.
- **PR with discussion**: new pipeline stages, changing existing JSON schemas (would break downstream tools), changing the SKILL.md description (affects auto-trigger), adding heavy dependencies.

## Releases

When you want to mark a stable point:

```bash
git tag v0.5 -m "v0.5 — short summary"
git push --tags
```

Friends can pin to a tag if they don't want bleeding-edge: `git checkout v0.5`. Default usage tracks `main`.
