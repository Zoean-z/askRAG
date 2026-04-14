import os
import unittest
from unittest.mock import patch

from langchain_core.documents import Document

from app.retrievers import backend
from app.retrievers.chunk_retriever import ChunkRetrievalBundle, RerankDiagnostics


class RetrievalBackendTests(unittest.TestCase):
    def setUp(self):
        self._original_backend = os.environ.get("ASKRAG_RETRIEVAL_BACKEND")

    def tearDown(self):
        if self._original_backend is None:
            os.environ.pop("ASKRAG_RETRIEVAL_BACKEND", None)
        else:
            os.environ["ASKRAG_RETRIEVAL_BACKEND"] = self._original_backend

    def test_default_backend_name_is_chroma(self):
        os.environ.pop("ASKRAG_RETRIEVAL_BACKEND", None)

        self.assertEqual(backend.get_active_retrieval_backend_name(), "chroma")
        self.assertEqual(backend.get_retrieval_backend().name, "chroma")

    def test_unknown_backend_name_falls_back_to_chroma(self):
        os.environ["ASKRAG_RETRIEVAL_BACKEND"] = "unknown-backend"

        self.assertEqual(backend.get_active_retrieval_backend_name(), "chroma")

    def test_prepare_chunk_answer_material_delegates_to_active_backend(self):
        bundle = ChunkRetrievalBundle(
            rewritten_question="q",
            vector_results=[],
            keyword_results=[],
            merged_results=[],
            reranked_results=[],
            results=[],
            sources=[],
            history=[],
            rerank_diagnostics=RerankDiagnostics(
                candidate_count=0,
                order_changed=False,
                merged_top_label=None,
                reranked_top_label=None,
                merged_top_ids=[],
                reranked_top_ids=[],
            ),
        )

        with patch("app.retrievers.chunk_retriever.prepare_chunk_answer_material", return_value=bundle) as mock_prepare:
            result = backend.prepare_chunk_answer_material("What is Chroma?")

        self.assertIs(result, bundle)
        mock_prepare.assert_called_once_with("What is Chroma?", history=None, k=3)

    def test_run_hybrid_chunk_search_delegates_to_active_backend(self):
        result = ([(Document(page_content="a", metadata={}), 0.1)], [], [], [], [])

        with patch("app.retrievers.chunk_retriever.run_hybrid_chunk_search", return_value=result) as mock_run:
            observed = backend.run_hybrid_chunk_search("What is Chroma?", vector_k=5)

        self.assertEqual(observed, result)
        mock_run.assert_called_once_with(
            "What is Chroma?",
            vector_k=5,
            keyword_limit=None,
            merge_limit=None,
            neighbor_window=1,
            final_limit=None,
        )


if __name__ == "__main__":
    unittest.main()
