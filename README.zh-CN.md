# Conversation Skill Auditor Skill

用于扫描本地 Codex 与 Claude CLI 对话历史、识别未被现有 skill 覆盖需求的可移植审计 skill。

## 提供内容

- 可安装 skill: [`conversation-skill-auditor`](./conversation-skill-auditor)
- 公开 references: [`conversation-skill-auditor/references/`](./conversation-skill-auditor/references)
- 辅助脚本: [`conversation-skill-auditor/scripts/`](./conversation-skill-auditor/scripts)

## 安装 / 使用

- `Codex App`：从本仓库路径 `conversation-skill-auditor` 安装
- GitHub 安装目标：
  - repo：`<owner>/conversation-skill-auditor-skill`
  - path：`conversation-skill-auditor`
- 安装后重启 `Codex App`，让新 skill 被发现。

## 覆盖范围

- 只读审计支持的本地 Codex 与 Claude CLI 历史来源
- 在主题统计前先做噪声过滤
- 区分 weak 与 actionable 两层 skill 候选输出

## 触发示例

- `Audit my local AI session history for missing skills.`
- `Check whether repeated requests justify a new skill.`
- `Inspect local Codex and Claude CLI sessions for unmet capability patterns.`

## 不触发示例

- `Summarize only this one current thread.`
- `Directly edit an existing skill package.`
- `Review a document that does not depend on local history.`

## 隐私边界

这个公开仓库只保留可复用、可公开的工作流部分。

- The published workflow stays read-only and generic to local history sources.
- Personal path references and startup-prompt noise labels are rewritten into host-generic wording.

## 仓库结构

- `conversation-skill-auditor/`: installable `Codex App` skill
- `conversation-skill-auditor/references/`: bundled public references
- `conversation-skill-auditor/scripts/`: bundled public scripts
- `CHANGELOG.md`: release history
- `LICENSE`: `MIT`

English:

- [README.md](./README.md)
