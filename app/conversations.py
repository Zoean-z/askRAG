from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.rag import BASE_DIR

CONVERSATION_STORE_PATH = BASE_DIR / "data" / "conversation_threads.json"
CONVERSATION_SCHEMA_VERSION = 1


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _default_store() -> dict[str, Any]:
    return {"schema_version": CONVERSATION_SCHEMA_VERSION, "conversations": []}


def read_conversation_store() -> dict[str, Any]:
    if not CONVERSATION_STORE_PATH.exists():
        store = _default_store()
        write_conversation_store(store)
        return store

    try:
        payload = json.loads(CONVERSATION_STORE_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        payload = {}

    store = _default_store()
    if isinstance(payload, dict):
        store["schema_version"] = int(payload.get("schema_version") or CONVERSATION_SCHEMA_VERSION)
        conversations = payload.get("conversations")
        if isinstance(conversations, list):
            store["conversations"] = [item for item in conversations if isinstance(item, dict)]
    return store


def write_conversation_store(store: dict[str, Any]) -> dict[str, Any]:
    CONVERSATION_STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
    store["schema_version"] = CONVERSATION_SCHEMA_VERSION
    CONVERSATION_STORE_PATH.write_text(json.dumps(store, ensure_ascii=False, indent=2), encoding="utf-8")
    return store


def _conversation_preview(messages: list[dict[str, Any]]) -> str:
    for message in reversed(messages):
        content = str(message.get("content") or "").strip()
        if content:
            return content[:140]
    return ""


def _conversation_summary(conversation: dict[str, Any]) -> dict[str, Any]:
    messages = [item for item in conversation.get("messages") or [] if isinstance(item, dict)]
    return {
        "id": str(conversation.get("id") or ""),
        "title": str(conversation.get("title") or "New chat"),
        "created_at": conversation.get("created_at"),
        "updated_at": conversation.get("updated_at"),
        "message_count": len(messages),
        "last_message_preview": _conversation_preview(messages),
    }


def _title_from_first_question(question: str) -> str:
    normalized = " ".join((question or "").strip().split())
    if not normalized:
        return "New chat"
    return normalized[:48]


def list_conversations() -> list[dict[str, Any]]:
    store = read_conversation_store()
    conversations = list(store.get("conversations") or [])
    summaries = [_conversation_summary(item) for item in conversations if isinstance(item, dict)]
    summaries.sort(key=lambda item: str(item.get("updated_at") or ""), reverse=True)
    return summaries


def create_conversation(*, title: str | None = None) -> dict[str, Any]:
    store = read_conversation_store()
    timestamp = utc_now()
    conversation = {
        "id": str(uuid.uuid4()),
        "title": (title or "").strip() or "New chat",
        "created_at": timestamp,
        "updated_at": timestamp,
        "messages": [],
    }
    conversations = list(store.get("conversations") or [])
    conversations.insert(0, conversation)
    store["conversations"] = conversations
    write_conversation_store(store)
    return conversation


def get_conversation(conversation_id: str) -> dict[str, Any]:
    for conversation in read_conversation_store().get("conversations") or []:
        if str(conversation.get("id") or "") == conversation_id:
            return conversation
    raise ValueError("Conversation not found.")


def ensure_conversation(conversation_id: str | None = None) -> dict[str, Any]:
    normalized = str(conversation_id or "").strip()
    if not normalized:
        return create_conversation()
    return get_conversation(normalized)


def append_conversation_message(
    conversation_id: str,
    *,
    role: str,
    content: str,
    sources: list[str] | None = None,
    trace: dict[str, Any] | None = None,
    memory_notices: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    normalized_content = str(content or "").strip()
    if not normalized_content:
        raise ValueError("Conversation message content must not be empty.")

    store = read_conversation_store()
    conversations = list(store.get("conversations") or [])
    timestamp = utc_now()
    for conversation in conversations:
        if str(conversation.get("id") or "") != conversation_id:
            continue

        messages = list(conversation.get("messages") or [])
        message = {
            "id": str(uuid.uuid4()),
            "role": role,
            "content": normalized_content,
            "sources": [str(item).strip() for item in (sources or []) if str(item).strip()],
            "created_at": timestamp,
            "memory_notices": [item for item in (memory_notices or []) if isinstance(item, dict)],
        }
        if trace:
            message["trace"] = trace
        messages.append(message)
        conversation["messages"] = messages
        conversation["updated_at"] = timestamp
        if len(messages) == 1 and role == "user":
            conversation["title"] = _title_from_first_question(normalized_content)
        store["conversations"] = sorted(
            conversations,
            key=lambda item: str(item.get("updated_at") or ""),
            reverse=True,
        )
        write_conversation_store(store)
        return message

    raise ValueError("Conversation not found.")


def delete_conversation(conversation_id: str) -> dict[str, Any]:
    store = read_conversation_store()
    conversations = list(store.get("conversations") or [])
    kept: list[dict[str, Any]] = []
    removed: dict[str, Any] | None = None
    for conversation in conversations:
        if str(conversation.get("id") or "") == conversation_id:
            removed = conversation
            continue
        kept.append(conversation)
    if removed is None:
        raise ValueError("Conversation not found.")
    store["conversations"] = kept
    write_conversation_store(store)
    return removed
