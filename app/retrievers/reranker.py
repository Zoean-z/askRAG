import re

from langchain_core.documents import Document

PROCEDURAL_QUERY_TERMS = (
    "\u5177\u4f53\u64cd\u4f5c",
    "\u64cd\u4f5c\u6b65\u9aa4",
    "\u6b65\u9aa4",
    "\u6d41\u7a0b",
    "\u65b9\u6cd5",
    "\u600e\u4e48\u505a",
    "\u5982\u4f55\u505a",
)
PROCEDURAL_STRUCTURE_PATTERN = re.compile(r"(?m)^\s*(?:[-*]|\d+[.)\u3001])\s+\S+")
SECTION_HEADING_PATTERN = re.compile(r"(?m)^\s*[#>]*\s*\S.{0,30}$")


def rerank_chunk_results(
    query: str,
    candidates: list[tuple[Document, float]],
    *,
    keywords: list[str],
    vector_score_lookup: dict[str, float],
    keyword_score_lookup: dict[str, float],
    limit: int = 5,
) -> list[tuple[Document, float]]:
    if not candidates:
        return []

    cleaned_query = _clean_query_text(query)
    query_phrase = _normalize(cleaned_query)
    procedural_query = any(term in query for term in PROCEDURAL_QUERY_TERMS)

    scored_candidates: list[tuple[Document, float, float, int]] = []
    for rank, (doc, fallback_score) in enumerate(candidates):
        chunk_id = _get_chunk_id(doc)
        rerank_score = _score_candidate(
            doc,
            keywords=keywords,
            query_phrase=query_phrase,
            procedural_query=procedural_query,
            vector_score=vector_score_lookup.get(chunk_id),
            keyword_score=keyword_score_lookup.get(chunk_id, 0.0),
            fallback_score=fallback_score,
        )
        scored_candidates.append((doc, rerank_score, fallback_score, rank))

    scored_candidates.sort(
        key=lambda item: (
            -item[1],
            item[3],
            item[0].metadata.get("chunk_index", 10**9),
        )
    )
    return [(doc, score) for doc, score, _, _ in scored_candidates[:limit]]


def _score_candidate(
    doc: Document,
    *,
    keywords: list[str],
    query_phrase: str,
    procedural_query: bool,
    vector_score: float | None,
    keyword_score: float,
    fallback_score: float,
) -> float:
    text = doc.page_content
    normalized_text = _normalize(text)
    score = 0.0

    matched_keywords = 0
    anchor_hits = 0
    ordered_positions: list[int] = []
    for keyword in keywords:
        normalized_keyword = _normalize(keyword)
        if len(normalized_keyword) < 2:
            continue
        position = normalized_text.find(normalized_keyword)
        if position < 0:
            continue

        matched_keywords += 1
        ordered_positions.append(position)
        score += 1.2 if len(normalized_keyword) >= 4 else 0.7
        if any(char.isdigit() for char in normalized_keyword) or len(normalized_keyword) >= 6:
            anchor_hits += 1

    keyword_count = len([keyword for keyword in keywords if len(_normalize(keyword)) >= 2])
    coverage = matched_keywords / keyword_count if keyword_count else 0.0
    score += coverage * 4.0
    score += anchor_hits * 0.9

    if query_phrase and len(query_phrase) >= 4 and query_phrase in normalized_text:
        score += 5.0

    if ordered_positions and ordered_positions == sorted(ordered_positions) and len(ordered_positions) >= 2:
        score += 1.2

    if matched_keywords and _has_early_match(text, keywords):
        score += 0.8

    if matched_keywords and _has_heading_match(text, keywords):
        score += 1.2

    if procedural_query:
        if PROCEDURAL_STRUCTURE_PATTERN.search(text):
            score += 2.5
        if any(term in text for term in ("\u6b65\u9aa4", "\u6d41\u7a0b", "\u64cd\u4f5c", "\u6ce8\u610f\u4e8b\u9879", "\u524d\u63d0\u6761\u4ef6")):
            score += 1.5

    score += keyword_score * 1.6
    if vector_score is not None:
        score += max(0.0, 1.8 - min(vector_score, 1.8)) * 1.4
    else:
        score += 0.2

    if fallback_score < 0:
        score += min(abs(fallback_score), 6.0) * 0.15

    return score


def _has_early_match(text: str, keywords: list[str], *, early_chars: int = 160) -> bool:
    early_text = _normalize(text[:early_chars])
    return any(_normalize(keyword) in early_text for keyword in keywords if len(_normalize(keyword)) >= 2)


def _has_heading_match(text: str, keywords: list[str]) -> bool:
    headings = SECTION_HEADING_PATTERN.findall(text[:400])
    if not headings:
        return False
    normalized_headings = [_normalize(line) for line in headings]
    for keyword in keywords:
        normalized_keyword = _normalize(keyword)
        if len(normalized_keyword) < 2:
            continue
        if any(normalized_keyword in heading for heading in normalized_headings):
            return True
    return False


def _clean_query_text(query: str) -> str:
    cleaned = re.sub(r'["\u201c\u201d\u2018\u2019\u300a\u300b]', " ", query)
    cleaned = re.sub(r"[\s,\uff0c\u3002\uff1b;:\uff1a!\uff01?\uff1f\u3001]+", " ", cleaned)
    return cleaned.strip()


def _normalize(text: str) -> str:
    return text.casefold()


def _get_chunk_id(doc: Document) -> str:
    source = doc.metadata.get("source", "unknown")
    chunk_index = doc.metadata.get("chunk_index", "chunk")
    return str(doc.metadata.get("chunk_id", f"{source}::{chunk_index}"))
