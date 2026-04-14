import unittest
from unittest.mock import patch

from app import openviking_runtime


class OpenVikingRuntimeTests(unittest.TestCase):
    def test_extract_json_payload_reads_last_json_line(self):
        payload = openviking_runtime._extract_json_payload('cmd: ov ls\n{"ok":true,"result":[1,2]}')

        self.assertEqual(payload["result"], [1, 2])

    def test_search_openviking_resources_returns_root_scoped_hits(self):
        fake_search_result = {
            "resources": [
                {
                    "uri": "viking://resources/askrag/memory/l1/entry-1",
                    "level": 1,
                    "score": 0.12,
                    "abstract": "memory overview",
                },
                {
                    "uri": "viking://resources/other/entry-2",
                    "level": 1,
                    "score": 0.05,
                    "abstract": "ignore me",
                },
            ]
        }
        with patch.object(openviking_runtime, "ensure_openviking_healthy"), patch.object(
            openviking_runtime, "_run_ov_json_command", return_value=fake_search_result
        ):
            hits = openviking_runtime.search_openviking_resources(
                "remembered preference",
                root_uri="viking://resources/askrag/memory",
            )

        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0].uri, "viking://resources/askrag/memory/l1/entry-1")
        self.assertEqual(hits[0].abstract, "memory overview")

    def test_describe_openviking_runtime_reports_memory_context_role(self):
        with patch.object(openviking_runtime, "ensure_openviking_healthy", return_value={"healthy": True, "server": "ok"}):
            status = openviking_runtime.describe_openviking_runtime()

        self.assertEqual(status["role"], "memory_context_infrastructure")
        self.assertEqual(status["status"], "ready")
        self.assertEqual(status["required_for"], ["assistant_memory", "answer_time_context"])
        self.assertEqual(status["not_required_for"], ["document_upload", "document_index_rebuild", "chroma_document_retrieval"])
        self.assertTrue(status["healthy"])


if __name__ == "__main__":
    unittest.main()
