import unittest
from types import SimpleNamespace
from unittest.mock import patch

from langchain_core.documents import Document

from app.pipeline import (
    AnswerRunResult,
    DIRECT_ANSWER_NOTICE,
    WEB_SEARCH_OFFICIAL_QUERY_SUFFIX_ZH_ACTIVE,
    WEB_SEARCH_FAILURE_MESSAGE,
    _build_direct_web_search_queries,
    answer_directly,
    answer_directly_detailed,
    answer_local_summary_detailed,
    answer_question_detailed,
    answer_question,
    build_summary_verification_query,
    execute_chunk_path,
    stream_answer_question,
    stream_summarize_loaded_document,
)
from app.rag import REFUSAL_MESSAGE, rewrite_web_search_query
from app.retrievers.chunk_retriever import ChunkRetrievalBundle, RerankDiagnostics
from app.tool_router import build_tool_plan
from app.workflow import (
    _allow_target_hint_in_web_query,
    _build_focused_web_query,
    WEB_SUPPLEMENT_INSUFFICIENT_NOTICE,
    _assess_web_result_relevance,
    _extract_web_relevance_terms,
    _is_generic_web_relevance_term,
)


class _FakeCompletions:
    def create(self, **kwargs):
        if kwargs.get("stream"):
            return [
                SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content="Latest "))]),
                SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content="model answer."))]),
            ]
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="Latest model answer."))])


class _FakeChatClient:
    def __init__(self):
        self.chat = SimpleNamespace(completions=_FakeCompletions())


class _CapturingCompletions:
    def __init__(self, response_text="Latest model answer."):
        self.response_text = response_text
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if kwargs.get("stream"):
            midpoint = max(1, len(self.response_text) // 2)
            return [
                SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content=self.response_text[:midpoint]))]),
                SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content=self.response_text[midpoint:]))]),
            ]
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=self.response_text))])


class _CapturingChatClient:
    def __init__(self, response_text="Latest model answer."):
        self.completions = _CapturingCompletions(response_text)
        self.chat = SimpleNamespace(completions=self.completions)


class _FakeResponsesAPI:
    def __init__(self):
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if kwargs.get("stream"):
            completed_response = SimpleNamespace(
                output_text="Latest model answer.",
                output=[
                    {
                        "type": "web_search_call",
                        "action": {
                            "sources": [
                                {"title": "OpenAI Models", "url": "https://platform.openai.com/docs/models"}
                            ]
                        },
                    }
                ],
            )
            return [
                SimpleNamespace(type="response.output_text.delta", delta="Latest "),
                SimpleNamespace(type="response.output_text.delta", delta="model answer."),
                SimpleNamespace(type="response.completed", response=completed_response),
            ]
        return SimpleNamespace(
            output_text="Latest model answer.",
            output=[
                {
                    "type": "web_search_call",
                    "action": {
                        "sources": [
                            {"title": "OpenAI Models", "url": "https://platform.openai.com/docs/models"}
                        ]
                    },
                }
            ],
        )


class _FakeResponsesClient:
    def __init__(self):
        self.responses = _FakeResponsesAPI()


class _SummaryVerifyResponsesAPI:
    def __init__(self):
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(
            output_text="Chroma stores local vectors and the app supports Markdown uploads.",
            output=[
                {
                    "type": "web_search_call",
                    "action": {
                        "sources": [
                            {"title": "Project Intro Notes", "url": "https://example.com/project-intro"}
                        ]
                    },
                }
            ],
        )


class _SummaryVerifyResponsesClient:
    def __init__(self):
        self.responses = _SummaryVerifyResponsesAPI()


class _SecondAttemptResponsesAPI:
    def __init__(self):
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if len(self.calls) == 1:
            return SimpleNamespace(output_text="General design article.", output=[])
        return SimpleNamespace(
            output_text="Progressive disclosure is a UX pattern that reveals complexity gradually.",
            output=[
                {
                    "type": "web_search_call",
                    "action": {
                        "sources": [
                            {"title": "NN/g Progressive Disclosure", "url": "https://www.nngroup.com/articles/progressive-disclosure/"}
                        ]
                    },
                }
            ],
        )


class _SecondAttemptResponsesClient:
    def __init__(self):
        self.responses = _SecondAttemptResponsesAPI()


class _FallbackResponsesAPI:
    def __init__(self):
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if kwargs.get("tools") == [{"type": "web_search"}]:
            return SimpleNamespace(output_text="Unverified draft.", output=[])
        return SimpleNamespace(
            output_text="OpenAI model update verified from the changelog.",
            output=[
                {
                    "type": "web_search_call",
                    "action": {
                        "sources": [
                            {"title": "OpenAI Changelog", "url": "https://platform.openai.com/docs/changelog"}
                        ]
                    },
                }
            ],
        )


class _FallbackResponsesClient:
    def __init__(self):
        self.responses = _FallbackResponsesAPI()


class _IrrelevantResponsesAPI:
    def __init__(self):
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(
            output_text="These results discuss the June Fourth Incident and legal materials unrelated to the asked concept.",
            output=[
                {
                    "type": "web_search_call",
                    "action": {
                        "sources": [
                            {"title": "June Fourth Incident", "url": "https://zh.wikipedia.org/wiki/June_Fourth_Incident"}
                        ]
                    },
                }
            ],
        )


class _IrrelevantResponsesClient:
    def __init__(self):
        self.responses = _IrrelevantResponsesAPI()


class _RelevantUnofficialResponsesAPI:
    def __init__(self):
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(
            output_text="News reports claim the latest OpenAI model is GPT-6, according to unnamed sources.",
            output=[
                {
                    "type": "web_search_call",
                    "action": {
                        "sources": [
                            {"title": "AI News Daily", "url": "https://ainews.example.com/openai-gpt6-rumor"}
                        ]
                    },
                }
            ],
        )


class _RelevantUnofficialResponsesClient:
    def __init__(self):
        self.responses = _RelevantUnofficialResponsesAPI()


class _RaisingResponsesClient:
    def __init__(self, detail):
        self.detail = detail
        self.responses = self

    def create(self, **kwargs):
        raise ValueError(self.detail)


def _empty_bundle(history=None):
    return ChunkRetrievalBundle(
        rewritten_question="standalone question",
        vector_results=[],
        keyword_results=[],
        merged_results=[],
        results=[],
        sources=[],
        history=history or [],
    )


def _strong_local_bundle(history=None):
    result = (Document(page_content="Chroma is the local vector store.", metadata={"source": "data/docs/project_intro.txt", "chunk_index": 0, "chunk_id": "c-1"}), 0.4)
    return ChunkRetrievalBundle(
        rewritten_question="What is Chroma used for",
        vector_results=[result],
        keyword_results=[],
        merged_results=[result],
        results=[result],
        sources=["data/docs/project_intro.txt"],
        history=history or [],
    )


class PipelineDirectAnswerTests(unittest.TestCase):
    def setUp(self):
        self._provider_patchers = [
            patch("app.workflow.get_provider_family", return_value="dashscope"),
            patch("app.pipeline.get_provider_family", return_value="dashscope"),
        ]
        for patcher in self._provider_patchers:
            patcher.start()

    def tearDown(self):
        for patcher in reversed(getattr(self, "_provider_patchers", [])):
            patcher.stop()

    def test_direct_answer_includes_notice_prefix(self):
        answer, sources = answer_directly("hello")

        self.assertTrue(answer.startswith(DIRECT_ANSWER_NOTICE))
        self.assertEqual(sources, [])

    def test_answer_question_detailed_delegates_non_stream_dispatch_to_agent_graph(self):
        expected = AnswerRunResult(answer="Graph answer.", sources=[], trace={"mode": "direct_answer"})

        with (
            patch("app.pipeline.build_reference_history", return_value=[{"role": "user", "content": "normalized"}]) as history_mock,
            patch("app.agent_graph.run_agent_graph_detailed", return_value=expected) as graph_mock,
        ):
            result = answer_question_detailed("hello", history=[{"role": "user", "content": "raw"}], k=7)

        self.assertIs(result, expected)
        history_mock.assert_called_once_with("hello", [{"role": "user", "content": "raw"}])
        graph_mock.assert_called_once_with(
            "hello",
            history=[{"role": "user", "content": "normalized"}],
            k=7,
        )

    def test_stream_answer_question_delegates_stream_dispatch_to_agent_graph(self):
        expected_events = [("trace", {"mode": "direct_answer"}), ("done", {})]

        def _fake_stream(*args, **kwargs):
            for event in expected_events:
                yield event

        with (
            patch("app.pipeline.build_reference_history", return_value=[{"role": "user", "content": "normalized"}]) as history_mock,
            patch("app.agent_graph.run_agent_graph_stream", side_effect=_fake_stream) as graph_mock,
        ):
            events = list(stream_answer_question("hello", history=[{"role": "user", "content": "raw"}], k=7))

        self.assertEqual(events, expected_events)
        history_mock.assert_called_once_with("hello", [{"role": "user", "content": "raw"}])
        graph_mock.assert_called_once_with(
            "hello",
            history=[{"role": "user", "content": "normalized"}],
            k=7,
        )

    def test_answer_directly_applies_structured_response_constraints_to_system_prompt(self):
        chat_client = _CapturingChatClient(response_text="简短回答。")
        with patch("app.pipeline.build_response_constraints", return_value={"response_language": "zh-CN", "max_answer_chars": 100}), patch(
            "app.pipeline.get_chat_client", return_value=chat_client
        ):
            result = answer_directly_detailed("Please answer this quickly.")

        self.assertIn("Answer in Simplified Chinese.", chat_client.completions.calls[0]["messages"][0]["content"])
        self.assertIn("within 100 characters", chat_client.completions.calls[0]["messages"][0]["content"])
        self.assertTrue(result.answer.startswith(DIRECT_ANSWER_NOTICE))

    def test_stream_summary_emits_progress_events(self):
        document = Document(page_content="x" * 6000, metadata={"source": "data/docs/project_intro.txt"})
        with patch("app.pipeline.get_chat_client", return_value=_FakeChatClient()):
            events = list(stream_summarize_loaded_document(document, "summarize this file"))

        event_names = [name for name, _ in events]
        self.assertEqual(event_names[0], "sources")
        self.assertEqual(event_names[1], "progress")
        self.assertIn("progress", event_names)
        self.assertIn("trace", event_names)
        self.assertIn("delta", event_names)
        self.assertEqual(event_names[-1], "done")
        self.assertTrue(any(payload.get("stage") == "summary_overview" for name, payload in events if name == "progress"))

    def test_chunk_fallback_passes_existing_child_results_to_summary(self):
        merged_results = [
            (Document(page_content="chunk-1", metadata={"source": "data/docs/project_intro.txt", "chunk_id": "c-1"}), 0.1),
            (Document(page_content="chunk-2", metadata={"source": "data/docs/project_intro.txt", "chunk_id": "c-2"}), 0.2),
        ]
        bundle = ChunkRetrievalBundle(
            rewritten_question="rewritten question",
            vector_results=[],
            keyword_results=[],
            merged_results=merged_results,
            results=merged_results,
            sources=["data/docs/project_intro.txt"],
            history=[],
        )
        tool_plan = build_tool_plan(
            "local_doc_query",
            reason="test",
            fallback_tool="local_doc_summary",
        )

        with patch("app.pipeline.prepare_chunk_answer_material", return_value=bundle), patch(
            "app.pipeline.answer_local_summary",
            return_value=("summary answer", ["data/docs/project_intro.txt"]),
        ) as mock_summary:
            answer, sources = execute_chunk_path("How does this method work", tool_plan)

        self.assertEqual(answer, "summary answer")
        self.assertEqual(sources, ["data/docs/project_intro.txt"])
        self.assertEqual(mock_summary.call_args.kwargs["child_results"], merged_results)

    def test_build_summary_verification_query_uses_recent_summary_claims(self):
        history = [
            {"role": "user", "content": "summarize project_intro.txt"},
            {
                "role": "assistant",
                "content": "1. Chroma stores local vectors. 2. The app supports Markdown uploads. 3. Answers can be streamed.",
                "sources": ["data/docs/project_intro.txt"],
            },
        ]

        query = build_summary_verification_query("verify these claims online", history=history)

        self.assertIn("project_intro", query)
        self.assertIn("Chroma stores local vectors", query)
        self.assertIn("The app supports Markdown uploads", query)

    def test_build_summary_verification_query_uses_reference_history_reconstruction(self):
        reconstructed_history = [
            {"role": "user", "content": "summarize project_intro.txt"},
            {
                "role": "assistant",
                "content": "Chroma stores local vectors. The app supports Markdown uploads.",
                "sources": ["data/docs/project_intro.txt"],
            },
        ]

        with patch("app.pipeline.build_reference_history", return_value=reconstructed_history):
            query = build_summary_verification_query("verify these claims online", history=[])

        self.assertIn("project_intro", query)
        self.assertIn("Chroma stores local vectors", query)

    def test_answer_local_summary_detailed_uses_reference_history(self):
        reference_history = [{"role": "assistant", "content": "summary context", "sources": ["data/docs/project_intro.txt"]}]
        document = Document(page_content="content", metadata={"source": "data/docs/project_intro.txt"})
        expected = AnswerRunResult(
            answer="summary answer",
            sources=["data/docs/project_intro.txt"],
            trace={"mode": "summary"},
        )

        with patch("app.pipeline.build_reference_history", return_value=reference_history), patch(
            "app.pipeline.choose_summary_document",
            return_value=document,
        ) as mock_choose, patch(
            "app.pipeline.summarize_loaded_document_detailed",
            return_value=expected,
        ) as mock_summarize:
            result = answer_local_summary_detailed("再短一点", history=[])

        self.assertEqual(result, expected)
        self.assertEqual(mock_choose.call_args.kwargs["history"], reference_history)
        self.assertEqual(mock_summarize.call_args.kwargs["history"], reference_history)

    def test_answer_local_summary_applies_structured_response_constraints_to_system_prompt(self):
        document = Document(page_content="content", metadata={"source": "data/docs/project_intro.txt"})
        chat_client = _CapturingChatClient(response_text="summary answer")

        with patch("app.pipeline.choose_summary_document", return_value=document), patch(
            "app.pipeline.build_response_constraints", return_value={"response_language": "zh-CN", "max_answer_chars": 100}
        ), patch(
            "app.pipeline.get_chat_client", return_value=chat_client
        ):
            result = answer_local_summary_detailed("summarize project_intro.txt", history=[])

        self.assertEqual(result.answer, "summary answer")
        self.assertIn("Answer in Simplified Chinese.", chat_client.completions.calls[0]["messages"][0]["content"])
        self.assertIn("within 100 characters", chat_client.completions.calls[0]["messages"][0]["content"])

    def test_answer_question_uses_workflow_local_only_when_sufficient(self):
        bundle = _strong_local_bundle()
        with patch("app.workflow.prepare_chunk_answer_material", return_value=bundle), patch(
            "app.workflow.get_chat_client", return_value=_FakeChatClient()
        ), patch("app.workflow.get_responses_client") as mock_responses:
            answer, sources = answer_question("What is Chroma used for?")

        self.assertEqual(answer, "Latest model answer.")
        self.assertEqual(sources, ["data/docs/project_intro.txt"])
        mock_responses.assert_not_called()

    def test_answer_question_plain_doc_question_uses_probe_before_web_fallback(self):
        with patch(
            "app.agent_graph.extract_router_hints",
            return_value=SimpleNamespace(
                doc_candidate=False,
                summary_candidate=False,
                web_candidate=False,
                direct_answer_candidate=False,
                followup_candidate=False,
                target_source_hint=None,
                needs_freshness=False,
                use_history=False,
            ),
        ), patch(
            "app.agent_tools.probe_local_docs",
            return_value=SimpleNamespace(has_hits=True, top_sources=["data/docs/project_intro.txt"], validation=None),
        ), patch(
            "app.agent_tools.search_kb_chroma",
            return_value=SimpleNamespace(
                bundle=_strong_local_bundle(),
                validation=SimpleNamespace(is_sufficient=True, reason="keyword_match_strong_enough"),
            ),
        ), patch(
            "app.agent_tools.initialize_retrieval_workflow_state",
            return_value=SimpleNamespace(
                status="running",
                needs_web=False,
                decision_reason="local_evidence_sufficient",
                trace={"mode": "query"},
            ),
        ), patch(
            "app.agent_tools.apply_local_kb_search_result"
        ), patch(
            "app.agent_tools.assess_local_retrieval_followup",
            return_value=SimpleNamespace(needs_web=False, decision_reason="local_evidence_sufficient"),
        ), patch(
            "app.agent_tools.finalize_retrieval_result",
            return_value=SimpleNamespace(answer="Latest model answer.", sources=["data/docs/project_intro.txt"], trace={"mode": "query"}),
        ), patch("app.workflow.get_responses_client") as mock_responses:
            answer, sources = answer_question("What does the harness file say about Codex?")

        self.assertEqual(answer, "Latest model answer.")
        self.assertEqual(sources, ["data/docs/project_intro.txt"])
        mock_responses.assert_not_called()

    def test_answer_question_chinese_doc_question_uses_probe_before_web_fallback(self):
        call_order = []

        def _search_kb_chroma(*args, **kwargs):
            call_order.append("retrieval")
            return SimpleNamespace(
                bundle=_strong_local_bundle(),
                validation=SimpleNamespace(is_sufficient=False, reason="best_vector_score_above_threshold"),
            )

        def _run_retrieval_web_search_step(state):
            call_order.append("web")
            return state

        def _run_retrieval_web_extract_step(state):
            call_order.append("web_extract")
            return state

        with patch(
            "app.agent_graph.extract_router_hints",
            return_value=SimpleNamespace(
                doc_candidate=False,
                summary_candidate=False,
                web_candidate=False,
                direct_answer_candidate=False,
                followup_candidate=False,
                target_source_hint=None,
                needs_freshness=False,
                use_history=False,
                force_web_only=False,
                force_local_only=False,
            ),
        ), patch(
            "app.agent_tools.probe_local_docs",
            return_value=SimpleNamespace(has_hits=True, top_sources=["data/docs/project_intro.txt"], validation=None),
        ), patch(
            "app.agent_tools.search_kb_chroma",
            side_effect=_search_kb_chroma,
        ), patch(
            "app.agent_tools.load_long_term_context",
            return_value=SimpleNamespace(reference_history=[], memory_context=""),
        ), patch(
            "app.agent_tools.load_response_constraints",
            return_value={},
        ), patch(
            "app.agent_tools.run_retrieval_web_search_step",
            side_effect=_run_retrieval_web_search_step,
        ), patch(
            "app.agent_tools.run_retrieval_web_extract_step",
            side_effect=_run_retrieval_web_extract_step,
        ), patch(
            "app.agent_tools.finalize_retrieval_result",
            return_value=SimpleNamespace(
                answer="Chroma is the local vector store.",
                sources=["data/docs/project_intro.txt"],
                trace={"mode": "query"},
            ),
        ):
            answer, sources = answer_question("Chroma 是用来做什么的？")

        self.assertEqual(answer, "Chroma is the local vector store.")
        self.assertEqual(sources, ["data/docs/project_intro.txt"])
        self.assertIn("retrieval", call_order)
        if "web" in call_order:
            self.assertLess(call_order.index("retrieval"), call_order.index("web"))

    def test_execute_chunk_path_applies_structured_response_constraints_to_system_prompt(self):
        bundle = _strong_local_bundle()
        tool_plan = build_tool_plan("local_doc_query", reason="test")
        chat_client = _CapturingChatClient(response_text="Chroma answer.")

        with patch("app.pipeline.prepare_chunk_answer_material", return_value=bundle), patch(
            "app.pipeline.build_response_constraints", return_value={"response_language": "zh-CN", "max_answer_chars": 100}
        ), patch(
            "app.pipeline.get_chat_client", return_value=chat_client
        ):
            answer, sources = execute_chunk_path("What is Chroma used for?", tool_plan)

        self.assertEqual(answer, "Chroma answer.")
        self.assertEqual(sources, ["data/docs/project_intro.txt"])
        self.assertIn("Answer in Simplified Chinese.", chat_client.completions.calls[0]["messages"][0]["content"])
        self.assertIn("within 100 characters", chat_client.completions.calls[0]["messages"][0]["content"])

    def test_answer_question_uses_lightweight_summary_verify_web_search(self):
        fake_client = _SummaryVerifyResponsesClient()
        memory_history = [
            {"role": "user", "content": "summarize project_intro.txt"},
            {
                "role": "assistant",
                "content": "Chroma stores local vectors. The app supports Markdown uploads. Answers can be streamed.",
                "sources": ["data/docs/project_intro.txt"],
            },
        ]
        with patch("app.pipeline.build_reference_history", return_value=memory_history), patch(
            "app.workflow.prepare_chunk_answer_material", return_value=_empty_bundle(memory_history)
        ), patch(
            "app.workflow.get_responses_client", return_value=fake_client
        ), patch("app.workflow.get_web_search_model", return_value="qwen3.5-plus"), patch(
            "app.workflow.get_chat_client", return_value=_FakeChatClient()
        ):
            answer, sources = answer_question("verify these claims online", history=[])

        self.assertEqual(answer, "Latest model answer.")
        self.assertEqual(sources, ["Project Intro Notes (https://example.com/project-intro)"])
        self.assertEqual(fake_client.responses.calls[0]["model"], "qwen3.5-plus")
        self.assertEqual(fake_client.responses.calls[0]["tools"], [{"type": "web_search"}])
        self.assertFalse(fake_client.responses.calls[0]["extra_body"]["enable_thinking"])
        self.assertIn("Chroma stores local vectors", fake_client.responses.calls[0]["input"])

    def test_answer_question_retries_lightweight_web_search_with_focused_query(self):
        fake_client = _SecondAttemptResponsesClient()
        with patch("app.workflow.prepare_chunk_answer_material", return_value=_empty_bundle()), patch(
            "app.workflow.get_responses_client", return_value=fake_client
        ), patch("app.workflow.get_web_search_model", return_value="qwen3.5-plus"), patch(
            "app.workflow.get_chat_client", return_value=_FakeChatClient()
        ):
            answer, sources = answer_question("search the web and explain progressive disclosure in detail")

        self.assertEqual(answer, "Latest model answer.")
        self.assertEqual(sources, ["NN/g Progressive Disclosure (https://www.nngroup.com/articles/progressive-disclosure/)"])
        self.assertEqual(len(fake_client.responses.calls), 2)
        self.assertEqual(fake_client.responses.calls[0]["tools"], [{"type": "web_search"}])
        self.assertEqual(fake_client.responses.calls[1]["tools"], [{"type": "web_search"}])
        self.assertNotEqual(fake_client.responses.calls[0]["input"], fake_client.responses.calls[1]["input"])

    def test_answer_question_falls_back_to_web_extract_when_light_evidence_is_insufficient(self):
        fake_client = _FallbackResponsesClient()
        with patch("app.workflow.prepare_chunk_answer_material", return_value=_empty_bundle()), patch(
            "app.workflow.get_responses_client", return_value=fake_client
        ), patch("app.workflow.get_web_search_model", return_value="qwen3.5-plus"), patch(
            "app.workflow.get_chat_client", return_value=_FakeChatClient()
        ):
            answer, sources = answer_question("What is the latest OpenAI model today?")

        self.assertEqual(answer, "Latest model answer.")
        self.assertEqual(sources, ["OpenAI Changelog (https://platform.openai.com/docs/changelog)"])
        self.assertEqual(len(fake_client.responses.calls), 3)
        self.assertEqual(fake_client.responses.calls[0]["tools"], [{"type": "web_search"}])
        self.assertEqual(fake_client.responses.calls[1]["tools"], [{"type": "web_search"}])
        self.assertNotEqual(fake_client.responses.calls[0]["input"], fake_client.responses.calls[1]["input"])
        self.assertEqual(fake_client.responses.calls[2]["tools"], [{"type": "web_search"}, {"type": "web_extractor"}])
        self.assertEqual(fake_client.responses.calls[2]["input"], fake_client.responses.calls[1]["input"])

    def test_rewrite_web_search_query_cleans_boilerplate_without_llm(self):
        with patch("app.rag.get_chat_client") as chat_mock:
            result = rewrite_web_search_query("帮我搜一下 Chroma 是做什么的")

        self.assertEqual(result.raw_query, "帮我搜一下 Chroma 是做什么的")
        self.assertEqual(result.normalized_query, "Chroma 是做什么的")
        self.assertFalse(result.rewrite_used)
        self.assertEqual(result.selected_query, "Chroma 是做什么的")
        self.assertEqual(result.resolved_references, [])
        chat_mock.assert_not_called()

    def test_rewrite_web_search_query_resolves_pronouns_with_history(self):
        recent_history = [
            {"role": "user", "content": "我们在聊甘雨和剧情。"},
            {"role": "assistant", "content": "甘雨是璃月角色。"},
        ]
        chat_client = _CapturingChatClient(response_text="甘雨 剧情 妹妹")

        with patch("app.session_memory.build_reference_history", return_value=recent_history), patch(
            "app.rag.get_chat_client", return_value=chat_client
        ):
            result = rewrite_web_search_query("联网搜索一下他的剧情，我记得他有个妹妹", history=[])

        self.assertTrue(result.rewrite_used)
        self.assertEqual(result.rewritten_query, "甘雨 剧情 妹妹")
        self.assertEqual(result.selected_query, "甘雨 剧情 妹妹")
        self.assertIn("他的", result.resolved_references)
        self.assertIn("我记得", result.resolved_references)
        self.assertEqual(len(chat_client.completions.calls), 1)
        self.assertIn("Recent conversation history", chat_client.completions.calls[0]["messages"][1]["content"])
        self.assertIn("甘雨", chat_client.completions.calls[0]["messages"][1]["content"])

    def test_answer_question_routes_general_web_search_directly(self):
        fake_client = _FakeResponsesClient()
        explicit_web_plan = build_tool_plan(
            "web_search",
            reason="test_explicit_web_direct",
            intent="web_search",
            needs_freshness=True,
        )

        with patch("app.pipeline.decide_tool_plan", return_value=explicit_web_plan), patch(
            "app.pipeline.get_responses_client", return_value=fake_client
        ), patch("app.pipeline.get_web_search_model", return_value="qwen3.5-plus"), patch(
            "app.pipeline.get_chat_client", return_value=_FakeChatClient()
        ), patch(
            "app.workflow.run_answer_workflow_detailed"
        ) as mock_workflow:
            result = answer_question_detailed("What is the latest OpenAI model today?")

        self.assertEqual(result.answer, "Latest model answer.")
        self.assertEqual(result.sources, ["OpenAI Models (https://platform.openai.com/docs/models)"])
        self.assertEqual(result.trace["mode"], "web_search")
        self.assertEqual(fake_client.responses.calls[0]["model"], "qwen3.5-plus")
        self.assertEqual(fake_client.responses.calls[0]["tools"][0]["type"], "web_search")
        mock_workflow.assert_not_called()

    def test_answer_question_uses_local_answer_with_web_caveat_when_web_is_insufficient(self):
        fake_client = _IrrelevantResponsesClient()
        bundle = _strong_local_bundle()
        with patch("app.workflow.prepare_chunk_answer_material", return_value=bundle), patch(
            "app.workflow.get_responses_client", return_value=fake_client
        ), patch("app.workflow.get_web_search_model", return_value="qwen3.5-plus"), patch(
            "app.workflow.get_chat_client", return_value=_FakeChatClient()
        ):
            answer, sources = answer_question("search the web and explain Chroma in detail")

        self.assertIn("Latest model answer.", answer)
        self.assertIn(WEB_SUPPLEMENT_INSUFFICIENT_NOTICE, answer)
        self.assertEqual(sources, ["data/docs/project_intro.txt"])

    def test_answer_question_meta_followup_does_not_auto_fallback_to_web_after_empty_local(self):
        history = [{"role": "assistant", "content": "上一条回答。"}]
        followup_plan = build_tool_plan(
            "local_doc_query",
            reason="test_followup_guardrail",
            intent="doc_query",
            confidence=0.52,
            use_history=True,
        )

        with patch("app.agent_graph.extract_router_hints", return_value=SimpleNamespace(doc_candidate=True, summary_candidate=False, web_candidate=False, direct_answer_candidate=False, followup_candidate=True, target_source_hint=None, needs_freshness=False, use_history=True)), patch(
            "app.agent_tools.probe_local_docs", return_value=SimpleNamespace(has_hits=False, top_sources=[], validation=None)
        ), patch(
            "app.workflow.prepare_chunk_answer_material", return_value=_empty_bundle(history)
        ), patch("app.workflow.get_responses_client") as mock_responses, patch(
            "app.workflow.get_chat_client"
        ) as mock_chat:
            answer, sources = answer_question("上次回答超过一百字了吗", history=history)

        self.assertEqual(answer, REFUSAL_MESSAGE)
        self.assertEqual(sources, [])
        mock_responses.assert_not_called()
        mock_chat.assert_not_called()

    def test_answer_question_file_anchored_query_stays_local_when_asking_file_content(self):
        target_result = (
            Document(page_content="Chroma is the local vector store.", metadata={"source": "data/docs/project_intro.txt", "chunk_index": 0, "chunk_id": "target"}),
            2.5,
        )
        bundle = ChunkRetrievalBundle(
            rewritten_question="project_intro.txt 里 Chroma 是用来做什么的？",
            vector_results=[],
            keyword_results=[target_result],
            merged_results=[target_result],
            reranked_results=[target_result],
            results=[target_result],
            sources=["data/docs/project_intro.txt"],
            history=[],
            retrieval_debug={"backend": "chroma", "target_source_hint": "project_intro.txt", "resolved_target_source": "data/docs/project_intro.txt"},
        )
        file_query_plan = build_tool_plan(
            "local_doc_query",
            reason="test_file_anchor_local",
            intent="doc_query",
            target_source_hint="project_intro.txt",
        )

        with patch("app.pipeline.decide_tool_plan", return_value=file_query_plan), patch(
            "app.workflow.prepare_chunk_answer_material", return_value=bundle
        ), patch("app.workflow.get_chat_client", return_value=_FakeChatClient()), patch(
            "app.workflow.get_responses_client"
        ) as mock_responses:
            answer, sources = answer_question("project_intro.txt 里 Chroma 是用来做什么的？")

        self.assertEqual(answer, "Latest model answer.")
        self.assertEqual(sources, ["data/docs/project_intro.txt"])
        mock_responses.assert_not_called()

    def test_answer_question_file_anchored_verification_query_can_still_use_web(self):
        target_result = (
            Document(page_content="Chroma is the local vector store.", metadata={"source": "data/docs/project_intro.txt", "chunk_index": 0, "chunk_id": "target"}),
            2.5,
        )
        bundle = ChunkRetrievalBundle(
            rewritten_question="project_intro.txt 里 Chroma 现在还对吗？",
            vector_results=[],
            keyword_results=[target_result],
            merged_results=[target_result],
            reranked_results=[target_result],
            results=[target_result],
            sources=["data/docs/project_intro.txt"],
            history=[],
            retrieval_debug={"backend": "chroma", "target_source_hint": "project_intro.txt", "resolved_target_source": "data/docs/project_intro.txt"},
        )
        file_query_plan = build_tool_plan(
            "local_doc_query",
            reason="test_file_anchor_web_allowed",
            intent="doc_query",
            target_source_hint="project_intro.txt",
        )
        fake_client = _FakeResponsesClient()

        with patch("app.pipeline.decide_tool_plan", return_value=file_query_plan), patch(
            "app.workflow.prepare_chunk_answer_material", return_value=bundle
        ), patch("app.workflow.get_responses_client", return_value=fake_client), patch(
            "app.workflow.get_web_search_model", return_value="qwen3.5-plus"
        ), patch("app.workflow.get_chat_client", return_value=_FakeChatClient()):
            answer, sources = answer_question("project_intro.txt 里 Chroma 现在还对吗？")

        self.assertTrue(answer)
        self.assertGreaterEqual(len(fake_client.responses.calls), 1)

    def test_answer_question_returns_inconclusive_message_when_web_results_are_irrelevant(self):
        fake_client = _IrrelevantResponsesClient()
        explicit_web_plan = build_tool_plan(
            "web_search",
            reason="test_irrelevant_web_direct",
            intent="web_search",
            needs_freshness=True,
        )
        with patch("app.pipeline.decide_tool_plan", return_value=explicit_web_plan), patch(
            "app.pipeline.get_responses_client", return_value=fake_client
        ), patch(
            "app.pipeline.get_web_search_model", return_value="qwen3.5-plus"
        ), patch(
            "app.workflow.get_responses_client", return_value=fake_client
        ), patch(
            "app.workflow.get_web_search_model", return_value="qwen3.5-plus"
        ), patch(
            "app.pipeline.get_chat_client"
        ) as mock_chat:
            answer, sources = answer_question("\u7528\u7f51\u7edc\u641c\u7d22\u529f\u80fd\u89e3\u91ca61\u5c40\u9650\u662f\u4ec0\u4e48")

        self.assertIn("无法可靠回答", answer)
        self.assertEqual(sources, [])
        self.assertGreaterEqual(len(fake_client.responses.calls), 1)
        self.assertEqual(fake_client.responses.calls[0]["tools"][0]["type"], "web_search")
        mock_chat.assert_not_called()

    def test_answer_question_uses_qwen_responses_web_search(self):
        fake_client = _FakeResponsesClient()
        with patch("app.pipeline.get_responses_client", return_value=fake_client), patch(
            "app.pipeline.get_web_search_model", return_value="qwen3.5-plus"
        ), patch(
            "app.pipeline.get_chat_client", return_value=_FakeChatClient()
        ):
            answer, sources = answer_question("What is the latest OpenAI model today?")

        self.assertEqual(answer, "Latest model answer.")
        self.assertEqual(sources, ["OpenAI Models (https://platform.openai.com/docs/models)"])
        self.assertEqual(fake_client.responses.calls[0]["model"], "qwen3.5-plus")
        self.assertEqual(fake_client.responses.calls[0]["tools"][0]["type"], "web_search")

    def test_stream_answer_question_streams_qwen_responses_web_search(self):
        fake_client = _FakeResponsesClient()
        with patch("app.pipeline.get_responses_client", return_value=fake_client), patch(
            "app.pipeline.get_web_search_model", return_value="qwen3.5-plus"
        ), patch(
            "app.pipeline.get_chat_client", return_value=_FakeChatClient()
        ):
            events = list(stream_answer_question("What is the latest OpenAI model today?"))

        stages = [payload.get("stage") for name, payload in events if name == "progress"]
        self.assertIn("web_search_start", stages)
        self.assertIn("web_search_quality", stages)
        self.assertNotIn("workflow_web_search", stages)
        self.assertTrue(any(name == "trace" and payload.get("mode") == "web_search" for name, payload in events))
        self.assertTrue(any(name == "delta" and payload == {"text": "Latest model answer."} for name, payload in events))
        self.assertTrue(any(name == "sources" and payload == {"sources": ["OpenAI Models (https://platform.openai.com/docs/models)"]} for name, payload in events))
        self.assertEqual(events[-1], ("done", {}))

    def test_stream_answer_question_routes_summary_verify_web_search_through_graph_tool_path(self):
        expected_events = [
            ("progress", {"stage": "web_search_start"}),
            ("trace", {"mode": "web_search", "web_search_mode": "summary_verify"}),
            ("sources", {"sources": ["Project Intro Notes (https://example.com/project-intro)"]}),
            ("delta", {"text": "Chroma stores local vectors and the app supports Markdown uploads."}),
            ("done", {}),
        ]

        def _fake_stream(*args, **kwargs):
            for event in expected_events:
                yield event

        with (
            patch("app.agent_graph.extract_router_hints", return_value=SimpleNamespace(doc_candidate=False, summary_candidate=False, web_candidate=False, direct_answer_candidate=False, followup_candidate=False, target_source_hint=None, needs_freshness=False, use_history=True)),
            patch("app.agent_tools.probe_local_docs", return_value=SimpleNamespace(has_hits=False, top_sources=[], validation=None)),
            patch("app.agent_tools.stream_web_search_tool", side_effect=_fake_stream) as stream_mock,
            patch("app.agent_tools.persist_turn_memory_result", return_value=SimpleNamespace(stored_entries=[], memory_notices=[])),
            patch("app.workflow.stream_answer_workflow") as legacy_mock,
            patch("app.tool_router.find_recent_summary_context", return_value=SimpleNamespace(user_question="summarize", assistant_answer="summary", sources=["data/docs/project_intro.txt"])),
        ):
            events = list(
                stream_answer_question(
                    "verify these claims online",
                    history=[{"role": "assistant", "content": "Chroma stores local vectors."}],
                )
            )

        self.assertEqual(events, expected_events)
        stream_mock.assert_called_once()
        legacy_mock.assert_not_called()

    def test_stream_answer_question_routes_summary_plus_web_through_graph_summary_strategy(self):
        summary_plan = build_tool_plan(
            "local_doc_summary",
            reason="matched_summary_rule",
            intent="doc_summary",
        )
        summary_result = AnswerRunResult(
            answer="local summary",
            sources=["data/docs/harness.txt"],
            trace={"mode": "summary"},
        )
        web_result = AnswerRunResult(
            answer="web supplement",
            sources=["https://example.com"],
            trace={"mode": "web_search"},
        )
        expected_events = [
            ("progress", {"stage": "summary_web_compose"}),
            ("done", {}),
        ]

        def _fake_stream(*args, **kwargs):
            for event in expected_events:
                yield event

        with (
            patch("app.agent_graph.extract_router_hints", return_value=SimpleNamespace(doc_candidate=False, summary_candidate=True, web_candidate=True, direct_answer_candidate=False, followup_candidate=False, target_source_hint=None, needs_freshness=False, use_history=False)),
            patch("app.agent_tools.probe_local_docs", return_value=SimpleNamespace(has_hits=False, top_sources=[], validation=None)),
            patch("app.agent_tools.decide_summary_strategy", return_value=SimpleNamespace(strategy="summary_plus_web")),
            patch("app.agent_tools.read_summary", return_value=summary_result) as summary_mock,
            patch("app.agent_tools.run_summary_web_search_result", return_value=web_result) as web_mock,
            patch("app.agent_tools.stream_compose_summary_with_web_result", side_effect=_fake_stream) as compose_mock,
            patch("app.agent_tools.persist_turn_memory_result", return_value=SimpleNamespace(stored_entries=[], memory_notices=[])),
        ):
            events = list(stream_answer_question("summarize this file and search the web", history=[]))

        self.assertEqual(events, expected_events)
        summary_mock.assert_called_once()
        web_mock.assert_called_once()
        compose_mock.assert_called_once()

    def test_answer_question_returns_web_search_fallback_message_on_failure(self):
        with patch("app.pipeline.get_responses_client", side_effect=ValueError("responses unavailable")
        ):
            answer, sources = answer_question("What is the latest OpenAI model today?")

        self.assertIn(WEB_SEARCH_FAILURE_MESSAGE, answer)
        self.assertIn("responses unavailable", answer)
        self.assertEqual(sources, [])

    def test_stream_answer_question_returns_web_search_fallback_message_on_failure(self):
        with patch("app.pipeline.get_responses_client", side_effect=ValueError("responses unavailable")
        ):
            events = list(stream_answer_question("What is the latest OpenAI model today?"))

        stages = [payload.get("stage") for name, payload in events if name == "progress"]
        self.assertIn("web_search_start", stages)
        self.assertIn("web_search_failed", stages)
        self.assertTrue(any(name == "delta" and WEB_SEARCH_FAILURE_MESSAGE in payload.get("text", "") for name, payload in events))
        self.assertTrue(any(name == "delta" and "responses unavailable" in payload.get("text", "") for name, payload in events))
        self.assertEqual(events[-1], ("done", {}))

    def test_answer_question_reports_provider_failure_when_web_provider_errors(self):
        bundle = _strong_local_bundle()
        with (
            patch("app.agent_tools.probe_local_docs", return_value=SimpleNamespace(has_hits=True, top_sources=["data/docs/efls.txt"], validation=SimpleNamespace(is_sufficient=False))),
            patch("app.workflow.prepare_chunk_answer_material", return_value=bundle),
            patch("app.workflow.get_responses_client", side_effect=ValueError("responses unavailable")),
            patch("app.workflow.get_web_search_model", return_value="qwen3.5-plus"),
            patch("app.workflow.get_chat_client", return_value=_FakeChatClient()),
        ):
            result = answer_question_detailed("\u8bf7\u8054\u7f51\u641c\u7d22\u5384\u6590\u7409\u65af\u4ecb\u7ecd")

        self.assertIn(WEB_SEARCH_FAILURE_MESSAGE, result.answer)
        self.assertIn("responses unavailable", result.answer)
        self.assertEqual(result.sources, [])

    def test_answer_question_rejects_relevant_but_unofficial_fresh_web_results(self):
        fake_client = _RelevantUnofficialResponsesClient()
        with patch("app.pipeline.get_responses_client", return_value=fake_client), patch(
            "app.pipeline.get_web_search_model", return_value="qwen3.5-plus"
        ), patch(
            "app.pipeline.get_chat_client"
        ) as mock_chat:
            answer, sources = answer_question("What is the latest OpenAI model today?")

        self.assertIn("无法可靠回答", answer)
        self.assertEqual(sources, [])
        self.assertGreaterEqual(len(fake_client.responses.calls), 1)
        mock_chat.assert_not_called()

    def test_stream_answer_question_uses_local_answer_with_web_caveat_when_web_is_insufficient(self):
        fake_client = _IrrelevantResponsesClient()
        bundle = _strong_local_bundle()
        web_request_plan = build_tool_plan(
            "local_doc_query",
            reason="test_stream_local_with_web_caveat",
            intent="doc_query",
            needs_freshness=True,
        )
        with patch("app.agent_graph.extract_router_hints", return_value=SimpleNamespace(doc_candidate=False, summary_candidate=False, web_candidate=True, direct_answer_candidate=False, followup_candidate=False, target_source_hint=None, needs_freshness=True, use_history=False)), patch(
            "app.agent_tools.probe_local_docs", return_value=SimpleNamespace(has_hits=True, top_sources=["data/docs/project_intro.txt"], validation=None)
        ), patch(
            "app.workflow.prepare_chunk_answer_material", return_value=bundle
        ), patch(
            "app.workflow.get_responses_client", return_value=fake_client
        ), patch("app.workflow.get_web_search_model", return_value="qwen3.5-plus"), patch(
            "app.workflow.get_chat_client", return_value=_FakeChatClient()
        ):
            events = list(stream_answer_question("search the web and explain Chroma in detail"))

        self.assertTrue(any(name == "sources" and payload == {"sources": ["data/docs/project_intro.txt"]} for name, payload in events))
        self.assertTrue(any(name == "delta" and payload == {"text": "Latest "} for name, payload in events))
        self.assertTrue(any(name == "delta" and WEB_SUPPLEMENT_INSUFFICIENT_NOTICE in payload.get("text", "") for name, payload in events))
        self.assertEqual(events[-1], ("done", {}))

    def test_stream_answer_question_meta_followup_does_not_emit_web_stage_after_empty_local(self):
        history = [{"role": "assistant", "content": "上一条回答。"}]
        followup_plan = build_tool_plan(
            "local_doc_query",
            reason="test_followup_guardrail",
            intent="doc_query",
            confidence=0.52,
            use_history=True,
        )

        with patch("app.agent_graph.extract_router_hints", return_value=SimpleNamespace(doc_candidate=True, summary_candidate=False, web_candidate=False, direct_answer_candidate=False, followup_candidate=True, target_source_hint=None, needs_freshness=False, use_history=True)), patch(
            "app.agent_tools.probe_local_docs", return_value=SimpleNamespace(has_hits=False, top_sources=[], validation=None)
        ), patch(
            "app.workflow.prepare_chunk_answer_material", return_value=_empty_bundle(history)
        ), patch("app.workflow.get_responses_client") as mock_responses, patch(
            "app.workflow.get_chat_client"
        ) as mock_chat:
            events = list(stream_answer_question("上次回答超过一百字了吗", history=history))

        stages = [payload.get("stage") for name, payload in events if name == "progress"]
        self.assertNotIn("workflow_web_search", stages)
        self.assertTrue(any(name == "delta" and payload == {"text": REFUSAL_MESSAGE} for name, payload in events))
        self.assertEqual(events[-1], ("done", {}))
        mock_responses.assert_not_called()
        mock_chat.assert_not_called()


    def test_web_relevance_rejects_single_source_overlap_without_answer_support(self):
        score, relevant = _assess_web_result_relevance(
            "What is the latest OpenAI model today?",
            "The announcement is available online.",
            ["OpenAI homepage (https://openai.com)"],
        )

        self.assertFalse(relevant)
        self.assertLess(score, 3.5)

    def test_web_relevance_accepts_multi_term_support_across_answer_and_sources(self):
        score, relevant = _assess_web_result_relevance(
            "What is the latest OpenAI model today?",
            "The latest model answer names the current model family.",
            ["OpenAI Models (https://platform.openai.com/docs/models)"],
        )

        self.assertTrue(relevant)
        self.assertGreaterEqual(score, 3.5)

    def test_web_relevance_accepts_single_anchor_query(self):
        score, relevant = _assess_web_result_relevance(
            "Chroma",
            "Chroma is the local vector store used by the app.",
            [],
        )

        self.assertTrue(relevant)
        self.assertGreaterEqual(score, 2.0)

    def test_web_relevance_generic_fragments_treat_chinese_boilerplate_as_generic(self):
        self.assertTrue(_is_generic_web_relevance_term("这些说法"))

    def test_extract_web_relevance_terms_filters_chinese_web_search_boilerplate(self):
        terms = _extract_web_relevance_terms("使用网络搜索核实这些说法是否准确")

        self.assertEqual(terms, [])

    def test_answer_question_uses_glm_web_search_api(self):
        glm_payload = {
            "search_result": [
                {
                    "title": "OpenAI Models",
                    "content": "OpenAI's latest flagship model is GPT-5.4 according to the official models page.",
                    "link": "https://platform.openai.com/docs/models",
                    "media": "OpenAI",
                    "publish_date": "2026-03-06",
                }
            ]
        }
        with patch("app.workflow.get_provider_family", return_value="glm"), patch(
            "app.pipeline.get_provider_family", return_value="glm"
        ), patch("app.workflow.is_web_search_enabled", return_value=True), patch(
            "app.pipeline.is_web_search_enabled", return_value=True
        ), patch(
            "app.pipeline.run_glm_web_search", return_value=glm_payload
        ), patch(
            "app.pipeline.get_chat_client", return_value=_FakeChatClient()
        ) as mock_search:
            answer, sources = answer_question("What is the latest OpenAI model today?")

        self.assertEqual(answer, "Latest model answer.")
        self.assertEqual(sources, ["OpenAI Models (https://platform.openai.com/docs/models)"])
        mock_search.assert_called()

    def test_stream_answer_question_uses_glm_web_search_api(self):
        glm_payload = {
            "search_result": [
                {
                    "title": "OpenAI Models",
                    "content": "OpenAI's latest flagship model is GPT-5.4 according to the official models page.",
                    "link": "https://platform.openai.com/docs/models",
                    "media": "OpenAI",
                    "publish_date": "2026-03-06",
                }
            ]
        }
        with patch("app.workflow.get_provider_family", return_value="glm"), patch(
            "app.pipeline.get_provider_family", return_value="glm"
        ), patch("app.workflow.is_web_search_enabled", return_value=True), patch(
            "app.pipeline.is_web_search_enabled", return_value=True
        ), patch(
            "app.pipeline.run_glm_web_search", return_value=glm_payload
        ), patch(
            "app.pipeline.get_chat_client", return_value=_FakeChatClient()
        ) as mock_search:
            events = list(stream_answer_question("What is the latest OpenAI model today?"))

        self.assertTrue(any(name == "progress" and payload.get("stage") == "web_search_start" for name, payload in events))
        self.assertTrue(any(name == "progress" and payload.get("stage") == "web_search_quality" for name, payload in events))
        self.assertTrue(any(name == "delta" and payload == {"text": "Latest model answer."} for name, payload in events))
        self.assertTrue(any(name == "sources" and payload == {"sources": ["OpenAI Models (https://platform.openai.com/docs/models)"]} for name, payload in events))
        self.assertEqual(events[-1], ("done", {}))
        mock_search.assert_called()


def _patched_test_answer_question_allows_relevant_but_unofficial_fresh_web_results(self):
    fake_client = _RelevantUnofficialResponsesClient()
    with patch("app.pipeline.get_responses_client", return_value=fake_client), patch(
        "app.pipeline.get_web_search_model", return_value="qwen3.5-plus"
    ), patch(
        "app.pipeline.get_chat_client", return_value=_FakeChatClient()
    ) as mock_chat:
        answer, sources = answer_question("What is the latest OpenAI model today?")

    self.assertEqual(answer, "Latest model answer.")
    self.assertEqual(sources, ["AI News Daily (https://ainews.example.com/openai-gpt6-rumor)"])
    self.assertGreaterEqual(len(fake_client.responses.calls), 1)
    mock_chat.assert_called_once()


def _patched_test_build_direct_web_search_queries_adds_clean_chinese_official_suffix(self):
    tool_plan = build_tool_plan(
        "web_search",
        reason="test_chinese_freshness_suffix",
        intent="web_search",
        needs_freshness=True,
    )

    with patch("app.pipeline.resolve_web_search_request", return_value={"input": "请联网搜索今天 OpenAI 最新模型是什么"}), patch(
        "app.workflow._build_focused_web_query", return_value=None
    ):
        queries = _build_direct_web_search_queries("请联网搜索今天 OpenAI 最新模型是什么", tool_plan)

    self.assertEqual(len(queries), 2)
    self.assertIn(WEB_SEARCH_OFFICIAL_QUERY_SUFFIX_ZH_ACTIVE, queries[1])


PipelineDirectAnswerTests.test_answer_question_rejects_relevant_but_unofficial_fresh_web_results = _patched_test_answer_question_allows_relevant_but_unofficial_fresh_web_results
PipelineDirectAnswerTests.test_build_direct_web_search_queries_adds_clean_chinese_official_suffix = _patched_test_build_direct_web_search_queries_adds_clean_chinese_official_suffix


def _patched_test_allow_target_hint_in_web_query_rejects_unrelated_web_search(self):
    self.assertFalse(
        _allow_target_hint_in_web_query(
            "请联网搜索 OpenAI 介绍",
            history=[],
            target_hint="递归学习与第一性原理求职——AI时代的方法论",
        )
    )


def _patched_test_build_focused_web_query_keeps_target_hint_for_clear_doc_follow_up(self):
    bundle = _strong_local_bundle()
    with patch("app.workflow.find_recent_summary_context", return_value=None):
        query = _build_focused_web_query(
            "Chroma",
            raw_question="请联网搜索这个文档里的 Chroma",
            history=[],
            local_bundle=bundle,
        )

    self.assertIsNotNone(query)
    self.assertIn("project_intro", query)


PipelineDirectAnswerTests.test_allow_target_hint_in_web_query_rejects_unrelated_web_search = _patched_test_allow_target_hint_in_web_query_rejects_unrelated_web_search
PipelineDirectAnswerTests.test_build_focused_web_query_keeps_target_hint_for_clear_doc_follow_up = _patched_test_build_focused_web_query_keeps_target_hint_for_clear_doc_follow_up


if __name__ == "__main__":
    unittest.main()
