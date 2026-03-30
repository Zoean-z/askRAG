import unittest
from unittest.mock import patch

from langchain_core.documents import Document

from app.retrievers.parent_retriever import ParentDocumentCandidate, choose_summary_document


class ParentRetrieverTests(unittest.TestCase):
    def test_choose_summary_document_prefers_contextual_match(self):
        document = Document(page_content="doc", metadata={"source": "data/docs/project_intro.txt"})
        with patch("app.retrievers.parent_retriever.resolve_summary_document_from_context", return_value=document), patch(
            "app.retrievers.parent_retriever.retrieve_parent_documents",
            side_effect=AssertionError("parent retrieval should not run when context already resolved"),
        ):
            selected = choose_summary_document("summarize this file")

        self.assertIs(selected, document)

    def test_choose_summary_document_rejects_weak_parent_match(self):
        weak = ParentDocumentCandidate(
            document=Document(page_content="weak", metadata={"source": "data/docs/weak.txt"}),
            score=3.0,
            hits=1,
        )
        with patch("app.retrievers.parent_retriever.resolve_summary_document_from_context", return_value=None), patch(
            "app.retrievers.parent_retriever.retrieve_parent_documents",
            return_value=[weak],
        ):
            with self.assertRaises(ValueError):
                choose_summary_document("summarize unknown doc")

    def test_choose_summary_document_accepts_strong_parent_match(self):
        strong_document = Document(page_content="strong", metadata={"source": "data/docs/strong.txt"})
        candidates = [
            ParentDocumentCandidate(document=strong_document, score=8.0, hits=2),
            ParentDocumentCandidate(
                document=Document(page_content="other", metadata={"source": "data/docs/other.txt"}),
                score=2.0,
                hits=1,
            ),
        ]
        with patch("app.retrievers.parent_retriever.resolve_summary_document_from_context", return_value=None), patch(
            "app.retrievers.parent_retriever.retrieve_parent_documents",
            return_value=candidates,
        ):
            selected = choose_summary_document("summarize unknown doc")

        self.assertIs(selected, strong_document)

    def test_choose_summary_document_reuses_existing_child_results(self):
        strong_document = Document(page_content="strong", metadata={"source": "data/docs/strong.txt"})
        other_document = Document(page_content="other", metadata={"source": "data/docs/other.txt"})
        child_results = [
            (Document(page_content="chunk-1", metadata={"source": "data/docs/strong.txt", "chunk_id": "s-1"}), 0.1),
            (Document(page_content="chunk-2", metadata={"source": "data/docs/strong.txt", "chunk_id": "s-2"}), 0.2),
            (Document(page_content="chunk-3", metadata={"source": "data/docs/other.txt", "chunk_id": "o-1"}), 0.3),
        ]
        with patch("app.retrievers.parent_retriever.resolve_summary_document_from_context", return_value=None), patch(
            "app.retrievers.parent_retriever.retrieve_parent_documents",
            side_effect=AssertionError("fallback should reuse existing child results"),
        ), patch(
            "app.retrievers.parent_retriever.get_corpus_documents_by_source",
            return_value={
                "data/docs/strong.txt": strong_document,
                "data/docs/other.txt": other_document,
            },
        ):
            selected = choose_summary_document("summarize unknown doc", child_results=child_results)

        self.assertIs(selected, strong_document)


if __name__ == "__main__":
    unittest.main()
