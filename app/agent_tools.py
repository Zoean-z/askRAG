from __future__ import annotations

import json
import logging
import re
from collections.abc import Iterator
from functools import lru_cache
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter

from app.context_layers import LayeredContextPlan, build_query_context_plan
from app.pipeline import (
    AnswerRunResult,
    WEB_SEARCH_DISABLED_MESSAGE,
    _run_direct_web_search_quality_pass,
    answer_directly_detailed,
    answer_local_summary_detailed,
    answer_web_search,
    build_web_search_disabled_trace,
    build_web_search_failure_message,
    build_web_search_trace,
    is_web_search_enabled,
    stream_direct_answer,
    stream_local_summary,
    stream_web_search,
)
from app.rag import apply_response_constraints_to_system_prompt, extract_stream_text, get_chat_client, get_chat_model
from app.retrievers.chunk_retriever import (
    ChunkRetrievalBundle,
    build_rerank_diagnostics,
    expand_results_with_neighbors,
    filter_results_to_source,
    get_sources,
    keyword_search_documents,
    merge_retrieval_results,
    rerank_retrieval_results,
    resolve_target_source_hint,
    retrieve_vector_documents,
)
from app.session_memory import build_memory_context, build_reference_history, record_completed_turn
from app.tool_router import ToolPlan, extract_target_source_hint, is_web_search_request
from app.validators import RetrievalValidation, validate_chunk_results
from app.workflow import WorkflowState

DIAGNOSTIC_LOGGER = logging.getLogger("askrag.diagnostic")
SOURCE_LABEL_PATTERN = re.compile(r"^(?P<title>.+?)\s*\((?P<url>https?://[^)]+)\)\s*$")


def log_diagnostic_event(stage: str, *, started_at: float | None = None, **payload: object) -> None:
    event = {"stage": stage, **payload}
    if started_at is not None:
        event["elapsed_ms"] = round((perf_counter() - started_at) * 1000, 1)
    DIAGNOSTIC_LOGGER.info("DIAG %s", json.dumps(event, ensure_ascii=False, default=str))


def build_source_preview(
    sources: list[str] | None,
    *,
    answer: str | None = None,
    limit: int = 3,
) -> list[dict[str, str]]:
    preview: list[dict[str, str]] = []
    if not sources:
        return preview

    summary = ""
    if answer:
        summary = " ".join(answer.strip().split())[:160]

    for source in sources[:limit]:
        label = str(source).strip()
        if not label:
            continue
        match = SOURCE_LABEL_PATTERN.match(label)
        title = match.group("title").strip() if match else label
        url = match.group("url").strip() if match else ""
        item = {"title": title, "url": url, "label": label}
        if summary:
            item["summary"] = summary
        preview.append(item)
    return preview

SUMMARY_WEB_SUPPLEMENT_SYSTEM_PROMPT = (
    "You are an evidence-grounded assistant. "
    "First rely on the provided local document summary, then incorporate the supplemental web findings. "
    "Keep the answer concise and directly answer the user's request. "
    "Do not paste raw evidence verbatim. "
    "If the web findings are weak or empty, fall back to the local summary instead of inventing new claims."
)


@dataclass(slots=True)
class KBSearchToolResult:
    bundle: ChunkRetrievalBundle
    validation: RetrievalValidation
    context_plan: LayeredContextPlan | None = None


@dataclass(slots=True)
class OpenVikingContextToolResult:
    context: str


@dataclass(slots=True)
class LongTermContextToolResult:
    reference_history: list[dict[str, str]]
    memory_context: str


@dataclass(slots=True)
class LocalAssessmentToolResult:
    needs_web: bool
    decision_reason: str


@dataclass(slots=True)
class PersistTurnMemoryToolResult:
    stored_entries: list[dict]
    memory_notices: list[dict]


@dataclass(slots=True)
class SummaryStrategyToolResult:
    strategy: str


@dataclass(slots=True)
class LocalDocProbeResult:
    has_hits: bool
    top_sources: list[str]
    validation: RetrievalValidation


@lru_cache(maxsize=1)
def _cached_vector_store():
    from app.rag import get_vector_store

    return get_vector_store()


def search_kb_chroma(
    question: str,
    history: list[dict[str, str]] | None = None,
    *,
    k: int = 3,
    include_context_plan: bool = False,
    reference_history: list[dict[str, str]] | None = None,
) -> KBSearchToolResult:
    started_at = perf_counter()
    reference_history = reference_history if reference_history is not None else build_reference_history(question, history)
    target_source_hint = extract_target_source_hint(question)
    resolved_target_source = resolve_target_source_hint(target_source_hint)
    rewritten_started = perf_counter()
    rewritten_question = question.strip()
    rewrite_applied = False
    if reference_history:
        from app.rag import rewrite_question

        rewritten_question = rewrite_question(question, reference_history)
        rewrite_applied = rewritten_question != question.strip()
    rewrite_elapsed = round((perf_counter() - rewritten_started) * 1000, 1)

    vector_started = perf_counter()
    vector_store = _cached_vector_store()
    vector_fetch_limit = max(k * 4, 12) if resolved_target_source else k
    vector_results = vector_store.similarity_search_with_score(rewritten_question, k=vector_fetch_limit)
    vector_results = filter_results_to_source(vector_results, resolved_target_source, limit=k)
    vector_elapsed = round((perf_counter() - vector_started) * 1000, 1)

    keyword_started = perf_counter()
    keyword_results = keyword_search_documents(
        rewritten_question,
        limit=max(k, 5),
        target_source_hint=resolved_target_source or target_source_hint,
    )
    keyword_elapsed = round((perf_counter() - keyword_started) * 1000, 1)

    merge_started = perf_counter()
    merged_results = merge_retrieval_results(vector_results, keyword_results, limit=max(k, 5))
    merge_elapsed = round((perf_counter() - merge_started) * 1000, 1)

    rerank_started = perf_counter()
    reranked_results = rerank_retrieval_results(
        rewritten_question,
        merged_results,
        vector_results=vector_results,
        keyword_results=keyword_results,
        limit=max(k, 5),
    )
    rerank_elapsed = round((perf_counter() - rerank_started) * 1000, 1)

    material_started = perf_counter()
    results = expand_results_with_neighbors(
        reranked_results,
        window=1,
        limit=max(k + 2, 7),
    )
    material_elapsed = round((perf_counter() - material_started) * 1000, 1)

    finalize_started = perf_counter()
    validation = validate_chunk_results(vector_results, keyword_results)
    source_list: list[str] = []
    seen_sources: set[str] = set()
    for doc, _ in results:
        source = str(doc.metadata.get("source", "")).strip()
        if not source or source in seen_sources:
            continue
        seen_sources.add(source)
        source_list.append(source)
    bundle = ChunkRetrievalBundle(
        rewritten_question=rewritten_question,
        vector_results=vector_results,
        keyword_results=keyword_results,
        merged_results=merged_results,
        reranked_results=reranked_results,
        results=results,
        sources=get_sources(results),
        history=reference_history,
        rerank_diagnostics=build_rerank_diagnostics(merged_results, reranked_results),
        retrieval_debug={
            "backend": "chroma",
            "target_source_hint": target_source_hint,
            "resolved_target_source": resolved_target_source,
            "rewrite_applied": rewrite_applied,
            "reference_history_count": len(reference_history),
            "timings_ms": {
                "rewrite": rewrite_elapsed,
                "vector": vector_elapsed,
                "keyword": keyword_elapsed,
                "merge": merge_elapsed,
                "rerank": rerank_elapsed,
                "material": material_elapsed,
            },
            "top_scores": [round(score, 4) for _, score in results[:3]],
            "chunk_count": len(results),
            "source_count": len(source_list),
        },
    )
    finalize_elapsed = round((perf_counter() - finalize_started) * 1000, 1)
    log_diagnostic_event(
        "retrieval_local_search_vector",
        raw_query=question,
        rewritten_query=rewritten_question,
        rewrite_applied=rewrite_applied,
        history_count=len(reference_history),
        target_source_hint=target_source_hint,
        resolved_target_source=resolved_target_source,
        vector_result_count=len(vector_results),
        top_scores=[round(score, 4) for _, score in vector_results[:3]],
        elapsed_ms=vector_elapsed,
    )
    log_diagnostic_event(
        "retrieval_local_search_keyword",
        raw_query=question,
        rewritten_query=rewritten_question,
        rewrite_applied=rewrite_applied,
        keyword_result_count=len(keyword_results),
        top_scores=[round(score, 4) for _, score in keyword_results[:3]],
        elapsed_ms=keyword_elapsed,
    )
    log_diagnostic_event(
        "retrieval_local_search_merge",
        raw_query=question,
        merged_result_count=len(merged_results),
        top_scores=[round(score, 4) for _, score in merged_results[:3]],
        elapsed_ms=merge_elapsed,
    )
    log_diagnostic_event(
        "retrieval_local_search_rerank",
        raw_query=question,
        reranked_result_count=len(reranked_results),
        top_scores=[round(score, 4) for _, score in reranked_results[:3]],
        elapsed_ms=rerank_elapsed,
    )
    log_diagnostic_event(
        "retrieval_local_search_material",
        raw_query=question,
        material_result_count=len(results),
        top_scores=[round(score, 4) for _, score in results[:3]],
        elapsed_ms=material_elapsed,
    )
    log_diagnostic_event(
        "retrieval_local_search_finalize",
        raw_query=question,
        has_hits=bool(source_list),
        source_count=len(source_list),
        source_preview=build_source_preview(source_list, limit=3),
        validation_reason=validation.reason,
        validation_sufficient=validation.is_sufficient,
        elapsed_ms=finalize_elapsed,
    )
    log_diagnostic_event(
        "retrieval_local_search_detail",
        started_at=started_at,
        raw_query=question,
        rewritten_query=rewritten_question,
        rewrite_applied=rewrite_applied,
        reference_history_count=len(reference_history),
        target_source_hint=target_source_hint,
        resolved_target_source=resolved_target_source,
        vector_result_count=len(vector_results),
        keyword_result_count=len(keyword_results),
        merged_result_count=len(merged_results),
        reranked_result_count=len(reranked_results),
        result_count=len(results),
        source_count=len(source_list),
        has_hits=bool(source_list),
        validation_reason=validation.reason,
        validation_sufficient=validation.is_sufficient,
        source_preview=build_source_preview(source_list, limit=3),
        top_scores=[round(score, 4) for _, score in results[:3]],
        step_timings_ms={
            "rewrite": rewrite_elapsed,
            "vector": vector_elapsed,
            "keyword": keyword_elapsed,
            "merge": merge_elapsed,
            "rerank": rerank_elapsed,
            "material": material_elapsed,
            "finalize": finalize_elapsed,
        },
    )

    context_plan: LayeredContextPlan | None = None
    if include_context_plan:
        memory_context = build_memory_context(
            question,
            history=reference_history,
            sources=bundle.sources,
        )
        context_plan = build_query_context_plan(
            question,
            bundle,
            history=reference_history,
            memory_context=memory_context,
        )

    return KBSearchToolResult(bundle=bundle, validation=validation, context_plan=context_plan)


def probe_local_docs(
    question: str,
    history: list[dict[str, str]] | None = None,
    *,
    k: int = 1,
    reference_history: list[dict[str, str]] | None = None,
) -> LocalDocProbeResult:
    started_at = perf_counter()
    probe_k = max(1, min(int(k), 2))
    history_count = len(reference_history or history or [])
    target_source_hint = extract_target_source_hint(question)
    resolved_target_source = resolve_target_source_hint(target_source_hint)

    vector_started = perf_counter()
    vector_results = retrieve_vector_documents(question, k=max(probe_k, 3))
    if resolved_target_source is not None:
        vector_results = filter_results_to_source(vector_results, resolved_target_source, limit=probe_k)
    vector_elapsed = round((perf_counter() - vector_started) * 1000, 1)
    log_diagnostic_event(
        "local_doc_probe_vector",
        raw_query=question,
        probe_k=probe_k,
        history_count=history_count,
        target_source_hint=target_source_hint,
        resolved_target_source=resolved_target_source,
        vector_result_count=len(vector_results),
        top_sources=[str(doc.metadata.get("source", "")).strip() for doc, _ in vector_results[:3] if str(doc.metadata.get("source", "")).strip()],
        elapsed_ms=vector_elapsed,
    )

    keyword_started = perf_counter()
    keyword_results = keyword_search_documents(
        question,
        limit=probe_k,
        target_source_hint=resolved_target_source or target_source_hint,
    )
    keyword_elapsed = round((perf_counter() - keyword_started) * 1000, 1)
    log_diagnostic_event(
        "local_doc_probe_keyword",
        raw_query=question,
        probe_k=probe_k,
        history_count=history_count,
        target_source_hint=target_source_hint,
        resolved_target_source=resolved_target_source,
        keyword_result_count=len(keyword_results),
        top_sources=[str(doc.metadata.get("source", "")).strip() for doc, _ in keyword_results[:3] if str(doc.metadata.get("source", "")).strip()],
        elapsed_ms=keyword_elapsed,
    )

    merge_started = perf_counter()
    merged_results = merge_retrieval_results(vector_results, keyword_results, limit=probe_k)
    merge_elapsed = round((perf_counter() - merge_started) * 1000, 1)
    log_diagnostic_event(
        "local_doc_probe_merge",
        raw_query=question,
        probe_k=probe_k,
        merged_result_count=len(merged_results),
        elapsed_ms=merge_elapsed,
    )

    rerank_started = perf_counter()
    reranked_results = rerank_retrieval_results(
        question,
        merged_results,
        vector_results=vector_results,
        keyword_results=keyword_results,
        limit=probe_k,
    )
    rerank_elapsed = round((perf_counter() - rerank_started) * 1000, 1)
    log_diagnostic_event(
        "local_doc_probe_rerank",
        raw_query=question,
        probe_k=probe_k,
        reranked_result_count=len(reranked_results),
        elapsed_ms=rerank_elapsed,
    )

    final_started = perf_counter()
    results = reranked_results
    validation = validate_chunk_results(vector_results, keyword_results)
    source_list: list[str] = []
    seen_sources: set[str] = set()
    for doc, _ in results:
        source = str(doc.metadata.get("source", "")).strip()
        if not source or source in seen_sources:
            continue
        seen_sources.add(source)
        source_list.append(source)
    source_preview = build_source_preview(source_list, limit=3)
    final_elapsed = round((perf_counter() - final_started) * 1000, 1)
    log_diagnostic_event(
        "local_doc_probe_finalize",
        raw_query=question,
        probe_k=probe_k,
        has_hits=bool(source_list),
        source_count=len(source_list),
        source_preview=source_preview,
        validation_reason=validation.reason,
        validation_sufficient=validation.is_sufficient,
        elapsed_ms=final_elapsed,
    )
    log_diagnostic_event(
        "local_doc_probe_detail",
        started_at=started_at,
        question=question,
        rewritten_query=question,
        rewrite_applied=False,
        probe_mode="lightweight",
        history_count=history_count,
        target_source_hint=target_source_hint,
        resolved_target_source=resolved_target_source,
        vector_result_count=len(vector_results),
        keyword_result_count=len(keyword_results),
        merged_result_count=len(merged_results),
        result_count=len(results),
        source_count=len(source_list),
        has_hits=bool(source_list),
        validation_reason=validation.reason,
        validation_sufficient=validation.is_sufficient,
        source_preview=source_preview,
        step_timings_ms={
            "vector": vector_elapsed,
            "keyword": keyword_elapsed,
            "merge": merge_elapsed,
            "rerank": rerank_elapsed,
            "finalize": final_elapsed,
        },
    )
    return LocalDocProbeResult(
        has_hits=bool(source_list),
        top_sources=list(source_list[:2]),
        validation=validation,
    )


def search_openviking_context(
    question: str,
    history: list[dict[str, str]] | None = None,
    *,
    sources: list[str] | None = None,
) -> OpenVikingContextToolResult:
    reference_history = build_reference_history(question, history)
    context = build_memory_context(question, history=reference_history, sources=sources)
    return OpenVikingContextToolResult(context=context)


def load_long_term_context(
    question: str,
    history: list[dict[str, str]] | None = None,
    *,
    sources: list[str] | None = None,
) -> LongTermContextToolResult:
    reference_history = build_reference_history(question, history)
    context = search_openviking_context(question, history=reference_history, sources=sources).context
    return LongTermContextToolResult(reference_history=reference_history, memory_context=context)


def load_response_constraints() -> dict[str, object]:
    from app.session_memory import build_response_constraints

    return build_response_constraints()


def build_memory_notices(
    entries: list[dict] | None = None,
    trace: dict | None = None,
) -> list[dict]:
    notices: list[dict] = []
    if trace and bool(((trace.get("debug") or {}).get("memory_context_used"))):
        notices.append(
            {
                "kind": "used",
                "summary": "Used assistant memory such as saved preferences or task context for this answer.",
            }
        )

    for entry in entries or []:
        memory_type = str(entry.get("memory_type") or "")
        if memory_type not in {"pinned_preference", "stable_profile_fact", "recent_task_state", "approved_long_term_fact"}:
            continue
        summary = str(entry.get("summary") or "").strip()
        if not summary:
            continue
        status = str(entry.get("status") or "")
        notices.append(
            {
                "kind": "remembered" if status == "approved" else "candidate",
                "summary": summary,
                "memory_type": memory_type,
                "status": status,
            }
        )
    return notices[:3]


def persist_turn_memory_result(
    *,
    question: str,
    answer: str,
    sources: list[str] | None = None,
    history: list[dict[str, str]] | None = None,
    trace: dict | None = None,
) -> PersistTurnMemoryToolResult:
    try:
        stored_entries = record_completed_turn(
            question=question,
            answer=answer,
            sources=sources,
            history=history,
        )
    except Exception:
        stored_entries = []
    return PersistTurnMemoryToolResult(
        stored_entries=stored_entries,
        memory_notices=build_memory_notices(stored_entries, trace),
    )


def decide_summary_strategy(
    question: str,
    history: list[dict[str, str]] | None = None,
) -> SummaryStrategyToolResult:
    if is_web_search_request(question, history=history):
        return SummaryStrategyToolResult(strategy="summary_plus_web")
    return SummaryStrategyToolResult(strategy="local_only")


def read_summary(
    question: str,
    history: list[dict[str, str]] | None = None,
    *,
    require_strong_parent_match: bool = True,
    child_results: list[tuple[object, float]] | None = None,
    reference_history: list[dict[str, str]] | None = None,
    memory_context: str | None = None,
    response_constraints: dict[str, object] | None = None,
) -> AnswerRunResult:
    kwargs: dict[str, object] = {}
    if reference_history is not None:
        kwargs["reference_history"] = reference_history
    if memory_context is not None:
        kwargs["memory_context"] = memory_context
    if response_constraints is not None:
        kwargs["response_constraints"] = response_constraints
    return answer_local_summary_detailed(
        question,
        history=history,
        require_strong_parent_match=require_strong_parent_match,
        child_results=child_results,
        **kwargs,
    )


def answer_directly_tool(
    question: str,
    history: list[dict[str, str]] | None = None,
    *,
    reference_history: list[dict[str, str]] | None = None,
    memory_context: str | None = None,
    response_constraints: dict[str, object] | None = None,
) -> AnswerRunResult:
    kwargs: dict[str, object] = {}
    if reference_history is not None:
        kwargs["reference_history"] = reference_history
    if memory_context is not None:
        kwargs["memory_context"] = memory_context
    if response_constraints is not None:
        kwargs["response_constraints"] = response_constraints
    return answer_directly_detailed(
        question,
        history=history,
        **kwargs,
    )


def stream_direct_answer_tool(
    question: str,
    history: list[dict[str, str]] | None = None,
    *,
    reference_history: list[dict[str, str]] | None = None,
    memory_context: str | None = None,
    response_constraints: dict[str, object] | None = None,
) -> Iterator[tuple[str, dict]]:
    kwargs: dict[str, object] = {}
    if reference_history is not None:
        kwargs["reference_history"] = reference_history
    if memory_context is not None:
        kwargs["memory_context"] = memory_context
    if response_constraints is not None:
        kwargs["response_constraints"] = response_constraints
    yield from stream_direct_answer(
        question,
        history=history,
        **kwargs,
    )


def stream_read_summary(
    question: str,
    history: list[dict[str, str]] | None = None,
    *,
    require_strong_parent_match: bool = True,
    child_results: list[tuple[object, float]] | None = None,
    reference_history: list[dict[str, str]] | None = None,
    memory_context: str | None = None,
    response_constraints: dict[str, object] | None = None,
) -> Iterator[tuple[str, dict]]:
    kwargs: dict[str, object] = {}
    if reference_history is not None:
        kwargs["reference_history"] = reference_history
    if memory_context is not None:
        kwargs["memory_context"] = memory_context
    if response_constraints is not None:
        kwargs["response_constraints"] = response_constraints
    yield from stream_local_summary(
        question,
        history=history,
        require_strong_parent_match=require_strong_parent_match,
        child_results=child_results,
        **kwargs,
    )


def _build_summary_web_supplement_query(question: str, summary_result: AnswerRunResult) -> str:
    source = summary_result.sources[0] if summary_result.sources else ""
    source_label = Path(source).stem.strip() if source else ""
    base = source_label or question.strip()
    if any(ord(char) > 127 for char in base):
        return f"{base} 相关内容 最新进展 官方信息"
    return f"{base} related information latest official updates"


def run_summary_web_search_result(
    question: str,
    summary_result: AnswerRunResult,
    *,
    response_constraints: dict[str, object] | None = None,
) -> AnswerRunResult:
    query = _build_summary_web_supplement_query(question, summary_result)
    web_plan = ToolPlan(
        intent="web_search",
        primary_tool="web_search",
        fallback_tool=None,
        confidence=1.0,
        reason="summary_web_supplement",
        use_history=False,
        needs_freshness=True,
        needs_external_knowledge=True,
        web_search_mode="general",
    )
    return run_direct_web_search_result(query, web_plan, response_constraints=response_constraints)


def _build_summary_web_compose_messages(
    question: str,
    summary_result: AnswerRunResult,
    web_result: AnswerRunResult,
    *,
    memory_context: str | None = None,
    response_constraints: dict[str, object] | None = None,
) -> list[dict[str, str]]:
    parts = [f"User request:\n{question.strip()}"]
    if memory_context:
        parts.append(f"Memory/context:\n{memory_context.strip()}")
    parts.append(f"Local summary:\n{summary_result.answer.strip()}")
    if summary_result.sources:
        parts.append("Local summary sources:\n" + "\n".join(summary_result.sources))
    if web_result.answer.strip():
        parts.append(f"Web supplement:\n{web_result.answer.strip()}")
    if web_result.sources:
        parts.append("Web sources:\n" + "\n".join(web_result.sources))
    return [
        {
            "role": "system",
            "content": apply_response_constraints_to_system_prompt(
                SUMMARY_WEB_SUPPLEMENT_SYSTEM_PROMPT,
                response_constraints,
            ),
        },
        {"role": "user", "content": "\n\n".join(parts)},
    ]


def compose_summary_with_web_result(
    question: str,
    summary_result: AnswerRunResult,
    web_result: AnswerRunResult,
    *,
    memory_context: str | None = None,
    response_constraints: dict[str, object] | None = None,
) -> AnswerRunResult:
    client = get_chat_client()
    response = client.chat.completions.create(
        model=get_chat_model(),
        temperature=0.2,
        messages=_build_summary_web_compose_messages(
            question,
            summary_result,
            web_result,
            memory_context=memory_context,
            response_constraints=response_constraints,
        ),
    )
    answer = response.choices[0].message.content or summary_result.answer
    combined_sources = list(dict.fromkeys([*summary_result.sources, *web_result.sources]))
    trace = {
        "mode": "summary_with_web",
        "layers_used": ["summary", "web_search"] + (["memory"] if memory_context else []),
        "selected_source": summary_result.sources[0] if summary_result.sources else None,
        "candidate_sources": combined_sources,
        "drilldown_path": ["summary_strategy", "local_summary", "web_search", "compose"],
        "debug": {
            "summary_sources": list(summary_result.sources),
            "web_sources": list(web_result.sources),
            "memory_context_used": bool(memory_context),
        },
    }
    return AnswerRunResult(answer=answer.strip(), sources=combined_sources, trace=trace)


def stream_compose_summary_with_web_result(
    question: str,
    summary_result: AnswerRunResult,
    web_result: AnswerRunResult,
    *,
    memory_context: str | None = None,
    response_constraints: dict[str, object] | None = None,
) -> Iterator[tuple[str, dict]]:
    combined_sources = list(dict.fromkeys([*summary_result.sources, *web_result.sources]))
    yield "sources", {"sources": combined_sources}
    yield "trace", {
        "mode": "summary_with_web",
        "layers_used": ["summary", "web_search"] + (["memory"] if memory_context else []),
        "selected_source": summary_result.sources[0] if summary_result.sources else None,
        "candidate_sources": combined_sources,
        "drilldown_path": ["summary_strategy", "local_summary", "web_search", "compose"],
        "debug": {
            "summary_sources": list(summary_result.sources),
            "web_sources": list(web_result.sources),
            "memory_context_used": bool(memory_context),
        },
    }
    yield "progress", {"stage": "summary_web_compose"}
    client = get_chat_client()
    stream = client.chat.completions.create(
        model=get_chat_model(),
        temperature=0.2,
        messages=_build_summary_web_compose_messages(
            question,
            summary_result,
            web_result,
            memory_context=memory_context,
            response_constraints=response_constraints,
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
        yield "delta", {"text": summary_result.answer}
    yield "done", {}


def web_search(
    question: str,
    tool_plan: ToolPlan,
    history: list[dict[str, str]] | None = None,
    *,
    response_constraints: dict[str, object] | None = None,
) -> tuple[str, list[str]]:
    kwargs: dict[str, object] = {}
    if response_constraints is not None:
        kwargs["response_constraints"] = response_constraints
    return answer_web_search(
        question,
        tool_plan,
        history=history,
        **kwargs,
    )


def run_direct_web_search_result(
    question: str,
    tool_plan: ToolPlan,
    *,
    history: list[dict[str, str]] | None = None,
    response_constraints: dict[str, object] | None = None,
) -> AnswerRunResult:
    from openai import APIConnectionError, AuthenticationError, BadRequestError, RateLimitError

    if not is_web_search_enabled():
        return AnswerRunResult(
            answer=WEB_SEARCH_DISABLED_MESSAGE,
            sources=[],
            trace=build_web_search_disabled_trace(question, tool_plan),
        )

    try:
        reference_history = build_reference_history(question, history)
        kwargs: dict[str, object] = {}
        if response_constraints is not None:
            kwargs["response_constraints"] = response_constraints
        answer, sources, debug = _run_direct_web_search_quality_pass(
            question,
            tool_plan,
            history=reference_history,
            **kwargs,
        )
    except (ValueError, AuthenticationError, RateLimitError, BadRequestError, APIConnectionError) as error:
        answer = build_web_search_failure_message(str(error))
        sources = []
        debug = {"web_search_failed": True, "detail": str(error)}

    return AnswerRunResult(
        answer=answer,
        sources=sources,
        trace=build_web_search_trace(question, tool_plan, sources, debug=debug),
    )


def stream_web_search_tool(
    question: str,
    tool_plan: ToolPlan,
    history: list[dict[str, str]] | None = None,
    *,
    response_constraints: dict[str, object] | None = None,
) -> Iterator[tuple[str, dict]]:
    kwargs: dict[str, object] = {}
    if response_constraints is not None:
        kwargs["response_constraints"] = response_constraints
    yield from stream_web_search(
        question,
        tool_plan,
        history=history,
        **kwargs,
    )


def run_retrieval_web_search_step(state: WorkflowState) -> WorkflowState:
    from app.workflow import _run_web_search_step

    _run_web_search_step(state)
    return state


def run_retrieval_web_extract_step(state: WorkflowState) -> WorkflowState:
    from app.workflow import _run_web_extract_step

    _run_web_extract_step(state)
    return state


def stream_retrieval_finalize_result(state: WorkflowState) -> Iterator[tuple[str, dict]]:
    from app.workflow import stream_finalize_retrieval_answer

    yield from stream_finalize_retrieval_answer(state)


def finalize_retrieval_result(state: WorkflowState):
    from app.workflow import finalize_retrieval_answer

    return finalize_retrieval_answer(state)


def assess_combined_retrieval_evidence(state: WorkflowState) -> WorkflowState:
    from app.workflow import _assess_combined_step

    _assess_combined_step(state)
    return state


def initialize_retrieval_workflow_state(
    question: str,
    tool_plan: ToolPlan,
    history: list[dict[str, str]] | None = None,
    *,
    reference_history: list[dict[str, str]] | None = None,
    allow_web_search: bool = True,
) -> WorkflowState:
    from app.workflow import init_workflow_state

    return init_workflow_state(
        question,
        tool_plan,
        reference_history if reference_history is not None else history,
        allow_web_search=allow_web_search,
    )


def apply_local_kb_search_result(
    state: WorkflowState,
    kb_result: KBSearchToolResult,
) -> WorkflowState:
    from app.workflow import _advance_step, _dedupe_sources, _local_confidence, _refresh_assessment_trace

    _advance_step(state, "local_search")
    if state.status != "running":
        return state

    state.local_attempted = True
    state.local_bundle = kb_result.bundle
    state.local_validation = kb_result.validation
    state.local_retrieval_relevant = bool(getattr(kb_result.validation, "is_relevant", kb_result.validation.is_sufficient))
    state.local_answer_sufficient = False
    state.local_sufficient = False
    state.confidence = _local_confidence(kb_result.validation)
    state.sources = _dedupe_sources(kb_result.bundle.sources, state.web_sources)
    _refresh_assessment_trace(state)
    return state


def assess_local_retrieval_followup(state: WorkflowState) -> LocalAssessmentToolResult:
    from app.workflow import (
        _advance_step,
        _refresh_assessment_trace,
        _local_answer_is_sufficient,
        _requires_relevant_web,
        _should_block_auto_web_fallback,
        _should_keep_file_anchored_query_local,
    )

    _advance_step(state, "assess_local")
    if state.status != "running":
        return LocalAssessmentToolResult(needs_web=bool(state.needs_web), decision_reason=state.decision_reason)

    if _requires_relevant_web(state):
        state.needs_web = True
        state.decision_reason = "external_knowledge_required_after_local"
        _refresh_assessment_trace(state)
        return LocalAssessmentToolResult(needs_web=True, decision_reason=state.decision_reason)

    if _should_keep_file_anchored_query_local(state):
        state.local_retrieval_relevant = True
        state.local_answer_sufficient = True
        state.local_sufficient = True
        state.combined_sufficient = True
        state.confidence = max(state.confidence, 0.78)
        state.needs_web = False
        state.decision_reason = "file_anchored_local_evidence_locked"
        _refresh_assessment_trace(state)
        return LocalAssessmentToolResult(needs_web=False, decision_reason=state.decision_reason)

    state.local_answer_sufficient = _local_answer_is_sufficient(state)
    state.local_sufficient = state.local_answer_sufficient

    if state.local_answer_sufficient:
        state.needs_web = False
        state.combined_sufficient = True
        state.decision_reason = "local_answer_sufficient"
        _refresh_assessment_trace(state)
        return LocalAssessmentToolResult(needs_web=False, decision_reason=state.decision_reason)

    if not getattr(state, "allow_web_search", True):
        state.needs_web = False
        state.combined_sufficient = state.local_answer_sufficient
        state.decision_reason = "web_search_disabled_by_toggle"
        _refresh_assessment_trace(state)
        return LocalAssessmentToolResult(needs_web=False, decision_reason=state.decision_reason)

    if _should_block_auto_web_fallback(state):
        state.needs_web = False
        state.combined_sufficient = False
        state.decision_reason = "guardrail_blocked_auto_web_fallback"
        _refresh_assessment_trace(state)
        return LocalAssessmentToolResult(needs_web=False, decision_reason=state.decision_reason)

    state.needs_web = True
    state.decision_reason = "local_retrieval_relevant_but_answer_insufficient" if state.local_retrieval_relevant else "local_evidence_insufficient"
    _refresh_assessment_trace(state)
    return LocalAssessmentToolResult(needs_web=True, decision_reason=state.decision_reason)


__all__ = [
    "KBSearchToolResult",
    "LocalDocProbeResult",
    "LocalAssessmentToolResult",
    "LongTermContextToolResult",
    "OpenVikingContextToolResult",
    "PersistTurnMemoryToolResult",
    "SummaryStrategyToolResult",
    "answer_directly_tool",
    "assess_combined_retrieval_evidence",
    "assess_local_retrieval_followup",
    "apply_local_kb_search_result",
    "build_source_preview",
    "build_memory_notices",
    "compose_summary_with_web_result",
    "decide_summary_strategy",
    "finalize_retrieval_result",
    "load_long_term_context",
    "load_response_constraints",
    "initialize_retrieval_workflow_state",
    "persist_turn_memory_result",
    "probe_local_docs",
    "read_summary",
    "run_direct_web_search_result",
    "run_retrieval_web_extract_step",
    "run_retrieval_web_search_step",
    "run_summary_web_search_result",
    "search_kb_chroma",
    "search_openviking_context",
    "log_diagnostic_event",
    "stream_direct_answer_tool",
    "stream_compose_summary_with_web_result",
    "stream_retrieval_finalize_result",
    "stream_read_summary",
    "stream_web_search_tool",
    "web_search",
]
