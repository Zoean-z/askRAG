import json
from dataclasses import dataclass
from typing import Literal

from app.tool_router import (
    ToolPlan,
    build_tool_messages,
    decide_tool_plan,
    llm_tool_plan,
    parse_tool_response,
    rule_tool_plan,
    should_use_llm_tool_plan,
)

RouteName = Literal["direct_answer", "local_chunk", "local_summary", "web_search"]

_TOOL_TO_ROUTE = {
    "direct_answer": "direct_answer",
    "local_doc_query": "local_chunk",
    "local_doc_summary": "local_summary",
    "web_search": "web_search",
}
_ROUTE_TO_TOOL = {
    "direct_answer": "direct_answer",
    "local_chunk": "local_doc_query",
    "local_summary": "local_doc_summary",
    "web_search": "web_search",
}


@dataclass(slots=True)
class RouteDecision:
    route: RouteName
    reason: str
    confidence: float = 1.0
    allow_fallback: bool = True


def _map_tool_plan(plan: ToolPlan) -> RouteDecision:
    return RouteDecision(
        route=_TOOL_TO_ROUTE[plan.primary_tool],
        reason=plan.reason,
        confidence=plan.confidence,
        allow_fallback=plan.primary_tool == "local_doc_query" and plan.fallback_tool == "local_doc_summary",
    )


def build_route_messages(question: str, history: list[dict[str, str]] | None = None) -> list[dict[str, str]]:
    return build_tool_messages(question, history=history)


def parse_route_response(content: str) -> RouteDecision:
    return _map_tool_plan(parse_tool_response(content))


def should_use_llm_route(question: str, history: list[dict[str, str]] | None = None) -> bool:
    return should_use_llm_tool_plan(question, history=history)


def rule_route(question: str, history: list[dict[str, str]] | None = None) -> RouteDecision | None:
    plan = rule_tool_plan(question, history=history)
    return _map_tool_plan(plan) if plan is not None else None


def llm_route(question: str, history: list[dict[str, str]] | None = None) -> RouteDecision:
    return _map_tool_plan(llm_tool_plan(question, history=history))


def decide_route(question: str, history: list[dict[str, str]] | None = None) -> RouteDecision:
    ruled = rule_route(question, history=history)
    if ruled is not None:
        return ruled

    if not should_use_llm_route(question, history=history):
        return RouteDecision(
            route="local_chunk",
            reason="default_local_doc_query_rule",
            confidence=0.8,
            allow_fallback=True,
        )

    try:
        classified = llm_route(question, history=history)
    except (json.JSONDecodeError, ValueError):
        return RouteDecision(
            route="local_chunk",
            reason="default_local_doc_query_after_invalid_llm_route",
            confidence=0.0,
            allow_fallback=True,
        )

    if classified.route in {"direct_answer", "local_summary", "web_search"} and classified.confidence < 0.7:
        return RouteDecision(
            route="local_chunk",
            reason="default_local_doc_query_after_low_confidence_llm_route",
            confidence=classified.confidence,
            allow_fallback=True,
        )

    return classified
