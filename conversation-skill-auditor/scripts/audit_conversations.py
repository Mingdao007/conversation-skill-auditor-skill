#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


HOME = Path.home()
CODEX_ROOT = HOME / ".codex"
CLAUDE_ROOT = HOME / ".claude"
MANIFEST_PATH = CODEX_ROOT / "context" / "skills-manifest.json"
SELF_SKILL_NAME = "conversation-skill-auditor"

NOISE_SUBSTRINGS = (
    "# agents.md instructions",
    "<instructions>",
    "you are codex, a coding agent",
    "<local-command-caveat>",
    "file-history-snapshot",
    "<proposed_plan>",
    "please implement this plan",
    "*** begin patch",
    "*** end patch",
    "chunk id:",
    "wall time:",
    "original token count:",
    "\"role\":\"developer\"",
    "\"role\":\"system\"",
)

TOPIC_PATTERNS = {
    "skill_meta": [
        r"\bskill\b",
        r"\bagent\b",
        r"\binstruction\b",
        r"\bcodex\b",
        r"\bclaude\b",
        r"\bsession(?:s)?\b",
        r"\bhistory\b",
        r"技能",
        r"对话记录",
    ],
    "research_control": [
        r"\bkoopman\b",
        r"\bpendulum\b",
        r"\bfr3\b",
        r"\bforce\b",
        r"\bimpedance\b",
        r"\bpid\b",
        r"\bhybrid\b",
        r"力控",
        r"流映射",
    ],
    "literature_outputs": [
        r"\bzotero\b",
        r"\breview\b",
        r"\bposter\b",
        r"\bpaper\b",
        r"\bliterature\b",
        r"\bsurvey\b",
        r"文献",
        r"海报",
    ],
    "course_work": [
        r"\bassignment\b",
        r"\bhomework\b",
        r"\bquiz\b",
        r"\bexam\b",
        r"\belec5640\b",
        r"\bme6603\b",
        r"作业",
        r"考试",
    ],
    "tooling_ops": [
        r"\bmcp\b",
        r"\bgithub\b",
        r"\bpdf\b",
        r"\bmac\b",
        r"\bvscode\b",
        r"\bdebug\b",
        r"\brepair\b",
        r"\bfix\b",
        r"工具",
        r"修复",
    ],
}

RECOMMENDATION_KEYWORDS = {
    "conversation_gap": [
        "所有对话记录",
        "历史对话",
        "skill md",
        "sessions",
        "history",
        "skill",
    ],
}

ENGLISH_SKILL_NAME_PATTERN = r"([A-Za-z][A-Za-z0-9_-]{1,60}(?:\s+[A-Za-z0-9_-]{1,60}){0,4})"

UNMET_SKILL_PATTERNS = [
    re.compile(rf"有没有做(?:过)?\s*{ENGLISH_SKILL_NAME_PATTERN}\s+skill(?![A-Za-z])", re.IGNORECASE),
    re.compile(rf"补(?:一个|个)?\s*{ENGLISH_SKILL_NAME_PATTERN}\s+skill(?![A-Za-z])", re.IGNORECASE),
    re.compile(rf"做(?:一个|个)?\s*{ENGLISH_SKILL_NAME_PATTERN}\s+skill(?![A-Za-z])", re.IGNORECASE),
    re.compile(rf"create\s+(?:a\s+)?{ENGLISH_SKILL_NAME_PATTERN}\s+skill(?![A-Za-z])", re.IGNORECASE),
    re.compile(rf"build\s+(?:a\s+)?{ENGLISH_SKILL_NAME_PATTERN}\s+skill(?![A-Za-z])", re.IGNORECASE),
    re.compile(rf"need\s+(?:a\s+)?{ENGLISH_SKILL_NAME_PATTERN}\s+skill(?![A-Za-z])", re.IGNORECASE),
    re.compile(rf"no\s+{ENGLISH_SKILL_NAME_PATTERN}\s+skill(?![A-Za-z])", re.IGNORECASE),
]

DEFAULT_CREATE_PRIORITY = 90
DEFAULT_WEAK_PRIORITY = 40
PROMOTED_PRIORITY = 95

WORKFLOW_TO_SKILL_PATTERNS = [
    re.compile(r"([^\n，。！？,.]{2,30}?工作流)[^\n，。！？,.]{0,24}?(?:做成|做(?:一个|个)?|只做一个)\s*skill", re.IGNORECASE),
]

PURPOSE_AFTER_SKILL_PATTERNS = [
    re.compile(r"(?:专门)?做(?:一个|个)?\s*skill(?:来|去)?\s*([^\n，。！？,.]{2,40})", re.IGNORECASE),
    re.compile(r"做成(?:一个|个)?\s*skill(?:并|来|去)\s*([^\n，。！？,.]{2,40})", re.IGNORECASE),
]

SKILL_COVERAGE_ALIASES = {
    "a separate blocker-tracking workflow": [
        "思维弱点",
        "弱点",
        "疑惑点",
        "卡点",
        "概念弱点",
    ],
    "health-tracker": [
        "健康跟踪",
        "跟踪健康",
        "健康记录",
    ],
    "read-clipboard": [
        "截图工作流",
        "读取截图",
        "读截图",
        "clipboard 工作流",
        "clipboard",
    ],
    "screenshot": [
        "截图工作流",
        "截图采集",
        "屏幕截图",
        "截图",
    ],
    "skill-publisher": [
        "上传到-github-工作流",
        "上传到-github",
        "upload-github",
        "github-upload",
    ],
    "thread-transfer": [
        "transfer",
        "thread-transfer",
    ],
    "literature-review-workflow": [
        "literature-review-workflow",
        "literature-review",
        "literature-review-流程",
        "literature-review-workflow",
    ],
    "skill-blueprint-coach": [
        "meta-skill",
        "meta-skill规范",
        "skill-creator",
        "skillscreator",
        "规范化-skill",
    ],
}

UNMET_DETECTION_SOURCES = {
    "codex:history",
    "codex:sessions",
    "codex:archived_sessions",
    "claude:history",
    "claude:projects",
}


@dataclass(frozen=True)
class CorpusItem:
    source: str
    path: str
    text: str


def normalize_text(text: str) -> str:
    return " ".join(text.split())


def excerpt(text: str, limit: int = 180) -> str:
    normalized = normalize_text(text)
    if len(normalized) <= limit:
        return normalized
    return normalized[: limit - 1].rstrip() + "…"


def slugify(value: str) -> str:
    value = normalize_text(value).lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    value = re.sub(r"-+", "-", value).strip("-")
    return value


def slugify_mixed(value: str) -> str:
    value = normalize_text(value).lower()
    value = re.sub(r"[^\u4e00-\u9fffa-z0-9]+", "-", value)
    value = re.sub(r"-+", "-", value).strip("-")
    return value


def normalize_candidate_phrase(raw: str) -> str:
    text = normalize_text(raw)
    replacements = (
        ("我的", ""),
        ("你的", ""),
        ("这个", ""),
        ("这套", ""),
        ("一下", ""),
        ("尝试", ""),
        ("专门", ""),
        ("一个", ""),
        ("个", ""),
        ("来", " "),
        ("去", " "),
    )
    for old, new in replacements:
        text = text.replace(old, new)
    text = text.strip("`'\"“”‘’[]()<>，。！？,. ")
    text = normalize_text(text)
    lowered = text.lower()
    if text in {"做这件事", "这件事"}:
        return ""
    if "matlab" in lowered:
        return "matlab-code"
    if "meta" in lowered or "规范化" in text:
        return "meta-skill"
    if "弱点" in text:
        return "思维弱点"
    if "健康" in text:
        return "健康跟踪"
    if "截图" in text or "clipboard" in lowered:
        return "截图工作流"
    if "literature review" in lowered:
        return "literature review workflow"
    if "transfer" in lowered:
        return "thread transfer"
    if "upload" in lowered and "github" in lowered:
        return "上传到 GitHub 工作流"
    if len(text) > 24:
        return text[:24].rstrip()
    return text


def candidate_key(value: str) -> str:
    return slugify_mixed(normalize_candidate_phrase(value))


def candidate_id(prefix: str, value: str) -> str:
    key = candidate_key(value) or slugify(value)
    if key:
        return f"{prefix}-{key}"
    digest = abs(hash(normalize_text(value))) % 1000000
    return f"{prefix}-{digest}"


def extract_unmet_skill_phrases(text: str) -> list[str]:
    phrases: list[str] = []
    for pattern in UNMET_SKILL_PATTERNS:
        for match in pattern.finditer(text):
            phrases.append(match.group(1))
    for pattern in WORKFLOW_TO_SKILL_PATTERNS:
        for match in pattern.finditer(text):
            phrases.append(match.group(1))
    for pattern in PURPOSE_AFTER_SKILL_PATTERNS:
        for match in pattern.finditer(text):
            phrases.append(match.group(1))
    return [normalize_candidate_phrase(phrase) for phrase in phrases if normalize_candidate_phrase(phrase)]


def is_noise(text: str) -> bool:
    stripped = normalize_text(text).strip()
    if not stripped:
        return True
    if stripped in {"。", ".", "/", "-", "--"}:
        return True
    lowered = stripped.lower()
    if any(marker in lowered for marker in NOISE_SUBSTRINGS):
        return True
    if lowered.startswith("/"):
        return True
    if lowered.startswith("<command-name>/"):
        return True
    if lowered.startswith("{") and '"type":"file-history-snapshot"' in lowered:
        return True
    if stripped.count("```") >= 2:
        return True
    return False


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    if not path.exists():
        return records
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return records


def add_item(
    items: list[CorpusItem],
    source: str,
    path: Path,
    text: str,
    dedupe: set[str],
) -> None:
    normalized = normalize_text(text)
    if is_noise(normalized):
        return
    key = normalized.lower()
    if key in dedupe:
        return
    dedupe.add(key)
    items.append(CorpusItem(source=source, path=str(path), text=normalized))


def collect_codex_threads(
    items: list[CorpusItem],
    dedupe: set[str],
    summary: dict[str, dict[str, Any]],
) -> None:
    db_path = CODEX_ROOT / "state_5.sqlite"
    source = summary["codex"]["threads_db"]
    source["path"] = str(db_path)
    if not db_path.exists():
        source["available"] = False
        return
    source["available"] = True
    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute(
            "select title, first_user_message from threads order by updated_at desc"
        ).fetchall()
    finally:
        conn.close()
    source["record_count"] = len(rows)
    for title, first_user_message in rows:
        if title:
            add_item(items, "codex:threads_db", db_path, title, dedupe)
        if first_user_message:
            add_item(items, "codex:threads_db", db_path, first_user_message, dedupe)


def collect_codex_session_index(
    items: list[CorpusItem],
    dedupe: set[str],
    summary: dict[str, dict[str, Any]],
) -> None:
    path = CODEX_ROOT / "session_index.jsonl"
    source = summary["codex"]["session_index"]
    source["path"] = str(path)
    if not path.exists():
        source["available"] = False
        return
    source["available"] = True
    rows = load_jsonl(path)
    source["record_count"] = len(rows)
    for row in rows:
        if row.get("thread_name"):
            add_item(items, "codex:session_index", path, row["thread_name"], dedupe)


def collect_codex_history(
    items: list[CorpusItem],
    dedupe: set[str],
    summary: dict[str, dict[str, Any]],
) -> None:
    path = CODEX_ROOT / "history.jsonl"
    source = summary["codex"]["history"]
    source["path"] = str(path)
    if not path.exists():
        source["available"] = False
        return
    source["available"] = True
    rows = load_jsonl(path)
    source["record_count"] = len(rows)
    source["session_count"] = len({row.get("session_id") for row in rows if row.get("session_id")})
    for row in rows:
        if row.get("text"):
            add_item(items, "codex:history", path, row["text"], dedupe)


def iter_codex_rollout_texts(path: Path) -> list[str]:
    texts: list[str] = []
    for row in load_jsonl(path):
        if row.get("type") != "response_item":
            continue
        payload = row.get("payload") or {}
        if payload.get("type") != "message" or payload.get("role") != "user":
            continue
        for chunk in payload.get("content") or []:
            text = chunk.get("text")
            if text:
                texts.append(text)
    return texts


def collect_codex_rollouts(
    root: Path,
    bucket: str,
    source_name: str,
    items: list[CorpusItem],
    dedupe: set[str],
    summary: dict[str, dict[str, Any]],
) -> None:
    source = summary["codex"][bucket]
    source["path"] = str(root)
    if not root.exists():
        source["available"] = False
        return
    files = sorted(root.rglob("*.jsonl"))
    source["available"] = True
    source["file_count"] = len(files)
    clean_messages = 0
    for path in files:
        for text in iter_codex_rollout_texts(path):
            before = len(items)
            add_item(items, source_name, path, text, dedupe)
            if len(items) > before:
                clean_messages += 1
    source["clean_message_count"] = clean_messages


def collect_claude_history(
    items: list[CorpusItem],
    dedupe: set[str],
    summary: dict[str, dict[str, Any]],
) -> None:
    path = CLAUDE_ROOT / "history.jsonl"
    source = summary["claude_cli"]["history"]
    source["path"] = str(path)
    if not path.exists():
        source["available"] = False
        return
    source["available"] = True
    rows = load_jsonl(path)
    source["record_count"] = len(rows)
    source["session_count"] = len({row.get("sessionId") for row in rows if row.get("sessionId")})
    source["project_count"] = len({row.get("project") for row in rows if row.get("project")})
    for row in rows:
        display = row.get("display")
        if display:
            add_item(items, "claude:history", path, display, dedupe)


def extract_claude_project_texts(path: Path) -> list[str]:
    texts: list[str] = []
    for row in load_jsonl(path):
        if row.get("type") != "user":
            continue
        message = row.get("message") or {}
        content = message.get("content")
        if isinstance(content, str):
            texts.append(content)
        elif isinstance(content, list):
            for part in content:
                if isinstance(part, dict) and part.get("text"):
                    texts.append(part["text"])
    return texts


def collect_claude_projects(
    items: list[CorpusItem],
    dedupe: set[str],
    summary: dict[str, dict[str, Any]],
) -> None:
    root = CLAUDE_ROOT / "projects"
    source = summary["claude_cli"]["projects"]
    source["path"] = str(root)
    if not root.exists():
        source["available"] = False
        return
    files = sorted(root.rglob("*.jsonl"))
    source["available"] = True
    source["jsonl_file_count"] = len(files)
    clean_messages = 0
    for path in files:
        for text in extract_claude_project_texts(path):
            before = len(items)
            add_item(items, "claude:projects", path, text, dedupe)
            if len(items) > before:
                clean_messages += 1
    source["clean_message_count"] = clean_messages


def load_manifest(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def manifest_index(manifest: dict[str, Any], ignored: set[str]) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for entry in manifest.get("entries", []):
        name = entry.get("name")
        if not name or name in ignored:
            continue
        index[name] = entry
    return index


def entry_text(entry: dict[str, Any]) -> str:
    parts: list[str] = [entry.get("name", "")]
    parts.extend(entry.get("primary_for") or [])
    parts.extend(entry.get("compatibility_for") or [])
    parts.extend(entry.get("notes") or [])
    if entry.get("runtime_description"):
        parts.append(entry["runtime_description"])
    return " ".join(parts).lower()


def anchor_is_covered(anchor: str, entries: dict[str, dict[str, Any]]) -> bool:
    anchor_slug = candidate_key(anchor)
    if not anchor_slug:
        return True
    anchor_tokens = [token for token in anchor_slug.split("-") if token]
    for skill_name, aliases in SKILL_COVERAGE_ALIASES.items():
        for alias in aliases:
            alias_slug = slugify_mixed(alias)
            if anchor_slug == alias_slug or anchor_slug in alias_slug or alias_slug in anchor_slug:
                if skill_name in entries:
                    return True
    for name, entry in entries.items():
        if anchor_slug == name:
            return True
        if anchor_slug in name or name in anchor_slug:
            return True
        text = entry_text(entry)
        if all(token in text for token in anchor_tokens):
            return True
    return False


def build_theme_summary(items: list[CorpusItem]) -> list[dict[str, Any]]:
    counts: Counter[str] = Counter()
    examples: dict[str, list[str]] = defaultdict(list)
    compiled = {
        name: [re.compile(pattern, re.IGNORECASE) for pattern in patterns]
        for name, patterns in TOPIC_PATTERNS.items()
    }
    for item in items:
        matched = False
        for name, patterns in compiled.items():
            if any(pattern.search(item.text) for pattern in patterns):
                counts[name] += 1
                matched = True
                if len(examples[name]) < 3:
                    examples[name].append(excerpt(item.text))
        if not matched:
            continue
    summary = []
    for name, count in counts.most_common():
        summary.append(
            {
                "name": name,
                "count": count,
                "examples": examples[name],
            }
        )
    return summary


def collect_representative_examples(items: list[CorpusItem], keywords: list[str], limit: int = 3) -> list[str]:
    matches: list[str] = []
    lowered_keywords = [keyword.lower() for keyword in keywords]
    for item in items:
        lowered = item.text.lower()
        if any(keyword in lowered for keyword in lowered_keywords):
            matches.append(excerpt(item.text))
        if len(matches) >= limit:
            break
    return matches


def build_source_counts(summary: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return {
        "codex": {
            "threads_db": summary["codex"]["threads_db"].get("record_count", 0),
            "session_index": summary["codex"]["session_index"].get("record_count", 0),
            "history": summary["codex"]["history"].get("record_count", 0),
            "sessions": summary["codex"]["sessions"].get("file_count", 0),
            "archived_sessions": summary["codex"]["archived_sessions"].get("file_count", 0),
        },
        "claude_cli": {
            "history": summary["claude_cli"]["history"].get("record_count", 0),
            "history_sessions": summary["claude_cli"]["history"].get("session_count", 0),
            "projects": summary["claude_cli"]["projects"].get("jsonl_file_count", 0),
        },
    }


def detect_unmet_skill_candidates(
    items: list[CorpusItem],
    entries: dict[str, dict[str, Any]],
    bootstrap_mode: bool,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    evidence_by_anchor: dict[str, dict[str, Any]] = {}
    for item in items:
        if item.source not in UNMET_DETECTION_SOURCES:
            continue
        for phrase in extract_unmet_skill_phrases(item.text):
            anchor = candidate_key(phrase)
            if not anchor or not phrase:
                continue
            if not bootstrap_mode and anchor == SELF_SKILL_NAME:
                continue
            if anchor_is_covered(phrase, entries):
                continue
            bucket = evidence_by_anchor.setdefault(
                anchor,
                {
                    "target_skill": phrase,
                    "examples": [],
                    "source_counts": Counter(),
                },
            )
            bucket["source_counts"][item.source] += 1
            if len(bucket["examples"]) < 4:
                bucket["examples"].append(excerpt(item.text))

    formal_recommendations: list[dict[str, Any]] = []
    weak_candidates: list[dict[str, Any]] = []
    for anchor, payload in sorted(evidence_by_anchor.items()):
        mention_count = len(payload["examples"])
        evidence = {
            "source_counts": {
                "unmet_skill_mentions": mention_count,
                "message_sources": dict(payload["source_counts"]),
            },
            "representative_examples": payload["examples"][:3],
            "existing_coverage": [],
        }
        draft_path = None
        ascii_slug = slugify(payload["target_skill"])
        if ascii_slug:
            draft_path = str(CODEX_ROOT / "skills" / ascii_slug)
        if mention_count >= 2:
            formal_recommendations.append(
                {
                    "action": "recommend_create",
                    "target": payload["target_skill"],
                    "reason": "Repeated unmet-skill phrasing appears in local conversation history, and no installed skill currently owns that capability.",
                    "evidence": evidence,
                    "tier": "formal",
                    "draft_path": draft_path,
                }
            )
            continue
        weak_candidates.append(
            {
                "candidate_id": candidate_id("weak", payload["target_skill"]),
                "kind": "create",
                "operation": "create_minimal_skill",
                "target_skill": payload["target_skill"],
                "priority": DEFAULT_WEAK_PRIORITY + mention_count,
                "reason": "A single explicit unmet-skill request appears in local history. Show it as a weak candidate and allow manual promotion if the user wants to create it.",
                "evidence": evidence,
                "draft_path": draft_path,
                "tier": "weak",
            }
        )
    weak_candidates.sort(key=lambda item: (-item["priority"], item["target_skill"]))
    return formal_recommendations, weak_candidates


def build_recommendations(
    items: list[CorpusItem],
    summary: dict[str, dict[str, Any]],
    theme_summary: list[dict[str, Any]],
    manifest: dict[str, Any] | None,
    bootstrap_mode: bool,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if manifest is None:
        return []
    ignored = {SELF_SKILL_NAME} if bootstrap_mode else set()
    entries = manifest_index(manifest, ignored)
    recommendations: list[dict[str, Any]] = []
    source_counts = build_source_counts(summary)
    theme_names = {item["name"] for item in theme_summary}

    recommendation_candidates, weak_candidates = detect_unmet_skill_candidates(items, entries, bootstrap_mode)
    recommendations.extend(recommendation_candidates)

    if (
        bootstrap_mode
        and
        source_counts["codex"]["threads_db"] > 0
        and source_counts["claude_cli"]["history"] > 0
        and "skill_meta" in theme_names
        and SELF_SKILL_NAME not in entries
    ):
        recommendations.append(
            {
                "action": "recommend_create",
                "target": SELF_SKILL_NAME,
                "reason": "Multiple local AI logs exist, but no installed skill owns cross-session, cross-tool conversation mining for skill-gap triage.",
                "evidence": {
                    "source_counts": source_counts,
                    "representative_examples": collect_representative_examples(
                        items, RECOMMENDATION_KEYWORDS["conversation_gap"]
                    ),
                    "existing_coverage": [],
                },
                "tier": "formal",
                "draft_path": str(CODEX_ROOT / "skills" / SELF_SKILL_NAME),
            }
        )
    return recommendations[:3], weak_candidates


def candidate_priority(recommendation: dict[str, Any]) -> int:
    action = recommendation["action"]
    if action == "recommend_create":
        mentions = recommendation["evidence"].get("source_counts", {}).get("unmet_skill_mentions", 0)
        return DEFAULT_CREATE_PRIORITY + min(mentions, 9)
    return 0


def actionable_operation(action: str) -> str | None:
    if action == "recommend_create":
        return "create_minimal_skill"
    return None


def build_actionable_candidates(
    recommendations: list[dict[str, Any]],
    manifest: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    if manifest is None:
        return []
    entries = manifest_index(manifest, set())
    candidates: list[dict[str, Any]] = []
    for recommendation in recommendations:
        operation = actionable_operation(recommendation["action"])
        if operation is None:
            continue
        target = recommendation["target"]
        draft_path = str(CODEX_ROOT / "skills" / target)
        kind = "create"
        identifier = candidate_id(kind, target)
        candidates.append(
            {
                "candidate_id": identifier,
                "kind": kind,
                "operation": operation,
                "target_skill": target,
                "priority": candidate_priority(recommendation),
                "reason": recommendation["reason"],
                "evidence": recommendation["evidence"],
                "draft_path": recommendation.get("draft_path", draft_path),
                "tier": "formal",
            }
        )
    candidates.sort(key=lambda item: (-item["priority"], item["target_skill"]))
    return candidates


def render_markdown(report: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# Local conversation audit")
    lines.append("")
    lines.append("## Source summary")
    for family, buckets in report["source_summary"].items():
        lines.append(f"- {family}")
        for name, payload in buckets.items():
            detail = ", ".join(
                f"{key}={value}"
                for key, value in payload.items()
                if key not in {"path"} and value not in (None, False, "", [])
            )
            lines.append(f"  - {name}: {detail or 'missing'}")
    lines.append("")
    lines.append("## Theme summary")
    for theme in report["theme_summary"]:
        lines.append(f"- {theme['name']}: {theme['count']}")
    lines.append("")
    lines.append("## Recommendations")
    if not report["recommendations"]:
        lines.append("- 本轮无新的 skill 创建建议")
    else:
        for rec in report["recommendations"]:
            lines.append(f"- {rec['action']} {rec['target']}: {rec['reason']}")
            examples = rec["evidence"].get("representative_examples") or []
            if examples:
                lines.append("  examples:")
                for example in examples:
                    lines.append(f"  - {example}")
    lines.append("")
    lines.append("## Weak candidates")
    if not report["weak_candidates"]:
        lines.append("- 本轮无弱候选")
    else:
        for candidate in report["weak_candidates"]:
            lines.append(f"- {candidate['candidate_id']} | {candidate['target_skill']}: {candidate['reason']}")
    lines.append("")
    lines.append("## Actionable candidates")
    if not report["actionable_candidates"]:
        lines.append("- 本轮无可确认生成项")
        return "\n".join(lines)
    for candidate in report["actionable_candidates"]:
        lines.append(
            f"- {candidate['kind']} {candidate['target_skill']} ({candidate['operation']}): {candidate['reason']}"
        )
    return "\n".join(lines)


def build_report(bootstrap_mode: bool) -> dict[str, Any]:
    summary: dict[str, dict[str, Any]] = {
        "codex": {
            "threads_db": {},
            "session_index": {},
            "history": {},
            "sessions": {},
            "archived_sessions": {},
        },
        "claude_cli": {
            "history": {},
            "projects": {},
        },
    }
    items: list[CorpusItem] = []
    dedupe: set[str] = set()

    collect_codex_threads(items, dedupe, summary)
    collect_codex_session_index(items, dedupe, summary)
    collect_codex_history(items, dedupe, summary)
    collect_codex_rollouts(CODEX_ROOT / "sessions", "sessions", "codex:sessions", items, dedupe, summary)
    collect_codex_rollouts(
        CODEX_ROOT / "archived_sessions",
        "archived_sessions",
        "codex:archived_sessions",
        items,
        dedupe,
        summary,
    )
    collect_claude_history(items, dedupe, summary)
    collect_claude_projects(items, dedupe, summary)

    manifest = load_manifest(MANIFEST_PATH)
    theme_summary = build_theme_summary(items)
    recommendations, weak_candidates = build_recommendations(items, summary, theme_summary, manifest, bootstrap_mode)
    actionable_candidates = build_actionable_candidates(recommendations, manifest)

    return {
        "source_summary": summary,
        "theme_summary": theme_summary,
        "recommendations": recommendations,
        "weak_candidates": weak_candidates,
        "actionable_candidates": actionable_candidates,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit local Codex and Claude CLI conversation logs for new-skill creation decisions."
    )
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON output.")
    parser.add_argument(
        "--bootstrap-mode",
        action="store_true",
        help="Ignore conversation-skill-auditor during coverage mapping.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_report(bootstrap_mode=args.bootstrap_mode)
    if args.json:
        json.dump(report, sys.stdout, indent=2, ensure_ascii=False)
        sys.stdout.write("\n")
    else:
        print(render_markdown(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
