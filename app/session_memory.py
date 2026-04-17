from __future__ import annotations

import json
import os
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from app.rag import BASE_DIR, normalize_history

MEMORY_STORE_PATH = BASE_DIR / "data" / "memory_registry.json"
LEGACY_MEMORY_STORE_PATH = BASE_DIR / "data" / "session_memory.json"
MEMORY_DOCS_DIR = BASE_DIR / "data" / "memory_docs"
OPENVIKING_MEMORY_ROOT_URI = os.getenv("ASKRAG_OPENVIKING_MEMORY_ROOT_URI", "viking://resources/askrag/memory")
MEMORY_SCHEMA_VERSION = 2

MEMORY_TYPES = (
    "raw_turn_log",
    "working_summary",
    "recent_task_state",
    "pinned_preference",
    "stable_profile_fact",
    "approved_long_term_fact",
)
MEMORY_TYPE_TO_LAYER = {
    "raw_turn_log": "L0",
    "working_summary": "L0",
    "recent_task_state": "L1",
    "pinned_preference": "L1",
    "stable_profile_fact": "L1",
    "approved_long_term_fact": "L2",
}
MEMORY_TYPE_TO_SCOPE = {
    "raw_turn_log": "session",
    "working_summary": "session",
    "recent_task_state": "cross_thread",
    "pinned_preference": "cross_thread",
    "stable_profile_fact": "cross_thread",
    "approved_long_term_fact": "cross_thread",
}
SHORT_LIVED_TYPES = {"raw_turn_log", "working_summary", "recent_task_state"}
SUPERCEDING_TYPES = {"pinned_preference", "stable_profile_fact"}
ALLOWED_STATUSES = ("pending", "approved", "rolled_back", "superseded")

RECENT_TASK_QUERY_TERMS = (
    "任务是什么",
    "我们在做什么",
    "我们现在在做什么",
    "当前任务",
    "最近任务",
    "今天任务是什么",
    "今天的任务是什么",
    "今天要做什么",
    "今天要做的任务",
    "刚才做到哪",
    "现在做到哪",
    "做到哪一步",
    "进度",
    "进展",
    "what are we doing",
    "what is the task",
    "current task",
    "where are we at",
    "what did we decide",
)

PROFILE_QUERY_TERMS = (
    "我住在哪里",
    "我住哪",
    "我住哪里",
    "我叫什么",
    "我是谁",
    "我来自哪里",
    "where do i live",
    "what is my name",
    "who am i",
    "where am i from",
)

PROFILE_QUERY_CATEGORY_TERMS = {
    "location": (
        "我住在哪里",
        "我住哪",
        "我住哪里",
        "where do i live",
        "where am i",
        "where am i located",
    ),
    "name": (
        "我叫什么",
        "我叫啥",
        "我是谁",
        "what is my name",
        "who am i",
    ),
    "origin": (
        "我来自哪里",
        "我从哪里来",
        "where am i from",
    ),
}

LANGUAGE_PATTERNS = (
    (
        re.compile(
            r"(?:^|[\s，,。.!?])(?:(?:请|請)\s*)?(?:(?:记住|記住)\s*)?(?:(?:以后|之后|之後|往后|后续|後續)\s*)?(?:(?:都|请|請)\s*)?(?:用|以)?\s*(?:中文|汉语|漢語|chinese)(?:来)?(?:回答|回复|回覆|作答)?",
            re.IGNORECASE,
        ),
        "zh-CN",
        "Prefer Chinese responses.",
    ),
    (
        re.compile(
            r"(?:^|[\s，,。.!?])(?:(?:请|請)\s*)?(?:(?:记住|記住)\s*)?(?:(?:以后|之后|之後|往后|后续|後續)\s*)?(?:(?:都|请|請)\s*)?(?:用|以)?\s*(?:英文|英语|英語|english)(?:来)?(?:回答|回复|回覆|作答)?",
            re.IGNORECASE,
        ),
        "en-US",
        "Prefer English responses.",
    ),
    (re.compile(r"\bprefer\s+chinese\b", re.IGNORECASE), "zh-CN", "Prefer Chinese responses."),
    (re.compile(r"\bprefer\s+english\b", re.IGNORECASE), "en-US", "Prefer English responses."),
)
STYLE_PATTERNS = (
    (re.compile(r"(?:简洁|精简|简短|精炼|concise|brief)", re.IGNORECASE), "concise", "Prefer concise answers."),
    (re.compile(r"(?:详细|展开|讲细|更细|detailed|verbose)", re.IGNORECASE), "detailed", "Prefer detailed answers."),
    (re.compile(r"(?:要点|列表|分点|bullet points?|bullet list)", re.IGNORECASE), "bullet_points", "Prefer answers in bullet points."),
)
MAX_ANSWER_LENGTH_PATTERNS = (
    re.compile(
        r"(?:(?:remember|记住|記住)\s*)?(?:(?:以后|之后|后面|后续)\s*)?"
        r"(?:回答|回复|回覆|答复|answer|answers|response|responses)"
        r"[^.!?\n]{0,24}?"
        r"(?:不超过|不要超过|不能超过|别超过|最多|少于|小于|控制在|限制在|under|within|less than|no more than)\s*"
        r"([0-9零〇一二两三四五六七八九十百千]+)\s*(?:字|字符|chars?|characters?)",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:(?:remember|记住|記住)\s*)?"
        r"(?:不超过|不要超过|不能超过|别超过|最多|少于|小于|控制在|限制在|under|within|less than|no more than)\s*"
        r"([0-9零〇一二两三四五六七八九十百千]+)\s*(?:字|字符|chars?|characters?)"
        r"[^.!?\n]{0,24}?"
        r"(?:回答|回复|回覆|答复|answer|answers|response|responses)",
        re.IGNORECASE,
    ),
)
EXPLICIT_MEMORY_PATTERN = re.compile(
    r"^\s*(?:(?:请|請)\s*)?(?:remember|记住|記住)\s*(?:[:：,，]\s*)?(.+?)\s*$",
    re.IGNORECASE,
)
PROFILE_PATTERNS = (
    (
        re.compile(r"(?:^|[\s，,])(?:i am|i'm|我是)\s*(male|man|男(?:的)?|female|woman|女(?:的)?)\b", re.IGNORECASE),
        "gender",
        lambda value: "male" if re.search(r"male|man|男", value, re.IGNORECASE) else "female",
        lambda normalized: f"User gender: {normalized}.",
    ),
    (
        re.compile(r"(?:^|[\s，,])(?:i live in|i am in|我住在|我在)\s*([A-Za-z\u4e00-\u9fff ._-]{2,40})", re.IGNORECASE),
        "location",
        lambda value: " ".join(value.strip().split()),
        lambda normalized: f"User location: {normalized}.",
    ),
    (
        re.compile(r"(?:^|[\s，,])(?:i am from|我来自|我來自)\s*([A-Za-z\u4e00-\u9fff ._-]{2,40})", re.IGNORECASE),
        "origin",
        lambda value: " ".join(value.strip().split()),
        lambda normalized: f"User origin: {normalized}.",
    ),
)
SUMMARY_SENTENCE_SPLIT = re.compile(r"(?<=[.!?。！？])\s+")
NORMALIZE_SPACE = re.compile(r"\s+")
NON_ALNUM = re.compile(r"[^a-z0-9]+")
CHINESE_DIGITS = {"零": 0, "〇": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
CHINESE_UNITS = {"十": 10, "百": 100, "千": 1000}
REFERENCE_HISTORY_TERMS = (
    "继续",
    "刚才",
    "上面",
    "前面",
    "这个",
    "那个",
    "这些",
    "这篇",
    "这份",
    "it",
    "this",
    "that",
    "these",
    "again",
    "continue",
    "follow-up",
    "follow up",
    "verify these claims",
    "this summary",
    "that summary",
)


@dataclass(frozen=True, slots=True)
class SummaryMemoryContext:
    user_question: str
    assistant_answer: str
    sources: list[str]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _parse_timestamp(value: str | None) -> datetime | None:
    normalized = str(value or "").strip()
    if not normalized:
        return None
    try:
        return datetime.fromisoformat(normalized.replace("Z", "+00:00"))
    except ValueError:
        return None


def _slugify(value: str) -> str:
    normalized = NON_ALNUM.sub("-", (value or "").casefold()).strip("-")
    return normalized[:64] or "memory"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _default_store() -> dict[str, Any]:
    return {"schema_version": MEMORY_SCHEMA_VERSION, "entries": [], "audit": []}


def _normalize_text(value: str) -> str:
    return NORMALIZE_SPACE.sub(" ", (value or "").casefold()).strip()


def _trimmed_sentence(text: str, limit: int = 180) -> str:
    normalized = NORMALIZE_SPACE.sub(" ", (text or "").strip())
    if not normalized:
        return ""
    parts = SUMMARY_SENTENCE_SPLIT.split(normalized, maxsplit=1)
    sentence = parts[0].strip() if parts else normalized
    return sentence[:limit].rstrip()


def _parse_chinese_number(text: str) -> int | None:
    normalized = str(text or "").strip()
    if not normalized:
        return None
    if normalized.isdigit():
        return int(normalized)

    total = 0
    current = 0
    has_digit = False
    for char in normalized:
        if char in CHINESE_DIGITS:
            current = CHINESE_DIGITS[char]
            has_digit = True
            continue
        if char in CHINESE_UNITS:
            unit = CHINESE_UNITS[char]
            if current == 0:
                current = 1
            total += current * unit
            current = 0
            has_digit = True
            continue
        return None

    if not has_digit:
        return None
    return total + current


def _extract_max_answer_chars(question: str) -> int | None:
    text = str(question or "")
    for pattern in MAX_ANSWER_LENGTH_PATTERNS:
        match = pattern.search(text)
        if not match:
            continue
        value = _parse_chinese_number(match.group(1))
        if value is None or value <= 0:
            continue
        return min(value, 2000)
    return None


def _build_expiry(memory_type: str) -> str | None:
    now = _now()
    if memory_type == "raw_turn_log":
        return (now + timedelta(days=3)).isoformat(timespec="seconds").replace("+00:00", "Z")
    if memory_type == "working_summary":
        return (now + timedelta(days=7)).isoformat(timespec="seconds").replace("+00:00", "Z")
    if memory_type == "recent_task_state":
        return (now + timedelta(days=14)).isoformat(timespec="seconds").replace("+00:00", "Z")
    return None


def _is_expired(entry: dict[str, Any], *, now: datetime | None = None) -> bool:
    expires_at = _parse_timestamp(str(entry.get("expires_at") or ""))
    if expires_at is None:
        return False
    reference = now or _now()
    return expires_at <= reference


def _is_active_entry(entry: dict[str, Any]) -> bool:
    status = str(entry.get("status") or "")
    return status in {"pending", "approved"} and not _is_expired(entry)


def _memory_type_to_layer(memory_type: str) -> str:
    if memory_type not in MEMORY_TYPE_TO_LAYER:
        raise ValueError("Unsupported memory type.")
    return MEMORY_TYPE_TO_LAYER[memory_type]


def _memory_type_to_scope(memory_type: str) -> str:
    if memory_type not in MEMORY_TYPE_TO_SCOPE:
        raise ValueError("Unsupported memory type.")
    return MEMORY_TYPE_TO_SCOPE[memory_type]


def _entry_subject_key(memory_type: str, payload: dict[str, Any], summary: str) -> str:
    subject_key = str(payload.get("subject_key") or "").strip()
    if subject_key:
        return subject_key
    if memory_type == "raw_turn_log":
        return f"turn:{_slugify(str(payload.get('question') or ''))}:{_slugify(str(payload.get('answer_excerpt') or ''))}"
    if memory_type == "working_summary":
        return f"working:{_slugify(str(payload.get('question') or ''))}"
    if memory_type == "recent_task_state":
        return f"task:{_slugify(summary)}"
    return f"{memory_type}:{_slugify(summary)}"


def _default_status(memory_type: str, payload: dict[str, Any]) -> str:
    if memory_type in {"raw_turn_log", "working_summary", "recent_task_state"}:
        return "approved"
    if memory_type in {"pinned_preference", "stable_profile_fact"} and payload.get("auto_approve", True):
        return "approved"
    if memory_type == "approved_long_term_fact" and payload.get("auto_approve"):
        return "approved"
    return "pending"


def _memory_uri(entry: dict[str, Any]) -> str:
    layer = str(entry.get("layer") or "L1").casefold()
    entry_id = str(entry.get("id") or "")
    return f"{OPENVIKING_MEMORY_ROOT_URI.rstrip('/')}/{layer}/{entry_id}"


def _memory_doc_path(entry: dict[str, Any]) -> Path:
    layer = str(entry.get("layer") or "L1").casefold()
    return MEMORY_DOCS_DIR / layer / f"{entry['id']}.md"


def _normalize_conversation_id(value: str | None) -> str:
    return str(value or "").strip()


def _attach_conversation_context(entry: dict[str, Any], conversation_id: str | None) -> dict[str, Any]:
    normalized = _normalize_conversation_id(conversation_id)
    if not normalized:
        return entry
    entry["conversation_id"] = normalized
    payload = entry.get("payload")
    if not isinstance(payload, dict):
        payload = {}
    payload["conversation_id"] = normalized
    entry["payload"] = payload
    return entry


def _memory_markdown(entry: dict[str, Any]) -> str:
    payload = json.dumps(entry.get("payload") or {}, ensure_ascii=False, indent=2)
    lines = [
        f"# {entry.get('title') or entry.get('memory_type')}",
        "",
        f"- id: {entry.get('id')}",
        f"- type: {entry.get('memory_type')}",
        f"- layer: {entry.get('layer')}",
        f"- scope: {entry.get('scope')}",
        f"- status: {entry.get('status')}",
        f"- confidence: {entry.get('confidence')}",
        f"- updated_at: {entry.get('updated_at')}",
    ]
    expires_at = str(entry.get("expires_at") or "").strip()
    if expires_at:
        lines.append(f"- expires_at: {expires_at}")
    lines.extend(
        [
            "",
            "## Summary",
            "",
            str(entry.get("summary") or "").strip(),
            "",
            "## Payload",
            "",
            "```json",
            payload,
            "```",
        ]
    )
    return "\n".join(lines).strip() + "\n"


def _sync_entry_to_openviking(entry: dict[str, Any]) -> None:
    entry["openviking_resource_uri"] = _memory_uri(entry)
    local_path = _memory_doc_path(entry)
    local_path.parent.mkdir(parents=True, exist_ok=True)
    local_path.write_text(_memory_markdown(entry), encoding="utf-8")

    try:
        from app import openviking_runtime

        health_timeout = max(2, int(os.getenv("ASKRAG_OPENVIKING_MEMORY_HEALTH_TIMEOUT_SECONDS", "5")))
        health_result = openviking_runtime._run_ov_json_command("health", "-o", "json", timeout=health_timeout)
        if not isinstance(health_result, dict) or not health_result.get("healthy", False):
            raise openviking_runtime.OpenVikingRuntimeError("OpenViking server is not healthy.")
        openviking_runtime.ensure_openviking_directories(OPENVIKING_MEMORY_ROOT_URI)
        openviking_runtime.ensure_openviking_directories(f"{OPENVIKING_MEMORY_ROOT_URI}/{str(entry.get('layer') or 'L1').casefold()}")
        try:
            openviking_runtime._run_ov_command("rm", entry["openviking_resource_uri"], "-r", "-o", "json", timeout=30)
        except openviking_runtime.OpenVikingRuntimeError as error:
            if "not found" not in str(error).casefold():
                raise

        openviking_runtime._run_ov_json_command(
            "add-resource",
            str(local_path),
            "--to",
            entry["openviking_resource_uri"],
            "--wait",
            "--timeout",
            str(openviking_runtime.DEFAULT_OV_TIMEOUT),
            "-o",
            "json",
            timeout=max(openviking_runtime.DEFAULT_OV_TIMEOUT * 2, 120),
        )
        entry["openviking_sync_status"] = "synced"
        entry["openviking_last_synced_at"] = utc_now()
        entry.pop("openviking_last_sync_error", None)
    except Exception as error:  # pragma: no cover - sync is best effort in tests
        message = str(error).strip()
        entry["openviking_sync_status"] = "sync_skipped" if "cli" in message.casefold() or "not found" in message.casefold() else "sync_error"
        entry["openviking_last_sync_error"] = message


def _delete_entry_artifacts(entry: dict[str, Any]) -> None:
    local_path = _memory_doc_path(entry)
    try:
        local_path.unlink(missing_ok=True)
    except TypeError:  # pragma: no cover - Python < 3.8 compatibility fallback
        if local_path.exists():
            local_path.unlink()

    resource_uri = str(entry.get("openviking_resource_uri") or "").strip()
    if not resource_uri:
        return

    try:
        from app import openviking_runtime

        openviking_runtime._run_ov_command("rm", resource_uri, "-r", "-o", "json", timeout=30)
    except Exception:  # pragma: no cover - best effort cleanup
        return


def _append_audit(store: dict[str, Any], action: str, memory_id: str, **detail: Any) -> None:
    audit = list(store.get("audit") or [])
    audit.insert(0, {"timestamp": utc_now(), "action": action, "memory_id": memory_id, **detail})
    store["audit"] = audit[:100]


def _entry_matches_conversation(
    entry: dict[str, Any],
    *,
    conversation_id: str,
    conversation_texts: set[str],
) -> bool:
    normalized_conversation_id = _normalize_conversation_id(conversation_id)
    if not normalized_conversation_id:
        return False

    payload = dict(entry.get("payload") or {})
    entry_conversation_id = _normalize_conversation_id(entry.get("conversation_id") or payload.get("conversation_id"))
    if entry_conversation_id and entry_conversation_id == normalized_conversation_id:
        return True

    if not conversation_texts:
        return False

    memory_type = str(entry.get("memory_type") or "")
    if memory_type not in SHORT_LIVED_TYPES:
        return False

    candidate_texts = [
        str(payload.get("question") or "").strip(),
        str(payload.get("answer_excerpt") or "").strip(),
        str(entry.get("summary") or "").strip(),
    ]
    for candidate in candidate_texts:
        normalized_candidate = _normalize_text(candidate)
        if not normalized_candidate:
            continue
        for text in conversation_texts:
            if not text:
                continue
            if normalized_candidate == text or normalized_candidate in text or text in normalized_candidate:
                return True
    return False


def _build_entry(
    memory_type: str,
    title: str,
    summary: str,
    *,
    payload: dict[str, Any],
    source_refs: list[str] | None = None,
    tags: list[str] | None = None,
    status: str | None = None,
    confidence: float = 0.8,
) -> dict[str, Any]:
    if memory_type not in MEMORY_TYPES:
        raise ValueError("Unsupported memory type.")
    timestamp = utc_now()
    subject_key = _entry_subject_key(memory_type, payload, summary)
    entry_status = status or _default_status(memory_type, payload)
    return {
        "id": str(uuid.uuid4()),
        "memory_type": memory_type,
        "layer": _memory_type_to_layer(memory_type),
        "scope": _memory_type_to_scope(memory_type),
        "status": entry_status,
        "title": title.strip(),
        "summary": summary.strip(),
        "payload": {**payload, "subject_key": subject_key},
        "subject_key": subject_key,
        "source_refs": [item for item in (source_refs or []) if item],
        "tags": [item for item in (tags or []) if item],
        "confidence": float(confidence),
        "created_at": timestamp,
        "updated_at": timestamp,
        "expires_at": _build_expiry(memory_type),
        "openviking_resource_uri": "",
        "openviking_sync_status": "pending_sync",
    }


def _remembered_content(question: str) -> str:
    match = EXPLICIT_MEMORY_PATTERN.search((question or "").strip())
    if not match:
        return ""
    remembered = " ".join(match.group(1).strip().split())
    return remembered.strip(" ,，。.!?？；;:：")


def _preference_entries(question: str) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    remembered = _remembered_content(question)
    explicit_memory = bool(remembered)

    for pattern, value, summary in LANGUAGE_PATTERNS:
        if not pattern.search(question):
            continue
        entries.append(
            _build_entry(
                "pinned_preference",
                "Language preference",
                summary,
                payload={
                    "question": question.strip(),
                    "preference_key": "response_language",
                    "value": value,
                    "subject_key": "preference:response_language",
                    "auto_approve": True,
                },
                tags=["preference", "language"],
                confidence=0.96,
            )
        )

    for pattern, value, summary in STYLE_PATTERNS:
        if not pattern.search(question):
            continue
        entries.append(
            _build_entry(
                "pinned_preference",
                "Response style preference",
                summary,
                payload={
                    "question": question.strip(),
                    "preference_key": "response_style",
                    "value": value,
                    "subject_key": "preference:response_style",
                    "auto_approve": True,
                },
                tags=["preference", "style"],
                confidence=0.9,
            )
        )

    max_answer_chars = _extract_max_answer_chars(question)
    if max_answer_chars is not None:
        entries.append(
            _build_entry(
                "pinned_preference",
                "Answer length preference",
                f"Keep answers within {max_answer_chars} characters.",
                payload={
                    "question": question.strip(),
                    "preference_key": "max_answer_chars",
                    "value": max_answer_chars,
                    "subject_key": "preference:max_answer_chars",
                    "auto_approve": True,
                },
                tags=["preference", "length"],
                confidence=0.92,
            )
        )

    if explicit_memory and remembered and not entries:
        entries.append(
            _build_entry(
                "pinned_preference",
                "Pinned memory",
                f"Remember: {remembered}.",
                payload={
                    "question": question.strip(),
                    "instruction": remembered,
                    "subject_key": f"pinned:{_slugify(remembered)}",
                    "auto_approve": True,
                },
                tags=["preference", "explicit"],
                confidence=0.94,
            )
        )
    return entries


def _profile_entries(question: str) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for pattern, profile_key, normalize_value, summary_builder in PROFILE_PATTERNS:
        match = pattern.search(question or "")
        if not match:
            continue
        raw_value = match.group(1).strip()
        normalized_value = normalize_value(raw_value)
        entries.append(
            _build_entry(
                "stable_profile_fact",
                f"User {profile_key}",
                summary_builder(normalized_value),
                payload={
                    "question": question.strip(),
                    "profile_key": profile_key,
                    "value": normalized_value,
                    "source": "user_stated",
                    "subject_key": f"profile:{profile_key}",
                    "auto_approve": True,
                },
                tags=["profile", profile_key],
                confidence=0.95,
            )
        )
    return entries


def _task_entries(question: str, answer: str, source_refs: list[str], history_turns: int) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    if source_refs:
        source_label = ", ".join(Path(source).name for source in source_refs[:2])
        entries.append(
            _build_entry(
                "recent_task_state",
                "Recent document focus",
                f"Recent discussion referenced {source_label}.",
                payload={
                    "question": question.strip(),
                    "sources": source_refs[:3],
                    "subject_key": f"recent_source:{_slugify('|'.join(source_refs[:3]))}",
                },
                source_refs=source_refs[:3],
                tags=["document", "recent"],
                confidence=0.78,
            )
        )

    answer_sentence = _trimmed_sentence(answer)
    if answer_sentence:
        entries.append(
            _build_entry(
                "recent_task_state",
                "Recent task state",
                answer_sentence,
                payload={
                    "question": question.strip(),
                    "answer_excerpt": answer_sentence,
                    "history_turns": history_turns,
                },
                source_refs=source_refs[:3],
                tags=["task", "recent"],
                confidence=0.72,
            )
        )
    return entries


def _turn_log_entry(question: str, answer: str, source_refs: list[str], history_turns: int) -> dict[str, Any] | None:
    answer_sentence = _trimmed_sentence(answer, limit=240)
    if not question.strip() and not answer_sentence:
        return None
    return _build_entry(
        "raw_turn_log",
        "Conversation turn",
        f"Q: {question.strip()} A: {answer_sentence}".strip(),
        payload={
            "question": question.strip(),
            "answer_excerpt": answer_sentence,
            "sources": source_refs[:5],
            "history_turns": history_turns,
        },
        source_refs=source_refs[:5],
        tags=["turn", "session"],
        confidence=1.0,
    )


def _working_summary_entry(question: str, answer: str, source_refs: list[str]) -> dict[str, Any] | None:
    answer_sentence = _trimmed_sentence(answer)
    if not answer_sentence:
        return None
    return _build_entry(
        "working_summary",
        "Working summary",
        answer_sentence,
        payload={
            "question": question.strip(),
            "answer_excerpt": answer_sentence,
            "sources": source_refs[:5],
        },
        source_refs=source_refs[:5],
        tags=["working", "summary"],
        confidence=0.84,
    )


def _dedupe_candidates(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for candidate in candidates:
        key = (
            str(candidate.get("memory_type") or ""),
            str(candidate.get("subject_key") or candidate.get("payload", {}).get("subject_key") or "").casefold(),
            str(candidate.get("summary") or "").casefold(),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(candidate)
    return deduped


def _convert_legacy_entry(entry: dict[str, Any]) -> dict[str, Any] | None:
    memory_type = str(entry.get("memory_type") or "").strip()
    summary = str(entry.get("summary") or "").strip()
    payload = dict(entry.get("payload") or {})
    source_refs = [str(item) for item in entry.get("source_refs") or [] if str(item).strip()]
    tags = [str(item) for item in entry.get("tags") or [] if str(item).strip()]
    status = str(entry.get("status") or "pending")
    if memory_type == "user_preference":
        new_type = "pinned_preference"
        payload.setdefault("subject_key", f"legacy_preference:{_slugify(summary)}")
    elif memory_type in {"document_relation", "task_result"}:
        new_type = "recent_task_state"
    else:
        return None

    converted = _build_entry(
        new_type,
        str(entry.get("title") or summary or new_type),
        summary or str(entry.get("title") or new_type),
        payload=payload,
        source_refs=source_refs,
        tags=tags,
        status=status if status in ALLOWED_STATUSES else _default_status(new_type, payload),
        confidence=float(entry.get("confidence") or 0.75),
    )
    for key in (
        "id",
        "created_at",
        "updated_at",
        "approved_at",
        "rolled_back_at",
        "superseded_at",
        "superseded_by",
        "expires_at",
        "openviking_resource_uri",
        "openviking_sync_status",
        "openviking_last_synced_at",
        "openviking_last_sync_error",
    ):
        if key in entry and entry.get(key) not in {None, ""}:
            converted[key] = entry[key]
    converted["layer"] = _memory_type_to_layer(new_type)
    converted["scope"] = _memory_type_to_scope(new_type)
    converted["subject_key"] = str(converted.get("subject_key") or converted.get("payload", {}).get("subject_key") or "")
    return converted


def _migrate_legacy_store() -> None:
    if MEMORY_STORE_PATH.exists() or not LEGACY_MEMORY_STORE_PATH.exists():
        return
    try:
        payload = json.loads(LEGACY_MEMORY_STORE_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        payload = {}

    store = _default_store()
    entries = []
    for item in payload.get("entries") or []:
        if not isinstance(item, dict):
            continue
        converted = _convert_legacy_entry(item)
        if converted is not None:
            entries.append(converted)
    store["entries"] = entries
    store["audit"] = [item for item in payload.get("audit") or [] if isinstance(item, dict)]
    write_memory_store(store)


def read_memory_store() -> dict[str, Any]:
    _migrate_legacy_store()
    if not MEMORY_STORE_PATH.exists():
        store = _default_store()
        write_memory_store(store)
        return store

    try:
        payload = json.loads(MEMORY_STORE_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        payload = {}

    store = _default_store()
    if isinstance(payload, dict):
        store["schema_version"] = int(payload.get("schema_version") or MEMORY_SCHEMA_VERSION)
        if isinstance(payload.get("entries"), list):
            store["entries"] = [entry for entry in payload["entries"] if isinstance(entry, dict)]
        if isinstance(payload.get("audit"), list):
            store["audit"] = [entry for entry in payload["audit"] if isinstance(entry, dict)]
    return store


def write_memory_store(store: dict[str, Any]) -> dict[str, Any]:
    MEMORY_STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
    store["schema_version"] = MEMORY_SCHEMA_VERSION
    MEMORY_STORE_PATH.write_text(json.dumps(store, ensure_ascii=False, indent=2), encoding="utf-8")
    return store


def list_memory_entries(
    *,
    include_pending: bool = True,
    include_rolled_back: bool = False,
    include_superseded: bool = False,
) -> list[dict[str, Any]]:
    entries = list(read_memory_store().get("entries") or [])
    filtered: list[dict[str, Any]] = []
    for entry in entries:
        status = str(entry.get("status") or "")
        if status == "pending" and not include_pending:
            continue
        if status == "rolled_back" and not include_rolled_back:
            continue
        if status == "superseded" and not include_superseded:
            continue
        filtered.append(entry)
    return filtered


def extract_memory_candidates(
    *,
    question: str,
    answer: str = "",
    sources: list[str] | None = None,
    history: list[dict[str, str]] | None = None,
) -> list[dict[str, Any]]:
    normalized_history = normalize_history(history)
    source_refs = [source.strip() for source in (sources or []) if source and source.strip()]
    candidates: list[dict[str, Any]] = []
    candidates.extend(_preference_entries(question))
    candidates.extend(_profile_entries(question))
    candidates.extend(_task_entries(question, answer, source_refs, len(normalized_history)))
    return _dedupe_candidates(candidates)


def extract_explicit_memory_command_candidates(
    *,
    question: str,
    history: list[dict[str, str]] | None = None,
) -> list[dict[str, Any]]:
    if not _remembered_content(question):
        return []
    return extract_memory_candidates(question=question, answer="", sources=[], history=history)


def build_explicit_memory_command_reply(question: str, entries: list[dict[str, Any]] | None = None) -> str:
    remembered = _remembered_content(question)
    for entry in entries or []:
        payload = dict(entry.get("payload") or {})
        if str(entry.get("memory_type") or "") != "pinned_preference":
            continue
        if payload.get("preference_key") == "response_language":
            value = str(payload.get("value") or "")
            if value == "zh-CN":
                return "已记住，之后我会用中文回答。"
            if value == "en-US":
                return "已记住，之后我会用英文回答。"
        if payload.get("preference_key") == "max_answer_chars":
            try:
                value = int(payload.get("value") or 0)
            except (TypeError, ValueError):
                value = 0
            if value > 0:
                return f"已记住，之后我会尽量把回答控制在 {value} 字以内。"
        instruction = str(payload.get("instruction") or "").strip()
        if instruction:
            return f"已记住：{instruction}。"
    if remembered:
        return f"已记住：{remembered}。"
    return "已记住。"


def _supersede_conflicting_entries(store: dict[str, Any], candidate: dict[str, Any]) -> None:
    memory_type = str(candidate.get("memory_type") or "")
    subject_key = str(candidate.get("subject_key") or candidate.get("payload", {}).get("subject_key") or "")
    if memory_type not in SUPERCEDING_TYPES or not subject_key:
        return

    timestamp = utc_now()
    for entry in store.get("entries") or []:
        if not isinstance(entry, dict):
            continue
        if str(entry.get("memory_type") or "") != memory_type:
            continue
        if str(entry.get("subject_key") or entry.get("payload", {}).get("subject_key") or "") != subject_key:
            continue
        if not _is_active_entry(entry):
            continue
        if str(entry.get("summary") or "").casefold() == str(candidate.get("summary") or "").casefold():
            continue
        entry["status"] = "superseded"
        entry["superseded_at"] = timestamp
        entry["superseded_by"] = candidate["id"]
        entry["updated_at"] = timestamp
        _append_audit(store, "supersede", str(entry.get("id") or ""), superseded_by=candidate["id"], subject_key=subject_key)
        _sync_entry_to_openviking(entry)


def persist_memory_candidates(
    candidates: list[dict[str, Any]],
    *,
    conversation_id: str | None = None,
) -> list[dict[str, Any]]:
    store = read_memory_store()
    entries = list(store.get("entries") or [])
    store["entries"] = entries
    stored: list[dict[str, Any]] = []

    existing_keys = {
        (
            str(entry.get("memory_type") or ""),
            str(entry.get("subject_key") or entry.get("payload", {}).get("subject_key") or "").casefold(),
            str(entry.get("summary") or "").casefold(),
            str(entry.get("status") or ""),
        )
        for entry in entries
        if isinstance(entry, dict)
    }

    for raw_candidate in _dedupe_candidates(candidates):
        candidate = dict(raw_candidate)
        _attach_conversation_context(candidate, conversation_id)
        candidate.setdefault("layer", _memory_type_to_layer(str(candidate.get("memory_type") or "")))
        candidate.setdefault("scope", _memory_type_to_scope(str(candidate.get("memory_type") or "")))
        candidate.setdefault("subject_key", _entry_subject_key(str(candidate.get("memory_type") or ""), dict(candidate.get("payload") or {}), str(candidate.get("summary") or "")))
        candidate.setdefault("status", _default_status(str(candidate.get("memory_type") or ""), dict(candidate.get("payload") or {})))
        candidate.setdefault("updated_at", utc_now())
        candidate.setdefault("created_at", candidate["updated_at"])
        candidate.setdefault("expires_at", _build_expiry(str(candidate.get("memory_type") or "")))
        candidate.setdefault("confidence", 0.8)
        candidate.setdefault("source_refs", [])
        candidate.setdefault("tags", [])
        candidate.setdefault("payload", {})
        candidate["payload"].setdefault("subject_key", candidate["subject_key"])
        candidate.setdefault("id", str(uuid.uuid4()))

        dedupe_key = (
            str(candidate.get("memory_type") or ""),
            str(candidate.get("subject_key") or "").casefold(),
            str(candidate.get("summary") or "").casefold(),
            str(candidate.get("status") or ""),
        )
        if dedupe_key in existing_keys:
            continue

        _supersede_conflicting_entries(store, candidate)
        entries.insert(0, candidate)
        existing_keys.add(dedupe_key)
        stored.append(candidate)
        _append_audit(store, "extract", str(candidate.get("id") or ""), summary=candidate.get("summary", ""), memory_type=candidate.get("memory_type", ""))
        if candidate.get("status") == "approved":
            candidate["approved_at"] = candidate.get("approved_at") or candidate["updated_at"]
        _sync_entry_to_openviking(candidate)

    write_memory_store(store)
    return stored


def _update_memory_status(memory_id: str, status: str, *, action: str, detail: str | None = None) -> dict[str, Any]:
    if status not in ALLOWED_STATUSES:
        raise ValueError("Unsupported memory status.")

    store = read_memory_store()
    entries = list(store.get("entries") or [])
    for entry in entries:
        if str(entry.get("id")) != memory_id:
            continue
        entry["status"] = status
        entry["updated_at"] = utc_now()
        if status == "approved":
            entry["approved_at"] = entry["updated_at"]
        if status == "rolled_back":
            entry["rolled_back_at"] = entry["updated_at"]
        if status == "superseded":
            entry["superseded_at"] = entry["updated_at"]
        _append_audit(store, action, memory_id, detail=detail or "")
        _sync_entry_to_openviking(entry)
        write_memory_store(store)
        return entry
    raise ValueError("Memory entry not found.")


def approve_memory_entry(memory_id: str) -> dict[str, Any]:
    return _update_memory_status(memory_id, "approved", action="approve")


def rollback_memory_entry(memory_id: str, detail: str | None = None) -> dict[str, Any]:
    return _update_memory_status(memory_id, "rolled_back", action="rollback", detail=detail)


def update_memory_entry(
    memory_id: str,
    *,
    title: str | None = None,
    summary: str | None = None,
    tags: list[str] | None = None,
) -> dict[str, Any]:
    store = read_memory_store()
    entries = list(store.get("entries") or [])
    for entry in entries:
        if str(entry.get("id") or "") != memory_id:
            continue
        if title is not None:
            normalized_title = str(title).strip()
            if not normalized_title:
                raise ValueError("Memory title must not be empty.")
            entry["title"] = normalized_title
        if summary is not None:
            normalized_summary = str(summary).strip()
            if not normalized_summary:
                raise ValueError("Memory summary must not be empty.")
            entry["summary"] = normalized_summary
        if tags is not None:
            entry["tags"] = [str(tag).strip() for tag in tags if str(tag).strip()]
        entry["updated_at"] = utc_now()
        _append_audit(store, "edit", memory_id, title=entry.get("title", ""), summary=entry.get("summary", ""))
        _sync_entry_to_openviking(entry)
        write_memory_store(store)
        return entry
    raise ValueError("Memory entry not found.")


def remove_memory_entry(memory_id: str, detail: str | None = None) -> dict[str, Any]:
    return _update_memory_status(memory_id, "rolled_back", action="delete", detail=detail or "user removed")


def delete_memory_entries_for_conversation(
    conversation_id: str,
    *,
    conversation_messages: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    normalized_conversation_id = _normalize_conversation_id(conversation_id)
    if not normalized_conversation_id:
        return {"deleted_count": 0, "deleted_ids": []}

    store = read_memory_store()
    entries = list(store.get("entries") or [])
    conversation_texts = {
        _normalize_text(str(item.get("content") or ""))
        for item in (conversation_messages or [])
        if isinstance(item, dict) and str(item.get("content") or "").strip()
    }

    kept: list[dict[str, Any]] = []
    deleted_ids: list[str] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        if _entry_matches_conversation(
            entry,
            conversation_id=normalized_conversation_id,
            conversation_texts=conversation_texts,
        ):
            deleted_id = str(entry.get("id") or "")
            if deleted_id:
                deleted_ids.append(deleted_id)
            _append_audit(
                store,
                "delete_conversation",
                deleted_id or normalized_conversation_id,
                conversation_id=normalized_conversation_id,
                memory_type=str(entry.get("memory_type") or ""),
            )
            _delete_entry_artifacts(entry)
            continue
        kept.append(entry)

    store["entries"] = kept
    write_memory_store(store)
    return {"deleted_count": len(deleted_ids), "deleted_ids": deleted_ids}


def _select_preferences(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    seen_subjects: set[str] = set()
    for entry in sorted(entries, key=lambda item: str(item.get("updated_at") or ""), reverse=True):
        subject_key = str(entry.get("subject_key") or entry.get("payload", {}).get("subject_key") or "")
        if subject_key in seen_subjects:
            continue
        seen_subjects.add(subject_key)
        selected.append(entry)
    return selected[:3]


def _sorted_recent_entries(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        entries,
        key=lambda item: (
            str(item.get("updated_at") or item.get("created_at") or ""),
            str(item.get("id") or ""),
        ),
        reverse=True,
    )


def _active_approved_entries() -> list[dict[str, Any]]:
    return [
        entry
        for entry in list_memory_entries(include_pending=False)
        if entry.get("status") == "approved" and not _is_expired(entry)
    ]


def _memory_entry_id_from_uri(uri: str) -> str:
    normalized = str(uri or "").strip().rstrip("/")
    for suffix in ("/.overview.md", "/.abstract.md"):
        if normalized.endswith(suffix):
            normalized = normalized[: -len(suffix)]
    return normalized.rsplit("/", 1)[-1] if normalized else ""


def _question_needs_reference_history(question: str) -> bool:
    normalized = _normalize_text(question)
    if not normalized:
        return False
    return any(term in normalized for term in REFERENCE_HISTORY_TERMS)


def _search_openviking_memory_entries(
    question: str,
    *,
    limit: int = 6,
    sources: list[str] | None = None,
) -> list[dict[str, Any]]:
    from time import perf_counter
    from app.agent_tools import log_diagnostic_event

    started_at = perf_counter()
    normalized_question = question.strip()
    if not normalized_question:
        return []

    queries = [normalized_question]
    for source in sources or []:
        stem = Path(source).stem.strip()
        if stem and stem not in queries:
            queries.append(stem)

    try:
        from app.openviking_runtime import search_openviking_resources
    except Exception:
        return []

    active_entries = {
        str(entry.get("id") or ""): entry
        for entry in _active_approved_entries()
        if str(entry.get("openviking_resource_uri") or "").strip()
    }
    if not active_entries:
        log_diagnostic_event(
            "openviking_memory_search_complete",
            started_at=started_at,
            question=question,
            query_count=len(queries[:3]),
            active_entry_count=0,
            hit_count=0,
            skipped=True,
            reason="no_active_openviking_entries",
        )
        return []
    matched: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    for query in queries[:3]:
        try:
            hits = search_openviking_resources(
                query,
                root_uri=OPENVIKING_MEMORY_ROOT_URI,
                node_limit=max(limit * 2, 8),
            )
        except Exception:
            continue

        for hit in hits:
            entry_id = _memory_entry_id_from_uri(hit.uri)
            entry = active_entries.get(entry_id)
            if entry is None or entry_id in seen_ids:
                continue
            seen_ids.add(entry_id)
            matched.append(entry)
            if len(matched) >= limit:
                log_diagnostic_event(
                    "openviking_memory_search_complete",
                    started_at=started_at,
                    question=question,
                    query_count=len(queries[:3]),
                    active_entry_count=len(active_entries),
                    hit_count=len(matched),
                    skipped=False,
                )
                return matched

    log_diagnostic_event(
        "openviking_memory_search_complete",
        started_at=started_at,
        question=question,
        query_count=len(queries[:3]),
        active_entry_count=len(active_entries),
        hit_count=len(matched),
        skipped=False,
    )
    return matched


def list_recent_memory_sources(*, limit: int = 4) -> list[str]:
    recent_entries = _sorted_recent_entries(
        [
            entry
            for entry in _active_approved_entries()
            if entry.get("memory_type") in {"raw_turn_log", "working_summary", "recent_task_state"}
        ]
    )
    recent_sources: list[str] = []
    seen: set[str] = set()
    for entry in recent_entries:
        for source in entry.get("source_refs") or []:
            normalized = str(source).strip()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            recent_sources.append(normalized)
            if len(recent_sources) >= limit:
                return recent_sources
    return recent_sources


def build_reference_history(
    question: str,
    history: list[dict[str, str]] | None = None,
    *,
    limit: int = 6,
) -> list[dict[str, str]]:
    explicit_history = normalize_history(history)[-limit:]
    if explicit_history:
        return explicit_history
    if not _question_needs_reference_history(question):
        return []

    turn_entries = _sorted_recent_entries(
        [
            entry
            for entry in _active_approved_entries()
            if entry.get("memory_type") == "raw_turn_log"
        ]
    )
    reconstructed: list[dict[str, str]] = []
    for entry in reversed(turn_entries[: max(1, limit // 2)]):
        payload = dict(entry.get("payload") or {})
        question = str(payload.get("question") or "").strip()
        answer_excerpt = str(payload.get("answer_excerpt") or "").strip()
        source_refs = [str(item).strip() for item in entry.get("source_refs") or [] if str(item).strip()]
        if question:
            reconstructed.append({"role": "user", "content": question})
        if answer_excerpt:
            assistant_entry = {"role": "assistant", "content": answer_excerpt}
            if source_refs:
                assistant_entry["sources"] = source_refs[:3]
            reconstructed.append(assistant_entry)

    if reconstructed:
        return normalize_history(reconstructed)[-limit:]
    return []


def find_recent_summary_memory_context() -> SummaryMemoryContext | None:
    try:
        from app.rag import is_summary_flow_request
    except Exception:
        return None

    for entry in _sorted_recent_entries(_active_approved_entries()):
        if entry.get("memory_type") not in {"raw_turn_log", "working_summary"}:
            continue
        payload = dict(entry.get("payload") or {})
        question = str(payload.get("question") or "").strip()
        sources = [str(item).strip() for item in entry.get("source_refs") or [] if str(item).strip()]
        answer_excerpt = str(payload.get("answer_excerpt") or entry.get("summary") or "").strip()
        if not question or not sources or not answer_excerpt:
            continue
        if not is_summary_flow_request(question, history=[]):
            continue
        return SummaryMemoryContext(
            user_question=question,
            assistant_answer=answer_excerpt,
            sources=sources[:3],
        )
    return None


def _score_relevant_entry(entry: dict[str, Any], *, question: str, history_text: str, normalized_sources: set[str]) -> int:
    summary = _normalize_text(str(entry.get("summary") or ""))
    tags = [_normalize_text(str(tag)) for tag in entry.get("tags") or []]
    source_refs = [str(item) for item in entry.get("source_refs") or []]
    question_text = _normalize_text(question)
    score = 0
    if summary and summary in question_text:
        score += 4
    if history_text and summary and summary in history_text:
        score += 2
    if any(tag and tag in question_text for tag in tags):
        score += 2
    if any(_normalize_text(Path(source).name) in normalized_sources for source in source_refs):
        score += 3
    if any(_normalize_text(Path(source).stem) in question_text for source in source_refs):
        score += 2
    return score


def _format_memory_line(entry: dict[str, Any]) -> str:
    layer = str(entry.get("layer") or "")
    memory_type = str(entry.get("memory_type") or "")
    return f"- [{layer}] {memory_type}: {entry.get('summary')}"


def is_recent_task_query(question: str) -> bool:
    normalized = _normalize_text(question)
    if not normalized:
        return False
    return any(term in normalized for term in RECENT_TASK_QUERY_TERMS)


def is_profile_query(question: str) -> bool:
    normalized = _normalize_text(question)
    if not normalized:
        return False
    return any(term in normalized for term in PROFILE_QUERY_TERMS)


def _profile_query_category(question: str) -> str | None:
    normalized = _normalize_text(question)
    if not normalized:
        return None
    for category, terms in PROFILE_QUERY_CATEGORY_TERMS.items():
        if any(term in normalized for term in terms):
            return category
    return None


def is_memory_recall_question(question: str) -> bool:
    return is_recent_task_query(question) or is_profile_query(question)


def _score_profile_entry(
    entry: dict[str, Any],
    *,
    question: str,
    history_text: str,
    normalized_sources: set[str],
    category: str | None,
) -> int:
    score = _score_relevant_entry(entry, question=question, history_text=history_text, normalized_sources=normalized_sources)
    payload = dict(entry.get("payload") or {})
    profile_key = str(payload.get("profile_key") or "").strip().casefold()
    if category and profile_key == category:
        score += 5
    elif profile_key:
        score += 1
    return score


def find_profile_memory_context(
    question: str,
    *,
    history: list[dict[str, str]] | None = None,
    sources: list[str] | None = None,
    limit: int = 2,
) -> str | None:
    if not is_profile_query(question):
        return None

    approved = _active_approved_entries()
    if not approved:
        return None

    normalized_history = normalize_history(history)
    history_text = _normalize_text(" ".join(item.get("content", "") for item in normalized_history))
    normalized_sources = {_normalize_text(Path(source).name) for source in (sources or []) if source}
    normalized_question = _normalize_text(question)
    category = _profile_query_category(question)

    recent = sorted(
        [
            (
                entry,
                _score_profile_entry(
                    entry,
                    question=question,
                    history_text=history_text,
                    normalized_sources=normalized_sources,
                    category=category,
                ),
            )
            for entry in approved
            if entry.get("memory_type") == "stable_profile_fact"
        ],
        key=lambda item: (item[1], str(item[0].get("updated_at") or "")),
        reverse=True,
    )
    if not recent:
        return None

    refusal_markers = (
        "[direct_answer]",
        "根据当前知识库内容",
        "暂时无法可靠回答",
        "无法可靠回答",
    )

    preferred: list[dict[str, Any]] = []
    fallback: list[dict[str, Any]] = []
    for entry, score in recent:
        payload = dict(entry.get("payload") or {})
        entry_question = _normalize_text(str(payload.get("question") or ""))
        summary = _normalize_text(str(entry.get("summary") or ""))
        profile_key = str(payload.get("profile_key") or "").strip().casefold()
        if not summary:
            continue
        if entry_question and entry_question == normalized_question:
            continue
        if any(marker in summary for marker in refusal_markers):
            continue
        if category and profile_key == category:
            preferred.append(entry)
            continue
        if score > 0:
            preferred.append(entry)
            continue
        fallback.append(entry)

    selected = preferred[:limit]
    if not selected:
        selected = fallback[:limit]

    deduped: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for entry in selected:
        entry_id = str(entry.get("id") or "")
        if not entry_id or entry_id in seen_ids:
            continue
        seen_ids.add(entry_id)
        deduped.append(entry)
        if len(deduped) >= limit:
            break

    if not deduped:
        return None

    lines = ["[Session Memory]"]
    lines.extend(_format_memory_line(entry) for entry in deduped)
    return "\n".join(lines)


def find_recent_task_memory_context(
    question: str,
    *,
    history: list[dict[str, str]] | None = None,
    sources: list[str] | None = None,
    limit: int = 2,
) -> str | None:
    if not is_recent_task_query(question):
        return None

    approved = _active_approved_entries()
    if not approved:
        return None

    normalized_history = normalize_history(history)
    history_text = _normalize_text(" ".join(item.get("content", "") for item in normalized_history))
    normalized_sources = {_normalize_text(Path(source).name) for source in (sources or []) if source}

    normalized_question = _normalize_text(question)

    recent = sorted(
        [
            (entry, _score_relevant_entry(entry, question=question, history_text=history_text, normalized_sources=normalized_sources))
            for entry in approved
            if entry.get("memory_type") == "recent_task_state"
        ],
        key=lambda item: (item[1], str(item[0].get("updated_at") or "")),
        reverse=True,
    )
    if not recent:
        return None

    refusal_markers = (
        "[direct_answer]",
        "根据当前知识库内容",
        "暂时无法可靠回答",
        "无法可靠回答",
    )

    preferred: list[dict[str, Any]] = []
    fallback: list[dict[str, Any]] = []
    for entry, score in recent:
        payload = dict(entry.get("payload") or {})
        entry_question = _normalize_text(str(payload.get("question") or ""))
        summary = _normalize_text(str(entry.get("summary") or ""))
        if not summary:
            continue
        if entry_question and entry_question == normalized_question:
            continue
        if any(marker in summary for marker in refusal_markers):
            continue
        if entry.get("source_refs"):
            preferred.append(entry)
            continue
        if score > 0:
            preferred.append(entry)
            continue
        fallback.append(entry)

    selected = preferred[:limit]
    if not selected:
        selected = fallback[:limit]

    deduped: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for entry in selected:
        entry_id = str(entry.get("id") or "")
        if not entry_id or entry_id in seen_ids:
            continue
        seen_ids.add(entry_id)
        deduped.append(entry)
        if len(deduped) >= limit:
            break

    if not deduped:
        return None

    lines = ["[Session Memory]"]
    lines.extend(_format_memory_line(entry) for entry in deduped)
    return "\n".join(lines)


def build_memory_context(
    question: str,
    *,
    history: list[dict[str, str]] | None = None,
    sources: list[str] | None = None,
    limit: int = 6,
) -> str:
    approved = _active_approved_entries()
    if not approved:
        return ""

    if is_profile_query(question):
        profile_context = find_profile_memory_context(question, history=history, sources=sources, limit=min(limit, 2))
        if profile_context:
            return profile_context

    normalized_history = normalize_history(history)
    history_text = _normalize_text(" ".join(item.get("content", "") for item in normalized_history))
    normalized_sources = {_normalize_text(Path(source).name) for source in (sources or []) if source}

    preferences = _select_preferences([entry for entry in approved if entry.get("memory_type") == "pinned_preference"])
    profiles = [
        entry
        for entry in approved
        if entry.get("memory_type") == "stable_profile_fact" and _score_relevant_entry(entry, question=question, history_text=history_text, normalized_sources=normalized_sources) > 0
    ]
    working = sorted(
        [
            (entry, _score_relevant_entry(entry, question=question, history_text=history_text, normalized_sources=normalized_sources))
            for entry in approved
            if entry.get("memory_type") == "working_summary"
        ],
        key=lambda item: (item[1], str(item[0].get("updated_at") or "")),
        reverse=True,
    )
    recent = sorted(
        [
            (entry, _score_relevant_entry(entry, question=question, history_text=history_text, normalized_sources=normalized_sources))
            for entry in approved
            if entry.get("memory_type") == "recent_task_state"
        ],
        key=lambda item: (item[1], str(item[0].get("updated_at") or "")),
        reverse=True,
    )
    durable = sorted(
        [
            (entry, _score_relevant_entry(entry, question=question, history_text=history_text, normalized_sources=normalized_sources))
            for entry in approved
            if entry.get("memory_type") == "approved_long_term_fact"
        ],
        key=lambda item: (item[1], str(item[0].get("updated_at") or "")),
        reverse=True,
    )
    openviking_hits = _search_openviking_memory_entries(question, limit=limit, sources=sources)

    selected: list[dict[str, Any]] = []
    selected.extend(preferences[:2])
    selected.extend(profiles[:2])
    if openviking_hits:
        selected.extend(openviking_hits[: max(0, limit - len(selected))])
    else:
        selected.extend([entry for entry, score in working[:1] if score > 0])
        selected.extend([entry for entry, score in recent[:2] if score > 0])
        selected.extend([entry for entry, score in durable[:2] if score > 0])

    if not selected:
        return ""

    deduped: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for entry in selected:
        entry_id = str(entry.get("id") or "")
        if not entry_id or entry_id in seen_ids:
            continue
        seen_ids.add(entry_id)
        deduped.append(entry)
        if len(deduped) >= limit:
            break

    lines = ["[Session Memory]"]
    lines.extend(_format_memory_line(entry) for entry in deduped)
    return "\n".join(lines)


def build_response_constraints() -> dict[str, Any]:
    approved = _active_approved_entries()
    if not approved:
        return {}

    preferences = _select_preferences([entry for entry in approved if entry.get("memory_type") == "pinned_preference"])
    constraints: dict[str, Any] = {}
    for entry in preferences:
        payload = dict(entry.get("payload") or {})
        preference_key = str(payload.get("preference_key") or "").strip()
        if preference_key == "response_language":
            value = str(payload.get("value") or "").strip()
            if value in {"zh-CN", "en-US"}:
                constraints["response_language"] = value
            continue
        if preference_key == "response_style":
            value = str(payload.get("value") or "").strip()
            if value in {"concise", "detailed", "bullet_points"}:
                constraints["response_style"] = value
            continue
        if preference_key == "max_answer_chars":
            try:
                value = int(payload.get("value") or 0)
            except (TypeError, ValueError):
                value = 0
            if value > 0:
                constraints["max_answer_chars"] = value
    return constraints


def record_completed_turn(
    *,
    question: str,
    answer: str,
    sources: list[str] | None = None,
    history: list[dict[str, str]] | None = None,
    conversation_id: str | None = None,
) -> list[dict[str, Any]]:
    from time import perf_counter

    started_at = perf_counter()
    from app.agent_tools import log_diagnostic_event

    normalized_history = normalize_history(history)
    source_refs = [source.strip() for source in (sources or []) if source and source.strip()]
    recall_question = is_memory_recall_question(question)
    if recall_question:
        log_diagnostic_event(
            "record_completed_turn_complete",
            started_at=started_at,
            question=question,
            history_count=len(normalized_history),
            source_count=len(source_refs),
            candidate_count=0,
            stored_entry_count=0,
            conversation_id=_normalize_conversation_id(conversation_id) or None,
            recall_question=True,
        )
        return []

    candidates: list[dict[str, Any]] = []
    turn_entry = _turn_log_entry(question, answer, source_refs, len(normalized_history))
    if turn_entry is not None:
        candidates.append(turn_entry)
    summary_entry = _working_summary_entry(question, answer, source_refs)
    if summary_entry is not None:
        candidates.append(summary_entry)
    candidates.extend(_preference_entries(question))
    candidates.extend(_profile_entries(question))
    candidates.extend(_task_entries(question, answer, source_refs, len(normalized_history)))
    stored_entries = persist_memory_candidates(candidates, conversation_id=conversation_id)
    log_diagnostic_event(
        "record_completed_turn_complete",
        started_at=started_at,
        question=question,
        history_count=len(normalized_history),
        source_count=len(source_refs),
        candidate_count=len(candidates),
        stored_entry_count=len(stored_entries),
        conversation_id=_normalize_conversation_id(conversation_id) or None,
    )
    return stored_entries


def summarize_memory_store() -> dict[str, Any]:
    entries = list_memory_entries(include_pending=True, include_rolled_back=True, include_superseded=True)
    by_layer: dict[str, int] = {}
    by_type: dict[str, int] = {}
    by_status: dict[str, int] = {}
    for entry in entries:
        layer = str(entry.get("layer") or "unknown")
        memory_type = str(entry.get("memory_type") or "unknown")
        status = str(entry.get("status") or "unknown")
        by_layer[layer] = by_layer.get(layer, 0) + 1
        by_type[memory_type] = by_type.get(memory_type, 0) + 1
        by_status[status] = by_status.get(status, 0) + 1
    return {
        "total": len(entries),
        "active": sum(1 for entry in entries if _is_active_entry(entry)),
        "by_layer": by_layer,
        "by_type": by_type,
        "by_status": by_status,
    }
