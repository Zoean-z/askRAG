import unittest
from types import SimpleNamespace
from unittest.mock import patch

from langchain_core.documents import Document

from app.agent_tools import (
    KBSearchToolResult,
    OpenVikingContextToolResult,
    PersistTurnMemoryToolResult,
    answer_directly_tool,
    assess_combined_retrieval_evidence,
    assess_local_retrieval_followup,
    apply_local_kb_search_result,
    finalize_retrieval_result,
    initialize_retrieval_workflow_state,
    probe_local_docs,
    persist_turn_memory_result,
    read_summary,
    run_direct_web_search_result,
    run_retrieval_web_extract_step,
    run_retrieval_web_search_step,
    search_kb_chroma,
    search_openviking_context,
    stream_direct_answer_tool,
    stream_retrieval_finalize_result,
    stream_read_summary,
    stream_web_search_tool,
    web_search,
)
from app.pipeline import AnswerRunResult
from app.retrievers.chunk_retriever import ChunkRetrievalBundle, RerankDiagnostics
from app.tool_router import build_tool_plan
from app.validators import RetrievalValidation
from app.workflow import WorkflowState, finalize_retrieval_answer


class AgentToolsTests(unittest.TestCase):
    def test_answer_directly_tool_delegates_to_pipeline_direct_answer_path(self):
        direct_result = AnswerRunResult(answer="Direct answer", sources=[], trace={"mode": "direct_answer"})

        with patch("app.agent_tools.answer_directly_detailed", return_value=direct_result) as direct_mock:
            result = answer_directly_tool("hello", history=[{"role": "user", "content": "hi"}])

        self.assertIs(result, direct_result)
        direct_mock.assert_called_once_with("hello", history=[{"role": "user", "content": "hi"}])

    def test_stream_direct_answer_tool_delegates_to_pipeline_stream_path(self):
        events = [("trace", {"mode": "direct_answer"}), ("done", {})]

        def _fake_stream(*args, **kwargs):
            for event in events:
                yield event

        with patch("app.agent_tools.stream_direct_answer", side_effect=_fake_stream) as stream_mock:
            result = list(stream_direct_answer_tool("hello", history=[{"role": "user", "content": "hi"}]))

        self.assertEqual(result, events)
        stream_mock.assert_called_once_with("hello", history=[{"role": "user", "content": "hi"}])

    def test_search_kb_chroma_returns_bundle_and_validation(self):
        fake_store = SimpleNamespace(
            similarity_search_with_score=lambda query, k: [(Document(page_content="vector hit", metadata={"source": "data/docs/project_intro.txt", "chunk_index": 0, "chunk_id": "data/docs/project_intro.txt::0"}), 0.92)]
        )
        bundle = ChunkRetrievalBundle(
            rewritten_question="What is Chroma?",
            vector_results=[(Document(page_content="vector hit", metadata={"source": "data/docs/project_intro.txt", "chunk_index": 0, "chunk_id": "data/docs/project_intro.txt::0"}), 0.92)],
            keyword_results=[(Document(page_content="keyword hit", metadata={"source": "data/docs/project_intro.txt", "chunk_index": 0, "chunk_id": "data/docs/project_intro.txt::0"}), 1.0)],
            merged_results=[(Document(page_content="merged hit", metadata={"source": "data/docs/project_intro.txt", "chunk_index": 0, "chunk_id": "data/docs/project_intro.txt::0"}), 1.0)],
            reranked_results=[(Document(page_content="reranked hit", metadata={"source": "data/docs/project_intro.txt", "chunk_index": 0, "chunk_id": "data/docs/project_intro.txt::0"}), 1.0)],
            results=[(Document(page_content="final hit", metadata={"source": "data/docs/project_intro.txt", "chunk_index": 0, "chunk_id": "data/docs/project_intro.txt::0"}), 1.0)],
            sources=["data/docs/project_intro.txt"],
            history=[{"role": "user", "content": "history"}],
            rerank_diagnostics=RerankDiagnostics(),
            retrieval_debug={"timings_ms": {"vector": 1.0}},
        )
        validation = RetrievalValidation(is_sufficient=False, reason="no_vector_results")
        rerank_diag = RerankDiagnostics(candidate_count=1, order_changed=False)

        with (
            patch("app.agent_tools.build_reference_history", return_value=[{"role": "user", "content": "normalized"}]) as history_mock,
            patch("app.agent_tools._cached_vector_store", return_value=fake_store) as store_mock,
            patch("app.agent_tools.extract_target_source_hint", return_value=None),
            patch("app.agent_tools.resolve_target_source_hint", return_value=None),
            patch("app.agent_tools.keyword_search_documents", return_value=bundle.keyword_results) as keyword_mock,
            patch("app.agent_tools.merge_retrieval_results", return_value=bundle.merged_results) as merge_mock,
            patch("app.agent_tools.rerank_retrieval_results", return_value=bundle.reranked_results) as rerank_mock,
            patch("app.agent_tools.expand_results_with_neighbors", return_value=bundle.results) as expand_mock,
            patch("app.agent_tools.validate_chunk_results", return_value=validation) as validate_mock,
            patch("app.agent_tools.build_rerank_diagnostics", return_value=rerank_diag) as diag_mock,
            patch("app.agent_tools.log_diagnostic_event"),
        ):
            result = search_kb_chroma("What is Chroma?", history=[{"role": "user", "content": "raw"}], k=4)

        self.assertIsInstance(result, KBSearchToolResult)
        self.assertEqual(result.bundle.rewritten_question, bundle.rewritten_question)
        self.assertEqual(result.bundle.vector_results, bundle.vector_results)
        self.assertEqual(result.bundle.keyword_results, bundle.keyword_results)
        self.assertEqual(result.bundle.merged_results, bundle.merged_results)
        self.assertEqual(result.bundle.reranked_results, bundle.reranked_results)
        self.assertEqual(result.bundle.results, bundle.results)
        self.assertEqual(result.bundle.sources, bundle.sources)
        self.assertEqual(result.bundle.history, [{"role": "user", "content": "normalized"}])
        self.assertIn("timings_ms", result.bundle.retrieval_debug)
        self.assertIn("rewrite_applied", result.bundle.retrieval_debug)
        self.assertIs(result.validation, validation)
        self.assertIsNone(result.context_plan)
        history_mock.assert_called_once_with("What is Chroma?", [{"role": "user", "content": "raw"}])
        store_mock.assert_called_once()
        keyword_mock.assert_called_once()
        merge_mock.assert_called_once()
        rerank_mock.assert_called_once()
        expand_mock.assert_called_once()
        validate_mock.assert_called_once_with(bundle.vector_results, bundle.keyword_results)
        diag_mock.assert_called_once()

    def test_search_kb_chroma_can_build_context_plan(self):
        fake_store = SimpleNamespace(
            similarity_search_with_score=lambda query, k: [(Document(page_content="vector hit", metadata={"source": "data/docs/project_intro.txt", "chunk_index": 0, "chunk_id": "data/docs/project_intro.txt::0"}), 0.92)]
        )
        bundle = ChunkRetrievalBundle(
            rewritten_question="What is Chroma?",
            vector_results=[(Document(page_content="vector hit", metadata={"source": "data/docs/project_intro.txt", "chunk_index": 0, "chunk_id": "data/docs/project_intro.txt::0"}), 0.92)],
            keyword_results=[(Document(page_content="keyword hit", metadata={"source": "data/docs/project_intro.txt", "chunk_index": 0, "chunk_id": "data/docs/project_intro.txt::0"}), 1.0)],
            merged_results=[(Document(page_content="merged hit", metadata={"source": "data/docs/project_intro.txt", "chunk_index": 0, "chunk_id": "data/docs/project_intro.txt::0"}), 1.0)],
            reranked_results=[(Document(page_content="reranked hit", metadata={"source": "data/docs/project_intro.txt", "chunk_index": 0, "chunk_id": "data/docs/project_intro.txt::0"}), 1.0)],
            results=[(Document(page_content="final hit", metadata={"source": "data/docs/project_intro.txt", "chunk_index": 0, "chunk_id": "data/docs/project_intro.txt::0"}), 1.0)],
            sources=["data/docs/project_intro.txt"],
            history=[],
            rerank_diagnostics=RerankDiagnostics(),
            retrieval_debug={"timings_ms": {"vector": 1.0}},
        )
        validation = RetrievalValidation(is_sufficient=True, reason="keyword_match_strong_enough")
        context_plan = SimpleNamespace(mode="query")

        with (
            patch("app.agent_tools._cached_vector_store", return_value=fake_store),
            patch("app.agent_tools.extract_target_source_hint", return_value=None),
            patch("app.agent_tools.resolve_target_source_hint", return_value=None),
            patch("app.agent_tools.build_reference_history", return_value=[{"role": "assistant", "content": "normalized"}]),
            patch("app.agent_tools.keyword_search_documents", return_value=bundle.keyword_results),
            patch("app.agent_tools.merge_retrieval_results", return_value=bundle.merged_results),
            patch("app.agent_tools.rerank_retrieval_results", return_value=bundle.reranked_results),
            patch("app.agent_tools.expand_results_with_neighbors", return_value=bundle.results),
            patch("app.agent_tools.validate_chunk_results", return_value=validation),
            patch("app.agent_tools.build_memory_context", return_value="memory-context") as memory_mock,
            patch("app.agent_tools.build_query_context_plan", return_value=context_plan) as context_mock,
            patch("app.agent_tools.build_rerank_diagnostics", return_value=RerankDiagnostics(candidate_count=1, order_changed=False)),
            patch("app.agent_tools.log_diagnostic_event"),
        ):
            result = search_kb_chroma("What is Chroma?", include_context_plan=True)

        self.assertEqual(result.bundle.rewritten_question, bundle.rewritten_question)
        self.assertEqual(result.bundle.sources, bundle.sources)
        self.assertEqual(result.bundle.history, [{"role": "assistant", "content": "normalized"}])
        self.assertIs(result.context_plan, context_plan)
        memory_mock.assert_called_once_with(
            "What is Chroma?",
            history=[{"role": "assistant", "content": "normalized"}],
            sources=["data/docs/project_intro.txt"],
        )
        context_call = context_mock.call_args
        self.assertEqual(context_call.args[0], "What is Chroma?")
        self.assertEqual(context_call.args[1].sources, ["data/docs/project_intro.txt"])
        self.assertEqual(context_call.kwargs["history"], [{"role": "assistant", "content": "normalized"}])
        self.assertEqual(context_call.kwargs["memory_context"], "memory-context")

    def test_probe_local_docs_uses_lightweight_probe_path(self):
        doc = Document(
            page_content="Probe chunk content",
            metadata={
                "source": "data/docs/project_intro.txt",
                "chunk_index": 0,
                "chunk_id": "data/docs/project_intro.txt::0",
            },
        )

        with (
            patch("app.agent_tools.build_reference_history") as history_mock,
            patch("app.agent_tools.retrieve_vector_documents", return_value=[(doc, 0.92)]) as vector_mock,
            patch("app.agent_tools.keyword_search_documents", return_value=[(doc, 1.0)]) as keyword_mock,
            patch("app.agent_tools.merge_retrieval_results", return_value=[(doc, 1.0)]) as merge_mock,
            patch("app.agent_tools.rerank_retrieval_results", return_value=[(doc, 1.0)]) as rerank_mock,
            patch("app.agent_tools.validate_chunk_results", return_value=RetrievalValidation(is_sufficient=True, reason="vector_match_strong_enough")) as validate_mock,
            patch("app.agent_tools.log_diagnostic_event"),
        ):
            result = probe_local_docs("What is Chroma?", history=[{"role": "user", "content": "raw"}])

        self.assertTrue(result.has_hits)
        self.assertEqual(result.top_sources, ["data/docs/project_intro.txt"])
        history_mock.assert_not_called()
        vector_mock.assert_called_once()
        keyword_mock.assert_called_once()
        merge_mock.assert_called_once()
        rerank_mock.assert_called_once()
        validate_mock.assert_called_once_with([(doc, 0.92)], [(doc, 1.0)])

    def test_search_openviking_context_wraps_current_memory_context_path(self):
        with (
            patch("app.agent_tools.build_reference_history", return_value=[{"role": "user", "content": "normalized"}]) as history_mock,
            patch("app.agent_tools.build_memory_context", return_value="memory context") as memory_mock,
        ):
            result = search_openviking_context(
                "Answer in Chinese",
                history=[{"role": "user", "content": "raw"}],
                sources=["data/docs/project_intro.txt"],
            )

        self.assertIsInstance(result, OpenVikingContextToolResult)
        self.assertEqual(result.context, "memory context")
        history_mock.assert_called_once_with("Answer in Chinese", [{"role": "user", "content": "raw"}])
        memory_mock.assert_called_once_with(
            "Answer in Chinese",
            history=[{"role": "user", "content": "normalized"}],
            sources=["data/docs/project_intro.txt"],
        )

    def test_read_summary_delegates_to_pipeline_summary_path(self):
        summary_result = AnswerRunResult(answer="Summary answer", sources=["data/docs/project_intro.txt"], trace={"mode": "summary"})

        with patch("app.agent_tools.answer_local_summary_detailed", return_value=summary_result) as summary_mock:
            result = read_summary(
                "Summarize project_intro.txt",
                history=[{"role": "user", "content": "history"}],
                require_strong_parent_match=False,
                child_results=[("child", 0.5)],
            )

        self.assertIs(result, summary_result)
        summary_mock.assert_called_once_with(
            "Summarize project_intro.txt",
            history=[{"role": "user", "content": "history"}],
            require_strong_parent_match=False,
            child_results=[("child", 0.5)],
        )

    def test_stream_read_summary_delegates_to_pipeline_stream_path(self):
        events = [("delta", {"text": "part one"}), ("done", {})]

        def _fake_stream(*args, **kwargs):
            for event in events:
                yield event

        with patch("app.agent_tools.stream_local_summary", side_effect=_fake_stream) as stream_mock:
            result = list(
                stream_read_summary(
                    "Summarize project_intro.txt",
                    history=[{"role": "user", "content": "history"}],
                )
            )

        self.assertEqual(result, events)
        stream_mock.assert_called_once_with(
            "Summarize project_intro.txt",
            history=[{"role": "user", "content": "history"}],
            require_strong_parent_match=True,
            child_results=None,
        )

    def test_web_search_delegates_to_pipeline_web_path(self):
        tool_plan = build_tool_plan(
            intent="web_search",
            primary_tool="web_search",
            fallback_tool=None,
            confidence=0.9,
            reason="test web search wrapper",
        )

        with patch("app.agent_tools.answer_web_search", return_value=("Web answer", ["https://example.com"])) as web_mock:
            answer, sources = web_search(
                "Search the web",
                tool_plan,
                history=[{"role": "user", "content": "history"}],
            )

        self.assertEqual(answer, "Web answer")
        self.assertEqual(sources, ["https://example.com"])
        web_mock.assert_called_once_with(
            "Search the web",
            tool_plan,
            history=[{"role": "user", "content": "history"}],
        )

    def test_run_direct_web_search_result_returns_disabled_trace_when_web_is_disabled(self):
        tool_plan = build_tool_plan(
            intent="web_search",
            primary_tool="web_search",
            fallback_tool=None,
            confidence=0.9,
            reason="test direct web tool",
        )
        disabled_trace = {"mode": "web_search", "disabled": True}

        with (
            patch("app.agent_tools.is_web_search_enabled", return_value=False),
            patch("app.agent_tools.build_web_search_disabled_trace", return_value=disabled_trace) as trace_mock,
        ):
            result = run_direct_web_search_result("Search the web", tool_plan)

        self.assertEqual(result.answer, "[web_search] 当前未启用网页查询工具，无法回答这类需要联网或最新信息的问题。")
        self.assertEqual(result.sources, [])
        self.assertEqual(result.trace, disabled_trace)
        trace_mock.assert_called_once_with("Search the web", tool_plan)

    def test_run_direct_web_search_result_runs_quality_pass_and_builds_trace(self):
        tool_plan = build_tool_plan(
            intent="web_search",
            primary_tool="web_search",
            fallback_tool=None,
            confidence=0.9,
            reason="test direct web tool",
        )
        trace = {"mode": "web_search"}

        with (
            patch("app.agent_tools.is_web_search_enabled", return_value=True),
            patch(
                "app.agent_tools._run_direct_web_search_quality_pass",
                return_value=("Web answer", ["https://example.com"], {"quality": "ok"}),
            ) as quality_mock,
            patch("app.agent_tools.build_web_search_trace", return_value=trace) as trace_mock,
        ):
            result = run_direct_web_search_result("Search the web", tool_plan)

        self.assertEqual(result.answer, "Web answer")
        self.assertEqual(result.sources, ["https://example.com"])
        self.assertEqual(result.trace, trace)
        quality_mock.assert_called_once_with("Search the web", tool_plan, history=[])
        trace_mock.assert_called_once_with("Search the web", tool_plan, ["https://example.com"], debug={"quality": "ok"})

    def test_run_direct_web_search_result_uses_recent_history_for_query_rewrite(self):
        tool_plan = build_tool_plan(
            intent="web_search",
            primary_tool="web_search",
            fallback_tool=None,
            confidence=0.9,
            reason="test direct web tool",
        )
        history = [
            {"role": "user", "content": "We were talking about the champion Ahri."},
            {"role": "assistant", "content": "Ahri is a mid laner."},
        ]

        with (
            patch("app.agent_tools.is_web_search_enabled", return_value=True),
            patch("app.agent_tools.build_reference_history", return_value=history) as history_mock,
            patch(
                "app.agent_tools._run_direct_web_search_quality_pass",
                return_value=("Web answer", ["https://example.com"], {"quality": "ok"}),
            ) as quality_mock,
            patch("app.agent_tools.build_web_search_trace", return_value={"mode": "web_search"}),
        ):
            result = run_direct_web_search_result("search her latest build", tool_plan, history=history)

        self.assertEqual(result.answer, "Web answer")
        self.assertEqual(result.sources, ["https://example.com"])
        history_mock.assert_called_once_with("search her latest build", history)
        quality_mock.assert_called_once_with("search her latest build", tool_plan, history=history)

    def test_stream_web_search_tool_delegates_to_pipeline_stream_web_path(self):
        tool_plan = build_tool_plan(
            intent="web_search",
            primary_tool="web_search",
            fallback_tool=None,
            confidence=0.9,
            reason="test web search wrapper",
        )
        events = [("trace", {"mode": "web_search"}), ("done", {})]

        def _fake_stream(*args, **kwargs):
            for event in events:
                yield event

        with patch("app.agent_tools.stream_web_search", side_effect=_fake_stream) as stream_mock:
            result = list(
                stream_web_search_tool(
                    "Search the web",
                    tool_plan,
                    history=[{"role": "user", "content": "history"}],
                )
            )

        self.assertEqual(result, events)
        stream_mock.assert_called_once_with(
            "Search the web",
            tool_plan,
            history=[{"role": "user", "content": "history"}],
        )

    def test_run_retrieval_web_search_step_delegates_to_workflow_helper(self):
        workflow_state = WorkflowState(question="q", history=[], tool_plan=build_tool_plan("local_doc_query", reason="test"))

        with patch("app.workflow._run_web_search_step") as helper_mock:
            result = run_retrieval_web_search_step(workflow_state)

        self.assertIs(result, workflow_state)
        helper_mock.assert_called_once_with(workflow_state)

    def test_run_retrieval_web_extract_step_delegates_to_workflow_helper(self):
        workflow_state = WorkflowState(question="q", history=[], tool_plan=build_tool_plan("local_doc_query", reason="test"))

        with patch("app.workflow._run_web_extract_step") as helper_mock:
            result = run_retrieval_web_extract_step(workflow_state)

        self.assertIs(result, workflow_state)
        helper_mock.assert_called_once_with(workflow_state)

    def test_stream_retrieval_finalize_result_delegates_to_workflow_helper(self):
        workflow_state = WorkflowState(question="q", history=[], tool_plan=build_tool_plan("local_doc_query", reason="test"))
        events = [("sources", {"sources": ["data/docs/project_intro.txt"]}), ("done", {})]

        def _fake_stream(*args, **kwargs):
            for event in events:
                yield event

        with patch("app.workflow.stream_finalize_retrieval_answer", side_effect=_fake_stream) as helper_mock:
            result = list(stream_retrieval_finalize_result(workflow_state))

        self.assertEqual(result, events)
        helper_mock.assert_called_once_with(workflow_state)

    def test_finalize_retrieval_result_delegates_to_workflow_helper(self):
        workflow_state = WorkflowState(question="q", history=[], tool_plan=build_tool_plan("local_doc_query", reason="test"))
        workflow_result = SimpleNamespace(answer="retrieval", sources=["data/docs/project_intro.txt"], trace={"mode": "query"})

        with patch("app.workflow.finalize_retrieval_answer", return_value=workflow_result) as helper_mock:
            result = finalize_retrieval_result(workflow_state)

        self.assertIs(result, workflow_result)
        helper_mock.assert_called_once_with(workflow_state)

    def test_persist_turn_memory_result_wraps_recorded_entries_as_notices(self):
        stored_entries = [
            {
                "memory_type": "pinned_preference",
                "summary": "Prefer concise answers.",
                "status": "approved",
            }
        ]

        with patch("app.agent_tools.record_completed_turn", return_value=stored_entries) as record_mock:
            result = persist_turn_memory_result(
                question="What is Chroma?",
                answer="Chroma is the local vector store.",
                sources=["data/docs/project_intro.txt"],
                history=[{"role": "user", "content": "What is Chroma?"}],
                trace={"debug": {"memory_context_used": True}},
            )

        self.assertIsInstance(result, PersistTurnMemoryToolResult)
        self.assertEqual(result.stored_entries, stored_entries)
        self.assertEqual(len(result.memory_notices), 2)
        self.assertEqual(result.memory_notices[0]["kind"], "used")
        self.assertEqual(result.memory_notices[1]["kind"], "remembered")
        record_mock.assert_called_once()

    def test_assess_combined_retrieval_evidence_delegates_to_workflow_helper(self):
        workflow_state = WorkflowState(question="q", history=[], tool_plan=build_tool_plan("local_doc_query", reason="test"))

        with patch("app.workflow._assess_combined_step") as helper_mock:
            result = assess_combined_retrieval_evidence(workflow_state)

        self.assertIs(result, workflow_state)
        helper_mock.assert_called_once_with(workflow_state)

    def test_initialize_retrieval_workflow_state_delegates_to_workflow_helper(self):
        workflow_state = WorkflowState(question="q", history=[], tool_plan=build_tool_plan("local_doc_query", reason="test"))

        with patch("app.workflow.init_workflow_state", return_value=workflow_state) as helper_mock:
            result = initialize_retrieval_workflow_state("q", build_tool_plan("local_doc_query", reason="test"), [])

        self.assertIs(result, workflow_state)
        helper_mock.assert_called_once()

    def test_apply_local_kb_search_result_updates_workflow_state(self):
        workflow_state = WorkflowState(question="q", history=[], tool_plan=build_tool_plan("local_doc_query", reason="test"))
        bundle = ChunkRetrievalBundle(
            rewritten_question="rewritten",
            vector_results=[],
            keyword_results=[],
            merged_results=[],
            reranked_results=[],
            results=[],
            sources=["data/docs/project_intro.txt"],
            history=[],
            rerank_diagnostics=RerankDiagnostics(),
            retrieval_debug={},
        )
        kb_result = KBSearchToolResult(
            bundle=bundle,
            validation=RetrievalValidation(is_sufficient=True, reason="keyword_match_strong_enough"),
        )

        with (
            patch("app.workflow._advance_step") as advance_mock,
            patch("app.workflow._local_confidence", return_value=0.78) as confidence_mock,
            patch("app.workflow._dedupe_sources", return_value=["data/docs/project_intro.txt"]) as dedupe_mock,
            patch("app.workflow._refresh_assessment_trace") as refresh_mock,
        ):
            result = apply_local_kb_search_result(workflow_state, kb_result)

        self.assertIs(result, workflow_state)
        self.assertTrue(workflow_state.local_attempted)
        self.assertIs(workflow_state.local_bundle, bundle)
        self.assertIs(workflow_state.local_validation, kb_result.validation)
        self.assertTrue(workflow_state.local_retrieval_relevant)
        self.assertFalse(workflow_state.local_sufficient)
        self.assertFalse(workflow_state.local_answer_sufficient)
        self.assertEqual(workflow_state.confidence, 0.78)
        self.assertEqual(workflow_state.sources, ["data/docs/project_intro.txt"])
        advance_mock.assert_called_once_with(workflow_state, "local_search")
        confidence_mock.assert_called_once_with(kb_result.validation)
        dedupe_mock.assert_called_once_with(bundle.sources, workflow_state.web_sources)
        refresh_mock.assert_called_once_with(workflow_state)

    def test_assess_local_retrieval_followup_blocks_auto_web_when_guardrail_matches(self):
        workflow_state = WorkflowState(question="q", history=[], tool_plan=build_tool_plan("local_doc_query", reason="test"))
        workflow_state.local_sufficient = False

        with (
            patch("app.workflow._advance_step") as advance_mock,
            patch("app.workflow._requires_relevant_web", return_value=False),
            patch("app.workflow._should_keep_file_anchored_query_local", return_value=False),
            patch("app.workflow._should_block_auto_web_fallback", return_value=True),
            patch("app.workflow._refresh_assessment_trace") as refresh_mock,
        ):
            result = assess_local_retrieval_followup(workflow_state)

        self.assertFalse(result.needs_web)
        self.assertEqual(result.decision_reason, "guardrail_blocked_auto_web_fallback")
        self.assertFalse(workflow_state.needs_web)
        self.assertEqual(workflow_state.decision_reason, "guardrail_blocked_auto_web_fallback")
        advance_mock.assert_called_once_with(workflow_state, "assess_local")
        refresh_mock.assert_called_once_with(workflow_state)

    def test_assess_local_retrieval_followup_continues_web_when_relevant_but_answer_insufficient(self):
        workflow_state = WorkflowState(question="厄斐琉斯的剧情是什么", history=[], tool_plan=build_tool_plan("local_doc_query", reason="test"))
        workflow_state.local_bundle = ChunkRetrievalBundle(
            rewritten_question="厄斐琉斯的剧情是什么",
            vector_results=[],
            keyword_results=[],
            merged_results=[],
            reranked_results=[],
            results=[
                (
                    Document(
                        page_content="厄斐琉斯是一名英雄，技能与机制说明。",
                        metadata={"source": "data/docs/project_intro.txt", "chunk_index": 0, "chunk_id": "doc::0"},
                    ),
                    1.0,
                )
            ],
            sources=["data/docs/project_intro.txt"],
            history=[],
            rerank_diagnostics=RerankDiagnostics(),
            retrieval_debug={},
        )
        workflow_state.local_retrieval_relevant = True
        workflow_state.local_sufficient = False

        with (
            patch("app.workflow._advance_step") as advance_mock,
            patch("app.workflow._requires_relevant_web", return_value=False),
            patch("app.workflow._should_keep_file_anchored_query_local", return_value=False),
            patch("app.workflow._should_block_auto_web_fallback", return_value=False),
            patch("app.workflow._local_answer_is_sufficient", return_value=False),
            patch("app.workflow._refresh_assessment_trace") as refresh_mock,
        ):
            result = assess_local_retrieval_followup(workflow_state)

        self.assertTrue(result.needs_web)
        self.assertEqual(result.decision_reason, "local_retrieval_relevant_but_answer_insufficient")
        self.assertTrue(workflow_state.local_retrieval_relevant)
        self.assertFalse(workflow_state.local_answer_sufficient)
        self.assertTrue(workflow_state.needs_web)
        advance_mock.assert_called_once_with(workflow_state, "assess_local")
        refresh_mock.assert_called_once_with(workflow_state)

    def test_finalize_retrieval_answer_refreshes_trace_after_answer(self):
        workflow_state = WorkflowState(question="q", history=[], tool_plan=build_tool_plan("local_doc_query", reason="test"))
        workflow_state.status = "running"
        workflow_state.combined_sufficient = True
        workflow_state.sources = ["data/docs/project_intro.txt"]

        def _fake_summarize(state):
            state.final_answer = "retrieval"
            state.sources = ["data/docs/project_intro.txt"]
            state.status = "done"
            return "retrieval", ["data/docs/project_intro.txt"]

        def _fake_refresh(state):
            state.trace = {"mode": "query", "debug": {"post_finalize": True}}

        with (
            patch("app.workflow._run_summarize_step", side_effect=_fake_summarize) as summarize_mock,
            patch("app.workflow._refresh_trace", side_effect=_fake_refresh) as refresh_mock,
        ):
            result = finalize_retrieval_answer(workflow_state)

        self.assertEqual(result.answer, "retrieval")
        self.assertEqual(result.sources, ["data/docs/project_intro.txt"])
        self.assertEqual(result.trace["debug"]["post_finalize"], True)
        summarize_mock.assert_called_once_with(workflow_state)
        refresh_mock.assert_called_once_with(workflow_state)


if __name__ == "__main__":
    unittest.main()
