import unittest
from unittest.mock import patch

from app.tool_router import build_tool_plan, decide_tool_plan


class ToolRouterTests(unittest.TestCase):
    def test_direct_answer_rule_short_circuits_llm(self):
        with patch("app.tool_router.llm_tool_plan", side_effect=AssertionError("llm_tool_plan should not be called")):
            plan = decide_tool_plan("hello")

        self.assertEqual(plan.primary_tool, "direct_answer")
        self.assertEqual(plan.reason, "matched_direct_answer_rule")
        self.assertIsNone(plan.fallback_tool)

    def test_summary_rule_uses_recent_sources_without_llm(self):
        history = [{"role": "assistant", "content": "previous answer", "sources": ["data/docs/project_intro.txt"]}]
        with patch("app.tool_router.llm_tool_plan", side_effect=AssertionError("llm_tool_plan should not be called")):
            plan = decide_tool_plan("summarize this file", history=history)

        self.assertEqual(plan.primary_tool, "local_doc_summary")
        self.assertEqual(plan.reason, "matched_summary_rule")

    def test_regular_question_defaults_to_local_doc_query_without_llm(self):
        with patch("app.tool_router.llm_tool_plan", side_effect=AssertionError("llm_tool_plan should not be called")):
            plan = decide_tool_plan("What is Chroma")

        self.assertEqual(plan.primary_tool, "local_doc_query")
        self.assertEqual(plan.reason, "default_local_doc_query_rule")
        self.assertEqual(plan.fallback_tool, "local_doc_summary")

    def test_web_search_rule_is_detected_and_marked_available(self):
        with patch("app.tool_router.llm_tool_plan", side_effect=AssertionError("llm_tool_plan should not be called")):
            plan = decide_tool_plan("What is the latest OpenAI model today?")

        self.assertEqual(plan.primary_tool, "web_search")
        self.assertEqual(plan.reason, "matched_web_search_rule")
        self.assertTrue(plan.needs_freshness)
        self.assertTrue(plan.tool_available)

    def test_ambiguous_capability_question_can_still_use_llm_tool_plan(self):
        with patch("app.tool_router.llm_tool_plan") as mock_llm:
            mock_llm.return_value = build_tool_plan(
                "direct_answer",
                reason="llm:capability",
                confidence=0.9,
                fallback_tool=None,
            )
            plan = decide_tool_plan("What can you do beyond local docs?")

        self.assertEqual(plan.primary_tool, "direct_answer")
        mock_llm.assert_called_once()

    def test_low_confidence_llm_result_falls_back_to_local_doc_query(self):
        with patch("app.tool_router.llm_tool_plan") as mock_llm:
            mock_llm.return_value = build_tool_plan(
                "web_search",
                reason="llm:freshness_guess",
                confidence=0.4,
                fallback_tool=None,
            )
            plan = decide_tool_plan("What can you do beyond local docs?")

        self.assertEqual(plan.primary_tool, "local_doc_query")
        self.assertEqual(plan.reason, "default_local_doc_query_after_low_confidence_llm_route")
        self.assertEqual(plan.fallback_tool, "local_doc_summary")


if __name__ == "__main__":
    unittest.main()
