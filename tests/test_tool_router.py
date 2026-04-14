import unittest
from unittest.mock import patch

from app.tool_router import build_tool_plan, decide_tool_plan, extract_router_hints


class ToolRouterTests(unittest.TestCase):
    def test_extract_router_hints_marks_doc_candidate(self):
        hints = extract_router_hints("project_intro.txt 里 Chroma 是做什么的？")

        self.assertTrue(hints.doc_candidate)
        self.assertEqual(hints.target_source_hint, "project_intro.txt")
        self.assertFalse(hints.force_web_only)
        self.assertFalse(hints.force_local_only)

    def test_extract_router_hints_marks_web_only_constraint(self):
        hints = extract_router_hints("只查网络，不要本地：今天 OpenAI 最新模型是什么")

        self.assertTrue(hints.web_candidate)
        self.assertTrue(hints.force_web_only)
        self.assertFalse(hints.force_local_only)

    def test_extract_router_hints_marks_local_only_constraint(self):
        hints = extract_router_hints("只用本地文档，不要联网，帮我解释 Chroma")

        self.assertTrue(hints.doc_candidate)
        self.assertTrue(hints.force_local_only)
        self.assertFalse(hints.force_web_only)

    def test_explicit_web_only_rule_short_circuits_llm(self):
        with patch("app.tool_router.llm_tool_plan", side_effect=AssertionError("llm_tool_plan should not be called")):
            plan = decide_tool_plan("只查网络，不要本地：今天 OpenAI 最新模型是什么")

        self.assertEqual(plan.primary_tool, "web_search")
        self.assertEqual(plan.reason, "matched_explicit_web_only_constraint")
        self.assertEqual(plan.intent, "web_search")

    def test_explicit_local_only_rule_short_circuits_llm(self):
        with patch("app.tool_router.llm_tool_plan", side_effect=AssertionError("llm_tool_plan should not be called")):
            plan = decide_tool_plan("只用本地文档，不要联网，帮我解释 Chroma")

        self.assertEqual(plan.primary_tool, "local_doc_query")
        self.assertEqual(plan.reason, "matched_explicit_local_only_constraint")
        self.assertEqual(plan.intent, "doc_query")

    def test_summary_request_uses_llm_when_no_hard_constraint(self):
        with patch("app.tool_router.llm_tool_plan") as mock_llm:
            mock_llm.return_value = build_tool_plan(
                "local_doc_summary",
                reason="llm:summary",
                confidence=0.91,
                intent="doc_summary",
            )
            plan = decide_tool_plan("summarize this file", history=[])

        self.assertEqual(plan.primary_tool, "local_doc_summary")
        self.assertEqual(plan.reason, "llm:summary")
        mock_llm.assert_called_once()

    def test_direct_answer_request_uses_llm_when_no_hard_constraint(self):
        with patch("app.tool_router.llm_tool_plan") as mock_llm:
            mock_llm.return_value = build_tool_plan(
                "direct_answer",
                reason="llm:direct",
                confidence=0.9,
                intent="direct_answer",
            )
            plan = decide_tool_plan("hello")

        self.assertEqual(plan.primary_tool, "direct_answer")
        self.assertEqual(plan.intent, "direct_answer")
        mock_llm.assert_called_once()

    def test_low_confidence_web_guess_without_constraint_falls_back_to_direct_answer(self):
        with patch("app.tool_router.llm_tool_plan") as mock_llm:
            mock_llm.return_value = build_tool_plan(
                "web_search",
                reason="llm:web_guess",
                confidence=0.35,
                fallback_tool=None,
                intent="web_search",
            )
            plan = decide_tool_plan("Do you think this answer is okay?")

        self.assertEqual(plan.primary_tool, "direct_answer")
        self.assertEqual(plan.intent, "direct_answer")
        self.assertEqual(plan.reason, "typed_fallback_after_low_confidence_llm_route_fallback_direct_answer")


if __name__ == "__main__":
    unittest.main()
