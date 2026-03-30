import unittest
from unittest.mock import patch

from app.router import decide_route


class RouterCompatibilityTests(unittest.TestCase):
    def test_direct_answer_rule_maps_to_legacy_route(self):
        with patch("app.router.llm_route", side_effect=AssertionError("llm_route should not be called")):
            decision = decide_route("hello")

        self.assertEqual(decision.route, "direct_answer")
        self.assertEqual(decision.reason, "matched_direct_answer_rule")
        self.assertFalse(decision.allow_fallback)

    def test_summary_rule_maps_to_legacy_route(self):
        history = [{"role": "assistant", "content": "previous answer", "sources": ["data/docs/project_intro.txt"]}]
        with patch("app.router.llm_route", side_effect=AssertionError("llm_route should not be called")):
            decision = decide_route("summarize this file", history=history)

        self.assertEqual(decision.route, "local_summary")
        self.assertEqual(decision.reason, "matched_summary_rule")
        self.assertFalse(decision.allow_fallback)

    def test_regular_question_defaults_to_legacy_local_chunk(self):
        with patch("app.router.llm_route", side_effect=AssertionError("llm_route should not be called")):
            decision = decide_route("What is Chroma")

        self.assertEqual(decision.route, "local_chunk")
        self.assertEqual(decision.reason, "default_local_doc_query_rule")
        self.assertTrue(decision.allow_fallback)

    def test_web_search_rule_maps_to_legacy_web_search_route(self):
        with patch("app.router.llm_route", side_effect=AssertionError("llm_route should not be called")):
            decision = decide_route("What is the latest OpenAI model today?")

        self.assertEqual(decision.route, "web_search")
        self.assertEqual(decision.reason, "matched_web_search_rule")
        self.assertFalse(decision.allow_fallback)

    def test_ambiguous_capability_question_can_still_use_legacy_llm_wrapper(self):
        with patch("app.router.llm_route") as mock_llm:
            mock_llm.return_value = type("Decision", (), {
                "route": "direct_answer",
                "reason": "llm:capability",
                "confidence": 0.9,
                "allow_fallback": False,
            })()
            decision = decide_route("What can you do beyond local docs?")

        self.assertEqual(decision.route, "direct_answer")
        mock_llm.assert_called_once()


if __name__ == "__main__":
    unittest.main()
