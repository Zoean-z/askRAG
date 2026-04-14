from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.openviking_runtime import OpenVikingRuntimeError, describe_openviking_runtime
from app.runtime_state import record_evaluation
from app.session_memory import MEMORY_TYPE_TO_LAYER, MEMORY_TYPE_TO_SCOPE, SHORT_LIVED_TYPES, extract_memory_candidates
from app.tool_router import decide_tool_plan

DATASET_PATH = ROOT / "data" / "eval" / "regression_cases.json"


def run_case(case: dict) -> tuple[bool, str]:
    kind = case.get("kind")
    expect = case.get("expect") or {}

    if kind == "tool_router":
        plan = decide_tool_plan(case.get("question", ""), history=case.get("history", []))
        expected_tool = expect.get("primary_tool")
        passed = plan.primary_tool == expected_tool
        return passed, f"tool={plan.primary_tool} expected={expected_tool}"

    if kind == "memory_extract":
        candidates = extract_memory_candidates(
            question=case.get("question", ""),
            answer=case.get("answer", ""),
            sources=case.get("sources", []),
            history=case.get("history", []),
        )
        observed = {item["memory_type"] for item in candidates}
        expected = set(expect.get("memory_types") or [])
        passed = expected.issubset(observed)
        return passed, f"memory_types={sorted(observed)} expected_subset={sorted(expected)}"

    if kind == "memory_extract_absent":
        candidates = extract_memory_candidates(
            question=case.get("question", ""),
            answer=case.get("answer", ""),
            sources=case.get("sources", []),
            history=case.get("history", []),
        )
        observed = {item["memory_type"] for item in candidates}
        forbidden = set(expect.get("absent_memory_types") or [])
        passed = observed.isdisjoint(forbidden)
        return passed, f"memory_types={sorted(observed)} forbidden={sorted(forbidden)}"

    if kind == "memory_lane_contract":
        memory_type = str(case.get("memory_type", ""))
        observed = {
            "layer": MEMORY_TYPE_TO_LAYER.get(memory_type),
            "scope": MEMORY_TYPE_TO_SCOPE.get(memory_type),
            "short_lived": memory_type in SHORT_LIVED_TYPES,
        }
        expected_contract = {
            "layer": expect.get("layer"),
            "scope": expect.get("scope"),
            "short_lived": bool(expect.get("short_lived")),
        }
        passed = observed == expected_contract
        return passed, f"observed={observed}"

    if kind == "openviking_runtime_contract":
        runtime = case.get("runtime") or {}
        expected_runtime = expect or {}
        if runtime.get("error"):
            with patch("app.openviking_runtime.ensure_openviking_healthy", side_effect=OpenVikingRuntimeError(runtime["error"])):
                status = describe_openviking_runtime()
        else:
            with patch("app.openviking_runtime.ensure_openviking_healthy", return_value=runtime.get("health") or {"healthy": True}):
                status = describe_openviking_runtime()
        observed = {
            "role": status.get("role"),
            "required_for": status.get("required_for"),
            "not_required_for": status.get("not_required_for"),
            "healthy": status.get("healthy"),
        }
        expected_observed = {
            "role": expected_runtime.get("role"),
            "required_for": expected_runtime.get("required_for"),
            "not_required_for": expected_runtime.get("not_required_for"),
            "healthy": expected_runtime.get("healthy"),
        }
        passed = observed == expected_observed
        return passed, f"runtime={observed}"

    return False, f"unsupported kind: {kind}"


def main() -> int:
    cases = json.loads(DATASET_PATH.read_text(encoding="utf-8"))
    failures: list[str] = []
    for case in cases:
        passed, detail = run_case(case)
        line = f"[{'PASS' if passed else 'FAIL'}] {case.get('id')} - {detail}"
        print(line)
        if not passed:
            failures.append(line)

    status = "success" if not failures else "failed"
    record_evaluation(status, str(DATASET_PATH.relative_to(ROOT)), total=len(cases), failures=len(failures))
    print(f"\nSummary: {len(cases) - len(failures)}/{len(cases)} passed")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
