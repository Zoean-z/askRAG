from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
import re
from functools import lru_cache
from dataclasses import asdict, replace
from time import perf_counter
from typing import Any, Literal, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

from app.agent_tools import build_source_preview, log_diagnostic_event
from app.rag import is_summary_flow_request
from app.session_memory import is_recent_task_query
from app.tool_router import (
    ToolPlan,
    build_tool_plan,
    extract_router_hints,
    find_recent_summary_context,
    is_summary_web_verify_request,
    _question_has_doc_shape,
)


def _diagnostic_router_hints_payload(router_hints: Any) -> dict[str, Any]:
    if router_hints is None:
        return {}
    if isinstance(router_hints, dict):
        return dict(router_hints)
    try:
        return asdict(router_hints)
    except TypeError:
        pass
    payload = getattr(router_hints, "__dict__", None)
    if isinstance(payload, dict):
        return dict(payload)
    asdict_like = getattr(router_hints, "_asdict", None)
    if callable(asdict_like):
        try:
            return dict(asdict_like())
        except Exception:
            pass
    return {"value": str(router_hints)}


def _looks_like_profile_memory_query(question: str) -> bool:
    normalized = question.strip().casefold()
    if not normalized:
        return False
    return any(
        phrase in normalized
        for phrase in (
            "我住在哪里",
            "我住哪",
            "我住哪儿",
            "我住在",
            "我在哪住",
            "我在哪里住",
            "我叫什么",
            "我叫啥",
            "我是谁",
            "我来自哪里",
            "我哪儿人",
            "我哪里人",
            "我的住址",
        )
    )


def _looks_like_profile_memory_query_stable(question: str) -> bool:
    normalized = re.sub(r"[\s\u3000]+", "", question.strip())
    if not normalized:
        return False
    return any(
        phrase in normalized
        for phrase in (
            "\u6211\u4f4f\u5728\u54ea\u91cc",
            "\u6211\u53eb\u4ec0\u4e48",
            "\u6211\u662f\u8c01",
            "\u6211\u6765\u81ea\u54ea\u91cc",
        )
    )


def _looks_like_simple_greeting(question: str) -> bool:
    normalized = re.sub(r"[\s\u3000]+", "", question.strip()).casefold()
    if not normalized:
        return False
    return normalized in {"\u4f60\u597d", "\u60a8\u597d", "hello", "hi", "hey"}


def _looks_like_short_casual_direct_answer(question: str, *, target_source_hint: str | None = None) -> bool:
    normalized = re.sub(r"[\s\u3000]+", "", question.strip()).casefold()
    if not normalized:
        return False
    if len(normalized) > 16:
        return False
    if _question_has_doc_shape(question, target_source_hint=target_source_hint):
        return False
    return any(
        term in normalized
        for term in (
            "\u5e2e\u6211\u4e00\u4e0b",
            "\u5e2e\u4e2a\u5fd9",
            "\u8bb2\u4e00\u4e0b",
            "\u8bf4\u4e00\u4e0b",
            "\u4ecb\u7ecd\u4e00\u4e0b",
            "\u89e3\u91ca\u4e00\u4e0b",
            "\u804a\u804a",
            "\u8c08\u8c08",
            "\u53ef\u4ee5\u5417",
            "\u597d\u5417",
            "\u884c\u5417",
            "\u80fd\u5e2e\u6211\u5417",
            "\u80fd\u5e2e\u5fd9\u5417",
            "\u6559\u6211\u4e00\u4e0b",
            "\u5728\u5417",
        )
    )


def _init_request(state: dict[str, Any]) -> dict[str, Any]:
    started_at = perf_counter()
    question = state["question"]
    history = list(state.get("history") or [])
    router_hints = extract_router_hints(question, history=history)
    allow_web_search = bool(state.get("allow_web_search", True))
    if bool(state.get("force_web_only")):
        router_hints = replace(
            router_hints,
            force_web_only=True,
            force_local_only=False,
            summary_candidate=False,
            doc_candidate=False,
            web_candidate=True,
            direct_answer_candidate=False,
            followup_candidate=False,
            needs_freshness=True,
        )
    if not allow_web_search:
        router_hints = replace(
            router_hints,
            force_web_only=False,
            web_candidate=False,
            needs_freshness=False,
        )
    next_state = {
        **state,
        "question": question,
        "history": history,
        "k": int(state.get("k") or 3),
        "tool_call_count": 0,
        "last_tool": None,
        "decision_reason": "",
        "reference_history": list(state.get("reference_history") or []),
        "memory_context": "",
        "response_constraints": {},
        "router_hints": router_hints,
        "force_web_only": bool(state.get("force_web_only")),
        "allow_web_search": allow_web_search,
        "local_doc_probe": None,
        "should_attempt_local_retrieval": False,
        "doc_first_candidate": False,
        "chosen_route": None,
    }
    log_diagnostic_event(
        "init_request",
        started_at=started_at,
        raw_query=question,
        history_count=len(history),
        router_hints=_diagnostic_router_hints_payload(router_hints),
    )
    return next_state


def _local_doc_probe_node(state: dict[str, Any]) -> dict[str, Any]:
    from app.agent_tools import probe_local_docs

    started_at = perf_counter()
    probe_result = probe_local_docs(
        state["question"],
        history=state.get("history"),
        k=1,
    )
    log_diagnostic_event(
        "local_doc_probe",
        started_at=started_at,
        raw_query=state["question"],
        has_hits=probe_result.has_hits,
        top_sources=list(probe_result.top_sources),
        validation_reason=getattr(probe_result.validation, "reason", None),
        validation_sufficient=getattr(probe_result.validation, "is_sufficient", None),
    )
    return {
        **state,
        "local_doc_probe": probe_result,
    }


def _load_long_term_context_node(state: dict[str, Any]) -> dict[str, Any]:
    from app.agent_tools import load_long_term_context

    result = load_long_term_context(state["question"], history=state.get("history"))
    return {
        **state,
        "reference_history": result.reference_history,
        "memory_context": result.memory_context,
    }


def _load_response_constraints_node(state: dict[str, Any]) -> dict[str, Any]:
    from app.agent_tools import load_response_constraints

    return {
        **state,
        "response_constraints": load_response_constraints(),
    }


def _fan_out_preplan(state: dict[str, Any]) -> list[Send]:
    return [
        Send("local_doc_probe", state),
        Send("load_long_term_context", state),
        Send("load_response_constraints", state),
    ]


def _local_doc_probe_parallel_node(state: dict[str, Any]) -> dict[str, Any]:
    result_state = _local_doc_probe_node(state)
    return {"local_doc_probe": result_state.get("local_doc_probe")}


def _load_long_term_context_parallel_node(state: dict[str, Any]) -> dict[str, Any]:
    result_state = _load_long_term_context_node(state)
    return {
        "reference_history": result_state.get("reference_history", []),
        "memory_context": result_state.get("memory_context", ""),
    }


def _load_response_constraints_parallel_node(state: dict[str, Any]) -> dict[str, Any]:
    result_state = _load_response_constraints_node(state)
    return {"response_constraints": result_state.get("response_constraints", {})}


def _run_preplan_parallel(state: dict[str, Any]) -> dict[str, Any]:
    started_at = perf_counter()
    node_specs = (
        ("local_doc_probe", _local_doc_probe_parallel_node),
        ("load_long_term_context", _load_long_term_context_parallel_node),
        ("load_response_constraints", _load_response_constraints_parallel_node),
    )
    merged_state = dict(state)
    timings_ms: dict[str, float] = {}

    def _invoke_node(name: str, func, current_state: dict[str, Any]) -> tuple[str, dict[str, Any], float]:
        node_started_at = perf_counter()
        result_state = func(current_state)
        elapsed_ms = round((perf_counter() - node_started_at) * 1000, 1)
        return name, result_state, elapsed_ms

    with ThreadPoolExecutor(max_workers=len(node_specs)) as executor:
        future_map = {
            executor.submit(_invoke_node, name, func, state): name
            for name, func in node_specs
        }
        for future in as_completed(future_map):
            name, result_state, elapsed_ms = future.result()
            merged_state.update(result_state)
            timings_ms[name] = elapsed_ms

    log_diagnostic_event(
        "preplan_parallel_complete",
        started_at=started_at,
        question=state.get("question"),
        history_count=len(state.get("history") or []),
        timings_ms=timings_ms,
    )
    return merged_state


def _plan_request(state: dict[str, Any]) -> dict[str, Any]:
    started_at = perf_counter()
    question = state["question"]
    history = state.get("history")
    allow_web_search = bool(state.get("allow_web_search", True))
    router_hints = state.get("router_hints") or extract_router_hints(question, history=history)
    probe_result = state.get("local_doc_probe")
    force_web_only = bool(getattr(router_hints, "force_web_only", False))
    force_local_only = bool(getattr(router_hints, "force_local_only", False))
    probe_has_hits = bool(getattr(probe_result, "has_hits", False))
    should_attempt_local_retrieval = bool(
        probe_has_hits
        and (
            not allow_web_search
            or (
                not force_web_only
                and not bool(getattr(router_hints, "needs_freshness", False))
            )
        )
    )
    doc_first_candidate = bool(
        force_local_only
        or router_hints.doc_candidate
        or should_attempt_local_retrieval
    )

    if allow_web_search and force_web_only:
        tool_plan = build_tool_plan(
            "web_search",
            reason="graph_force_web_only",
            confidence=1.0,
            fallback_tool=None,
            use_history=router_hints.use_history,
            target_source_hint=router_hints.target_source_hint,
            intent="web_search",
            needs_freshness=True,
            needs_external_knowledge=True,
        )
    elif force_local_only:
        tool_plan = build_tool_plan(
            "local_doc_query",
            reason="graph_force_local_only",
            confidence=1.0,
            fallback_tool="local_doc_summary",
            use_history=router_hints.use_history,
            target_source_hint=router_hints.target_source_hint,
            intent="doc_query",
            needs_freshness=False,
            needs_external_knowledge=False,
        )
    elif allow_web_search and (
        not router_hints.summary_candidate
        and is_summary_web_verify_request(question, history=history)
    ):
        summary_context = find_recent_summary_context(history)
        tool_plan = build_tool_plan(
            "web_search",
            reason="matched_summary_web_verify_rule",
            confidence=1.0,
            fallback_tool=None,
            use_history=True,
            target_source_hint=summary_context.sources[0] if summary_context and summary_context.sources else None,
            needs_freshness=True,
            needs_external_knowledge=True,
            web_search_mode="summary_verify",
        )
    elif router_hints.summary_candidate:
        tool_plan = build_tool_plan(
            "local_doc_summary",
            reason="graph_summary_hint",
            confidence=1.0,
            fallback_tool=None,
            use_history=router_hints.use_history,
            target_source_hint=router_hints.target_source_hint,
            intent="doc_summary",
        )
    elif is_recent_task_query(question):
        tool_plan = build_tool_plan(
            "direct_answer",
            reason="graph_recent_task_memory_direct_answer",
            confidence=0.92,
            fallback_tool=None,
            use_history=router_hints.use_history,
            intent="chat_followup",
        )
    elif state.get("memory_context") and _looks_like_profile_memory_query_stable(question):
        tool_plan = build_tool_plan(
            "direct_answer",
            reason="graph_profile_memory_direct_answer",
            confidence=0.9,
            fallback_tool=None,
            use_history=router_hints.use_history,
            intent="direct_answer",
        )
    elif _looks_like_simple_greeting(question):
        tool_plan = build_tool_plan(
            "direct_answer",
            reason="graph_simple_greeting_direct_answer",
            confidence=0.98,
            fallback_tool=None,
            use_history=False,
            intent="direct_answer",
        )
    elif router_hints.direct_answer_candidate or router_hints.followup_candidate or _looks_like_short_casual_direct_answer(
        question,
        target_source_hint=router_hints.target_source_hint,
    ):
        tool_plan = build_tool_plan(
            "direct_answer",
            reason=(
                "graph_followup_hint"
                if router_hints.followup_candidate
                else "graph_direct_answer_hint"
                if router_hints.direct_answer_candidate
                else "graph_short_casual_direct_answer"
            ),
            confidence=1.0 if router_hints.direct_answer_candidate or router_hints.followup_candidate else 0.78,
            fallback_tool=None,
            use_history=router_hints.use_history,
            intent="chat_followup" if router_hints.followup_candidate else "direct_answer",
        )
    elif doc_first_candidate:
        tool_plan = build_tool_plan(
            "local_doc_query",
            reason=(
                "graph_doc_first_with_probe"
                if should_attempt_local_retrieval and not router_hints.doc_candidate
                else "graph_doc_hint_with_probe"
                if probe_has_hits
                else "graph_doc_hint"
            ),
            confidence=1.0 if router_hints.doc_candidate or force_local_only else 0.9 if probe_has_hits else 0.82,
            fallback_tool="local_doc_summary",
            use_history=router_hints.use_history,
            target_source_hint=router_hints.target_source_hint,
            intent="doc_query",
            needs_freshness=router_hints.needs_freshness,
            needs_external_knowledge=False,
        )
    elif allow_web_search and router_hints.web_candidate:
        tool_plan = build_tool_plan(
            "web_search",
            reason="graph_web_hint",
            confidence=1.0,
            fallback_tool=None,
            use_history=router_hints.use_history,
            target_source_hint=router_hints.target_source_hint,
            intent="web_search",
            needs_freshness=router_hints.needs_freshness or bool(getattr(probe_result, "has_hits", False)),
            needs_external_knowledge=True,
        )
    else:
        tool_plan = build_tool_plan(
            "direct_answer",
            reason="graph_default_direct_answer",
            confidence=0.55,
            fallback_tool=None,
            use_history=router_hints.use_history,
            intent="direct_answer",
        )
    planned_node = _decide_next_action({**state, "tool_plan": tool_plan})
    log_diagnostic_event(
        "plan_request",
        started_at=started_at,
        raw_query=question,
        router_hints=_diagnostic_router_hints_payload(router_hints),
        local_doc_probe={
            "has_hits": probe_has_hits,
            "top_sources": list(getattr(probe_result, "top_sources", []) or []),
            "validation_reason": getattr(getattr(probe_result, "validation", None), "reason", None),
            "validation_sufficient": getattr(getattr(probe_result, "validation", None), "is_sufficient", None),
        },
        probe_has_hits=probe_has_hits,
        should_attempt_local_retrieval=should_attempt_local_retrieval,
        doc_first_candidate=doc_first_candidate,
        chosen_route=tool_plan.primary_tool,
        planner_path=planned_node,
        tool_plan={
            "intent": tool_plan.intent,
            "primary_tool": tool_plan.primary_tool,
            "fallback_tool": tool_plan.fallback_tool,
            "confidence": tool_plan.confidence,
            "reason": tool_plan.reason,
            "web_search_mode": tool_plan.web_search_mode,
        },
    )
    return {
        **state,
        "tool_plan": tool_plan,
        "decision_reason": tool_plan.reason,
        "should_attempt_local_retrieval": should_attempt_local_retrieval,
        "doc_first_candidate": doc_first_candidate,
        "chosen_route": tool_plan.primary_tool,
    }


def _decide_next_action(state: dict[str, Any]) -> Literal[
    "direct_answer_node",
    "summary_strategy_node",
    "direct_web_search_node",
    "retrieval_local_search_node",
]:
    tool_plan: ToolPlan = state["tool_plan"]
    if tool_plan.primary_tool == "direct_answer":
        return "direct_answer_node"
    if tool_plan.primary_tool == "local_doc_summary":
        return "summary_strategy_node"
    if tool_plan.primary_tool == "web_search":
        return "direct_web_search_node"
    return "retrieval_local_search_node"


def _direct_answer_node(state: dict[str, Any]) -> dict[str, Any]:
    from app.agent_tools import answer_directly_tool
    reference_history = state.get("reference_history") or state.get("history")
    kwargs: dict[str, Any] = {}
    if state.get("memory_context"):
        kwargs["memory_context"] = state["memory_context"]
    if state.get("response_constraints"):
        kwargs["response_constraints"] = state["response_constraints"]

    return {
        **state,
        "tool_call_count": int(state.get("tool_call_count") or 0) + 1,
        "last_tool": "direct_answer",
        "result": answer_directly_tool(
            state["question"],
            history=reference_history,
            **kwargs,
        )
    }


def _summary_strategy_node(state: dict[str, Any]) -> dict[str, Any]:
    from app.agent_tools import decide_summary_strategy

    started_at = perf_counter()
    strategy = decide_summary_strategy(
        state["question"],
        history=state.get("reference_history") or state.get("history"),
    )
    log_diagnostic_event(
        "summary_strategy",
        started_at=started_at,
        raw_query=state["question"],
        strategy=strategy.strategy,
    )
    return {
        **state,
        "summary_strategy": strategy.strategy,
    }


def _decide_summary_strategy(state: dict[str, Any]) -> Literal[
    "local_summary_node",
    "summary_web_search_node",
]:
    if state.get("summary_strategy") == "summary_plus_web":
        return "summary_web_search_node"
    return "local_summary_node"


def _local_summary_node(state: dict[str, Any]) -> dict[str, Any]:
    from app.agent_tools import read_summary
    started_at = perf_counter()
    reference_history = state.get("reference_history") or state.get("history")
    kwargs: dict[str, Any] = {}
    if state.get("memory_context"):
        kwargs["memory_context"] = state["memory_context"]
    if state.get("response_constraints"):
        kwargs["response_constraints"] = state["response_constraints"]

    summary_result = read_summary(
        state["question"],
        history=reference_history,
        require_strong_parent_match=True,
        **kwargs,
    )
    next_state = {
        **state,
        "tool_call_count": int(state.get("tool_call_count") or 0) + 1,
        "last_tool": "local_doc_summary",
        "summary_result": summary_result,
    }
    if state.get("summary_strategy") != "summary_plus_web":
        next_state["result"] = summary_result
    log_diagnostic_event(
        "summary_local",
        started_at=started_at,
        raw_query=state["question"],
        mode="summary_local_summary",
        source_count=len(summary_result.sources),
        source_preview=build_source_preview(summary_result.sources, answer=summary_result.answer),
        answer_preview=summary_result.answer[:180],
    )
    return next_state


def _summary_web_search_node(state: dict[str, Any]) -> dict[str, Any]:
    from app.agent_tools import run_summary_web_search_result

    started_at = perf_counter()
    summary_result = state.get("summary_result")
    if summary_result is None:
        state = _local_summary_node(state)
        summary_result = state["summary_result"]

    web_result = run_summary_web_search_result(
        state["question"],
        summary_result,
        response_constraints=state.get("response_constraints") or None,
    )
    log_diagnostic_event(
        "web_search",
        started_at=started_at,
        raw_query=state["question"],
        mode="summary_web_supplement",
        source_count=len(web_result.sources),
        source_preview=build_source_preview(web_result.sources, answer=web_result.answer),
        answer_preview=web_result.answer[:180],
    )
    return {
        **state,
        "tool_call_count": int(state.get("tool_call_count") or 0) + 1,
        "last_tool": "summary_web_search",
        "web_result": web_result,
    }


def _summary_finalize_node(state: dict[str, Any]) -> dict[str, Any]:
    from app.agent_tools import compose_summary_with_web_result

    started_at = perf_counter()
    summary_result = state["summary_result"]
    if state.get("summary_strategy") != "summary_plus_web" or state.get("web_result") is None:
        log_diagnostic_event(
            "finalize",
            started_at=started_at,
            raw_query=state["question"],
            mode="summary_local_only",
            source_count=len(summary_result.sources),
            source_preview=build_source_preview(summary_result.sources, answer=summary_result.answer),
            answer_preview=summary_result.answer[:180],
        )
        return {
            **state,
            "result": summary_result,
        }
    result = compose_summary_with_web_result(
        state["question"],
        summary_result,
        state["web_result"],
        memory_context=state.get("memory_context") or None,
        response_constraints=state.get("response_constraints") or None,
    )
    log_diagnostic_event(
        "finalize",
        started_at=started_at,
        raw_query=state["question"],
        mode="summary_plus_web",
        source_count=len(result.sources),
        source_preview=build_source_preview(result.sources, answer=result.answer),
        answer_preview=result.answer[:180],
    )
    return {
        **state,
        "result": result,
    }


def _direct_web_search_node(state: dict[str, Any]) -> dict[str, Any]:
    from app.agent_tools import run_direct_web_search_result

    started_at = perf_counter()
    question = state["question"]
    tool_plan: ToolPlan = state["tool_plan"]
    response_constraints = state.get("response_constraints") or None

    if tool_plan.web_search_mode == "general":
        result = run_direct_web_search_result(
            question,
            tool_plan,
            history=state.get("reference_history") or state.get("history"),
            response_constraints=response_constraints,
        )
        log_diagnostic_event(
            "web_search",
            started_at=started_at,
            raw_query=question,
            mode="direct_general",
            query_count=result.trace.get("debug", {}).get("query_count"),
            selected_query=result.trace.get("debug", {}).get("selected_query"),
            source_count=len(result.sources),
            source_preview=build_source_preview(result.sources, answer=result.answer),
            answer_preview=result.answer[:180],
            web_relevance_score=result.trace.get("debug", {}).get("web_relevance_score"),
            web_relevant=result.trace.get("debug", {}).get("web_relevant"),
            official_like_sources=result.trace.get("debug", {}).get("official_like_sources"),
        )
        return {
            **state,
            "tool_call_count": int(state.get("tool_call_count") or 0) + 1,
            "last_tool": "web_search",
            "result": result,
        }

    from app.workflow import run_answer_workflow_detailed
    reference_history = state.get("reference_history") or state.get("history")
    result = run_answer_workflow_detailed(
        question,
        tool_plan,
        history=reference_history,
        k=int(state.get("k") or 3),
        allow_web_search=bool(state.get("allow_web_search", True)),
    )
    trace_debug = result.trace.get("debug", {}) if isinstance(result.trace, dict) else {}
    log_diagnostic_event(
        "web_search",
        started_at=started_at,
        raw_query=question,
        mode="direct_legacy_workflow",
        source_count=len(result.sources),
        source_preview=build_source_preview(result.sources, answer=result.answer),
        answer_preview=result.answer[:180],
        decision_reason=trace_debug.get("decision_reason"),
        trace_mode=result.trace.get("mode") if isinstance(result.trace, dict) else None,
    )
    return {
        **state,
        "tool_call_count": int(state.get("tool_call_count") or 0) + 1,
        "last_tool": "web_search",
        "result": result,
    }


def _retrieval_local_search_node(state: dict[str, Any]) -> dict[str, Any]:
    from app.agent_tools import (
        apply_local_kb_search_result,
        initialize_retrieval_workflow_state,
        search_kb_chroma,
    )

    started_at = perf_counter()
    workflow_state = state.get("workflow_state")
    if workflow_state is None:
        workflow_state = initialize_retrieval_workflow_state(
            state["question"],
            state["tool_plan"],
            state.get("reference_history") or state.get("history"),
            allow_web_search=bool(state.get("allow_web_search", True)),
        )

    kb_result = search_kb_chroma(
        state["question"],
        history=state.get("history"),
        reference_history=state.get("reference_history") or None,
        k=int(state.get("k") or 3),
    )
    apply_local_kb_search_result(workflow_state, kb_result)
    local_bundle = getattr(workflow_state, "local_bundle", None)
    local_validation = getattr(workflow_state, "local_validation", None)
    log_diagnostic_event(
        "retrieval_local_search",
        started_at=started_at,
        raw_query=state["question"],
        mode="retrieval_local_search",
        rewritten_query=getattr(local_bundle, "rewritten_question", None),
        vector_result_count=len(getattr(local_bundle, "vector_results", []) or []),
        keyword_result_count=len(getattr(local_bundle, "keyword_results", []) or []),
        result_count=len(getattr(local_bundle, "results", []) or []),
        source_count=len(getattr(local_bundle, "sources", []) or []),
        source_preview=build_source_preview(getattr(local_bundle, "sources", []) or [], limit=3),
        validation_reason=getattr(local_validation, "reason", None),
        validation_sufficient=getattr(local_validation, "is_sufficient", None),
    )
    return {
        **state,
        "tool_call_count": int(state.get("tool_call_count") or 0) + 1,
        "last_tool": "search_kb_chroma",
        "workflow_state": workflow_state,
    }


def _retrieval_assess_local_node(state: dict[str, Any]) -> dict[str, Any]:
    from app.agent_tools import assess_local_retrieval_followup

    started_at = perf_counter()
    workflow_state = state["workflow_state"]
    assess_local_retrieval_followup(workflow_state)
    log_diagnostic_event(
        "assess",
        started_at=started_at,
        raw_query=state["question"],
        mode="retrieval_assess_local",
        local_retrieval_attempted_before_web=True,
        web_fallback_reason=getattr(workflow_state, "decision_reason", None)
        if getattr(workflow_state, "needs_web", False)
        else None,
        decision_reason=getattr(workflow_state, "decision_reason", None),
        needs_web=getattr(workflow_state, "needs_web", None),
        local_sufficient=getattr(workflow_state, "local_sufficient", None),
        combined_sufficient=getattr(workflow_state, "combined_sufficient", None),
        source_count=len(getattr(workflow_state, "sources", []) or []),
        source_preview=build_source_preview(getattr(workflow_state, "sources", []) or [], answer=getattr(workflow_state, "local_context", None) or None),
    )
    return {**state, "workflow_state": workflow_state}


def _decide_retrieval_followup(state: dict[str, Any]) -> Literal[
    "retrieval_finalize_node",
    "retrieval_web_search_node",
]:
    workflow_state = state["workflow_state"]
    if workflow_state.needs_web:
        return "retrieval_web_search_node"
    return "retrieval_finalize_node"


def _retrieval_web_search_node(state: dict[str, Any]) -> dict[str, Any]:
    from app.agent_tools import run_retrieval_web_search_step
    from app.workflow import _refresh_trace

    started_at = perf_counter()
    workflow_state = state["workflow_state"]
    run_retrieval_web_search_step(workflow_state)
    _refresh_trace(workflow_state)
    log_diagnostic_event(
        "web_search",
        started_at=started_at,
        raw_query=state["question"],
        mode="retrieval_web_search",
        local_retrieval_attempted_before_web=True,
        web_fallback_reason=getattr(workflow_state, "decision_reason", None),
        query_count=len(getattr(workflow_state, "web_queries", []) or []),
        selected_query=getattr(workflow_state, "web_query", None),
        source_count=len(getattr(workflow_state, "web_sources", []) or []),
        source_preview=build_source_preview(getattr(workflow_state, "web_sources", []) or [], answer=getattr(workflow_state, "web_answer", None)),
        answer_preview=(getattr(workflow_state, "web_answer", "") or "")[:180],
        web_relevance_score=getattr(workflow_state, "web_relevance_score", None),
        web_relevant=getattr(workflow_state, "web_relevant", None),
        needs_web_extract=getattr(workflow_state, "needs_web_extract", None),
        decision_reason=getattr(workflow_state, "decision_reason", None),
    )
    return {
        **state,
        "tool_call_count": int(state.get("tool_call_count") or 0) + 1,
        "last_tool": "workflow_web_search",
        "workflow_state": workflow_state,
    }


def _decide_after_web_search(state: dict[str, Any]) -> Literal[
    "retrieval_web_extract_node",
    "retrieval_assess_combined_node",
]:
    workflow_state = state["workflow_state"]
    if workflow_state.needs_web_extract:
        return "retrieval_web_extract_node"
    return "retrieval_assess_combined_node"


def _retrieval_web_extract_node(state: dict[str, Any]) -> dict[str, Any]:
    from app.agent_tools import run_retrieval_web_extract_step
    from app.workflow import _refresh_trace

    started_at = perf_counter()
    workflow_state = state["workflow_state"]
    run_retrieval_web_extract_step(workflow_state)
    _refresh_trace(workflow_state)
    log_diagnostic_event(
        "web_extract",
        started_at=started_at,
        raw_query=state["question"],
        mode="retrieval_web_extract",
        local_retrieval_attempted_before_web=True,
        web_fallback_reason=getattr(workflow_state, "decision_reason", None),
        selected_query=getattr(workflow_state, "web_query", None),
        source_count=len(getattr(workflow_state, "web_sources", []) or []),
        source_preview=build_source_preview(getattr(workflow_state, "web_sources", []) or [], answer=getattr(workflow_state, "web_answer", None)),
        answer_preview=(getattr(workflow_state, "web_answer", "") or "")[:180],
        web_relevance_score=getattr(workflow_state, "web_relevance_score", None),
        web_relevant=getattr(workflow_state, "web_relevant", None),
    )
    return {
        **state,
        "tool_call_count": int(state.get("tool_call_count") or 0) + 1,
        "last_tool": "workflow_web_extract",
        "workflow_state": workflow_state,
    }


def _retrieval_assess_combined_node(state: dict[str, Any]) -> dict[str, Any]:
    from app.agent_tools import assess_combined_retrieval_evidence
    from app.workflow import _refresh_trace

    started_at = perf_counter()
    workflow_state = state["workflow_state"]
    assess_combined_retrieval_evidence(workflow_state)
    _refresh_trace(workflow_state)
    log_diagnostic_event(
        "assess",
        started_at=started_at,
        raw_query=state["question"],
        mode="retrieval_assess_combined",
        decision_reason=getattr(workflow_state, "decision_reason", None),
        combined_sufficient=getattr(workflow_state, "combined_sufficient", None),
        local_sufficient=getattr(workflow_state, "local_sufficient", None),
        web_relevant=getattr(workflow_state, "web_relevant", None),
        web_relevance_score=getattr(workflow_state, "web_relevance_score", None),
        source_count=len(getattr(workflow_state, "sources", []) or []),
        source_preview=build_source_preview(
            getattr(workflow_state, "sources", []) or [],
            answer=getattr(workflow_state, "web_answer", None) or getattr(workflow_state, "local_context", None) or None,
        ),
    )
    return {
        **state,
        "workflow_state": workflow_state,
    }


def _retrieval_finalize_node(state: dict[str, Any]) -> dict[str, Any]:
    from app.agent_tools import finalize_retrieval_result

    started_at = perf_counter()
    workflow_state = state["workflow_state"]
    result = finalize_retrieval_result(workflow_state)
    trace_debug = result.trace.get("debug", {}) if isinstance(result.trace, dict) else {}
    log_diagnostic_event(
        "finalize",
        started_at=started_at,
        raw_query=state["question"],
        mode="retrieval_finalize",
        source_count=len(result.sources),
        source_preview=build_source_preview(result.sources, answer=result.answer),
        answer_preview=result.answer[:180],
        decision_reason=trace_debug.get("decision_reason"),
    )
    return {
        **state,
        "workflow_state": workflow_state,
        "result": result,
    }


def _stream_with_turn_memory(
    *,
    question: str,
    history: list[dict[str, str]] | None,
    event_stream: Iterator[tuple[str, dict]],
    conversation_id: str | None = None,
) -> Iterator[tuple[str, dict]]:
    from app.agent_tools import persist_turn_memory_result

    wrapper_started_at = perf_counter()
    collected_answer: list[str] = []
    collected_sources: list[str] = []
    collected_trace: dict[str, Any] = {}

    for event_name, payload in event_stream:
        if event_name == "sources":
            collected_sources = [str(item) for item in payload.get("sources", []) if str(item).strip()]
        elif event_name == "delta":
            text = str(payload.get("text") or "")
            if text:
                collected_answer.append(text)
        elif event_name == "trace":
            collected_trace = dict(payload or {})

        if event_name == "done":
            memory_started_at = perf_counter()
            persistence = persist_turn_memory_result(
                question=question,
                answer="".join(collected_answer),
                sources=collected_sources,
                history=history,
                trace=collected_trace,
                conversation_id=conversation_id,
            )
            log_diagnostic_event(
                "stream_turn_memory_wrapper_complete",
                started_at=memory_started_at,
                question=question,
                answer_chars=len("".join(collected_answer)),
                source_count=len(collected_sources),
                notice_count=len(persistence.memory_notices),
            )
            if persistence.memory_notices:
                yield "memory_notices", {"items": persistence.memory_notices}
            log_diagnostic_event(
                "stream_event_pipeline_complete",
                started_at=wrapper_started_at,
                question=question,
                answer_chars=len("".join(collected_answer)),
                source_count=len(collected_sources),
                trace_mode=collected_trace.get("mode"),
            )
            yield "done", payload
            return

        yield event_name, payload


@lru_cache(maxsize=1)
def build_agent_graph():
    builder = StateGraph(AgentGraphState)
    builder.add_node("init_request", _init_request)
    builder.add_node("local_doc_probe", _local_doc_probe_parallel_node)
    builder.add_node("load_long_term_context", _load_long_term_context_parallel_node)
    builder.add_node("load_response_constraints", _load_response_constraints_parallel_node)
    builder.add_node("plan_request", _plan_request)
    builder.add_node("direct_answer_node", _direct_answer_node)
    builder.add_node("summary_strategy_node", _summary_strategy_node)
    builder.add_node("local_summary_node", _local_summary_node)
    builder.add_node("summary_web_search_node", _summary_web_search_node)
    builder.add_node("summary_finalize_node", _summary_finalize_node)
    builder.add_node("direct_web_search_node", _direct_web_search_node)
    builder.add_node("retrieval_local_search_node", _retrieval_local_search_node)
    builder.add_node("retrieval_assess_local_node", _retrieval_assess_local_node)
    builder.add_node("retrieval_web_search_node", _retrieval_web_search_node)
    builder.add_node("retrieval_web_extract_node", _retrieval_web_extract_node)
    builder.add_node("retrieval_assess_combined_node", _retrieval_assess_combined_node)
    builder.add_node("retrieval_finalize_node", _retrieval_finalize_node)

    builder.add_edge(START, "init_request")
    builder.add_conditional_edges("init_request", _fan_out_preplan)
    builder.add_edge("local_doc_probe", "plan_request")
    builder.add_edge("load_long_term_context", "plan_request")
    builder.add_edge("load_response_constraints", "plan_request")
    builder.add_conditional_edges("plan_request", _decide_next_action)
    builder.add_edge("direct_answer_node", END)
    builder.add_conditional_edges("summary_strategy_node", _decide_summary_strategy)
    builder.add_edge("local_summary_node", "summary_finalize_node")
    builder.add_edge("summary_web_search_node", "summary_finalize_node")
    builder.add_edge("summary_finalize_node", END)
    builder.add_edge("direct_web_search_node", END)
    builder.add_edge("retrieval_local_search_node", "retrieval_assess_local_node")
    builder.add_conditional_edges("retrieval_assess_local_node", _decide_retrieval_followup)
    builder.add_conditional_edges("retrieval_web_search_node", _decide_after_web_search)
    builder.add_edge("retrieval_web_extract_node", "retrieval_assess_combined_node")
    builder.add_edge("retrieval_assess_combined_node", "retrieval_finalize_node")
    builder.add_edge("retrieval_finalize_node", END)
    return builder.compile()


def run_agent_graph_detailed(
    question: str,
    *,
    history: list[dict[str, str]] | None,
    k: int = 3,
):
    graph = build_agent_graph()
    state = graph.invoke(
        {
            "question": question,
            "history": list(history or []),
            "k": int(k),
        }
    )
    return state["result"]


def run_agent_graph_stream(
    question: str,
    *,
    history: list[dict[str, str]] | None,
    k: int = 3,
    allow_web_search: bool = True,
    conversation_id: str | None = None,
):
    initial_state = _init_request(
        {
            "question": question,
            "history": list(history or []),
            "k": int(k),
            "allow_web_search": bool(allow_web_search),
        }
    )
    state = _plan_request(_run_preplan_parallel(initial_state))
    next_action = _decide_next_action(state)
    tool_plan: ToolPlan = state["tool_plan"]

    if next_action == "direct_answer_node":
        from app.agent_tools import stream_direct_answer_tool
        kwargs: dict[str, Any] = {}
        if state.get("memory_context"):
            kwargs["memory_context"] = state["memory_context"]
        if state.get("response_constraints"):
            kwargs["response_constraints"] = state["response_constraints"]

        yield from _stream_with_turn_memory(
            question=question,
            history=state.get("history"),
            conversation_id=conversation_id,
            event_stream=stream_direct_answer_tool(
            question,
            history=state.get("reference_history") or state.get("history"),
            **kwargs,
            ),
        )
        return

    if next_action == "summary_strategy_node":
        from app.agent_tools import (
            compose_summary_with_web_result,
            decide_summary_strategy,
            read_summary,
            run_summary_web_search_result,
            stream_compose_summary_with_web_result,
            stream_read_summary,
        )

        summary_strategy = decide_summary_strategy(
            question,
            history=state.get("reference_history") or state.get("history"),
        ).strategy
        if summary_strategy != "summary_plus_web":
            yield from _stream_with_turn_memory(
                question=question,
                history=state.get("history"),
                conversation_id=conversation_id,
                event_stream=stream_read_summary(
                    question,
                    history=state.get("reference_history") or state.get("history"),
                    require_strong_parent_match=True,
                    memory_context=state.get("memory_context") or None,
                    response_constraints=state.get("response_constraints") or None,
                ),
            )
            return

        summary_result = read_summary(
            question,
            history=state.get("reference_history") or state.get("history"),
            require_strong_parent_match=True,
            memory_context=state.get("memory_context") or None,
            response_constraints=state.get("response_constraints") or None,
        )
        web_result = run_summary_web_search_result(
            question,
            summary_result,
            response_constraints=state.get("response_constraints") or None,
        )
        yield from _stream_with_turn_memory(
            question=question,
            history=state.get("history"),
            conversation_id=conversation_id,
            event_stream=stream_compose_summary_with_web_result(
                question,
                summary_result,
                web_result,
                memory_context=state.get("memory_context") or None,
                response_constraints=state.get("response_constraints") or None,
            ),
        )
        return

    if next_action == "direct_web_search_node":
        from app.agent_tools import stream_web_search_tool

        yield from _stream_with_turn_memory(
            question=question,
            history=state.get("history"),
            conversation_id=conversation_id,
            event_stream=stream_web_search_tool(
            question,
            tool_plan,
            history=state.get("reference_history") or state.get("history"),
            response_constraints=state.get("response_constraints") or None,
            ),
        )
        return

    if next_action == "retrieval_local_search_node":
        from app.agent_tools import (
            apply_local_kb_search_result,
            assess_local_retrieval_followup,
            assess_combined_retrieval_evidence,
            initialize_retrieval_workflow_state,
            run_retrieval_web_extract_step,
            run_retrieval_web_search_step,
            search_kb_chroma,
            stream_retrieval_finalize_result,
        )
        from app.rag import REFUSAL_MESSAGE
        from app.workflow import _progress, _refresh_trace

        workflow_state = initialize_retrieval_workflow_state(
            question,
            tool_plan,
            state.get("history"),
            allow_web_search=bool(state.get("allow_web_search", True)),
        )
        yield _progress("workflow_start", workflow_state)
        yield _progress("workflow_local_search", workflow_state)
        kb_result = search_kb_chroma(
            question,
            history=state.get("history"),
            k=int(state.get("k") or 3),
        )
        apply_local_kb_search_result(workflow_state, kb_result)
        if workflow_state.trace:
            yield "trace", workflow_state.trace
        if workflow_state.local_bundle and workflow_state.local_bundle.sources:
            yield "sources", {"sources": workflow_state.local_bundle.sources}

        yield _progress(
            "workflow_assess_local",
            workflow_state,
            sufficient=workflow_state.local_answer_sufficient,
            relevant=workflow_state.local_retrieval_relevant,
        )
        assessment = assess_local_retrieval_followup(workflow_state)
        if workflow_state.trace:
            yield "trace", workflow_state.trace
        if assessment.decision_reason == "guardrail_blocked_auto_web_fallback":
            yield "delta", {"text": REFUSAL_MESSAGE}
            yield _progress("workflow_done", workflow_state)
            yield "done", {}
            return
        if workflow_state.needs_web:
            yield _progress("workflow_web_search", workflow_state)
            run_retrieval_web_search_step(workflow_state)
            _refresh_trace(workflow_state)
            if workflow_state.trace:
                yield "trace", workflow_state.trace
            if workflow_state.needs_web_extract:
                yield _progress("workflow_web_extract", workflow_state)
                run_retrieval_web_extract_step(workflow_state)
                _refresh_trace(workflow_state)
                if workflow_state.trace:
                    yield "trace", workflow_state.trace
            assess_combined_retrieval_evidence(workflow_state)
            _refresh_trace(workflow_state)
            if workflow_state.trace:
                yield "trace", workflow_state.trace
            yield _progress(
                "workflow_assess_combined",
                workflow_state,
                sufficient=workflow_state.combined_sufficient,
                used_web=bool(workflow_state.web_attempted),
            )

        yield from _stream_with_turn_memory(
            question=question,
            history=state.get("history"),
            conversation_id=conversation_id,
            event_stream=stream_retrieval_finalize_result(workflow_state),
        )
        return

    raise RuntimeError(f"Unhandled stream next action: {next_action}")


__all__ = ["build_agent_graph", "run_agent_graph_detailed", "run_agent_graph_stream"]
class AgentGraphState(TypedDict, total=False):
    question: str
    history: list[dict[str, str]]
    k: int
    tool_call_count: int
    last_tool: str | None
    decision_reason: str
    reference_history: list[dict[str, str]]
    memory_context: str
    response_constraints: dict[str, Any]
    router_hints: Any
    local_doc_probe: Any
    should_attempt_local_retrieval: bool
    doc_first_candidate: bool
    chosen_route: str | None
    tool_plan: ToolPlan
    summary_strategy: str
    summary_result: Any
    web_result: Any
    workflow_state: Any
    result: Any
