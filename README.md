# Conversation Skill Auditor Skill

Portable audit skill for scanning local Codex and Claude CLI conversation history to detect unmet-skill demand.

## What Ships

- installable skill: [`conversation-skill-auditor`](./conversation-skill-auditor)
- bundled public references: [`conversation-skill-auditor/references/`](./conversation-skill-auditor/references)
- bundled helper scripts: [`conversation-skill-auditor/scripts/`](./conversation-skill-auditor/scripts)

## Install / Use

- `Codex App`: install the skill from this repo path `conversation-skill-auditor`
- GitHub install target:
  - repo: `<owner>/conversation-skill-auditor-skill`
  - path: `conversation-skill-auditor`
- Restart `Codex App` after installation so the new skill is discovered.

## Coverage

- read-only auditing of supported local Codex and Claude CLI history sources
- noise filtering before theme counting and recommendation generation
- weak versus actionable candidate output for genuinely unmet skill requests

## Trigger Examples

- `Audit my local AI session history for missing skills.`
- `Check whether repeated requests justify a new skill.`
- `Inspect local Codex and Claude CLI sessions for unmet capability patterns.`

## Non-Trigger Examples

- `Summarize only this one current thread.`
- `Directly edit an existing skill package.`
- `Review a document that does not depend on local history.`

## Privacy Boundary

This public repository keeps the workflow generic and reusable.

- The published workflow stays read-only and generic to local history sources.
- Personal path references and startup-prompt noise labels are rewritten into host-generic wording.

## Repository Layout

- `conversation-skill-auditor/`: installable `Codex App` skill
- `conversation-skill-auditor/references/`: bundled public references
- `conversation-skill-auditor/scripts/`: bundled public scripts
- `CHANGELOG.md`: release history
- `LICENSE`: `MIT`

Chinese:

- [README.zh-CN.md](./README.zh-CN.md)
