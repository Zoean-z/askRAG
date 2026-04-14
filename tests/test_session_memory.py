import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app import session_memory


class SessionMemoryTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.memory_path = Path(self.temp_dir.name) / "memory_registry.json"
        self.legacy_path = Path(self.temp_dir.name) / "session_memory.json"
        self.store_patcher = patch.object(session_memory, "MEMORY_STORE_PATH", self.memory_path)
        self.legacy_patcher = patch.object(session_memory, "LEGACY_MEMORY_STORE_PATH", self.legacy_path)
        self.sync_patcher = patch.object(session_memory, "_sync_entry_to_openviking", lambda entry: entry.update({"openviking_sync_status": "test_synced"}))
        self.store_patcher.start()
        self.legacy_patcher.start()
        self.sync_patcher.start()

    def tearDown(self):
        self.sync_patcher.stop()
        self.legacy_patcher.stop()
        self.store_patcher.stop()
        self.temp_dir.cleanup()

    def test_extract_candidates_includes_layered_types(self):
        candidates = session_memory.extract_memory_candidates(
            question="请用中文简洁回答这个问题",
            answer="project_intro.txt explains that Chroma is the local vector store.",
            sources=["data/docs/project_intro.txt"],
            history=[],
        )

        memory_types = {item["memory_type"] for item in candidates}
        self.assertIn("pinned_preference", memory_types)
        self.assertIn("recent_task_state", memory_types)

    def test_explicit_remember_chinese_response_preference_extracts_pinned_preference(self):
        candidates = session_memory.extract_memory_candidates(
            question="\u8bb0\u4f4f\u4ee5\u540e\u7528\u4e2d\u6587\u56de\u7b54",
            answer="",
            sources=[],
            history=[],
        )

        preference = next(item for item in candidates if item["memory_type"] == "pinned_preference")
        self.assertEqual(preference["title"], "Language preference")
        self.assertEqual(preference["payload"]["preference_key"], "response_language")
        self.assertEqual(preference["payload"]["value"], "zh-CN")

    def test_polite_chinese_response_preference_extracts_pinned_preference(self):
        candidates = session_memory.extract_memory_candidates(
            question="\u8bf7\u4ee5\u540e\u7528\u4e2d\u6587\u56de\u7b54",
            answer="",
            sources=[],
            history=[],
        )

        preference = next(item for item in candidates if item["memory_type"] == "pinned_preference")
        self.assertEqual(preference["title"], "Language preference")
        self.assertEqual(preference["payload"]["preference_key"], "response_language")
        self.assertEqual(preference["payload"]["value"], "zh-CN")

    def test_prefer_chinese_extracts_language_preference(self):
        candidates = session_memory.extract_memory_candidates(
            question="prefer Chinese",
            answer="",
            sources=[],
            history=[],
        )

        preference = next(item for item in candidates if item["memory_type"] == "pinned_preference")
        self.assertEqual(preference["title"], "Language preference")
        self.assertEqual(preference["payload"]["preference_key"], "response_language")
        self.assertEqual(preference["payload"]["value"], "zh-CN")

    def test_generic_explicit_remember_falls_back_to_generic_pinned_preference(self):
        candidates = session_memory.extract_memory_candidates(
            question="\u8bb0\u4f4f\u4ee5\u540e\u56de\u7b54\u65f6\u5148\u7ed9\u7ed3\u8bba",
            answer="",
            sources=[],
            history=[],
        )

        preference = next(item for item in candidates if item["memory_type"] == "pinned_preference")
        self.assertEqual(preference["title"], "Pinned memory")
        self.assertEqual(preference["payload"]["instruction"], "\u4ee5\u540e\u56de\u7b54\u65f6\u5148\u7ed9\u7ed3\u8bba")

    def test_remember_max_answer_chars_extracts_structured_preference(self):
        candidates = session_memory.extract_memory_candidates(
            question="记住以后回答不要超过一百字",
            answer="",
            sources=[],
            history=[],
        )

        preference = next(
            item
            for item in candidates
            if item["memory_type"] == "pinned_preference" and item["payload"].get("preference_key") == "max_answer_chars"
        )
        self.assertEqual(preference["payload"]["value"], 100)

    def test_build_response_constraints_collects_language_and_length_preferences(self):
        session_memory.record_completed_turn(
            question="记住以后用中文回答",
            answer="好的。",
            sources=[],
            history=[],
        )
        session_memory.record_completed_turn(
            question="记住以后回答不要超过一百字",
            answer="好的。",
            sources=[],
            history=[],
        )

        constraints = session_memory.build_response_constraints()

        self.assertEqual(constraints["response_language"], "zh-CN")
        self.assertEqual(constraints["max_answer_chars"], 100)

    def test_extract_explicit_memory_command_candidates_requires_remember_keyword(self):
        explicit_candidates = session_memory.extract_explicit_memory_command_candidates(
            question="记住以后用中文回答",
            history=[],
        )
        non_explicit_candidates = session_memory.extract_explicit_memory_command_candidates(
            question="请以后用中文回答",
            history=[],
        )

        self.assertTrue(explicit_candidates)
        self.assertEqual(non_explicit_candidates, [])

    def test_build_explicit_memory_command_reply_prefers_localized_language_confirmation(self):
        entries = session_memory.extract_explicit_memory_command_candidates(
            question="记住以后用中文回答",
            history=[],
        )

        reply = session_memory.build_explicit_memory_command_reply("记住以后用中文回答", entries)

        self.assertEqual(reply, "已记住，之后我会用中文回答。")

    def test_build_explicit_memory_command_reply_confirms_max_answer_chars(self):
        entries = session_memory.extract_explicit_memory_command_candidates(
            question="记住以后回答不要超过100字",
            history=[],
        )

        reply = session_memory.build_explicit_memory_command_reply("记住以后回答不要超过100字", entries)

        self.assertEqual(reply, "已记住，之后我会尽量把回答控制在 100 字以内。")

    def test_approve_and_rollback_update_status(self):
        stored = session_memory.persist_memory_candidates(
            session_memory.extract_memory_candidates(
                question="请用中文回答",
                answer="The latest answer references project_intro.",
                sources=["data/docs/project_intro.txt"],
                history=[],
            )
        )
        target_id = stored[0]["id"]

        approved = session_memory.approve_memory_entry(target_id)
        rolled_back = session_memory.rollback_memory_entry(target_id, detail="manual test")

        self.assertEqual(approved["status"], "approved")
        self.assertEqual(rolled_back["status"], "rolled_back")

    def test_build_memory_context_uses_approved_entries(self):
        stored = session_memory.persist_memory_candidates(
            session_memory.extract_memory_candidates(
                question="请用中文简洁回答",
                answer="Chroma stores local vectors for the project.",
                sources=["data/docs/project_intro.txt"],
                history=[],
            )
        )
        for entry in stored:
            if entry["status"] != "approved":
                session_memory.approve_memory_entry(entry["id"])

        context = session_memory.build_memory_context(
            "请继续解释 project_intro.txt",
            sources=["data/docs/project_intro.txt"],
            history=[],
        )

        self.assertIn("[Session Memory]", context)
        self.assertIn("pinned_preference", context)

    def test_build_memory_context_prefers_openviking_hits_when_available(self):
        stored = session_memory.record_completed_turn(
            question="Remember I prefer Chinese answers.",
            answer="project_intro.txt explains that Chroma is the local vector store.",
            sources=["data/docs/project_intro.txt"],
            history=[],
        )
        with patch(
            "app.session_memory._search_openviking_memory_entries",
            return_value=[entry for entry in stored if entry["memory_type"] == "recent_task_state"],
        ):
            context = session_memory.build_memory_context(
                "Explain project_intro.txt again",
                sources=["data/docs/project_intro.txt"],
                history=[],
            )

        self.assertIn("Recent discussion referenced project_intro.txt.", context)

    def test_build_reference_history_reconstructs_recent_turns_from_memory(self):
        session_memory.record_completed_turn(
            question="What is Chroma used for?",
            answer="Chroma stores local vectors for the project.",
            sources=["data/docs/project_intro.txt"],
            history=[],
        )

        history = session_memory.build_reference_history("How does it work?", [])

        self.assertEqual(history[0]["role"], "user")
        self.assertEqual(history[1]["role"], "assistant")
        self.assertEqual(history[0]["content"], "What is Chroma used for?")
        self.assertIn("Chroma stores local vectors", history[1]["content"])

    def test_record_completed_turn_writes_turn_and_summary_memory(self):
        stored = session_memory.record_completed_turn(
            question="记住我喜欢中文回答",
            answer="Chroma stores local vectors for the project.",
            sources=["data/docs/project_intro.txt"],
            history=[],
        )

        memory_types = {entry["memory_type"] for entry in stored}
        self.assertIn("raw_turn_log", memory_types)
        self.assertIn("working_summary", memory_types)
        self.assertIn("pinned_preference", memory_types)

    def test_cross_thread_preference_recall_is_available_without_history(self):
        session_memory.record_completed_turn(
            question="记住我喜欢中文回答",
            answer="好的，我会用中文回答。",
            sources=[],
            history=[],
        )

        context = session_memory.build_memory_context("继续说下去", history=[], sources=[])

        self.assertIn("pinned_preference", context)

    def test_profile_fact_supersedes_previous_value(self):
        first = session_memory.persist_memory_candidates(
            session_memory.extract_memory_candidates(question="我是男的", answer="", sources=[], history=[])
        )
        second = session_memory.persist_memory_candidates(
            session_memory.extract_memory_candidates(question="我是女的", answer="", sources=[], history=[])
        )

        entries = session_memory.list_memory_entries(include_pending=True, include_rolled_back=True, include_superseded=True)
        profile_entries = [entry for entry in entries if entry["memory_type"] == "stable_profile_fact"]

        self.assertEqual(len(first), 1)
        self.assertEqual(len(second), 1)
        self.assertEqual(len(profile_entries), 2)
        self.assertEqual(profile_entries[0]["summary"], "User gender: female.")
        self.assertEqual(profile_entries[1]["status"], "superseded")

    def test_record_completed_turn_does_not_promote_generic_answer_to_long_term_fact(self):
        stored = session_memory.record_completed_turn(
            question="What is Chroma used for?",
            answer="Chroma stores local vectors for the project.",
            sources=["data/docs/project_intro.txt"],
            history=[],
        )

        memory_types = {entry["memory_type"] for entry in stored}
        self.assertNotIn("approved_long_term_fact", memory_types)

    def test_expired_recent_task_state_is_not_used_in_context(self):
        stored = session_memory.persist_memory_candidates(
            session_memory.extract_memory_candidates(
                question="Explain project_intro.txt",
                answer="Recent work focused on project_intro.txt.",
                sources=["data/docs/project_intro.txt"],
                history=[],
            )
        )
        target = next(entry for entry in stored if entry["memory_type"] == "recent_task_state")
        store = session_memory.read_memory_store()
        for entry in store["entries"]:
            if entry["id"] == target["id"]:
                entry["expires_at"] = "2000-01-01T00:00:00Z"
                break
        session_memory.write_memory_store(store)

        context = session_memory.build_memory_context(
            "继续解释 project_intro.txt",
            history=[],
            sources=["data/docs/project_intro.txt"],
        )

        self.assertNotIn(target["summary"], context)

    def test_expired_recent_context_drops_but_long_term_preference_remains(self):
        session_memory.record_completed_turn(
            question="请记住我喜欢中文回答，并继续处理 project_intro.txt",
            answer="Recent work focused on project_intro.txt.",
            sources=["data/docs/project_intro.txt"],
            history=[],
        )

        store = session_memory.read_memory_store()
        preference = next(entry for entry in store["entries"] if entry["memory_type"] == "pinned_preference")
        for entry in store["entries"]:
            if entry["memory_type"] in session_memory.SHORT_LIVED_TYPES:
                entry["expires_at"] = "2000-01-01T00:00:00Z"
        session_memory.write_memory_store(store)

        context = session_memory.build_memory_context("继续说下去", history=[], sources=["data/docs/project_intro.txt"])

        self.assertNotIn("recent_task_state", context)
        self.assertNotIn("working_summary", context)
        self.assertIn(preference["summary"], context)

    def test_build_reference_history_does_not_use_long_term_memory_lane(self):
        session_memory.persist_memory_candidates(
            session_memory.extract_memory_candidates(
                question="记住我喜欢中文回答",
                answer="好的，我会用中文回答。",
                sources=[],
                history=[],
            )
        )

        history = session_memory.build_reference_history("继续说下去", [])

        self.assertEqual(history, [])

    def test_legacy_store_is_migrated(self):
        self.legacy_path.write_text(
            """{
  "entries": [
    {
      "id": "legacy-1",
      "memory_type": "user_preference",
      "status": "approved",
      "title": "Language preference",
      "summary": "Prefer Chinese responses.",
      "payload": {"response_language": "zh-CN"},
      "tags": ["preference", "language"]
    }
  ],
  "audit": []
}""",
            encoding="utf-8",
        )

        store = session_memory.read_memory_store()

        self.assertEqual(store["schema_version"], session_memory.MEMORY_SCHEMA_VERSION)
        self.assertEqual(store["entries"][0]["memory_type"], "pinned_preference")

    def test_find_recent_summary_memory_context_prefers_memory_registry(self):
        session_memory.record_completed_turn(
            question="summarize project_intro.txt",
            answer="Chroma stores local vectors. The app supports Markdown uploads. Answers can be streamed.",
            sources=["data/docs/project_intro.txt"],
            history=[],
        )

        context = session_memory.find_recent_summary_memory_context()

        self.assertIsNotNone(context)
        assert context is not None
        self.assertEqual(context.sources, ["data/docs/project_intro.txt"])
        self.assertIn("Chroma stores local vectors", context.assistant_answer)


if __name__ == "__main__":
    unittest.main()
