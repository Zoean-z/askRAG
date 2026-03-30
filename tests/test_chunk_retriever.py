import unittest
from types import SimpleNamespace
from unittest.mock import patch

from langchain_core.documents import Document

import app.retrievers.chunk_retriever as chunk_retriever
from app.rag import build_chat_messages, rewrite_question


class ChunkRetrieverCacheTests(unittest.TestCase):
    def setUp(self):
        chunk_retriever._CORPUS_SIGNATURE = None
        chunk_retriever._CACHED_DOCUMENTS = None
        chunk_retriever._CACHED_DOCUMENTS_BY_SOURCE = None
        chunk_retriever._CACHED_CHUNKS.clear()
        chunk_retriever._CACHED_CHUNK_LOOKUPS.clear()

    def tearDown(self):
        chunk_retriever._CORPUS_SIGNATURE = None
        chunk_retriever._CACHED_DOCUMENTS = None
        chunk_retriever._CACHED_DOCUMENTS_BY_SOURCE = None
        chunk_retriever._CACHED_CHUNKS.clear()
        chunk_retriever._CACHED_CHUNK_LOOKUPS.clear()

    def test_get_corpus_chunks_uses_cache_for_same_signature(self):
        documents = [Document(page_content="doc", metadata={"source": "data/docs/demo.txt"})]
        chunks = [Document(page_content="chunk", metadata={"source": "data/docs/demo.txt", "chunk_index": 0})]
        signature = (("demo.txt", 1, 3),)

        with patch.object(chunk_retriever, "get_docs_signature", return_value=signature), patch.object(
            chunk_retriever,
            "load_documents",
            return_value=documents,
        ) as mock_load, patch.object(chunk_retriever, "split_documents", return_value=chunks) as mock_split:
            first = chunk_retriever.get_corpus_chunks()
            second = chunk_retriever.get_corpus_chunks()

        self.assertEqual(first, chunks)
        self.assertEqual(second, chunks)
        self.assertEqual(mock_load.call_count, 1)
        self.assertEqual(mock_split.call_count, 1)


class RewriteQuestionTests(unittest.TestCase):
    def test_rewrite_question_skips_complete_question_even_with_history(self):
        history = [{"role": "assistant", "content": "\u6211\u4eec\u521a\u624d\u5728\u804a\u5411\u91cf\u5e93\u3002"}]

        with patch("app.rag.get_chat_client", side_effect=AssertionError("chat client should not be called")):
            rewritten = rewrite_question("\u4ec0\u4e48\u662f Chroma", history=history)

        self.assertEqual(rewritten, "\u4ec0\u4e48\u662f Chroma")

    def test_rewrite_question_uses_llm_for_reference_follow_up(self):
        history = [{"role": "assistant", "content": "Chroma \u53ef\u4ee5\u4f5c\u4e3a\u672c\u5730\u5411\u91cf\u6570\u636e\u5e93\u3002"}]
        fake_response = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="Chroma \u7684\u4f5c\u7528\u662f\u4ec0\u4e48"))]
        )
        fake_client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=lambda **kwargs: fake_response)))

        with patch("app.rag.get_chat_client", return_value=fake_client):
            rewritten = rewrite_question("\u5b83\u7684\u4f5c\u7528\u662f\u4ec0\u4e48", history=history)

        self.assertEqual(rewritten, "Chroma \u7684\u4f5c\u7528\u662f\u4ec0\u4e48")

    def test_prepare_chunk_answer_material_uses_original_question_when_rewrite_is_skipped(self):
        history = [{"role": "assistant", "content": "\u6211\u4eec\u521a\u624d\u5728\u804a\u5411\u91cf\u5e93\u3002"}]
        empty_results: list[tuple[Document, float]] = []

        with patch.object(
            chunk_retriever,
            "run_hybrid_chunk_search",
            return_value=(empty_results, empty_results, empty_results, empty_results),
        ) as mock_search:
            bundle = chunk_retriever.prepare_chunk_answer_material("\u4ec0\u4e48\u662f Chroma", history=history)

        self.assertEqual(bundle.rewritten_question, "\u4ec0\u4e48\u662f Chroma")
        self.assertEqual(mock_search.call_args.args[0], "\u4ec0\u4e48\u662f Chroma")


    def test_prepare_chunk_answer_material_returns_only_top_source(self):
        history = []
        merged_results = [
            (Document(page_content="a1", metadata={"source": "data/docs/a.txt", "chunk_id": "a-1"}), 0.1),
            (Document(page_content="a2", metadata={"source": "data/docs/a.txt", "chunk_id": "a-2"}), 0.2),
            (Document(page_content="b1", metadata={"source": "data/docs/b.txt", "chunk_id": "b-1"}), 0.3),
        ]
        final_results = merged_results + [
            (Document(page_content="b2", metadata={"source": "data/docs/b.txt", "chunk_id": "b-2"}), 0.3001)
        ]
        empty_results: list[tuple[Document, float]] = []

        with patch.object(
            chunk_retriever,
            "run_hybrid_chunk_search",
            return_value=(empty_results, empty_results, merged_results, final_results),
        ):
            bundle = chunk_retriever.prepare_chunk_answer_material("what is this")

        self.assertEqual(bundle.sources, ["data/docs/a.txt"])


class ChatPromptHistoryTests(unittest.TestCase):
    def test_build_chat_messages_omits_history_after_meaningful_rewrite(self):
        history = [{"role": "assistant", "content": "Chroma \u53ef\u4ee5\u4f5c\u4e3a\u672c\u5730\u5411\u91cf\u6570\u636e\u5e93\u3002"}]

        messages = build_chat_messages(
            question="\u5b83\u7684\u4f5c\u7528\u662f\u4ec0\u4e48",
            context="ctx",
            history=history,
            standalone_question="Chroma \u7684\u4f5c\u7528\u662f\u4ec0\u4e48",
        )

        user_content = messages[1]["content"]
        self.assertNotIn("\u5bf9\u8bdd\u5386\u53f2", user_content)
        self.assertIn("\u8865\u5168\u540e\u7684\u68c0\u7d22\u95ee\u9898", user_content)

    def test_build_chat_messages_keeps_history_when_rewrite_is_not_meaningful(self):
        history = [{"role": "assistant", "content": "\u6211\u4eec\u521a\u624d\u5728\u804a Chroma\u3002"}]

        messages = build_chat_messages(
            question="\u4ec0\u4e48\u662f Chroma",
            context="ctx",
            history=history,
            standalone_question="\u4ec0\u4e48\u662f Chroma",
        )

        user_content = messages[1]["content"]
        self.assertIn("\u5bf9\u8bdd\u5386\u53f2", user_content)

    def test_build_chat_messages_keeps_history_when_rewrite_still_has_reference(self):
        history = [{"role": "assistant", "content": "\u6211\u4eec\u521a\u624d\u5728\u804a Chroma\u3002"}]

        messages = build_chat_messages(
            question="\u5b83\u7684\u4f5c\u7528\u662f\u4ec0\u4e48",
            context="ctx",
            history=history,
            standalone_question="\u8fd9\u4e2a\u4e1c\u897f\u7684\u4f5c\u7528\u662f\u4ec0\u4e48",
        )

        user_content = messages[1]["content"]
        self.assertIn("\u5bf9\u8bdd\u5386\u53f2", user_content)


if __name__ == "__main__":
    unittest.main()
