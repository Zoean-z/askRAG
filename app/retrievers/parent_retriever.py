import re
from dataclasses import dataclass

from langchain_core.documents import Document

from app.rag import (
    SUMMARY_FOLLOW_UP_TERMS,
    SUMMARY_INTENT_TERMS,
    find_document_by_recent_sources,
    normalize_history,
    score_document_match,
    score_document_match_in_history,
)
from app.retrievers.chunk_retriever import (
    get_corpus_documents,
    get_corpus_documents_by_source,
    run_hybrid_chunk_search,
)
from app.validators import ParentValidation, validate_parent_candidates


@dataclass(slots=True)
class ParentDocumentCandidate:
    document: Document
    score: float
    hits: int


@dataclass(slots=True)
class SummaryDocumentResolution:
    document: Document
    reason: str
    parent_validation: ParentValidation | None = None


def build_summary_search_query(question: str) -> str:
    query = question.strip()
    if not query:
        return query

    for term in SUMMARY_INTENT_TERMS + SUMMARY_FOLLOW_UP_TERMS:
        query = re.sub(re.escape(term), " ", query, flags=re.IGNORECASE)

    query = re.sub(r"这个文件|这篇文章|这份文档|这个文档|这篇文档", " ", query)
    query = re.sub(r"[\s,，。；;:：!！?？、]+", " ", query)
    query = query.strip()
    return query or question.strip()


def resolve_summary_document_from_context(question: str, history: list[dict[str, str]] | None = None) -> Document | None:
    documents = get_corpus_documents()
    documents_by_source = get_corpus_documents_by_source()
    scored_documents: list[tuple[int, Document]] = []
    for document in documents:
        source = document.metadata.get("source", "")
        score = score_document_match(question, source)
        if score > 0:
            scored_documents.append((score, document))

    if scored_documents:
        scored_documents.sort(key=lambda item: item[0], reverse=True)
        return scored_documents[0][1]

    recent_source_document = find_document_by_recent_sources(history, documents_by_source)
    if recent_source_document is not None:
        return recent_source_document

    return score_document_match_in_history(history, documents)


def rank_parent_documents_from_child_results(
    child_results: list[tuple[Document, float]],
    *,
    limit: int = 3,
) -> list[ParentDocumentCandidate]:
    if not child_results:
        return []

    documents_by_source = get_corpus_documents_by_source()
    aggregated: dict[str, dict[str, float | int]] = {}

    for rank, (chunk, _) in enumerate(child_results):
        source = chunk.metadata.get("source", "")
        if not source:
            continue

        current = aggregated.setdefault(source, {"score": 0.0, "hits": 0})
        current["score"] += max(1.0, float(len(child_results) - rank))
        current["hits"] += 1

    ranked: list[ParentDocumentCandidate] = []
    for source, stats in aggregated.items():
        document = documents_by_source.get(source)
        if document is None:
            continue
        ranked.append(
            ParentDocumentCandidate(
                document=document,
                score=float(stats["score"]),
                hits=int(stats["hits"]),
            )
        )

    ranked.sort(
        key=lambda item: (
            -item.score,
            -item.hits,
            item.document.metadata.get("source", "unknown"),
        )
    )
    return ranked[:limit]


def retrieve_parent_documents(question: str, history: list[dict[str, str]] | None = None, limit: int = 3) -> list[ParentDocumentCandidate]:
    search_query = build_summary_search_query(question)
    _, _, _, child_results = run_hybrid_chunk_search(
        search_query,
        vector_k=max(4, limit * 2),
        keyword_limit=max(6, limit * 3),
        merge_limit=max(6, limit * 3),
        neighbor_window=0,
        final_limit=max(6, limit * 3),
    )
    return rank_parent_documents_from_child_results(child_results, limit=limit)


def resolve_summary_document(
    question: str,
    history: list[dict[str, str]] | None = None,
    *,
    require_strong_parent_match: bool = True,
    parent_candidates: list[ParentDocumentCandidate] | None = None,
    child_results: list[tuple[Document, float]] | None = None,
) -> SummaryDocumentResolution:
    normalized_history = normalize_history(history)
    contextual = resolve_summary_document_from_context(question, history=normalized_history)
    if contextual is not None:
        return SummaryDocumentResolution(document=contextual, reason="contextual_summary_document")

    parents = parent_candidates
    if parents is None and child_results is not None:
        parents = rank_parent_documents_from_child_results(child_results, limit=3)
    if parents is None:
        parents = retrieve_parent_documents(question, history=normalized_history, limit=3)

    parent_validation = validate_parent_candidates(parents)
    if parents and (parent_validation.is_sufficient or not require_strong_parent_match):
        return SummaryDocumentResolution(
            document=parents[0].document,
            reason="parent_document_retrieval",
            parent_validation=parent_validation,
        )

    raise ValueError(
        "Summary request detected, but no document could be resolved from file names, recent sources, or a strong enough parent-document match."
    )


def choose_summary_document(
    question: str,
    history: list[dict[str, str]] | None = None,
    *,
    require_strong_parent_match: bool = True,
    parent_candidates: list[ParentDocumentCandidate] | None = None,
    child_results: list[tuple[Document, float]] | None = None,
) -> Document:
    return resolve_summary_document(
        question,
        history=history,
        require_strong_parent_match=require_strong_parent_match,
        parent_candidates=parent_candidates,
        child_results=child_results,
    ).document
