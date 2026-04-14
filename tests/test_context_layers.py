import unittest

from app.context_layers import ANALYSIS_TERMS, question_requires_deep_read


class ContextLayersTests(unittest.TestCase):
    def test_deep_read_triggers_for_protocol_question_in_chinese(self):
        self.assertTrue(question_requires_deep_read("递归学习法的操作协议是什么？", history=[]))

    def test_deep_read_triggers_for_step_by_step_question_in_chinese(self):
        self.assertTrue(question_requires_deep_read("递归学习法的具体操作步骤是什么？", history=[]))

    def test_deep_read_triggers_for_how_to_question_in_chinese(self):
        self.assertTrue(question_requires_deep_read("如何操作递归学习法？", history=[]))

    def test_deep_read_keeps_existing_english_trigger_terms(self):
        self.assertTrue(question_requires_deep_read("How does this method work in detail?", history=[]))

    def test_deep_read_does_not_trigger_for_plain_factoid_without_history(self):
        self.assertFalse(question_requires_deep_read("project_intro.txt 里 Chroma 是用来做什么的？", history=[]))

    def test_analysis_terms_include_common_chinese_summary_words(self):
        self.assertIn("分析", ANALYSIS_TERMS)
        self.assertIn("解读", ANALYSIS_TERMS)


if __name__ == "__main__":
    unittest.main()
