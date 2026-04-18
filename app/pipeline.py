import re
from collections.abc import Iterator
from dataclasses import asdict, dataclass
from pathlib import Path
from time import perf_counter
from urllib.parse import urlparse
from typing import Any

from langchain_core.documents import Document
from openai import APIConnectionError, AuthenticationError, BadRequestError, RateLimitError

from app.context_layers import build_query_context_plan, build_summary_context_plan
from app.rag import (
    EMPTY_ANSWER_MESSAGE,
    REFUSAL_MESSAGE,
    apply_response_constraints_to_system_prompt,
    build_chat_messages,
    build_summary_messages,
    extract_stream_text,
    get_chat_client,
    get_chat_model,
    get_provider_family,
    get_responses_client,
    get_web_search_model,
    is_web_search_enabled,
    normalize_history,
    extract_web_search_result_count,
    run_glm_web_search,
    rewrite_web_search_query,
    split_documents,
)
from app.retrievers.backend import prepare_chunk_answer_material
from app.retrievers.parent_retriever import choose_summary_document
from app.session_memory import build_memory_context, build_reference_history, build_response_constraints
from app.tool_router import ToolPlan, decide_tool_plan, extract_router_hints, find_recent_summary_context
from app.validators import should_fallback_to_summary, validate_chunk_results

DIRECT_ANSWER_SYSTEM_PROMPT = (
    "You are the assistant for a local RAG demo application. "
    "Answer brief small-talk or product capability questions directly. "
    "Handle safe text transformation requests such as translation, polishing, or rewriting. "
    "Do not claim to have searched the knowledge base unless retrieval was actually used. "
    "Keep the answer concise."
)
WEB_SEARCH_DISABLED_MESSAGE = "[web_search] \u5f53\u524d\u672a\u542f\u7528\u7f51\u9875\u67e5\u8be2\u5de5\u5177\uff0c\u65e0\u6cd5\u56de\u7b54\u8fd9\u7c7b\u9700\u8981\u8054\u7f51\u6216\u6700\u65b0\u4fe1\u606f\u7684\u95ee\u9898\u3002"
LONG_SUMMARY_DIRECT_THRESHOLD = 4200
SUMMARY_CHUNK_SIZE = 2200
SUMMARY_CHUNK_OVERLAP = 180
WEB_SEARCH_TOOLS = [
    {"type": "web_search"},
    {"type": "web_extractor"},
]
LIGHTWEIGHT_WEB_SEARCH_TOOLS = [{"type": "web_search"}]
WEB_SEARCH_EXTRA_BODY = {"enable_thinking": True}
LIGHTWEIGHT_WEB_SEARCH_EXTRA_BODY = {"enable_thinking": False}
SUMMARY_VERIFY_MAX_CLAIMS = 3
SUMMARY_VERIFY_MIN_CLAIM_LENGTH = 12
SUMMARY_VERIFY_MAX_CLAIM_LENGTH = 140
SUMMARY_VERIFY_SPLIT_PATTERN = re.compile(r"[\r\n]+|[\u3002\uFF01\uFF1F!?\uFF1B;]+")
SUMMARY_VERIFY_BULLET_PREFIX = re.compile(
    r"^\s*(?:[-*+]|(?:\d+|[\u4e00\u4e8c\u4e09\u56db\u4e94\u516d\u4e03\u516b\u4e5d\u5341\u4e24]+)[.)\u3001])\s*"
)
WEB_SEARCH_PROGRESS_MESSAGE = "[web_search] Searching the web..."
WEB_SEARCH_FAILURE_MESSAGE = "[web_search] Web search is temporarily unavailable. Check the configured provider endpoint, model support, and tool permissions."
WEB_SEARCH_ANSWER_SYSTEM_PROMPT = (
    "You are an evidence-grounded assistant. "
    "Answer only from the provided web findings and cited sources. "
    "Do not paste raw search snippets or article bodies back to the user. "
    "Rewrite the answer in your own words and keep it concise. "
    "Prefer official or first-party sources when they are available. "
    "If the evidence is insufficient, conflicting, or too weak to answer reliably, say you cannot answer reliably."
)
WEB_SEARCH_QUALITY_FRESHNESS_TERMS = (
    "latest",
    "today",
    "recent",
    "current",
    "release",
    "released",
    "pricing",
    "price",
    "model",
    "version",
    "official",
    "官网",
    "官方",
    "最新",
    "今天",
    "近期",
    "最近",
    "当前",
    "发布",
    "价格",
    "型号",
    "版本",
)
WEB_SEARCH_OFFICIAL_QUERY_SUFFIX_EN = "site:openai.com site:platform.openai.com official site official docs"
WEB_SEARCH_OFFICIAL_QUERY_SUFFIX_ZH = "site:openai.com site:platform.openai.com 官方 官网 官方文档"


WEB_SEARCH_QUALITY_FRESHNESS_TERMS_ACTIVE = (
    "latest",
    "today",
    "recent",
    "current",
    "release",
    "released",
    "pricing",
    "price",
    "model",
    "version",
    "official",
    "官网",
    "官方",
    "最新",
    "今天",
    "近期",
    "最近",
    "当前",
    "发布",
    "价格",
    "型号",
    "版本",
)
WEB_SEARCH_OFFICIAL_QUERY_SUFFIX_ZH_ACTIVE = "site:openai.com site:platform.openai.com 官方 官网 官方文档"


def build_web_search_disabled_trace(question: str, tool_plan: ToolPlan) -> dict[str, Any]:
    return {
        "mode": "web_search_disabled",
        "question": question,
        "layers_used": [],
        "selected_source": None,
        "candidate_sources": [],
        "drilldown_path": ["web_search_disabled"],
        "debug": {
            "provider": get_provider_family(),
            "primary_tool": tool_plan.primary_tool,
            "web_search_enabled": False,
        },
    }


def build_web_search_trace(
    question: str,
    tool_plan: ToolPlan,
    sources: list[str] | None = None,
    *,
    debug: dict[str, Any] | None = None,
) -> dict[str, Any]:
    resolved_sources = [source for source in (sources or []) if isinstance(source, str) and source.strip()]
    debug_payload = {
        "provider": get_provider_family(),
        "primary_tool": tool_plan.primary_tool,
        "web_search_enabled": True,
        "web_search_mode": tool_plan.web_search_mode,
    }
    if debug:
        debug_payload.update(debug)
    return {
        "mode": "web_search",
        "question": question,
        "layers_used": ["web_search"],
        "selected_source": None,
        "candidate_sources": resolved_sources,
        "drilldown_path": ["web_search"],
        "debug": debug_payload,
    }


def _log_pre_router_diagnostic(question: str, history: list[dict[str, str]] | None = None) -> None:
    from app.agent_tools import log_diagnostic_event

    started_at = perf_counter()
    router_hints = extract_router_hints(question, history=history)
    log_diagnostic_event(
        "pre_router",
        started_at=started_at,
        raw_query=question,
        history_count=len(normalize_history(history)),
        router_hints=_diagnostic_router_hints_payload(router_hints),
        rewrite_query=None,
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


@dataclass(slots=True)
class AnswerRunResult:
    answer: str
    sources: list[str]
    trace: dict[str, Any]


def build_web_search_failure_message(detail: str | None = None) -> str:
    message = WEB_SEARCH_FAILURE_MESSAGE
    normalized = (detail or "").strip()
    if normalized:
        return f"{message}\n\nDetail: {normalized}"
    return message


def _web_provider_status_from_error_detail(detail: str | None) -> str:
    normalized = (detail or "").strip()
    if not normalized:
        return "error"
    match = re.search(r"http_status=(\d+)", normalized, flags=re.IGNORECASE)
    if match:
        return f"http_{match.group(1)}"
    match = re.search(r"HTTP Error (\d+)", normalized, flags=re.IGNORECASE)
    if match:
        return f"http_{match.group(1)}"
    return "error"


def _extract_source_host(source: str) -> str:
    match = re.search(r"\((https?://[^)]+)\)", source)
    candidate = match.group(1) if match else source.strip()
    if not candidate.startswith(("http://", "https://")):
        return ""
    return (urlparse(candidate).hostname or "").casefold()


def _extract_question_entity_tokens(question: str) -> list[str]:
    tokens = {
        token.casefold()
        for token in re.findall(r"[A-Za-z][A-Za-z0-9_-]{2,}", question)
        if len(token) >= 4
    }
    return sorted(tokens)


def _is_freshness_or_high_trust_question(question: str, tool_plan: ToolPlan) -> bool:
    if tool_plan.needs_freshness:
        return True
    normalized = question.casefold()
    return any(term in normalized for term in WEB_SEARCH_QUALITY_FRESHNESS_TERMS_ACTIVE)


def _has_official_like_source(question: str, sources: list[str]) -> bool:
    entity_tokens = _extract_question_entity_tokens(question)
    for source in sources:
        normalized = source.casefold()
        if any(term in normalized for term in ("official", "官网", "官方")):
            return True
        host = _extract_source_host(source)
        if not host:
            continue
        if any(marker in host for marker in ("docs.", "developer.", "help.", "support.", "platform.")) and entity_tokens:
            return True
        if any(token in host for token in entity_tokens):
            return True
    return False


def _build_web_search_summary_messages(
    question: str,
    evidence_text: str,
    sources: list[str],
    *,
    response_constraints: dict[str, object] | None = None,
) -> list[dict[str, str]]:
    source_lines = "\n".join(f"- {source}" for source in sources) or "- none"
    return [
        {
            "role": "system",
            "content": apply_response_constraints_to_system_prompt(WEB_SEARCH_ANSWER_SYSTEM_PROMPT, response_constraints),
        },
        {
            "role": "user",
            "content": (
                f"Current question: {question.strip()}\n\n"
                f"[Web Findings]\n{evidence_text.strip()}\n\n"
                f"[Web Sources]\n{source_lines}"
            ),
        },
    ]


def _build_direct_web_search_queries(
    question: str,
    tool_plan: ToolPlan,
    *,
    history: list[dict[str, str]] | None = None,
    rewrite_result: object | None = None,
) -> list[str]:
    query_rewrite = rewrite_result if rewrite_result is not None else rewrite_web_search_query(question, history=history)
    queries: list[str] = [getattr(query_rewrite, "selected_query", "") or question.strip()]
    try:
        from app.workflow import _build_focused_web_query

        focused_query = _build_focused_web_query(
            queries[0] or question,
            raw_question=question,
            history=history,
            local_bundle=None,
        )
    except Exception:
        focused_query = None
    if focused_query and focused_query not in queries:
        queries.append(focused_query)
    if _is_freshness_or_high_trust_question(question, tool_plan):
        suffix = WEB_SEARCH_OFFICIAL_QUERY_SUFFIX_ZH_ACTIVE if re.search(r"[\u4e00-\u9fff]", question) else WEB_SEARCH_OFFICIAL_QUERY_SUFFIX_EN
        official_query = f"{queries[0]} {suffix}".strip()
        if official_query and official_query not in queries:
            queries.append(official_query)
    return [query for query in queries if query][:3]


def _execute_direct_web_request(query: str, *, lightweight: bool = False) -> tuple[Any, str, list[str]]:
    request = build_web_search_request(query, lightweight=lightweight)
    if request.get("provider") == "glm":
        response = run_glm_web_search(
            str(request.get("input", "")).strip(),
            lightweight=bool(request.get("lightweight")),
            use_extractor=bool(request.get("use_extractor")),
        )
    else:
        request.pop("provider", None)
        client = get_responses_client()
        response = client.responses.create(**request)
    return response, extract_web_search_text(response) or EMPTY_ANSWER_MESSAGE, extract_web_search_sources(response)


def _summarize_web_search_answer(
    question: str,
    evidence_text: str,
    sources: list[str],
    *,
    stream: bool = False,
    response_constraints: dict[str, object] | None = None,
) -> Any:
    client = get_chat_client()
    return client.chat.completions.create(
        model=get_chat_model(),
        temperature=0.2,
        messages=_build_web_search_summary_messages(
            question,
            evidence_text,
            sources,
            response_constraints=response_constraints,
        ),
        stream=stream,
    )


def _run_direct_web_search_quality_pass(
    question: str,
    tool_plan: ToolPlan,
    *,
    history: list[dict[str, str]] | None = None,
    response_constraints: dict[str, object] | None = None,
) -> tuple[str, list[str], dict[str, Any]]:
    from app.workflow import WEB_EVIDENCE_INSUFFICIENT_MESSAGE, _assess_web_result_relevance
    from app.agent_tools import build_source_preview, log_diagnostic_event

    started_at = perf_counter()
    rewrite_result = rewrite_web_search_query(question, history=history)
    queries = _build_direct_web_search_queries(question, tool_plan, history=history, rewrite_result=rewrite_result)
    best_answer = ""
    best_sources: list[str] = []
    best_query = ""
    best_score = 0.0
    best_relevant = False
    best_official = False
    best_raw_count = 0
    provider_name = get_provider_family()

    for attempt_index, query in enumerate(queries, start=1):
        attempt_started_at = perf_counter()
        try:
            response, answer, sources = _execute_direct_web_request(query, lightweight=True)
        except (ValueError, AuthenticationError, RateLimitError, BadRequestError, APIConnectionError) as error:
            provider_error = str(error)
            failure_message = build_web_search_failure_message(provider_error)
            log_diagnostic_event(
                "web_search_failed",
                started_at=attempt_started_at,
                raw_query=rewrite_result.raw_query,
                normalized_query=rewrite_result.normalized_query,
                rewrite_used=rewrite_result.rewrite_used,
                rewritten_query=rewrite_result.rewritten_query,
                resolved_references=rewrite_result.resolved_references,
                selected_query=queries[0] if queries else question,
                attempt_query=query,
                attempt_index=attempt_index,
                total_attempts=len(queries),
                web_provider_name=provider_name,
                web_request_sent=True,
                web_provider_status=_web_provider_status_from_error_detail(provider_error),
                web_provider_error=provider_error,
                raw_web_result_count=0,
                parsed_web_result_count=0,
                failure_category="provider_failure",
                final_failure_reason=failure_message,
            )
            debug = {
                "query_count": len(queries),
                "selected_query": query,
                "web_relevance_score": 0.0,
                "web_relevant": False,
                "official_like_sources": False,
                "failure_category": "provider_failure",
                "web_provider_name": provider_name,
                "web_request_sent": True,
                "web_provider_status": _web_provider_status_from_error_detail(provider_error),
                "web_provider_error": provider_error,
                "raw_web_result_count": 0,
                "parsed_web_result_count": 0,
                "final_failure_reason": failure_message,
            }
            return failure_message, [], debug
        raw_result_count = extract_web_search_result_count(response)
        score, relevant = _assess_web_result_relevance(question, answer, sources)
        official_like = _has_official_like_source(question, sources)
        candidate_rank = (
            int(relevant),
            int(official_like and _is_freshness_or_high_trust_question(question, tool_plan)),
            score,
            int(bool(sources)),
            len(answer.strip()),
        )
        current_rank = (
            int(best_relevant),
            int(best_official and _is_freshness_or_high_trust_question(question, tool_plan)),
            best_score,
            int(bool(best_sources)),
            len(best_answer.strip()),
        )
        if candidate_rank > current_rank:
            best_answer = answer
            best_sources = sources
            best_query = query
            best_score = score
            best_relevant = relevant
            best_official = official_like
            best_raw_count = raw_result_count
        log_diagnostic_event(
            "web_search_attempt",
            started_at=attempt_started_at,
            raw_query=rewrite_result.raw_query,
            normalized_query=rewrite_result.normalized_query,
            rewrite_used=rewrite_result.rewrite_used,
            rewritten_query=rewrite_result.rewritten_query,
            resolved_references=rewrite_result.resolved_references,
            selected_query=queries[0] if queries else question,
            attempt_query=query,
            attempt_index=attempt_index,
            total_attempts=len(queries),
            web_provider_name=provider_name,
            web_request_sent=True,
            web_provider_status="success",
            web_provider_error="",
            raw_web_result_count=raw_result_count,
            parsed_web_result_count=len(sources),
            result_count=len(sources),
            source_preview=build_source_preview(sources, answer=answer),
            relevance_score=score,
            relevant=relevant,
            web_result_relevance=score,
            web_result_relevant=relevant,
            official_like=official_like,
        )
        if best_relevant and (not _is_freshness_or_high_trust_question(question, tool_plan) or best_official):
            break

    if not best_relevant and best_sources:
        try:
            response, answer, sources = _execute_direct_web_request(best_query or queries[0], lightweight=False)
        except (ValueError, AuthenticationError, RateLimitError, BadRequestError, APIConnectionError) as error:
            provider_error = str(error)
            failure_message = build_web_search_failure_message(provider_error)
            log_diagnostic_event(
                "web_search_failed",
                started_at=started_at,
                raw_query=rewrite_result.raw_query,
                normalized_query=rewrite_result.normalized_query,
                rewrite_used=rewrite_result.rewrite_used,
                rewritten_query=rewrite_result.rewritten_query,
                resolved_references=rewrite_result.resolved_references,
                selected_query=best_query or (queries[0] if queries else question),
                attempt_query=best_query or (queries[0] if queries else question),
                attempt_index=len(queries) + 1,
                total_attempts=len(queries) + 1,
                web_provider_name=provider_name,
                web_request_sent=True,
                web_provider_status=_web_provider_status_from_error_detail(provider_error),
                web_provider_error=provider_error,
                raw_web_result_count=0,
                parsed_web_result_count=0,
                failure_category="provider_failure",
                final_failure_reason=failure_message,
            )
            debug = {
                "query_count": len(queries) + 1,
                "selected_query": best_query or (queries[0] if queries else question),
                "web_relevance_score": best_score,
                "web_relevant": best_relevant,
                "official_like_sources": best_official,
                "failure_category": "provider_failure",
                "web_provider_name": provider_name,
                "web_request_sent": True,
                "web_provider_status": _web_provider_status_from_error_detail(provider_error),
                "web_provider_error": provider_error,
                "raw_web_result_count": best_raw_count,
                "parsed_web_result_count": len(best_sources),
                "final_failure_reason": failure_message,
            }
            return failure_message, best_sources or [], debug
        raw_result_count = extract_web_search_result_count(response)
        score, relevant = _assess_web_result_relevance(question, answer, sources)
        official_like = _has_official_like_source(question, sources)
        candidate_rank = (
            int(relevant),
            int(official_like and _is_freshness_or_high_trust_question(question, tool_plan)),
            score,
            int(bool(sources)),
            len(answer.strip()),
        )
        current_rank = (
            int(best_relevant),
            int(best_official and _is_freshness_or_high_trust_question(question, tool_plan)),
            best_score,
            int(bool(best_sources)),
            len(best_answer.strip()),
        )
        if candidate_rank > current_rank:
            best_answer = answer
            best_sources = sources
            best_query = best_query or (queries[0] if queries else question)
            best_score = score
            best_relevant = relevant
            best_official = official_like
            best_raw_count = raw_result_count
        log_diagnostic_event(
            "web_search_attempt",
            started_at=started_at,
            raw_query=rewrite_result.raw_query,
            normalized_query=rewrite_result.normalized_query,
            rewrite_used=rewrite_result.rewrite_used,
            rewritten_query=rewrite_result.rewritten_query,
            resolved_references=rewrite_result.resolved_references,
            selected_query=best_query,
            attempt_query=best_query or (queries[0] if queries else question),
            attempt_index=len(queries) + 1,
            total_attempts=len(queries) + 1,
            web_provider_name=provider_name,
            web_request_sent=True,
            web_provider_status="success",
            web_provider_error="",
            raw_web_result_count=raw_result_count,
            parsed_web_result_count=len(sources),
            result_count=len(sources),
            source_preview=build_source_preview(sources, answer=answer),
            relevance_score=score,
            relevant=relevant,
            web_result_relevance=score,
            web_result_relevant=relevant,
            official_like=official_like,
        )

    debug = {
        "query_count": len(queries),
        "selected_query": best_query,
        "web_relevance_score": best_score,
        "web_relevant": best_relevant,
        "official_like_sources": best_official,
        "web_provider_name": provider_name,
        "web_request_sent": True,
        "web_provider_status": "success",
        "web_provider_error": "",
        "raw_web_result_count": best_raw_count,
        "parsed_web_result_count": len(best_sources),
        "failure_category": "irrelevant_results" if best_sources else "empty_results",
    }
    freshness_question = _is_freshness_or_high_trust_question(question, tool_plan)
    relaxed_acceptance = freshness_question and bool(best_sources) and best_score >= 2.5
    if not best_relevant and relaxed_acceptance:
        best_relevant = True
        best_official = best_official or _has_official_like_source(question, best_sources)
        debug["web_relevant"] = True
        debug["official_like_sources"] = best_official
        debug["relevance_relaxed"] = True
    if not best_relevant:
        failure_category = "irrelevant_results" if best_sources else "empty_results"
        final_failure_reason = WEB_EVIDENCE_INSUFFICIENT_MESSAGE
        log_diagnostic_event(
            "web_search_rejected",
            started_at=started_at,
            raw_query=question,
            selected_query=best_query,
            query_count=len(queries),
            result_count=len(best_sources),
            web_provider_name=provider_name,
            web_request_sent=True,
            web_provider_status="success",
            web_provider_error="",
            raw_web_result_count=best_raw_count,
            parsed_web_result_count=len(best_sources),
            source_preview=build_source_preview(best_sources, answer=best_answer),
            reject_reason=failure_category,
            failure_category=failure_category,
            final_failure_reason=final_failure_reason,
            web_relevance_score=best_score,
            web_result_relevance=best_score,
            web_relevant=best_relevant,
            official_like_sources=best_official,
            relevance_relaxed=debug.get("relevance_relaxed", False),
        )
        debug["failure_category"] = failure_category
        debug["final_failure_reason"] = final_failure_reason
        log_diagnostic_event(
            "web_search_total_complete",
            started_at=started_at,
            question=question,
            query_count=len(queries),
            selected_query=best_query,
            source_count=len(best_sources),
            failure_category=failure_category,
            final_failure_reason=final_failure_reason,
            web_relevance_score=best_score,
            web_relevant=best_relevant,
        )
        return final_failure_reason, [], debug
    if _is_freshness_or_high_trust_question(question, tool_plan) and not best_official:
        debug["official_preference_unmet"] = True
    try:
        response = _summarize_web_search_answer(
            question,
            best_answer,
            best_sources,
            stream=False,
            response_constraints=response_constraints,
        )
    except (ValueError, AuthenticationError, RateLimitError, BadRequestError, APIConnectionError) as error:
        provider_error = str(error)
        log_diagnostic_event(
            "web_search_failed",
            started_at=started_at,
            raw_query=question,
            selected_query=best_query,
            query_count=len(queries),
            result_count=len(best_sources),
            web_provider_name=provider_name,
            web_request_sent=True,
            web_provider_status="summary_failed",
            web_provider_error=provider_error,
            raw_web_result_count=best_raw_count,
            parsed_web_result_count=len(best_sources),
            source_preview=build_source_preview(best_sources, answer=best_answer),
            detail=provider_error,
            failure_category="provider_failure",
            final_failure_reason=build_web_search_failure_message(provider_error),
        )
        debug["failure_category"] = "provider_failure"
        debug["web_provider_name"] = provider_name
        debug["web_request_sent"] = True
        debug["web_provider_status"] = "summary_failed"
        debug["web_provider_error"] = provider_error
        debug["raw_web_result_count"] = best_raw_count
        debug["parsed_web_result_count"] = len(best_sources)
        debug["final_failure_reason"] = build_web_search_failure_message(provider_error)
        log_diagnostic_event(
            "web_search_total_complete",
            started_at=started_at,
            question=question,
            query_count=len(queries),
            selected_query=best_query,
            source_count=len(best_sources),
            failure_category="provider_failure",
            final_failure_reason=build_web_search_failure_message(provider_error),
        )
        return build_web_search_failure_message(provider_error), [], debug
    summarized = response.choices[0].message.content or EMPTY_ANSWER_MESSAGE
    log_diagnostic_event(
        "web_search_finalize",
        started_at=started_at,
        raw_query=question,
        selected_query=best_query,
        query_count=len(queries),
        result_count=len(best_sources),
        web_provider_name=provider_name,
        web_request_sent=True,
        web_provider_status="success",
        web_provider_error="",
        raw_web_result_count=best_raw_count,
        parsed_web_result_count=len(best_sources),
        source_preview=build_source_preview(best_sources, answer=best_answer),
        web_relevance_score=best_score,
        web_relevant=best_relevant,
        official_like_sources=best_official,
        official_preference_unmet=debug.get("official_preference_unmet", False),
        failure_category="success",
        final_failure_reason="",
        answer_preview=summarized[:180],
    )
    log_diagnostic_event(
        "web_search_total_complete",
        started_at=started_at,
        question=question,
        query_count=len(queries),
        selected_query=best_query,
        source_count=len(best_sources),
        failure_category="success",
        final_failure_reason="",
        web_relevance_score=best_score,
        web_relevant=best_relevant,
        relevance_relaxed=debug.get("relevance_relaxed", False),
    )
    return summarized.strip() or EMPTY_ANSWER_MESSAGE, best_sources, debug


def _to_plain_data(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(key): _to_plain_data(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_plain_data(item) for item in value]
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        return _to_plain_data(model_dump())
    dict_method = getattr(value, "dict", None)
    if callable(dict_method):
        return _to_plain_data(dict_method())
    if hasattr(value, "__dict__"):
        return {str(key): _to_plain_data(item) for key, item in vars(value).items()}
    return value


def _collect_web_source_values(node: Any, collected: list[str]) -> None:
    if isinstance(node, dict):
        title = node.get("title") or node.get("name")
        url = node.get("url")
        if isinstance(url, str) and url.startswith(("http://", "https://")):
            collected.append(f"{title} ({url})" if isinstance(title, str) and title.strip() else url)

        for key in ("sources", "results", "citations"):
            child = node.get(key)
            if isinstance(child, list):
                for item in child:
                    _collect_web_source_values(item, collected)

        for value in node.values():
            if isinstance(value, (dict, list, tuple)):
                _collect_web_source_values(value, collected)
        return

    if isinstance(node, (list, tuple)):
        for item in node:
            _collect_web_source_values(item, collected)


def extract_web_search_sources(payload: Any) -> list[str]:
    plain = _to_plain_data(payload)
    glm_results = plain.get("search_result", []) if isinstance(plain, dict) else []
    if isinstance(glm_results, list) and glm_results:
        collected: list[str] = []
        for item in glm_results:
            if not isinstance(item, dict):
                continue
            title = str(item.get("title") or "").strip()
            link = str(item.get("link") or "").strip()
            media = str(item.get("media") or "").strip()
            publish_date = str(item.get("publish_date") or "").strip()
            if link:
                collected.append(f"{title} ({link})" if title else link)
                continue
            label = title or media
            if publish_date and label:
                label = f"{label} [{publish_date}]"
            if label:
                collected.append(label)
        return collected[:5]

    collected: list[str] = []
    _collect_web_source_values(plain, collected)

    deduped: list[str] = []
    seen: set[str] = set()
    for item in collected:
        normalized = item.strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(normalized)
    return deduped[:5]


def extract_web_search_text(response: Any) -> str:
    output_text = getattr(response, "output_text", None)
    if isinstance(output_text, str) and output_text.strip():
        return output_text.strip()

    plain = _to_plain_data(response)
    glm_results = plain.get("search_result", []) if isinstance(plain, dict) else []
    if isinstance(glm_results, list) and glm_results:
        sections: list[str] = []
        for index, item in enumerate(glm_results[:5], start=1):
            if not isinstance(item, dict):
                continue
            title = str(item.get("title") or "").strip() or f"Result {index}"
            content = str(item.get("content") or "").strip()
            media = str(item.get("media") or "").strip()
            publish_date = str(item.get("publish_date") or "").strip()
            meta: list[str] = []
            if media:
                meta.append(f"source={media}")
            if publish_date:
                meta.append(f"date={publish_date}")
            header = f"[Result {index}] title={title}"
            if meta:
                header += " " + " ".join(meta)
            sections.append(f"{header}\n{content}".strip())
        return "\n\n".join(section for section in sections if section.strip()).strip()

    outputs = plain.get("output", []) if isinstance(plain, dict) else []
    texts: list[str] = []
    for item in outputs:
        if not isinstance(item, dict) or item.get("type") != "message":
            continue
        for content in item.get("content", []):
            if isinstance(content, dict) and content.get("type") in {"output_text", "text", "input_text"}:
                text = content.get("text")
                if isinstance(text, str) and text.strip():
                    texts.append(text.strip())
    return "\n\n".join(texts).strip()


def _normalize_summary_claim(text: str) -> str:
    normalized = SUMMARY_VERIFY_BULLET_PREFIX.sub("", text.strip())
    normalized = normalized.replace("`", "")
    normalized = normalized.replace("**", "")
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip(" -:;,.，。；")[:SUMMARY_VERIFY_MAX_CLAIM_LENGTH].strip()


def extract_summary_verification_claims(summary: str) -> list[str]:
    claims: list[str] = []
    seen: set[str] = set()
    for part in SUMMARY_VERIFY_SPLIT_PATTERN.split(summary):
        claim = _normalize_summary_claim(part)
        if len(claim) < SUMMARY_VERIFY_MIN_CLAIM_LENGTH:
            continue
        key = claim.casefold()
        if key in seen:
            continue
        seen.add(key)
        claims.append(claim)
        if len(claims) >= SUMMARY_VERIFY_MAX_CLAIMS:
            return claims

    fallback = _normalize_summary_claim(summary)
    if fallback and fallback.casefold() not in seen:
        claims.append(fallback)
    return claims[:SUMMARY_VERIFY_MAX_CLAIMS]


def build_summary_verification_query(question: str, history: list[dict[str, str]] | None = None) -> str:
    reference_history = build_reference_history(question, history)
    summary_context = find_recent_summary_context(reference_history)
    if summary_context is None:
        return question.strip()

    claims = extract_summary_verification_claims(summary_context.assistant_answer)
    if not claims:
        return question.strip()

    source_label = Path(summary_context.sources[0]).stem if summary_context.sources else "recent summary"
    normalized_question = question.casefold()
    source_instruction = (
        "优先使用官网或官方来源"
        if any(term in normalized_question for term in ("官网", "官方", "official"))
        else "优先使用高可信来源"
    )
    lines = [f"请联网核实以下关于 {source_label} 的说法是否准确，{source_instruction}："]
    for index, claim in enumerate(claims, start=1):
        lines.append(f"{index}. {claim}")
    return "\n".join(lines)


def resolve_web_search_request(question: str, tool_plan: ToolPlan, history: list[dict[str, str]] | None = None) -> dict[str, Any]:
    query = build_summary_verification_query(question, history=history) if tool_plan.web_search_mode == "summary_verify" else question
    rewrite_result = rewrite_web_search_query(
        query,
        history=history,
        allow_llm_rewrite=tool_plan.web_search_mode != "summary_verify",
    )
    return build_web_search_request(rewrite_result.selected_query, lightweight=tool_plan.web_search_mode == "summary_verify")


def build_web_search_request(question: str, *, lightweight: bool = False) -> dict[str, Any]:
    provider = get_provider_family()
    if provider == "glm":
        return {
            "provider": provider,
            "input": question.strip(),
            "lightweight": lightweight,
            "use_extractor": False,
        }

    tools = LIGHTWEIGHT_WEB_SEARCH_TOOLS if lightweight else WEB_SEARCH_TOOLS
    extra_body = LIGHTWEIGHT_WEB_SEARCH_EXTRA_BODY if lightweight else WEB_SEARCH_EXTRA_BODY
    return {
        "provider": provider,
        "model": get_web_search_model(),
        "input": question.strip(),
        "tools": tools,
        "extra_body": dict(extra_body),
    }


DIRECT_ANSWER_MAP = {
    "你好": "你好，我可以帮你基于本地知识库问答、总结文档，并管理已上传的文本文件。",
    "您好": "您好，我可以帮你基于本地知识库问答、总结文档，并管理已上传的文本文件。",
    "谢谢": "不客气。",
    "多谢": "不客气。",
    "你是谁": "我是这个本地知识库问答项目里的助手，负责基于知识库回答、总结文档和处理简单对话。",
    "你能做什么": "我可以基于当前知识库回答问题、总结文档，并支持上传和删除 `.txt`、`.md` 文件。",
    "你支持上传什么文件": "当前支持上传 UTF-8 编码的 `.txt` 和 `.md` 文件。",
    "这个项目支持上传什么文件": "当前支持上传 UTF-8 编码的 `.txt` 和 `.md` 文件。",
    "hello": "Hello. I can answer questions from the local knowledge base, summarize documents, and manage uploaded text files.",
    "hi": "Hello. I can answer questions from the local knowledge base, summarize documents, and manage uploaded text files.",
    "thanks": "You're welcome.",
    "thank you": "You're welcome.",
}


def normalize_direct_answer_key(question: str) -> str:
    return question.strip().casefold().replace("？", "").replace("?", "").replace("！", "").replace("!", "").replace("。", "")


def format_direct_answer(answer: str) -> str:
    return answer.strip() or EMPTY_ANSWER_MESSAGE


def build_direct_answer_messages(
    question: str,
    history: list[dict[str, str]] | None = None,
    *,
    memory_context: str = "",
    response_constraints: dict[str, object] | None = None,
) -> list[dict[str, str]]:
    history_block = ""
    normalized_history = normalize_history(history)
    if normalized_history:
        history_block = "\n".join(f"{item['role']}: {item['content']}" for item in normalized_history)

    content_parts = [f"Current question: {question.strip()}"]
    if memory_context:
        content_parts.insert(0, memory_context)
    if history_block:
        content_parts.insert(0, f"Recent history:\n{history_block}")
    return [
        {
            "role": "system",
            "content": apply_response_constraints_to_system_prompt(DIRECT_ANSWER_SYSTEM_PROMPT, response_constraints),
        },
        {"role": "user", "content": "\n\n".join(content_parts)},
    ]
def answer_directly_detailed(
    question: str,
    history: list[dict[str, str]] | None = None,
    *,
    reference_history: list[dict[str, str]] | None = None,
    memory_context: str | None = None,
    response_constraints: dict[str, object] | None = None,
) -> AnswerRunResult:
    from app.agent_tools import log_diagnostic_event

    started_at = perf_counter()
    reference_history = reference_history if reference_history is not None else build_reference_history(question, history)
    normalized_key = normalize_direct_answer_key(question)
    if normalized_key in DIRECT_ANSWER_MAP:
        result = AnswerRunResult(
            answer=format_direct_answer(DIRECT_ANSWER_MAP[normalized_key]),
            sources=[],
            trace={"mode": "direct_answer", "layers_used": [], "selected_source": None, "drilldown_path": ["direct_answer"]},
        )
        log_diagnostic_event(
            "finalize_answer_complete",
            started_at=started_at,
            question=question,
            mode="direct_answer_static",
            source_count=0,
        )
        return result

    client = get_chat_client()
    resolved_memory_context = memory_context if memory_context is not None else build_memory_context(question, history=reference_history)
    resolved_response_constraints = response_constraints if response_constraints is not None else build_response_constraints()
    response = client.chat.completions.create(
        model=get_chat_model(),
        temperature=0.2,
        messages=build_direct_answer_messages(
            question,
            history=reference_history,
            memory_context=resolved_memory_context,
            response_constraints=resolved_response_constraints,
        ),
    )
    answer = response.choices[0].message.content or EMPTY_ANSWER_MESSAGE
    result = AnswerRunResult(
        answer=format_direct_answer(answer),
        sources=[],
        trace={
            "mode": "direct_answer",
            "layers_used": ["memory"] if resolved_memory_context else [],
            "selected_source": None,
            "drilldown_path": ["direct_answer"],
            "debug": {"memory_context_used": bool(resolved_memory_context)},
        },
    )
    log_diagnostic_event(
        "finalize_answer_complete",
        started_at=started_at,
        question=question,
        mode="direct_answer",
        source_count=0,
        memory_context_used=bool(resolved_memory_context),
    )
    return result


def answer_directly(question: str, history: list[dict[str, str]] | None = None) -> tuple[str, list[str]]:
    result = answer_directly_detailed(question, history=history)
    return result.answer, result.sources


def stream_direct_answer(
    question: str,
    history: list[dict[str, str]] | None = None,
    *,
    reference_history: list[dict[str, str]] | None = None,
    memory_context: str | None = None,
    response_constraints: dict[str, object] | None = None,
) -> Iterator[tuple[str, dict]]:
    result = answer_directly_detailed(
        question,
        history=history,
        reference_history=reference_history,
        memory_context=memory_context,
        response_constraints=response_constraints,
    )
    yield "sources", {"sources": []}
    yield "trace", result.trace
    yield "delta", {"text": result.answer}
    yield "done", {}


def split_summary_document(document: Document) -> list[Document]:
    return split_documents(
        [Document(page_content=document.page_content, metadata={"source": document.metadata.get("source", "unknown")})],
        chunk_size=SUMMARY_CHUNK_SIZE,
        chunk_overlap=SUMMARY_CHUNK_OVERLAP,
    )


def summarize_loaded_document_detailed(
    document: Document,
    question: str,
    *,
    history: list[dict[str, str]] | None = None,
    child_results: list[tuple[Document, float]] | None = None,
    reference_history: list[dict[str, str]] | None = None,
    memory_context: str | None = None,
    response_constraints: dict[str, object] | None = None,
) -> AnswerRunResult:
    from app.agent_tools import log_diagnostic_event

    started_at = perf_counter()
    reference_history = reference_history if reference_history is not None else build_reference_history(question, history)
    source = document.metadata.get("source", "unknown")
    content = document.page_content.strip()
    if not content:
        raise ValueError("The target document is empty.")

    resolved_memory_context = memory_context if memory_context is not None else build_memory_context(question, history=reference_history, sources=[source])
    resolved_response_constraints = response_constraints if response_constraints is not None else build_response_constraints()
    context_plan = build_summary_context_plan(
        question,
        document,
        history=reference_history,
        child_results=child_results,
        memory_context=resolved_memory_context,
    )
    client = get_chat_client()
    response = client.chat.completions.create(
        model=get_chat_model(),
        temperature=0.2,
        messages=build_summary_messages(
            question,
            source,
            context_plan.context or content[:LONG_SUMMARY_DIRECT_THRESHOLD],
            response_constraints=resolved_response_constraints,
        ),
    )
    answer = response.choices[0].message.content or EMPTY_ANSWER_MESSAGE
    result = AnswerRunResult(answer=answer.strip(), sources=[source], trace=context_plan.to_dict())
    log_diagnostic_event(
        "finalize_answer_complete",
        started_at=started_at,
        question=question,
        mode="local_summary",
        source_count=1,
        selected_source=source,
        memory_context_used=bool(resolved_memory_context),
    )
    return result


def summarize_loaded_document(document: Document, question: str) -> tuple[str, list[str]]:
    result = summarize_loaded_document_detailed(document, question)
    return result.answer, result.sources


def stream_summarize_loaded_document(document: Document, question: str) -> Iterator[tuple[str, dict]]:
    source = document.metadata.get("source", "unknown")
    content = document.page_content.strip()
    if not content:
        raise ValueError("The target document is empty.")

    context_plan = build_summary_context_plan(question, document)
    response_constraints = build_response_constraints()
    yield "sources", {"sources": [source]}
    yield "progress", {"stage": "summary_start", "source": source}
    yield "trace", context_plan.to_dict()
    if "L0" in context_plan.layers_used:
        yield "progress", {"stage": "summary_locate", "source": source}
    yield "progress", {"stage": "summary_overview", "source": source}
    if "L2" in context_plan.layers_used:
        yield "progress", {"stage": "summary_deep_read", "source": source}

    client = get_chat_client()
    messages = build_summary_messages(
        question,
        source,
        context_plan.context or content[:LONG_SUMMARY_DIRECT_THRESHOLD],
        response_constraints=response_constraints,
    )
    yield "progress", {"stage": "summary_generating", "source": source}

    stream = client.chat.completions.create(
        model=get_chat_model(),
        temperature=0.2,
        messages=messages,
        stream=True,
    )

    has_text = False
    for chunk in stream:
        if not chunk.choices:
            continue

        delta = getattr(chunk.choices[0], "delta", None)
        text = extract_stream_text(getattr(delta, "content", None))
        if not text:
            continue

        has_text = True
        yield "delta", {"text": text}

    if not has_text:
        yield "delta", {"text": EMPTY_ANSWER_MESSAGE}

    yield "done", {}


def answer_local_summary_detailed(
    question: str,
    history: list[dict[str, str]] | None = None,
    *,
    require_strong_parent_match: bool = True,
    child_results: list[tuple[Document, float]] | None = None,
    reference_history: list[dict[str, str]] | None = None,
    memory_context: str | None = None,
    response_constraints: dict[str, object] | None = None,
) -> AnswerRunResult:
    reference_history = reference_history if reference_history is not None else build_reference_history(question, history)
    document = choose_summary_document(
        question,
        history=reference_history,
        require_strong_parent_match=require_strong_parent_match,
        child_results=child_results,
    )
    return summarize_loaded_document_detailed(
        document,
        question,
        history=reference_history,
        child_results=child_results,
        memory_context=memory_context,
        response_constraints=response_constraints,
    )


def answer_local_summary(
    question: str,
    history: list[dict[str, str]] | None = None,
    *,
    require_strong_parent_match: bool = True,
    child_results: list[tuple[Document, float]] | None = None,
) -> tuple[str, list[str]]:
    result = answer_local_summary_detailed(
        question,
        history=history,
        reference_history=reference_history,
        require_strong_parent_match=require_strong_parent_match,
        child_results=child_results,
    )
    return result.answer, result.sources


def stream_local_summary(
    question: str,
    history: list[dict[str, str]] | None = None,
    *,
    require_strong_parent_match: bool = True,
    child_results: list[tuple[Document, float]] | None = None,
    reference_history: list[dict[str, str]] | None = None,
    memory_context: str | None = None,
    response_constraints: dict[str, object] | None = None,
) -> Iterator[tuple[str, dict]]:
    from app.agent_tools import log_diagnostic_event

    started_at = perf_counter()
    reference_history = reference_history if reference_history is not None else build_reference_history(question, history)
    document = choose_summary_document(
        question,
        history=reference_history,
        require_strong_parent_match=require_strong_parent_match,
        child_results=child_results,
    )
    source = document.metadata.get("source", "unknown")
    resolved_memory_context = memory_context if memory_context is not None else build_memory_context(question, history=reference_history, sources=[source])
    resolved_response_constraints = response_constraints if response_constraints is not None else build_response_constraints()
    context_plan = build_summary_context_plan(
        question,
        document,
        history=reference_history,
        child_results=child_results,
        memory_context=resolved_memory_context,
    )
    summary_context = context_plan.context or document.page_content[:LONG_SUMMARY_DIRECT_THRESHOLD]
    summary_messages = build_summary_messages(
        question,
        source,
        summary_context,
        response_constraints=resolved_response_constraints,
    )
    log_diagnostic_event(
        "summary_prompt_ready",
        started_at=started_at,
        question=question,
        source=source,
        mode="local_summary_stream",
        history_count=len(reference_history),
        context_chars=len(context_plan.context),
        fallback_content_chars=len(document.page_content[:LONG_SUMMARY_DIRECT_THRESHOLD]),
        prompt_chars=sum(len(str(item.get("content", ""))) for item in summary_messages),
        message_count=len(summary_messages),
        system_chars=len(str(summary_messages[0].get("content", ""))) if summary_messages else 0,
        user_chars=len(str(summary_messages[1].get("content", ""))) if len(summary_messages) > 1 else 0,
        deep_read=bool(context_plan.debug.get("deep_read_enabled")),
        memory_context_chars=len(resolved_memory_context or ""),
        source_hit_count=len(context_plan.source_hits),
        layer_count=len(context_plan.layers_used),
    )
    yield "sources", {"sources": [source]}
    yield "progress", {"stage": "summary_start", "source": source}
    yield "trace", context_plan.to_dict()
    if "L0" in context_plan.layers_used:
        yield "progress", {"stage": "summary_locate", "source": source}
    yield "progress", {"stage": "summary_overview", "source": source}
    if "L2" in context_plan.layers_used:
        yield "progress", {"stage": "summary_deep_read", "source": source}

    client = get_chat_client()
    stream = client.chat.completions.create(
        model=get_chat_model(),
        temperature=0.2,
        messages=summary_messages,
        stream=True,
    )

    has_text = False
    first_token_logged = False
    for chunk in stream:
        if not chunk.choices:
            continue

        delta = getattr(chunk.choices[0], "delta", None)
        text = extract_stream_text(getattr(delta, "content", None))
        if not text:
            continue

        has_text = True
        if not first_token_logged:
            log_diagnostic_event(
                "summary_stream_first_token",
                started_at=started_at,
                question=question,
                source=source,
                mode="local_summary_stream",
                history_count=len(reference_history),
            )
            first_token_logged = True
        yield "delta", {"text": text}

    if not has_text:
        log_diagnostic_event(
            "summary_stream_first_token",
            started_at=started_at,
            question=question,
            source=source,
            mode="local_summary_stream_empty",
            history_count=len(reference_history),
            emitted_text=False,
        )
        yield "delta", {"text": EMPTY_ANSWER_MESSAGE}

    log_diagnostic_event(
        "summary_stream_complete",
        started_at=started_at,
        question=question,
        source=source,
        mode="local_summary_stream",
        history_count=len(reference_history),
        emitted_text=has_text,
    )
    yield "done", {}


def execute_chunk_path_detailed(
    question: str,
    tool_plan: ToolPlan,
    history: list[dict[str, str]] | None = None,
    k: int = 3,
    *,
    reference_history: list[dict[str, str]] | None = None,
    memory_context: str | None = None,
    response_constraints: dict[str, object] | None = None,
) -> AnswerRunResult:
    reference_history = reference_history if reference_history is not None else build_reference_history(question, history)
    bundle = prepare_chunk_answer_material(question, history=reference_history, k=k)
    validation = validate_chunk_results(bundle.vector_results, bundle.keyword_results)
    if should_fallback_to_summary(tool_plan, validation):
        try:
            answer, sources = answer_local_summary(
                question,
                history=reference_history,
                require_strong_parent_match=True,
                child_results=bundle.merged_results,
            )
            return AnswerRunResult(
                answer=answer,
                sources=sources,
                trace={"mode": "summary_fallback", "layers_used": ["L1"], "selected_source": sources[0] if sources else None, "drilldown_path": ["summary_fallback"]},
            )
        except ValueError:
            return AnswerRunResult(
                answer=REFUSAL_MESSAGE,
                sources=bundle.sources,
                trace={"mode": "query", "layers_used": [], "selected_source": None, "drilldown_path": ["fallback_refusal"]},
            )

    if not validation.is_sufficient:
        return AnswerRunResult(
            answer=REFUSAL_MESSAGE,
            sources=bundle.sources,
            trace={"mode": "query", "layers_used": [], "selected_source": None, "drilldown_path": ["insufficient_local_evidence"]},
        )

    resolved_memory_context = memory_context if memory_context is not None else build_memory_context(question, history=reference_history, sources=bundle.sources)
    resolved_response_constraints = response_constraints if response_constraints is not None else build_response_constraints()
    context_plan = build_query_context_plan(question, bundle, history=reference_history, memory_context=resolved_memory_context)
    client = get_chat_client()
    response = client.chat.completions.create(
        model=get_chat_model(),
        temperature=0.2,
        messages=build_chat_messages(
            question,
            context_plan.context,
            history=bundle.history,
            standalone_question=bundle.rewritten_question,
            response_constraints=resolved_response_constraints,
        ),
    )

    answer = response.choices[0].message.content or EMPTY_ANSWER_MESSAGE
    return AnswerRunResult(answer=answer.strip(), sources=bundle.sources, trace=context_plan.to_dict())


def execute_chunk_path(
    question: str,
    tool_plan: ToolPlan,
    history: list[dict[str, str]] | None = None,
    k: int = 3,
) -> tuple[str, list[str]]:
    result = execute_chunk_path_detailed(question, tool_plan, history=history, k=k)
    return result.answer, result.sources


def execute_chunk_stream_path(
    question: str,
    tool_plan: ToolPlan,
    history: list[dict[str, str]] | None = None,
    k: int = 3,
    *,
    reference_history: list[dict[str, str]] | None = None,
    memory_context: str | None = None,
    response_constraints: dict[str, object] | None = None,
) -> Iterator[tuple[str, dict]]:
    reference_history = reference_history if reference_history is not None else build_reference_history(question, history)
    bundle = prepare_chunk_answer_material(question, history=reference_history, k=k)
    validation = validate_chunk_results(bundle.vector_results, bundle.keyword_results)
    if should_fallback_to_summary(tool_plan, validation):
        try:
            yield from stream_local_summary(
                question,
                history=reference_history,
                require_strong_parent_match=True,
                child_results=bundle.merged_results,
                reference_history=reference_history,
            )
            return
        except ValueError:
            yield "sources", {"sources": bundle.sources}
            yield "delta", {"text": REFUSAL_MESSAGE}
            yield "done", {}
            return

    yield "sources", {"sources": bundle.sources}

    if not validation.is_sufficient:
        yield "trace", {"mode": "query", "layers_used": [], "selected_source": None, "drilldown_path": ["insufficient_local_evidence"]}
        yield "delta", {"text": REFUSAL_MESSAGE}
        yield "done", {}
        return

    resolved_memory_context = memory_context if memory_context is not None else build_memory_context(question, history=reference_history, sources=bundle.sources)
    resolved_response_constraints = response_constraints if response_constraints is not None else build_response_constraints()
    context_plan = build_query_context_plan(question, bundle, history=reference_history, memory_context=resolved_memory_context)
    yield "trace", context_plan.to_dict()
    client = get_chat_client()
    stream = client.chat.completions.create(
        model=get_chat_model(),
        temperature=0.2,
        messages=build_chat_messages(
            question,
            context_plan.context,
            history=bundle.history,
            standalone_question=bundle.rewritten_question,
            response_constraints=resolved_response_constraints,
        ),
        stream=True,
    )

    has_text = False
    for chunk in stream:
        if not chunk.choices:
            continue

        delta = getattr(chunk.choices[0], "delta", None)
        text = extract_stream_text(getattr(delta, "content", None))
        if not text:
            continue

        has_text = True
        yield "delta", {"text": text}

    if not has_text:
        yield "delta", {"text": EMPTY_ANSWER_MESSAGE}

    yield "done", {}


def answer_web_search(
    question: str,
    tool_plan: ToolPlan,
    history: list[dict[str, str]] | None = None,
    *,
    response_constraints: dict[str, object] | None = None,
) -> tuple[str, list[str]]:
    if not is_web_search_enabled():
        return WEB_SEARCH_DISABLED_MESSAGE, []

    try:
        answer, sources, _ = _run_direct_web_search_quality_pass(
            question,
            tool_plan,
            history=history,
            response_constraints=response_constraints,
        )
    except (ValueError, AuthenticationError, RateLimitError, BadRequestError, APIConnectionError) as error:
        return build_web_search_failure_message(str(error)), []
    return answer, sources


def stream_web_search(
    question: str,
    tool_plan: ToolPlan,
    history: list[dict[str, str]] | None = None,
    *,
    response_constraints: dict[str, object] | None = None,
) -> Iterator[tuple[str, dict]]:
    if not is_web_search_enabled():
        yield "progress", {"stage": "web_search_disabled"}
        yield "sources", {"sources": []}
        yield "delta", {"text": WEB_SEARCH_DISABLED_MESSAGE}
        yield "done", {}
        return

    yield "progress", {"stage": "web_search_start"}

    try:
        answer, final_sources, debug = _run_direct_web_search_quality_pass(
            question,
            tool_plan,
            history=history,
            response_constraints=response_constraints,
        )
    except (ValueError, AuthenticationError, RateLimitError, BadRequestError, APIConnectionError) as error:
        yield "progress", {"stage": "web_search_failed", "detail": str(error)}
        yield "sources", {"sources": []}
        yield "delta", {"text": build_web_search_failure_message(str(error))}
        yield "done", {}
        return

    yield "trace", build_web_search_trace(question, tool_plan, final_sources, debug=debug)
    if debug:
        yield "progress", {"stage": "web_search_quality", **debug}
        if debug.get("failure_category") == "provider_failure":
            failure_detail = debug.get("web_provider_error") or debug.get("final_failure_reason") or answer
            yield "progress", {"stage": "web_search_failed", "detail": failure_detail, "failure_category": "provider_failure"}

    yield "sources", {"sources": final_sources}
    yield "delta", {"text": answer or EMPTY_ANSWER_MESSAGE}
    yield "done", {}


# Primary non-stream answer entry for the whole application.
def answer_question_detailed(question: str, history: list[dict[str, str]] | None = None, k: int = 3) -> AnswerRunResult:
    reference_history = build_reference_history(question, history)
    _log_pre_router_diagnostic(question, history=reference_history)
    from app.agent_graph import run_agent_graph_detailed

    return run_agent_graph_detailed(
        question,
        history=reference_history,
        k=k,
    )


def answer_question(question: str, history: list[dict[str, str]] | None = None, k: int = 3) -> tuple[str, list[str]]:
    result = answer_question_detailed(question, history=history, k=k)
    return result.answer, result.sources


# Primary streaming answer entry for the whole application.
def stream_answer_question(
    question: str,
    history: list[dict[str, str]] | None = None,
    k: int = 3,
    allow_web_search: bool = True,
    conversation_id: str | None = None,
) -> Iterator[tuple[str, dict]]:
    reference_history = build_reference_history(question, history)
    _log_pre_router_diagnostic(question, history=reference_history)
    from app.agent_graph import run_agent_graph_stream

    yield from run_agent_graph_stream(
        question,
        history=reference_history,
        k=k,
        allow_web_search=allow_web_search,
        conversation_id=conversation_id,
    )
