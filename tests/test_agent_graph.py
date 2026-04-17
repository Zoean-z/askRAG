import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.agent_graph import build_agent_graph, run_agent_graph_detailed, run_agent_graph_stream
from app.pipeline import AnswerRunResult
from app.retrievers.chunk_retriever import ChunkRetrievalBundle, RerankDiagnostics
from app.validators import RetrievalValidation


def _bundle(*, sources=None, retrieval_debug=None):
    return ChunkRetrievalBundle(
        rewritten_question="rewritten",
        vector_results=[],
        keyword_results=[],
        merged_results=[],
        reranked_results=[],
        results=[],
        sources=list(sources or []),
        history=[],
        rerank_diagnostics=RerankDiagnostics(),
        retrieval_debug=dict(retrieval_debug or {}),
    )


def _router_hints(
    *,
    target_source_hint=None,
    summary_candidate=False,
    doc_candidate=False,
    web_candidate=False,
    direct_answer_candidate=False,
    followup_candidate=False,
    needs_freshness=False,
    use_history=False,
):
    return SimpleNamespace(
        target_source_hint=target_source_hint,
        summary_candidate=summary_candidate,
        doc_candidate=doc_candidate,
        web_candidate=web_candidate,
        direct_answer_candidate=direct_answer_candidate,
        followup_candidate=followup_candidate,
        needs_freshness=needs_freshness,
        use_history=use_history,
    )


def _probe(*, has_hits=False, top_sources=None, validation=None):
    return SimpleNamespace(
        has_hits=has_hits,
        top_sources=list(top_sources or []),
        validation=validation or RetrievalValidation(is_sufficient=False, reason="probe"),
    )


class AgentGraphTests(unittest.TestCase):
    def test_run_agent_graph_routes_direct_answer_from_hints(self):
        expected = AnswerRunResult(answer="direct", sources=[], trace={"mode": "direct_answer"})

        with (
            patch("app.agent_graph.extract_router_hints", return_value=_router_hints(direct_answer_candidate=True, use_history=True)) as hints_mock,
            patch("app.agent_tools.probe_local_docs", return_value=_probe()) as probe_mock,
            patch("app.agent_tools.load_long_term_context", return_value=SimpleNamespace(reference_history=[], memory_context="")),
            patch("app.agent_tools.load_response_constraints", return_value={}),
            patch("app.agent_tools.answer_directly_tool", return_value=expected) as direct_mock,
        ):
            result = run_agent_graph_detailed("hello", history=[{"role": "user", "content": "hi"}], k=3)

        self.assertIs(result, expected)
        hints_mock.assert_called_once_with("hello", history=[{"role": "user", "content": "hi"}])
        probe_mock.assert_called_once_with("hello", history=[{"role": "user", "content": "hi"}], k=1)
        direct_mock.assert_called_once_with("hello", history=[{"role": "user", "content": "hi"}])

    def test_run_agent_graph_routes_summary_from_hint_label_only(self):
        expected = AnswerRunResult(answer="summary", sources=["data/docs/project_intro.txt"], trace={"mode": "summary"})

        with (
            patch("app.agent_graph.extract_router_hints", return_value=_router_hints(summary_candidate=True)),
            patch("app.agent_tools.probe_local_docs", return_value=_probe()),
            patch("app.agent_tools.load_long_term_context", return_value=SimpleNamespace(reference_history=[], memory_context="")),
            patch("app.agent_tools.load_response_constraints", return_value={}),
            patch("app.agent_tools.read_summary", return_value=expected) as summary_mock,
        ):
            result = run_agent_graph_detailed("summarize file", history=[], k=3)

        self.assertIs(result, expected)
        summary_mock.assert_called_once_with("summarize file", history=[], require_strong_parent_match=True)

    def test_run_agent_graph_routes_recent_task_query_to_direct_answer(self):
        expected = AnswerRunResult(answer="task", sources=[], trace={"mode": "direct_answer"})
        task_context = "[Session Memory]\n- [L1] recent_task_state: We are focusing on ralph-superpowers-integration.md."

        with (
            patch("app.agent_graph.is_recent_task_query", return_value=True),
            patch("app.agent_graph.extract_router_hints", return_value=_router_hints()),
            patch("app.agent_tools.probe_local_docs", return_value=_probe()),
            patch("app.agent_tools.load_long_term_context", return_value=SimpleNamespace(reference_history=[], memory_context=task_context)),
            patch("app.agent_tools.load_response_constraints", return_value={}),
            patch("app.agent_tools.answer_directly_tool", return_value=expected) as direct_mock,
        ):
            result = run_agent_graph_detailed("任务是什么", history=[], k=3)

        self.assertIs(result, expected)
        direct_mock.assert_called_once_with("任务是什么", history=[], memory_context=task_context)

    def test_run_preplan_parallel_preserves_memory_context(self):
        from app.agent_graph import _init_request, _run_preplan_parallel

        initial = _init_request(
            {
                "question": "我住在哪里",
                "history": [],
                "k": 3,
                "allow_web_search": False,
            }
        )

        result = _run_preplan_parallel(initial)

        self.assertIn("Memory", result.get("memory_context", ""))

    def test_run_agent_graph_routes_summary_plus_web_strategy_through_tool_layer(self):
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
        final_result = AnswerRunResult(
            answer="combined answer",
            sources=["data/docs/harness.txt", "https://example.com"],
            trace={"mode": "summary_with_web"},
        )

        with (
            patch("app.agent_graph.extract_router_hints", return_value=_router_hints(summary_candidate=True)),
            patch("app.agent_tools.probe_local_docs", return_value=_probe()),
            patch("app.agent_tools.load_long_term_context", return_value=SimpleNamespace(reference_history=[], memory_context="memory")),
            patch("app.agent_tools.load_response_constraints", return_value={"language": "zh"}),
            patch("app.agent_tools.decide_summary_strategy", return_value=SimpleNamespace(strategy="summary_plus_web")),
            patch("app.agent_tools.read_summary", return_value=summary_result),
            patch("app.agent_tools.run_summary_web_search_result", return_value=web_result),
            patch("app.agent_tools.compose_summary_with_web_result", return_value=final_result) as compose_mock,
        ):
            result = run_agent_graph_detailed("summarize this file and search the web", history=[], k=3)

        self.assertIs(result, final_result)
        compose_mock.assert_called_once_with(
            "summarize this file and search the web",
            summary_result,
            web_result,
            memory_context="memory",
            response_constraints={"language": "zh"},
        )

    def test_run_agent_graph_uses_probe_to_route_ordinary_doc_question_into_retrieval(self):
        with (
            patch("app.agent_graph.extract_router_hints", return_value=_router_hints()),
            patch("app.agent_tools.probe_local_docs", return_value=_probe(has_hits=True, top_sources=["data/docs/project_intro.txt"])),
            patch(
                "app.agent_tools.load_long_term_context",
                return_value=SimpleNamespace(
                    reference_history=[{"role": "assistant", "content": "normalized"}],
                    memory_context="",
                ),
            ),
            patch("app.agent_tools.load_response_constraints", return_value={}),
            patch("app.agent_graph.log_diagnostic_event") as log_mock,
            patch("app.agent_tools.initialize_retrieval_workflow_state") as init_mock,
            patch(
                "app.agent_tools.search_kb_chroma",
                return_value=SimpleNamespace(
                    bundle=_bundle(sources=["data/docs/project_intro.txt"]),
                    validation=RetrievalValidation(is_sufficient=True, reason="keyword_match_strong_enough"),
                ),
            ) as search_mock,
            patch("app.agent_tools.apply_local_kb_search_result"),
            patch("app.agent_tools.assess_local_retrieval_followup", return_value=SimpleNamespace(needs_web=False, decision_reason="local_evidence_sufficient")),
            patch(
                "app.agent_tools.finalize_retrieval_result",
                return_value=SimpleNamespace(answer="retrieval", sources=["data/docs/project_intro.txt"], trace={"mode": "query"}),
            ) as finalize_mock,
        ):
            init_mock.return_value = SimpleNamespace(
                status="running",
                needs_web=False,
                decision_reason="local_evidence_sufficient",
                trace={"mode": "query"},
            )
            result = run_agent_graph_detailed("What does the harness file say about Codex?", history=[], k=5)

        self.assertEqual(result.answer, "retrieval")
        finalize_mock.assert_called_once()
        self.assertEqual(
            search_mock.call_args.kwargs.get("reference_history"),
            [{"role": "assistant", "content": "normalized"}],
        )
        plan_logs = [
            call for call in log_mock.call_args_list if call.args and call.args[0] == "plan_request"
        ]
        self.assertTrue(plan_logs)
        plan_payload = plan_logs[0].kwargs
        self.assertTrue(plan_payload["probe_has_hits"])
        self.assertTrue(plan_payload["should_attempt_local_retrieval"])
        self.assertTrue(plan_payload["doc_first_candidate"])
        self.assertEqual(plan_payload["chosen_route"], "local_doc_query")

    def test_run_agent_graph_routes_general_web_search_from_hints(self):
        expected = AnswerRunResult(answer="web", sources=["https://example.com"], trace={"mode": "web_search"})

        with (
            patch("app.agent_graph.extract_router_hints", return_value=_router_hints(web_candidate=True, needs_freshness=True)),
            patch("app.agent_tools.probe_local_docs", return_value=_probe()),
            patch("app.agent_tools.load_long_term_context", return_value=SimpleNamespace(reference_history=[], memory_context="")),
            patch("app.agent_tools.load_response_constraints", return_value={}),
            patch("app.agent_tools.run_direct_web_search_result", return_value=expected) as web_mock,
        ):
            result = run_agent_graph_detailed("Search the web", history=[], k=3)

        self.assertIs(result, expected)
        called_plan = web_mock.call_args.args[1]
        self.assertEqual(called_plan.primary_tool, "web_search")
        self.assertEqual(called_plan.reason, "graph_web_hint")

    def test_run_agent_graph_stream_routes_direct_answer_through_stream_tool(self):
        events = [("trace", {"mode": "direct_answer"}), ("done", {})]

        def _fake_stream(*args, **kwargs):
            for event in events:
                yield event

        with (
            patch("app.agent_graph.extract_router_hints", return_value=_router_hints(direct_answer_candidate=True, use_history=True)),
            patch("app.agent_tools.probe_local_docs", return_value=_probe()),
            patch("app.agent_tools.load_long_term_context", return_value=SimpleNamespace(reference_history=[], memory_context="")),
            patch("app.agent_tools.load_response_constraints", return_value={}),
            patch("app.agent_tools.stream_direct_answer_tool", side_effect=_fake_stream) as stream_mock,
            patch("app.agent_tools.persist_turn_memory_result", return_value=SimpleNamespace(stored_entries=[], memory_notices=[])),
        ):
            result = list(run_agent_graph_stream("hello", history=[{"role": "user", "content": "hi"}], k=3))

        self.assertEqual(result, events)
        stream_mock.assert_called_once_with("hello", history=[{"role": "user", "content": "hi"}])

    def test_run_agent_graph_stream_routes_summary_verify_web_search_through_stream_tool(self):
        events = [("progress", {"stage": "web_search_start"}), ("done", {})]

        def _fake_stream(*args, **kwargs):
            for event in events:
                yield event

        with (
            patch("app.agent_graph.extract_router_hints", return_value=_router_hints()),
            patch("app.agent_tools.probe_local_docs", return_value=_probe()),
            patch("app.agent_tools.stream_web_search_tool", side_effect=_fake_stream) as stream_mock,
            patch("app.agent_tools.persist_turn_memory_result", return_value=SimpleNamespace(stored_entries=[], memory_notices=[])),
            patch("app.tool_router.find_recent_summary_context", return_value=SimpleNamespace(user_question="summarize", assistant_answer="summary", sources=["data/docs/project_intro.txt"])),
        ):
            result = list(run_agent_graph_stream("verify these claims", history=[], k=4))

        self.assertEqual(result, events)
        stream_mock.assert_called_once()
        called_plan = stream_mock.call_args.args[1]
        self.assertEqual(called_plan.web_search_mode, "summary_verify")

    def test_build_agent_graph_is_cached(self):
        graph_a = build_agent_graph()
        graph_b = build_agent_graph()
        self.assertIs(graph_a, graph_b)


if __name__ == "__main__":
    unittest.main()
