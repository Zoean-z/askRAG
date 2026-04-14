import re
from dataclasses import dataclass, field
from pathlib import Path

from langchain_core.documents import Document

from app.rag import (
    DOCS_DIR,
    SUPPORTED_EXTENSIONS,
    load_documents,
    retrieve_vector_documents,
    rewrite_question,
    split_documents,
)
from app.retrievers.reranker import rerank_chunk_results
from app.session_memory import build_reference_history
from app.tool_router import extract_target_source_hint

QUESTION_HINT_TERMS = [
    "具体操作",
    "操作步骤",
    "步骤",
    "流程",
    "方法",
    "注意事项",
    "适用范围",
    "前提条件",
]


@dataclass(slots=True)
class ChunkRetrievalBundle:
    rewritten_question: str
    vector_results: list[tuple[Document, float]]
    keyword_results: list[tuple[Document, float]]
    merged_results: list[tuple[Document, float]]
    reranked_results: list[tuple[Document, float]] = field(default_factory=list)
    results: list[tuple[Document, float]] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)
    history: list[dict[str, str]] = field(default_factory=list)
    rerank_diagnostics: "RerankDiagnostics" = field(default_factory=lambda: RerankDiagnostics())
    retrieval_debug: dict[str, object] = field(default_factory=dict)


@dataclass(slots=True)
class RerankDiagnostics:
    candidate_count: int = 0
    order_changed: bool = False
    merged_top_label: str | None = None
    reranked_top_label: str | None = None
    merged_top_ids: list[str] = field(default_factory=list)
    reranked_top_ids: list[str] = field(default_factory=list)


_CORPUS_SIGNATURE: tuple[tuple[str, int, int], ...] | None = None
_CACHED_DOCUMENTS: list[Document] | None = None
_CACHED_CHUNKS: dict[tuple[int, int], list[Document]] = {}
_CACHED_CHUNK_LOOKUPS: dict[tuple[int, int], dict[tuple[str, int], Document]] = {}
_CACHED_DOCUMENTS_BY_SOURCE: dict[str, Document] | None = None


def get_docs_signature(docs_dir: Path = DOCS_DIR) -> tuple[tuple[str, int, int], ...]:
    signature: list[tuple[str, int, int]] = []
    for path in sorted(docs_dir.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            continue
        stat = path.stat()
        signature.append((path.relative_to(docs_dir).as_posix(), stat.st_mtime_ns, stat.st_size))
    return tuple(signature)


def refresh_corpus_cache() -> None:
    global _CORPUS_SIGNATURE, _CACHED_DOCUMENTS, _CACHED_DOCUMENTS_BY_SOURCE

    signature = get_docs_signature()
    if signature == _CORPUS_SIGNATURE and _CACHED_DOCUMENTS is not None:
        return

    _CORPUS_SIGNATURE = signature
    _CACHED_DOCUMENTS = load_documents()
    _CACHED_DOCUMENTS_BY_SOURCE = {
        document.metadata.get("source", ""): document for document in _CACHED_DOCUMENTS
    }
    _CACHED_CHUNKS.clear()
    _CACHED_CHUNK_LOOKUPS.clear()


def get_corpus_documents() -> list[Document]:
    refresh_corpus_cache()
    return list(_CACHED_DOCUMENTS or [])


def get_corpus_documents_by_source() -> dict[str, Document]:
    refresh_corpus_cache()
    return dict(_CACHED_DOCUMENTS_BY_SOURCE or {})


def get_corpus_chunks(
    *,
    chunk_size: int = 360,
    chunk_overlap: int = 80,
) -> list[Document]:
    refresh_corpus_cache()
    cache_key = (chunk_size, chunk_overlap)
    if cache_key not in _CACHED_CHUNKS:
        _CACHED_CHUNKS[cache_key] = split_documents(
            list(_CACHED_DOCUMENTS or []),
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )
    return list(_CACHED_CHUNKS[cache_key])


def get_chunk_lookup(
    *,
    chunk_size: int = 360,
    chunk_overlap: int = 80,
) -> dict[tuple[str, int], Document]:
    refresh_corpus_cache()
    cache_key = (chunk_size, chunk_overlap)
    if cache_key not in _CACHED_CHUNK_LOOKUPS:
        lookup: dict[tuple[str, int], Document] = {}
        for chunk in get_corpus_chunks(chunk_size=chunk_size, chunk_overlap=chunk_overlap):
            source = chunk.metadata.get("source", "unknown")
            chunk_index = chunk.metadata.get("chunk_index")
            if isinstance(chunk_index, int):
                lookup[(source, chunk_index)] = chunk
        _CACHED_CHUNK_LOOKUPS[cache_key] = lookup
    return dict(_CACHED_CHUNK_LOOKUPS[cache_key])


def normalize_for_search(text: str) -> str:
    return text.casefold()


def normalize_source_path(source: str) -> str:
    return source.replace("\\", "/").strip().casefold()


def get_source_basename(source: str) -> str:
    normalized = normalize_source_path(source)
    return normalized.rsplit("/", 1)[-1]


def resolve_target_source_hint(target_source_hint: str | None) -> str | None:
    normalized_hint = normalize_source_path(target_source_hint or "")
    if not normalized_hint:
        return None

    documents_by_source = get_corpus_documents_by_source()
    if not documents_by_source:
        return None

    exact_matches = [
        source for source in documents_by_source if normalize_source_path(source) == normalized_hint
    ]
    if exact_matches:
        return sorted(exact_matches)[0]

    basename = get_source_basename(normalized_hint)
    basename_matches = [source for source in documents_by_source if get_source_basename(source) == basename]
    if len(basename_matches) == 1:
        return basename_matches[0]

    suffix_matches = [source for source in documents_by_source if normalize_source_path(source).endswith(f"/{normalized_hint}")]
    if len(suffix_matches) == 1:
        return suffix_matches[0]

    return None


def filter_results_to_source(
    results: list[tuple[Document, float]],
    target_source: str | None,
    *,
    limit: int | None = None,
) -> list[tuple[Document, float]]:
    if not target_source:
        return results[:limit] if limit is not None else list(results)

    filtered = [
        (doc, score)
        for doc, score in results
        if doc.metadata.get("source", "") == target_source
    ]
    return filtered[:limit] if limit is not None else filtered


def extract_keyword_candidates(query: str) -> list[str]:
    candidates: list[str] = []

    quoted_parts = re.findall(r'["“”‘’《》](.+?)["“”‘’《》]', query)
    candidates.extend(part.strip() for part in quoted_parts if part.strip())

    cleaned_query = re.sub(r'["“”‘’《》]', " ", query)
    for marker in (
        "是什么",
        "有哪些",
        "怎么",
        "如何",
        "请问",
        "一下",
        "详细",
        "介绍",
        "说明",
        "内容",
        "里面",
        "中的",
        "这个",
        "那个",
        "吗",
        "呢",
        "吧",
        "请",
        "告诉我",
        "告诉",
        "的",
    ):
        cleaned_query = cleaned_query.replace(marker, " ")
    cleaned_query = re.sub(r"[\s,，。；;:：!！?？、]+", " ", cleaned_query)
    candidates.extend(part.strip() for part in cleaned_query.split(" ") if len(part.strip()) >= 2)

    english_terms = re.findall(r"[A-Za-z][A-Za-z0-9_-]{1,}", query)
    candidates.extend(term.strip() for term in english_terms if term.strip())

    candidates.extend(term for term in QUESTION_HINT_TERMS if term in query)

    deduped: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        normalized = normalize_for_search(candidate)
        if normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(candidate)

    return deduped


def score_chunk_by_keywords(chunk: Document, query: str, keywords: list[str]) -> float:
    text = chunk.page_content
    normalized_text = normalize_for_search(text)
    score = 0.0
    matched_keywords = 0

    for keyword in keywords:
        normalized_keyword = normalize_for_search(keyword)
        if not normalized_keyword or normalized_keyword not in normalized_text:
            continue

        matched_keywords += 1
        score += 1.0 if len(normalized_keyword) <= 3 else 2.0
        if len(normalized_keyword) >= 6:
            score += 0.5

    if matched_keywords == 0:
        return 0.0

    if any(term in query for term in ("具体操作", "操作步骤", "步骤", "流程")):
        if re.search(r"(?m)^\s*(?:[-*•]|\d+[.)、])\s+\S+", text):
            score += 3.0
        if "具体操作" in text or "步骤" in text or "流程" in text:
            score += 2.0

    if any(term in query for term in ("方法", "怎么做", "如何做")) and (":" in text or "：" in text):
        score += 0.5

    score += max(0, matched_keywords - 1) * 0.5
    return score


def keyword_search_documents(
    query: str,
    limit: int = 5,
    *,
    target_source_hint: str | None = None,
) -> list[tuple[Document, float]]:
    keywords = extract_keyword_candidates(query)
    if not keywords:
        return []

    target_source = resolve_target_source_hint(target_source_hint)
    chunks = get_corpus_chunks()
    if target_source is not None:
        chunks = [chunk for chunk in chunks if chunk.metadata.get("source", "") == target_source]
    scored_chunks: list[tuple[Document, float]] = []

    for chunk in chunks:
        score = score_chunk_by_keywords(chunk, query, keywords)
        if score > 0:
            scored_chunks.append((chunk, score))

    scored_chunks.sort(
        key=lambda item: (
            -item[1],
            item[0].metadata.get("chunk_index", 10**9),
        )
    )
    return scored_chunks[:limit]


def merge_retrieval_results(
    vector_results: list[tuple[Document, float]],
    keyword_results: list[tuple[Document, float]],
    limit: int = 5,
) -> list[tuple[Document, float]]:
    combined: dict[str, dict] = {}

    for doc, vector_score in vector_results:
        chunk_id = doc.metadata.get("chunk_id", "unknown")
        combined[chunk_id] = {
            "doc": doc,
            "vector_score": vector_score,
            "keyword_score": 0.0,
        }

    for doc, keyword_score in keyword_results:
        chunk_id = doc.metadata.get("chunk_id", "unknown")
        if chunk_id not in combined:
            combined[chunk_id] = {
                "doc": doc,
                "vector_score": None,
                "keyword_score": keyword_score,
            }
        else:
            combined[chunk_id]["keyword_score"] = max(combined[chunk_id]["keyword_score"], keyword_score)

    def sort_key(item: dict) -> tuple:
        has_vector = item["vector_score"] is not None
        has_keyword = item["keyword_score"] > 0
        priority = 0 if has_vector and has_keyword else 1 if has_keyword else 2
        vector_score = item["vector_score"] if item["vector_score"] is not None else 999.0
        return (
            priority,
            -item["keyword_score"],
            vector_score,
            item["doc"].metadata.get("chunk_index", 10**9),
        )

    ranked_items = sorted(combined.values(), key=sort_key)
    return [
        (item["doc"], item["vector_score"] if item["vector_score"] is not None else -item["keyword_score"])
        for item in ranked_items[:limit]
    ]


def build_score_lookup(results: list[tuple[Document, float]]) -> dict[str, float]:
    lookup: dict[str, float] = {}
    for doc, score in results:
        source = doc.metadata.get("source", "unknown")
        chunk_index = doc.metadata.get("chunk_index", "chunk")
        chunk_id = str(doc.metadata.get("chunk_id", f"{source}::{chunk_index}"))
        lookup[chunk_id] = score
    return lookup


def get_chunk_id(doc: Document) -> str:
    source = doc.metadata.get("source", "unknown")
    chunk_index = doc.metadata.get("chunk_index", "chunk")
    return str(doc.metadata.get("chunk_id", f"{source}::{chunk_index}"))


def get_chunk_label(doc: Document) -> str:
    source = doc.metadata.get("source", "unknown")
    chunk_index = doc.metadata.get("chunk_index", "chunk")
    return f"{source}#{chunk_index}"


def rerank_retrieval_results(
    query: str,
    merged_results: list[tuple[Document, float]],
    *,
    vector_results: list[tuple[Document, float]],
    keyword_results: list[tuple[Document, float]],
    limit: int = 5,
) -> list[tuple[Document, float]]:
    return rerank_chunk_results(
        query,
        merged_results,
        keywords=extract_keyword_candidates(query),
        vector_score_lookup=build_score_lookup(vector_results),
        keyword_score_lookup=build_score_lookup(keyword_results),
        limit=limit,
    )


def build_rerank_diagnostics(
    merged_results: list[tuple[Document, float]],
    reranked_results: list[tuple[Document, float]],
) -> RerankDiagnostics:
    merged_top = merged_results[0][0] if merged_results else None
    reranked_top = reranked_results[0][0] if reranked_results else None
    merged_top_ids = [get_chunk_id(doc) for doc, _ in merged_results[:3]]
    reranked_top_ids = [get_chunk_id(doc) for doc, _ in reranked_results[:3]]
    return RerankDiagnostics(
        candidate_count=len(merged_results),
        order_changed=merged_top_ids != reranked_top_ids,
        merged_top_label=get_chunk_label(merged_top) if merged_top is not None else None,
        reranked_top_label=get_chunk_label(reranked_top) if reranked_top is not None else None,
        merged_top_ids=merged_top_ids,
        reranked_top_ids=reranked_top_ids,
    )


def expand_results_with_neighbors(
    results: list[tuple[Document, float]],
    window: int = 1,
    limit: int = 7,
) -> list[tuple[Document, float]]:
    if not results:
        return []

    chunk_lookup = get_chunk_lookup()
    selected: dict[str, tuple[Document, float]] = {}
    source_rank: dict[str, int] = {}

    for rank, (doc, score) in enumerate(results):
        source = doc.metadata.get("source", "unknown")
        chunk_index = doc.metadata.get("chunk_index")
        source_rank.setdefault(source, rank)

        if not isinstance(chunk_index, int):
            chunk_id = doc.metadata.get("chunk_id", f"{source}::chunk")
            selected.setdefault(chunk_id, (doc, score))
            continue

        for offset in range(-window, window + 1):
            neighbor = chunk_lookup.get((source, chunk_index + offset))
            if neighbor is None:
                continue

            neighbor_id = neighbor.metadata.get("chunk_id", f"{source}::chunk-{chunk_index + offset}")
            if neighbor_id in selected:
                continue

            neighbor_score = score if offset == 0 else score + abs(offset) * 0.0001
            selected[neighbor_id] = (neighbor, neighbor_score)

    ordered_items = sorted(
        selected.values(),
        key=lambda item: (
            source_rank.get(item[0].metadata.get("source", "unknown"), 10**9),
            item[0].metadata.get("chunk_index", 10**9),
        ),
    )
    return ordered_items[:limit]


def run_hybrid_chunk_search(
    query: str,
    *,
    vector_k: int = 3,
    keyword_limit: int | None = None,
    merge_limit: int | None = None,
    neighbor_window: int = 1,
    final_limit: int | None = None,
    target_source_hint: str | None = None,
) -> tuple[
    list[tuple[Document, float]],
    list[tuple[Document, float]],
    list[tuple[Document, float]],
    list[tuple[Document, float]],
]:
    keyword_limit = keyword_limit or max(vector_k, 5)
    merge_limit = merge_limit or max(vector_k, 5)
    final_limit = final_limit or max(vector_k + 2, 7)
    target_source = resolve_target_source_hint(target_source_hint)
    vector_fetch_limit = max(vector_k * 4, 12) if target_source else vector_k

    # Main local retrieval flow:
    # 1. recall candidate chunks with vector and keyword search
    # 2. merge both recall channels into one candidate list
    # 3. rerank merged candidates before any neighbor expansion
    # 4. expand neighbors only around the reranked core hits
    vector_results = retrieve_vector_documents(query, k=vector_fetch_limit)
    vector_results = filter_results_to_source(vector_results, target_source, limit=vector_k)
    keyword_results = keyword_search_documents(query, limit=keyword_limit, target_source_hint=target_source)
    merged_results = merge_retrieval_results(vector_results, keyword_results, limit=merge_limit)
    reranked_results = rerank_retrieval_results(
        query,
        merged_results,
        vector_results=vector_results,
        keyword_results=keyword_results,
        limit=merge_limit,
    )
    if neighbor_window > 0:
        final_results = expand_results_with_neighbors(reranked_results, window=neighbor_window, limit=final_limit)
    else:
        final_results = reranked_results[:final_limit]
    return vector_results, keyword_results, merged_results, reranked_results, final_results


def get_sources(results: list[tuple[Document, float]]) -> list[str]:
    if not results:
        return []

    aggregated: dict[str, float] = {}
    for rank, (doc, _) in enumerate(results):
        source = doc.metadata.get("source", "unknown")
        aggregated[source] = aggregated.get(source, 0.0) + max(1.0, float(len(results) - rank))

    top_source = max(
        aggregated.items(),
        key=lambda item: (item[1], item[0]),
    )[0]
    return [top_source]


def build_context(results: list[tuple[Document, float]]) -> str:
    context_parts: list[str] = []

    for index, (doc, score) in enumerate(results, start=1):
        source = doc.metadata.get("source", "unknown")
        chunk_index = doc.metadata.get("chunk_index", "unknown")
        context_parts.append(
            f"[Source {index}] file={source}, chunk={chunk_index}, score={score:.4f}\n{doc.page_content}"
        )

    return "\n\n".join(context_parts)


def prepare_chunk_answer_material(
    question: str,
    history: list[dict[str, str]] | None = None,
    k: int = 3,
) -> ChunkRetrievalBundle:
    # Primary retrieval entry used by pipeline.py and workflow.py.
    reference_history = build_reference_history(question, history)
    rewritten_question = rewrite_question(question, reference_history)
    target_source_hint = extract_target_source_hint(question)
    resolved_target_source = resolve_target_source_hint(target_source_hint)
    vector_results, keyword_results, merged_results, reranked_results, results = run_hybrid_chunk_search(
        rewritten_question,
        vector_k=k,
        keyword_limit=max(k, 5),
        merge_limit=max(k, 5),
        neighbor_window=1,
        final_limit=max(k + 2, 7),
        target_source_hint=target_source_hint,
    )
    return ChunkRetrievalBundle(
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
        },
    )


def retrieve_documents(query: str, k: int = 3) -> list[tuple[Document, float]]:
    _, _, _, _, results = run_hybrid_chunk_search(
        query,
        vector_k=k,
        keyword_limit=max(k, 5),
        merge_limit=max(k, 5),
        neighbor_window=1,
        final_limit=max(k + 2, 7),
        target_source_hint=extract_target_source_hint(query),
    )
    return results



