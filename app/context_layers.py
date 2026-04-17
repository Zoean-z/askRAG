from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from langchain_core.documents import Document

from app.rag import split_documents
from app.retrievers.chunk_retriever import ChunkRetrievalBundle, get_chunk_id
from app.retrievers.parent_retriever import ParentDocumentCandidate, rank_parent_documents_from_child_results
from app.session_memory import build_reference_history

DETAIL_TERMS = (
    "具体",
    "细节",
    "深入",
    "步骤",
    "操作步骤",
    "操作协议",
    "协议",
    "实现",
    "原理",
    "怎么",
    "如何",
    "怎么做",
    "如何做",
    "如何操作",
    "操作方法",
    "做法",
    "流程",
    "注意事项",
    "前提条件",
    "why",
    "how",
    "detail",
    "deep",
    "compare",
    "difference",
)
ANALYSIS_TERMS = ("分析", "评价", "解读", "点评", "review", "analysis")
HEADING_PATTERN = re.compile(r"^\s{0,3}(?:#{1,4}\s+.+|(?:\d+\.|[-*])\s+.+)$", flags=re.MULTILINE)


@dataclass(slots=True)
class LayeredContextPlan:
    mode: str
    question: str
    context: str
    layers_used: list[str]
    selected_source: str | None = None
    candidate_sources: list[str] = field(default_factory=list)
    drilldown_path: list[str] = field(default_factory=list)
    source_hits: list[dict[str, Any]] = field(default_factory=list)
    debug: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "question": self.question,
            "layers_used": list(self.layers_used),
            "selected_source": self.selected_source,
            "candidate_sources": list(self.candidate_sources),
            "drilldown_path": list(self.drilldown_path),
            "source_hits": list(self.source_hits),
            "debug": dict(self.debug),
        }


def _trim_text(text: str, limit: int) -> str:
    normalized = re.sub(r"\s+", " ", (text or "").strip())
    if len(normalized) <= limit:
        return normalized
    return normalized[: max(0, limit - 1)].rstrip() + "鈥?"


def question_requires_deep_read(question: str, history: list[dict[str, str]] | None = None) -> bool:
    normalized = question.casefold()
    if any(term in normalized for term in DETAIL_TERMS):
        return True
    reference_history = build_reference_history(question, history)
    if reference_history and len(question.strip()) <= 48:
        return True
    return False


def _document_title(document: Document) -> str:
    source = document.metadata.get("source", "unknown")
    for line in document.page_content.splitlines():
        normalized = line.strip().lstrip("#").strip()
        if len(normalized) >= 4:
            return _trim_text(normalized, 96)
    return Path(source).name


def _document_headings(document: Document, limit: int = 5) -> list[str]:
    headings = []
    for match in HEADING_PATTERN.finditer(document.page_content):
        heading = match.group(0).strip().lstrip("#").strip()
        if heading:
            headings.append(_trim_text(heading, 80))
        if len(headings) >= limit:
            break
    return headings


def _document_preview_lines(document: Document, limit: int = 3) -> list[str]:
    lines: list[str] = []
    for raw in document.page_content.splitlines():
        normalized = raw.strip()
        if not normalized or normalized.startswith("#"):
            continue
        lines.append(_trim_text(normalized, 180))
        if len(lines) >= limit:
            break
    return lines


def build_document_overview(document: Document, *, max_chars: int = 1200) -> str:
    source = document.metadata.get("source", "unknown")
    title = _document_title(document)
    headings = _document_headings(document)
    preview_lines = _document_preview_lines(document)

    lines = [
        f"source: {source}",
        f"title: {title}",
    ]
    if headings:
        lines.append("headings:")
        lines.extend(f"- {heading}" for heading in headings)
    if preview_lines:
        lines.append("preview:")
        lines.extend(f"- {line}" for line in preview_lines)

    return _trim_text("\n".join(lines), max_chars)


def _sample_detail_chunks(document: Document, *, limit: int = 3) -> list[Document]:
    chunks = split_documents([Document(page_content=document.page_content, metadata={"source": document.metadata.get("source", "unknown")})])
    return chunks[:limit]


def _source_hits_from_parents(parents: list[ParentDocumentCandidate]) -> list[dict[str, Any]]:
    return [
        {
            "source": candidate.document.metadata.get("source", "unknown"),
            "score": round(candidate.score, 4),
            "hits": candidate.hits,
            "title": _document_title(candidate.document),
        }
        for candidate in parents
    ]


def _build_l0_collection_section(source_hits: list[dict[str, Any]]) -> str:
    if not source_hits:
        return ""
    lines = ["[L0 Locate]", "Candidate sources:"]
    for item in source_hits:
        lines.append(f"- {item['source']} | hits={item['hits']} | score={item['score']:.4f} | title={item['title']}")
    return "\n".join(lines)


def _build_l1_overview_section(documents: list[Document]) -> str:
    if not documents:
        return ""
    sections = ["[L1 Overview]"]
    for document in documents:
        sections.append(build_document_overview(document))
    return "\n\n".join(sections)


def _build_l2_section(chunks: list[tuple[Document, float]]) -> str:
    if not chunks:
        return ""
    lines = ["[L2 Deep Read]"]
    for index, (document, score) in enumerate(chunks, start=1):
        source = document.metadata.get("source", "unknown")
        chunk_index = document.metadata.get("chunk_index", "unknown")
        lines.append(f"[Chunk {index}] source={source} chunk={chunk_index} score={score:.4f}")
        lines.append(document.page_content.strip())
    return "\n".join(lines)


def build_query_context_plan(
    question: str,
    bundle: ChunkRetrievalBundle,
    *,
    history: list[dict[str, str]] | None = None,
    memory_context: str = "",
) -> LayeredContextPlan:
    parent_candidates = rank_parent_documents_from_child_results(bundle.reranked_results or bundle.merged_results, limit=3)
    overview_documents = [candidate.document for candidate in parent_candidates]
    source_hits = _source_hits_from_parents(parent_candidates)
    selected_source = source_hits[0]["source"] if source_hits else (bundle.sources[0] if bundle.sources else None)
    deep_read = question_requires_deep_read(question, history=history)

    filtered_results = bundle.results
    if deep_read and selected_source:
        selected_only = [item for item in bundle.results if item[0].metadata.get("source") == selected_source]
        if selected_only:
            filtered_results = selected_only

    sections = [part for part in (memory_context, _build_l0_collection_section(source_hits), _build_l1_overview_section(overview_documents)) if part]
    layers_used = ["L0", "L1"]
    drilldown_path = ["corpus"]
    candidate_sources = [item["source"] for item in source_hits]
    if selected_source:
        drilldown_path.append(selected_source)
    if deep_read and filtered_results:
        layers_used.append("L2")
        l2_results = filtered_results[:4]
        sections.append(_build_l2_section(l2_results))
        drilldown_path.extend(get_chunk_id(document) for document, _ in l2_results[:3])

    context = "\n\n".join(section for section in sections if section.strip())
    return LayeredContextPlan(
        mode="query",
        question=question,
        context=context,
        layers_used=layers_used,
        selected_source=selected_source,
        candidate_sources=candidate_sources,
        drilldown_path=drilldown_path,
        source_hits=source_hits,
        debug={
            "deep_read_enabled": deep_read,
            "memory_context_used": bool(memory_context.strip()),
            "rerank_candidate_count": bundle.rerank_diagnostics.candidate_count,
            "order_changed_after_rerank": bundle.rerank_diagnostics.order_changed,
            "retrieval": dict(bundle.retrieval_debug),
        },
    )


def build_summary_context_plan(
    question: str,
    document: Document,
    *,
    history: list[dict[str, str]] | None = None,
    child_results: list[tuple[Document, float]] | None = None,
    memory_context: str = "",
) -> LayeredContextPlan:
    parent_candidates = rank_parent_documents_from_child_results(child_results or [], limit=3)
    source_hits = _source_hits_from_parents(parent_candidates)
    selected_source = document.metadata.get("source", "unknown")
    if not source_hits:
        source_hits = [{"source": selected_source, "score": 1.0, "hits": 1, "title": _document_title(document)}]

    sections = []
    layers_used: list[str] = []
    if memory_context:
        sections.append(memory_context)
    if len(source_hits) > 1:
        sections.append(_build_l0_collection_section(source_hits))
        layers_used.append("L0")

    sections.append(_build_l1_overview_section([document]))
    layers_used.append("L1")

    deep_read = question_requires_deep_read(question, history=history) or any(term in question.casefold() for term in ANALYSIS_TERMS)
    drilldown_path = ["summary", selected_source]
    if deep_read:
        sampled = _sample_detail_chunks(document, limit=3)
        l2_results = [(chunk, float(index)) for index, chunk in enumerate(sampled, start=1)]
        sections.append(_build_l2_section(l2_results))
        layers_used.append("L2")
        drilldown_path.extend(get_chunk_id(chunk) for chunk in sampled[:3])

    return LayeredContextPlan(
        mode="summary",
        question=question,
        context="\n\n".join(section for section in sections if section.strip()),
        layers_used=layers_used,
        selected_source=selected_source,
        candidate_sources=[item["source"] for item in source_hits],
        drilldown_path=drilldown_path,
        source_hits=source_hits,
        debug={
            "deep_read_enabled": deep_read,
            "memory_context_used": bool(memory_context.strip()),
            "memory_context_chars": len(memory_context.strip()),
            "context_chars": len("\n\n".join(section for section in sections if section.strip())),
            "source_hit_count": len(source_hits),
            "layer_count": len(layers_used),
            "section_count": len([section for section in sections if section.strip()]),
            "l2_chunk_count": len(l2_results) if deep_read else 0,
        },
    )
