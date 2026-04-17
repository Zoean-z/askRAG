from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Any

from app.rag import BASE_DIR

DEFAULT_OV_TIMEOUT = int(os.getenv("ASKRAG_OPENVIKING_TIMEOUT_SECONDS", "120"))
OPENVIKING_RUNTIME_ROLE = "memory_context_infrastructure"
DIAGNOSTIC_LOGGER = logging.getLogger("askrag.diagnostic")


class OpenVikingRuntimeError(ValueError):
    pass


@dataclass(slots=True)
class OpenVikingResourceHit:
    uri: str
    level: int
    score: float
    abstract: str
    context_type: str = "resource"


def _find_ov_executable() -> str:
    configured = os.getenv("ASKRAG_OPENVIKING_CLI", "").strip()
    if configured:
        return configured

    candidates = [
        BASE_DIR / ".venv" / "Scripts" / "ov.exe",
        BASE_DIR / ".venv" / "Scripts" / "ov",
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)

    found = shutil.which("ov.exe") or shutil.which("ov")
    if found:
        return found
    raise OpenVikingRuntimeError("OpenViking CLI not found. Install openviking and ensure `ov` is available.")


def _run_ov_command(*args: str, timeout: int = DEFAULT_OV_TIMEOUT) -> str:
    command = [_find_ov_executable(), *args]
    completed = subprocess.run(
        command,
        cwd=str(BASE_DIR),
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=timeout,
        check=False,
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip() or "unknown OpenViking command failure"
        raise OpenVikingRuntimeError(detail)
    return completed.stdout.strip()


def _extract_json_payload(raw_output: str) -> Any:
    lines = [line for line in (raw_output or "").splitlines() if line.strip()]
    for line in reversed(lines):
        normalized = line.strip()
        if normalized.startswith("{") or normalized.startswith("["):
            try:
                return json.loads(normalized)
            except json.JSONDecodeError:
                continue
    raise OpenVikingRuntimeError("OpenViking command did not return JSON output.")


def _run_ov_json_command(*args: str, timeout: int = DEFAULT_OV_TIMEOUT) -> Any:
    payload = _extract_json_payload(_run_ov_command(*args, timeout=timeout))
    if isinstance(payload, dict) and payload.get("ok") is False:
        raise OpenVikingRuntimeError(str(payload.get("error") or payload.get("result") or "OpenViking API error"))
    return payload.get("result", payload) if isinstance(payload, dict) else payload


def ensure_openviking_healthy() -> dict[str, Any]:
    result = _run_ov_json_command("health", "-o", "json", timeout=30)
    if not isinstance(result, dict) or not result.get("healthy", False):
        raise OpenVikingRuntimeError("OpenViking server is not healthy.")
    return result


def describe_openviking_runtime() -> dict[str, Any]:
    status: dict[str, Any] = {
        "role": OPENVIKING_RUNTIME_ROLE,
        "status": "unavailable",
        "healthy": False,
        "required_for": ["assistant_memory", "answer_time_context"],
        "not_required_for": ["document_upload", "document_index_rebuild", "chroma_document_retrieval"],
    }
    try:
        health = ensure_openviking_healthy()
    except OpenVikingRuntimeError as error:
        status["detail"] = str(error)
        return status

    status["status"] = "ready"
    status["healthy"] = True
    if isinstance(health, dict):
        status["detail"] = health
    return status


def ensure_openviking_directories(root_uri: str) -> None:
    normalized = root_uri.strip().rstrip("/")
    parts = normalized.split("/")
    if len(parts) < 4:
        raise OpenVikingRuntimeError("OpenViking root URI is invalid.")

    current = parts[0] + "//" + parts[2]
    for segment in parts[3:]:
        current = f"{current}/{segment}"
        try:
            _run_ov_command("mkdir", current, "-o", "json", timeout=30)
        except OpenVikingRuntimeError as error:
            lowered = str(error).casefold()
            if "already exists" not in lowered and "exist" not in lowered:
                raise


def search_openviking_resources(
    query: str,
    *,
    root_uri: str,
    mode: str = "search",
    node_limit: int = 10,
) -> list[OpenVikingResourceHit]:
    started_at = perf_counter()
    ensure_openviking_healthy()
    command = mode.strip().casefold()
    if command not in {"search", "find"}:
        raise OpenVikingRuntimeError("Unsupported OpenViking search mode.")

    result = _run_ov_json_command(
        command,
        "-u",
        root_uri,
        "-n",
        str(max(1, node_limit)),
        query,
        "-o",
        "json",
        timeout=max(DEFAULT_OV_TIMEOUT, 60),
    )
    resources = result.get("resources", []) if isinstance(result, dict) else []

    hits: list[OpenVikingResourceHit] = []
    seen: set[str] = set()
    normalized_root = root_uri.rstrip("/")
    for item in resources:
        uri = str(item.get("uri") or "").strip()
        if not uri or uri in seen:
            continue
        if not uri.startswith(normalized_root + "/") and uri.rstrip("/") != normalized_root:
            continue
        seen.add(uri)
        hits.append(
            OpenVikingResourceHit(
                uri=uri,
                level=int(item.get("level", 2) or 2),
                score=float(item.get("score", 0.0) or 0.0),
                abstract=str(item.get("abstract") or "").strip(),
                context_type=str(item.get("context_type") or "resource"),
            )
        )

    hits.sort(key=lambda item: (item.score, item.level, item.uri))
    DIAGNOSTIC_LOGGER.info(
        "DIAG %s",
        json.dumps(
            {
                "stage": "openviking_cli_search_complete",
                "elapsed_ms": round((perf_counter() - started_at) * 1000, 1),
                "query": query,
                "mode": command,
                "root_uri": root_uri,
                "node_limit": max(1, node_limit),
                "hit_count": len(hits),
            },
            ensure_ascii=False,
            default=str,
        ),
    )
    return hits
