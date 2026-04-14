from __future__ import annotations

import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.rag import BASE_DIR

LOOP_STATE_PATH = BASE_DIR / "data" / "loop_state.json"
CANONICAL_VERIFICATION_COMMAND = r".\.venv\Scripts\python.exe -m unittest discover -s tests"

DEFAULT_LOOP_STATE: dict[str, Any] = {
    "current_goal": "Finalize askRAg with Chroma for static documents and OpenViking for assistant memory/context.",
    "current_milestone": "stage_4a_document_side_openviking_cleanup",
    "canonical_verification_command": CANONICAL_VERIFICATION_COMMAND,
    "success_metric": "Unit tests pass and runtime/operator state reflects the final Chroma-for-docs plus OpenViking-for-memory split.",
    "stop_condition": "Stop when tests are green, the regression run passes, and the remaining document-side OpenViking path is no longer treated as normal workflow.",
    "guardrails": {
        "max_steps_per_run": 6,
        "max_failures_per_run": 3,
        "fallback_backend": "chroma",
        "rollback_strategy": "Keep Chroma as the document-evidence backend, keep OpenViking focused on memory/context, and preserve approval/rollback boundaries for durable memory writes.",
    },
    "last_verification": {},
    "last_evaluation": {},
    "last_operations": [],
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _default_state() -> dict[str, Any]:
    return deepcopy(DEFAULT_LOOP_STATE)


def read_loop_state() -> dict[str, Any]:
    if not LOOP_STATE_PATH.exists():
        state = _default_state()
        write_loop_state(state)
        return state

    try:
        payload = json.loads(LOOP_STATE_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        payload = {}

    state = _default_state()
    if isinstance(payload, dict):
        state.update(payload)
        if isinstance(payload.get("guardrails"), dict):
            state["guardrails"].update(payload["guardrails"])
    return state


def write_loop_state(state: dict[str, Any]) -> dict[str, Any]:
    LOOP_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    LOOP_STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    return state


def _append_operation(state: dict[str, Any], operation: dict[str, Any]) -> dict[str, Any]:
    history = list(state.get("last_operations") or [])
    history.insert(0, operation)
    state["last_operations"] = history[:10]
    return state


def record_operation(name: str, status: str, **detail: Any) -> dict[str, Any]:
    state = read_loop_state()
    operation = {
        "name": name,
        "status": status,
        "timestamp": utc_now(),
        **detail,
    }
    _append_operation(state, operation)
    write_loop_state(state)
    return operation


def record_verification(status: str, command: str | None = None, **detail: Any) -> dict[str, Any]:
    state = read_loop_state()
    state["last_verification"] = {
        "status": status,
        "command": command or state.get("canonical_verification_command") or CANONICAL_VERIFICATION_COMMAND,
        "timestamp": utc_now(),
        **detail,
    }
    write_loop_state(state)
    return state["last_verification"]


def record_evaluation(status: str, dataset: str, **detail: Any) -> dict[str, Any]:
    state = read_loop_state()
    state["last_evaluation"] = {
        "status": status,
        "dataset": dataset,
        "timestamp": utc_now(),
        **detail,
    }
    write_loop_state(state)
    return state["last_evaluation"]
