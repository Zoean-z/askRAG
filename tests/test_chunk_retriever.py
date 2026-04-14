import unittest
from types import SimpleNamespace
from unittest.mock import patch

from langchain_core.documents import Document

import app.retrievers.chunk_retriever as chunk_retriever
from app.rag import build_chat_messages, rewrite_question
from app.retrievers.reranker import rerank_chunk_results


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
            return_value=(empty_results, empty_results, empty_results, empty_results, empty_results),
        ) as mock_search:
            bundle = chunk_retriever.prepare_chunk_answer_material("\u4ec0\u4e48\u662f Chroma", history=history)

        self.assertEqual(bundle.rewritten_question, "\u4ec0\u4e48\u662f Chroma")
        self.assertEqual(mock_search.call_args.args[0], "\u4ec0\u4e48\u662f Chroma")

    def test_prepare_chunk_answer_material_uses_reference_history_before_rewrite(self):
        reference_history = [{"role": "assistant", "content": "Chroma \u53ef\u4ee5\u4f5c\u4e3a\u672c\u5730\u5411\u91cf\u5e93\u3002"}]
        empty_results: list[tuple[Document, float]] = []

        def fake_rewrite(question: str, history: list[dict[str, str]] | None = None) -> str:
            self.assertEqual(history, reference_history)
            return "Chroma \u7684\u4f5c\u7528\u662f\u4ec0\u4e48"

        with patch.object(chunk_retriever, "build_reference_history", return_value=reference_history), patch.object(
            chunk_retriever,
            "rewrite_question",
            side_effect=fake_rewrite,
        ), patch.object(
            chunk_retriever,
            "run_hybrid_chunk_search",
            return_value=(empty_results, empty_results, empty_results, empty_results, empty_results),
        ):
            bundle = chunk_retriever.prepare_chunk_answer_material("\u5b83\u7684\u4f5c\u7528\u662f\u4ec0\u4e48", history=[])

        self.assertEqual(bundle.history, reference_history)
        self.assertEqual(bundle.rewritten_question, "Chroma \u7684\u4f5c\u7528\u662f\u4ec0\u4e48")

    def test_prepare_chunk_answer_material_preserves_explicit_file_hint_after_rewrite(self):
        empty_results: list[tuple[Document, float]] = []

        with patch.object(chunk_retriever, "rewrite_question", return_value="Chroma 是做什么的"), patch.object(
            chunk_retriever,
            "run_hybrid_chunk_search",
            return_value=(empty_results, empty_results, empty_results, empty_results, empty_results),
        ) as mock_search:
            bundle = chunk_retriever.prepare_chunk_answer_material("project_intro.txt 里 Chroma 是做什么的")

        self.assertEqual(bundle.retrieval_debug["target_source_hint"], "project_intro.txt")
        self.assertEqual(bundle.retrieval_debug["resolved_target_source"], "data/docs/project_intro.txt")
        self.assertEqual(mock_search.call_args.kwargs["target_source_hint"], "project_intro.txt")


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
            return_value=(empty_results, empty_results, merged_results, merged_results, final_results),
        ):
            bundle = chunk_retriever.prepare_chunk_answer_material("what is this")

        self.assertEqual(bundle.sources, ["data/docs/a.txt"])


class ChunkRerankerTests(unittest.TestCase):
    def test_reranker_promotes_exact_phrase_match_over_generic_vector_hit(self):
        generic = Document(
            page_content="This article discusses UI complexity and interface design tradeoffs in general terms.",
            metadata={"source": "data/docs/ui.txt", "chunk_index": 0, "chunk_id": "generic"},
        )
        exact = Document(
            page_content="Progressive disclosure is a UX pattern that reveals advanced controls gradually.",
            metadata={"source": "data/docs/ui.txt", "chunk_index": 1, "chunk_id": "exact"},
        )

        reranked = rerank_chunk_results(
            "progressive disclosure",
            [(generic, 0.15), (exact, 0.65)],
            keywords=["progressive disclosure", "progressive", "disclosure"],
            vector_score_lookup={"generic": 0.15, "exact": 0.65},
            keyword_score_lookup={"generic": 0.5, "exact": 3.5},
            limit=2,
        )

        self.assertEqual(reranked[0][0].metadata["chunk_id"], "exact")

    def test_reranker_promotes_procedural_chunk_for_step_queries(self):
        generic = Document(
            page_content="Chroma can be used in local RAG systems and is often configured with embeddings.",
            metadata={"source": "data/docs/chroma.txt", "chunk_index": 0, "chunk_id": "generic"},
        )
        steps = Document(
            page_content="\u64cd\u4f5c\u6b65\u9aa4\n1. \u521d\u59cb\u5316 Chroma\n2. \u5199\u5165\u6587\u6863\u5207\u7247\n3. \u6267\u884c\u68c0\u7d22",
            metadata={"source": "data/docs/chroma.txt", "chunk_index": 1, "chunk_id": "steps"},
        )

        reranked = rerank_chunk_results(
            "Chroma \u5177\u4f53\u64cd\u4f5c\u6b65\u9aa4",
            [(generic, 0.12), (steps, 0.45)],
            keywords=["Chroma", "\u5177\u4f53\u64cd\u4f5c", "\u6b65\u9aa4"],
            vector_score_lookup={"generic": 0.12, "steps": 0.45},
            keyword_score_lookup={"generic": 1.0, "steps": 4.5},
            limit=2,
        )

        self.assertEqual(reranked[0][0].metadata["chunk_id"], "steps")

    def test_run_hybrid_chunk_search_reranks_before_neighbor_expansion(self):
        merged_results = [
            (Document(page_content="generic", metadata={"source": "data/docs/demo.txt", "chunk_index": 0, "chunk_id": "generic"}), 0.2),
            (Document(page_content="exact", metadata={"source": "data/docs/demo.txt", "chunk_index": 1, "chunk_id": "exact"}), 0.5),
        ]
        reranked_results = [merged_results[1], merged_results[0]]

        with patch.object(chunk_retriever, "retrieve_vector_documents", return_value=[]), patch.object(
            chunk_retriever, "keyword_search_documents", return_value=[]
        ), patch.object(chunk_retriever, "merge_retrieval_results", return_value=merged_results), patch.object(
            chunk_retriever, "rerank_retrieval_results", return_value=reranked_results
        ) as mock_rerank, patch.object(
            chunk_retriever, "expand_results_with_neighbors", return_value=reranked_results
        ) as mock_expand:
            _, _, _, _, final_results = chunk_retriever.run_hybrid_chunk_search("progressive disclosure")

        mock_rerank.assert_called_once()
        self.assertEqual(mock_expand.call_args.args[0], reranked_results)
        self.assertEqual(final_results, reranked_results)

    def test_run_hybrid_chunk_search_filters_vector_results_to_explicit_target_source(self):
        target_doc = Document(
            page_content="target",
            metadata={"source": "data/docs/project_intro.txt", "chunk_index": 0, "chunk_id": "target"},
        )
        other_doc = Document(
            page_content="other",
            metadata={"source": "data/docs/other.txt", "chunk_index": 0, "chunk_id": "other"},
        )
        merged_results = [(target_doc, 0.4)]

        with patch.object(
            chunk_retriever,
            "get_corpus_documents_by_source",
            return_value={
                "data/docs/project_intro.txt": Document(page_content="full target", metadata={"source": "data/docs/project_intro.txt"}),
                "data/docs/other.txt": Document(page_content="full other", metadata={"source": "data/docs/other.txt"}),
            },
        ), patch.object(
            chunk_retriever,
            "retrieve_vector_documents",
            return_value=[(other_doc, 0.1), (target_doc, 0.4)],
        ) as mock_vector, patch.object(
            chunk_retriever,
            "keyword_search_documents",
            return_value=[],
        ) as mock_keyword, patch.object(
            chunk_retriever,
            "merge_retrieval_results",
            return_value=merged_results,
        ) as mock_merge, patch.object(
            chunk_retriever,
            "rerank_retrieval_results",
            return_value=merged_results,
        ), patch.object(
            chunk_retriever,
            "expand_results_with_neighbors",
            return_value=merged_results,
        ):
            _, _, _, _, final_results = chunk_retriever.run_hybrid_chunk_search(
                "Chroma 是做什么的",
                target_source_hint="project_intro.txt",
            )

        self.assertEqual(mock_vector.call_args.kwargs["k"], 12)
        self.assertEqual(mock_keyword.call_args.kwargs["target_source_hint"], "data/docs/project_intro.txt")
        self.assertEqual(mock_merge.call_args.args[0], [(target_doc, 0.4)])
        self.assertEqual(final_results, merged_results)


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
