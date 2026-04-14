from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Protocol

from langchain_core.documents import Document

from app.retrievers.chunk_retriever import ChunkRetrievalBundle


class RetrievalBackend(Protocol):
    name: str

    def prepare_chunk_answer_material(
        self,
        question: str,
        history: list[dict[str, str]] | None = None,
        k: int = 3,
    ) -> ChunkRetrievalBundle: ...

    def run_hybrid_chunk_search(
        self,
        query: str,
        *,
        vector_k: int = 3,
        keyword_limit: int | None = None,
        merge_limit: int | None = None,
        neighbor_window: int = 1,
        final_limit: int | None = None,
    ) -> tuple[
        list[tuple[Document, float]],
        list[tuple[Document, float]],
        list[tuple[Document, float]],
        list[tuple[Document, float]],
        list[tuple[Document, float]],
    ]: ...

    def get_corpus_documents(self) -> list[Document]: ...

    def get_corpus_documents_by_source(self) -> dict[str, Document]: ...


@dataclass(slots=True)
class ChromaRetrievalBackend:
    name: str = "chroma"

    def prepare_chunk_answer_material(
        self,
        question: str,
        history: list[dict[str, str]] | None = None,
        k: int = 3,
    ) -> ChunkRetrievalBundle:
        from app.retrievers import chunk_retriever

        return chunk_retriever.prepare_chunk_answer_material(question, history=history, k=k)

    def run_hybrid_chunk_search(
        self,
        query: str,
        *,
        vector_k: int = 3,
        keyword_limit: int | None = None,
        merge_limit: int | None = None,
        neighbor_window: int = 1,
        final_limit: int | None = None,
    ) -> tuple[
        list[tuple[Document, float]],
        list[tuple[Document, float]],
        list[tuple[Document, float]],
        list[tuple[Document, float]],
        list[tuple[Document, float]],
    ]:
        from app.retrievers import chunk_retriever

        return chunk_retriever.run_hybrid_chunk_search(
            query,
            vector_k=vector_k,
            keyword_limit=keyword_limit,
            merge_limit=merge_limit,
            neighbor_window=neighbor_window,
            final_limit=final_limit,
        )

    def get_corpus_documents(self) -> list[Document]:
        from app.retrievers import chunk_retriever

        return chunk_retriever.get_corpus_documents()

    def get_corpus_documents_by_source(self) -> dict[str, Document]:
        from app.retrievers import chunk_retriever

        return chunk_retriever.get_corpus_documents_by_source()


_BACKENDS: dict[str, RetrievalBackend] = {
    "chroma": ChromaRetrievalBackend(),
}


def register_retrieval_backend(name: str, backend: RetrievalBackend) -> None:
    normalized = name.strip().casefold()
    if not normalized:
        raise ValueError("Backend name is required.")
    _BACKENDS[normalized] = backend


def get_active_retrieval_backend_name() -> str:
    configured = os.getenv("ASKRAG_RETRIEVAL_BACKEND", "chroma").strip().casefold()
    return configured if configured in _BACKENDS else "chroma"


def get_retrieval_backend() -> RetrievalBackend:
    return _BACKENDS[get_active_retrieval_backend_name()]


def prepare_chunk_answer_material(
    question: str,
    history: list[dict[str, str]] | None = None,
    k: int = 3,
) -> ChunkRetrievalBundle:
    return get_retrieval_backend().prepare_chunk_answer_material(question, history=history, k=k)


def run_hybrid_chunk_search(
    query: str,
    *,
    vector_k: int = 3,
    keyword_limit: int | None = None,
    merge_limit: int | None = None,
    neighbor_window: int = 1,
    final_limit: int | None = None,
) -> tuple[
    list[tuple[Document, float]],
    list[tuple[Document, float]],
    list[tuple[Document, float]],
    list[tuple[Document, float]],
    list[tuple[Document, float]],
]:
    return get_retrieval_backend().run_hybrid_chunk_search(
        query,
        vector_k=vector_k,
        keyword_limit=keyword_limit,
        merge_limit=merge_limit,
        neighbor_window=neighbor_window,
        final_limit=final_limit,
    )


def get_corpus_documents() -> list[Document]:
    return get_retrieval_backend().get_corpus_documents()


def get_corpus_documents_by_source() -> dict[str, Document]:
    return get_retrieval_backend().get_corpus_documents_by_source()
