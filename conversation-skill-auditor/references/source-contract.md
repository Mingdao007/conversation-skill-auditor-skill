# Source and output contract

## Supported local sources

### Codex
- `$CODEX_HOME/state_5.sqlite`
- `$CODEX_HOME/session_index.jsonl`
- `$CODEX_HOME/history.jsonl`
- `$CODEX_HOME/sessions/**/*.jsonl`
- `$CODEX_HOME/archived_sessions/*.jsonl`

### Claude CLI
- `$HOME/.claude/history.jsonl`
- `$HOME/.claude/projects/**/*.jsonl`

## Noise filters

Drop these before theme counting and recommendation generation:
- repeated startup instruction injections
- system or developer prompt bodies
- slash commands such as `/mcp`, `/model`, `/clear`
- `file-history-snapshot`
- `local-command-caveat`
- patch payloads, tool returns, and empty punctuation-only messages

## Recommendation labels

- `recommend_create`: no installed skill owns the repeated capability

## Bootstrap mode

Bootstrap mode ignores `conversation-skill-auditor` itself during skill mapping.

Use it only when validating whether the machine would have needed this skill before installation.

## Output schema

The script returns these top-level keys:
- `source_summary`
- `theme_summary`
- `recommendations`
- `weak_candidates`
- `actionable_candidates`

Each recommendation includes:
- `action`
- `target`
- `reason`
- `evidence.source_counts`
- `evidence.representative_examples`
- `evidence.existing_coverage`

Each actionable candidate includes:
- `candidate_id`
- `kind`
- `operation`
- `target_skill`
- `priority`
- `reason`
- `evidence`
- `draft_path`
- `tier`

Each weak candidate includes:
- `candidate_id`
- `kind`
- `operation`
- `target_skill`
- `priority`
- `reason`
- `evidence`
- `draft_path`
- `tier`

## Ordinary mode rule

In ordinary mode:
- only emit create-layer output
- do not emit installed `conversation-skill-auditor` as a create candidate
- allow `weak_candidates` from single explicit unmet-skill requests
- keep `actionable_candidates` empty unless repetition or manual promotion happens
