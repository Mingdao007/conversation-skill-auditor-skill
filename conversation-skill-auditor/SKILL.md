---
name: conversation-skill-auditor
description: "Audit local Codex and Claude CLI conversation logs, detect unmet-skill requests, and return two create-only layers: weak candidates from single explicit requests and formal candidates from repeated or manually promoted requests. Use when the user asks to inspect local sessions or history and decide whether a genuinely new skill should be created from local demand."
---

# Conversation skill auditor

## Mission

Read local conversation sources, remove obvious prompt-injection and tool-output noise, and detect unmet-skill requests that justify a genuinely new skill.

Keep the workflow read-only by default. This skill reports recommendations. It does not edit other skills unless a separate skill-design workflow takes over.

## Trigger boundary

Use this skill when the user asks things like:
- `查看本地所有对话记录`
- `审计 sessions/history`
- `看历史对话要不要加 skill`
- `based on local AI sessions update skill`
- `根据本机聊天记录判断哪些新 skill 应该新增`

Do not use this skill for:
- ordinary single-thread summarization
- editing a skill package directly
- document-level review that does not depend on local session history
- web-chat products whose history is not exported to local files

Route follow-up work after the audit:
- create or redesign a skill: `skill-blueprint-coach`
- determinize wording in an existing `SKILL.md`: `instruction-determinizer`
- update stateful memory or supported adapters: `skill-sync`

## Default workflow

1. Run the local audit entrypoint:

```bash
python3 "$CODEX_HOME/skills/conversation-skill-auditor/scripts/audit_conversations.py"
```

Use `--json` when the result will be consumed programmatically.

2. Read only the supported local sources listed in `references/source-contract.md`.

3. Apply noise filtering before theme counting:
- skip repeated `startup instruction payload` injections
- skip system or developer prompt payloads
- skip slash commands such as `/mcp`, `/model`, `/clear`
- skip tool output, patch payloads, and `file-history-snapshot`
- skip `local-command-caveat` meta lines and empty punctuation-only entries

4. Cluster recurring demand using stable topic buckets. Keep the buckets compact and deterministic. The v1 buckets are:
- `skill_meta`
- `research_control`
- `literature_outputs`
- `course_work`
- `tooling_ops`

5. Map repeated unmet-skill requests against the installed skill inventory from `skills-manifest.json`.

Only emit create-layer output when no installed skill owns the capability.

For create candidates:
- accept Chinese or mixed-language unmet-skill phrasing from local logs
- keep single explicit requests as weak candidates
- upgrade repeated requests to formal create candidates
- do not invent a new skill name from a vague theme alone
- do not emit `conversation-skill-auditor` as a normal create candidate after it is installed
- preserve the original Chinese or mixed phrase in the candidate layer when the final skill name is not stable yet

6. Return two create-only layers:
- `weak_candidates` for single explicit requests
- `actionable_candidates` for repeated or manually promoted requests

Formal create suggestions should still include:
- the action label
- the target skill or skill set
- a short reason
- source counts
- representative examples
- whether existing coverage already exists

## Bootstrap validation mode

Use bootstrap mode only when validating whether this machine would have needed a dedicated auditor before this skill was installed:

```bash
python3 "$CODEX_HOME/skills/conversation-skill-auditor/scripts/audit_conversations.py" --bootstrap-mode
```

Bootstrap mode ignores `conversation-skill-auditor` itself during coverage mapping so the report can still say whether this capability deserved a new skill in the first place.

## Output contract

The script returns:
- `source_summary`
- `theme_summary`
- `recommendations`
- `weak_candidates`
- `actionable_candidates`

Each recommendation uses one of these labels only:
- `recommend_create`

Each actionable candidate must include:
- `candidate_id`
- `kind`
- `operation`
- `target_skill`
- `priority`
- `reason`
- `evidence`
- `draft_path`
- `tier`

Each weak candidate must include the same common fields and set `tier` to `weak`.

Keep recommendation targets stable and concrete. On this machine, the expected first-pass outcome is:
- bootstrap audit: create `conversation-skill-auditor` when validating whether this skill was needed before installation
- post-install audit: weak candidates may appear from single explicit requests, while formal create candidates stay empty unless repetition or manual promotion happens

## Failure handling

- If one source family is missing, report the missing source and continue with the remaining local sources.
- If one parser fails, keep the rest of the audit running and mark the source as partial.
- If `skills-manifest.json` is missing, return theme counts and source counts, then stop before coverage decisions.
- If the log corpus is too small after filtering, return `样本不足` instead of inventing recommendations.

## Resources

- `scripts/audit_conversations.py`: local log audit entrypoint
- `references/source-contract.md`: supported sources, noise filters, and output schema


## Validation And Checkpoints

- Before final handoff, validate the requested artifact or decision against this skill's output contract and report the verification result explicitly.
- Before any local mutation, pass the recoverability gate: create a rollback point when the change is reversible, and request confirmation when backup cannot cover the risk.
- Use an explicit checkpoint when required input is missing, tool evidence conflicts, or repeated attempts fail; wait for approval or route to the named owner instead of guessing.
- For multi-session work, update a progress or HANDOFF artifact with current state, verified result, and next executable step.
