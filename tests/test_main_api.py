import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app
from app import session_memory


class MainApiTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.memory_path = Path(self.temp_dir.name) / "session_memory.json"
        self.loop_state_path = Path(self.temp_dir.name) / "loop_state.json"
        self.conversation_path = Path(self.temp_dir.name) / "conversation_threads.json"

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_ask_endpoint_returns_trace(self):
        with patch("app.conversations.CONVERSATION_STORE_PATH", self.conversation_path), patch(
            "app.main.stream_answer_question",
            return_value=iter(
                [
                    ("trace", {"mode": "query", "layers_used": ["L0", "L1"], "debug": {"memory_context_used": True}}),
                    ("sources", {"sources": ["data/docs/project_intro.txt"]}),
                    ("delta", {"text": "an"}),
                    ("delta", {"text": "swer"}),
                    ("memory_notices", {"items": [{"kind": "remembered", "summary": "Prefer concise answers.", "status": "approved"}]}),
                    ("done", {}),
                ]
            ),
        ):
            client = TestClient(app)
            response = client.post("/ask", json={"question": "What is Chroma?", "history": []})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["answer"], "answer")
        self.assertEqual(payload["trace"]["mode"], "query")
        self.assertEqual(payload["sources"], ["data/docs/project_intro.txt"])
        self.assertTrue(payload["conversation_id"])
        self.assertGreaterEqual(len(payload["memory_notices"]), 1)

        with patch("app.conversations.CONVERSATION_STORE_PATH", self.conversation_path):
            client = TestClient(app)
            conversation = client.get(f"/conversations/{payload['conversation_id']}")

        self.assertEqual(conversation.status_code, 200)
        conversation_payload = conversation.json()
        self.assertEqual(len(conversation_payload["messages"]), 2)
        self.assertEqual(conversation_payload["messages"][0]["role"], "user")
        self.assertEqual(conversation_payload["messages"][1]["role"], "assistant")

    def test_ask_endpoint_short_circuits_explicit_memory_commands(self):
        with patch("app.conversations.CONVERSATION_STORE_PATH", self.conversation_path), patch(
            "app.session_memory.MEMORY_STORE_PATH", self.memory_path
        ), patch(
            "app.session_memory.LEGACY_MEMORY_STORE_PATH", self.memory_path.with_name("legacy.json")
        ), patch(
            "app.session_memory._sync_entry_to_openviking", lambda entry: entry.update({"openviking_sync_status": "test_synced"})
        ), patch(
            "app.main.stream_answer_question"
        ) as mock_stream:
            client = TestClient(app)
            response = client.post("/ask", json={"question": "记住以后用中文回答", "history": []})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["answer"], "已记住，之后我会用中文回答。")
        self.assertEqual(payload["sources"], [])
        self.assertEqual(payload["trace"]["mode"], "memory_command")
        self.assertTrue(payload["conversation_id"])
        self.assertGreaterEqual(len(payload["memory_notices"]), 1)
        self.assertEqual(payload["memory_notices"][0]["kind"], "remembered")
        mock_stream.assert_not_called()

    def test_ask_stream_short_circuits_explicit_memory_commands(self):
        with patch("app.conversations.CONVERSATION_STORE_PATH", self.conversation_path), patch(
            "app.session_memory.MEMORY_STORE_PATH", self.memory_path
        ), patch(
            "app.session_memory.LEGACY_MEMORY_STORE_PATH", self.memory_path.with_name("legacy.json")
        ), patch(
            "app.session_memory._sync_entry_to_openviking", lambda entry: entry.update({"openviking_sync_status": "test_synced"})
        ), patch(
            "app.main.stream_answer_question"
        ) as mock_stream:
            client = TestClient(app)
            with client.stream("POST", "/ask/stream", json={"question": "记住：以后回答时先给结论", "history": []}) as response:
                body = "".join(chunk.decode("utf-8") if isinstance(chunk, bytes) else chunk for chunk in response.iter_text())

        self.assertEqual(response.status_code, 200)
        self.assertIn('event: trace', body)
        self.assertIn('"mode": "memory_command"', body)
        self.assertIn("已记住：以后回答时先给结论。", body)
        self.assertIn('event: memory_notices', body)
        self.assertIn('event: done', body)
        mock_stream.assert_not_called()

    def test_memory_extract_endpoint_persists_candidates(self):
        with patch("app.session_memory.MEMORY_STORE_PATH", self.memory_path), patch("app.session_memory.LEGACY_MEMORY_STORE_PATH", self.memory_path.with_name("legacy.json")), patch(
            "app.session_memory._sync_entry_to_openviking", lambda entry: entry.update({"openviking_sync_status": "test_synced"})
        ):
            client = TestClient(app)
            response = client.post(
                "/memories/extract",
                json={
                    "question": "请用中文简洁回答",
                    "answer": "project_intro.txt explains Chroma.",
                    "sources": ["data/docs/project_intro.txt"],
                    "history": [],
                    "persist": True,
                },
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertGreaterEqual(len(payload["memories"]), 1)
        self.assertIn(payload["memories"][0]["memory_type"], {"pinned_preference", "recent_task_state", "stable_profile_fact"})

    def test_ops_state_endpoint_returns_counts(self):
        records = [
            {
                "file_name": "project_intro.txt",
                "source": "data/docs/project_intro.txt",
                "md5": "abc",
                "uploaded_at": None,
                "chunk_count": 5,
            }
        ]
        state = {"canonical_verification_command": "python -m unittest", "stop_condition": "tests pass"}
        memory_entries = [
            {
                "id": "memory-1",
                "memory_type": "pinned_preference",
                "layer": "L1",
                "scope": "cross_thread",
                "status": "approved",
                "title": "Language preference",
                "summary": "Prefer Chinese responses.",
                "payload": {"preference_key": "response_language", "value": "zh-CN", "subject_key": "preference:response_language"},
                "subject_key": "preference:response_language",
                "source_refs": [],
                "tags": ["preference", "language"],
                "created_at": None,
                "updated_at": None,
                "confidence": 0.9,
            }
        ]
        openviking_status = {
            "role": "memory_context_infrastructure",
            "status": "ready",
            "healthy": True,
            "required_for": ["assistant_memory", "answer_time_context"],
            "not_required_for": ["document_upload", "document_index_rebuild", "chroma_document_retrieval"],
        }
        with patch("app.main.list_documents", return_value=records), patch("app.runtime_state.LOOP_STATE_PATH", self.loop_state_path), patch("app.main.read_loop_state", return_value=state), patch(
            "app.main.describe_openviking_runtime", return_value=openviking_status
        ), patch(
            "app.main.list_memory_entries", return_value=memory_entries
        ), patch("app.main.summarize_memory_store", return_value={"total": 1, "by_layer": {"L1": 1}}):
            client = TestClient(app)
            response = client.get("/ops/state")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["document_count"], 1)
        self.assertEqual(payload["state"]["canonical_verification_command"], "python -m unittest")
        self.assertEqual(payload["state"]["openviking"]["role"], "memory_context_infrastructure")
        self.assertIn("assistant_memory", payload["state"]["openviking"]["required_for"])
        self.assertIn("chroma_document_retrieval", payload["state"]["openviking"]["not_required_for"])
        self.assertEqual(payload["memory_summary"]["total"], 1)

    def test_documents_endpoint_hides_openviking_document_metadata(self):
        records = [
            {
                "file_name": "project_intro.txt",
                "source": "data/docs/project_intro.txt",
                "md5": "abc",
                "uploaded_at": None,
                "chunk_count": 5,
                "openviking_resource_uri": "viking://resources/askrag/docs/project-intro",
                "openviking_sync_status": "ready_for_sync",
            }
        ]
        with patch("app.main.list_documents", return_value=records):
            client = TestClient(app)
            response = client.get("/documents")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["documents"][0]["file_name"], "project_intro.txt")
        self.assertNotIn("openviking_resource_uri", payload["documents"][0])
        self.assertNotIn("openviking_sync_status", payload["documents"][0])

    def test_sync_openviking_endpoint_is_not_exposed(self):
        client = TestClient(app)
        response = client.post("/ops/sync-openviking")

        self.assertEqual(response.status_code, 404)

    def test_memory_page_route_serves_html(self):
        client = TestClient(app)
        response = client.get("/memory")

        self.assertEqual(response.status_code, 200)
        self.assertIn("text/html", response.headers.get("content-type", ""))
        self.assertIn("memoryList", response.text)

    def test_chat_page_route_serves_html_with_conversation_ui(self):
        client = TestClient(app)
        response = client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertIn("text/html", response.headers.get("content-type", ""))
        self.assertIn("conversationList", response.text)
        self.assertIn("newConversationButton", response.text)

    def test_library_page_route_serves_html_with_memory_nav(self):
        client = TestClient(app)
        response = client.get("/library")

        self.assertEqual(response.status_code, 200)
        self.assertIn("text/html", response.headers.get("content-type", ""))
        self.assertIn("documentList", response.text)
        self.assertIn('href="/memory"', response.text)

    def test_conversation_endpoints_create_list_and_delete_threads(self):
        with patch("app.conversations.CONVERSATION_STORE_PATH", self.conversation_path):
            client = TestClient(app)
            created = client.post("/conversations", json={"title": "Sprint planning"})

            self.assertEqual(created.status_code, 200)
            created_payload = created.json()
            conversation_id = created_payload["conversation"]["id"]
            self.assertEqual(created_payload["conversation"]["title"], "Sprint planning")

            listed = client.get("/conversations")
            self.assertEqual(listed.status_code, 200)
            listed_payload = listed.json()
            self.assertEqual(len(listed_payload["conversations"]), 1)
            self.assertEqual(listed_payload["conversations"][0]["id"], conversation_id)

            deleted = client.delete(f"/conversations/{conversation_id}")
            self.assertEqual(deleted.status_code, 200)

            listed_again = client.get("/conversations")
            self.assertEqual(listed_again.status_code, 200)
            self.assertEqual(listed_again.json()["conversations"], [])

    def test_conversation_delete_cascades_memory_entries_for_that_conversation(self):
        memory_docs_dir = Path(self.temp_dir.name) / "memory_docs"
        with patch("app.conversations.CONVERSATION_STORE_PATH", self.conversation_path), patch(
            "app.session_memory.MEMORY_STORE_PATH", self.memory_path
        ), patch(
            "app.session_memory.LEGACY_MEMORY_STORE_PATH", self.memory_path.with_name("legacy.json")
        ), patch(
            "app.session_memory.MEMORY_DOCS_DIR", memory_docs_dir
        ), patch(
            "app.session_memory._sync_entry_to_openviking", lambda entry: entry.update({"openviking_sync_status": "test_synced"})
        ):
            client = TestClient(app)
            created = client.post("/conversations", json={"title": "Memory cleanup"})
            conversation_id = created.json()["conversation"]["id"]

            session_memory.persist_memory_candidates(
                session_memory.extract_memory_candidates(
                    question="Remember I prefer Chinese responses.",
                    answer="",
                    sources=[],
                    history=[],
                ),
                conversation_id=conversation_id,
            )
            session_memory.persist_memory_candidates(
                session_memory.extract_memory_candidates(
                    question="Remember answers under 100 chars.",
                    answer="",
                    sources=[],
                    history=[],
                ),
                conversation_id="other-conversation",
            )

            deleted = client.delete(f"/conversations/{conversation_id}")
            self.assertEqual(deleted.status_code, 200)

            remaining = session_memory.list_memory_entries(include_pending=True, include_rolled_back=True, include_superseded=True)
            self.assertTrue(all(entry.get("conversation_id") != conversation_id for entry in remaining))
            self.assertTrue(any(entry.get("conversation_id") == "other-conversation" for entry in remaining))

    def test_memory_update_endpoint_edits_existing_entry(self):
        with patch("app.session_memory.MEMORY_STORE_PATH", self.memory_path), patch(
            "app.session_memory.LEGACY_MEMORY_STORE_PATH", self.memory_path.with_name("legacy.json")
        ), patch("app.session_memory._sync_entry_to_openviking", lambda entry: entry.update({"openviking_sync_status": "test_synced"})):
            client = TestClient(app)
            extract_response = client.post(
                "/memories/extract",
                json={
                    "question": "Please reply in English from now on.",
                    "answer": "",
                    "sources": [],
                    "history": [],
                    "persist": True,
                },
            )
            self.assertEqual(extract_response.status_code, 200)
            memory_id = extract_response.json()["memories"][0]["id"]

            update_response = client.patch(
                f"/memories/{memory_id}",
                json={"title": "Language preference", "summary": "Prefer English replies."},
            )

        self.assertEqual(update_response.status_code, 200)
        payload = update_response.json()
        self.assertEqual(payload["status"], "updated")
        self.assertEqual(payload["memory"]["title"], "Language preference")
        self.assertEqual(payload["memory"]["summary"], "Prefer English replies.")

    def test_memory_delete_endpoint_rolls_back_existing_entry(self):
        with patch("app.session_memory.MEMORY_STORE_PATH", self.memory_path), patch(
            "app.session_memory.LEGACY_MEMORY_STORE_PATH", self.memory_path.with_name("legacy.json")
        ), patch("app.session_memory._sync_entry_to_openviking", lambda entry: entry.update({"openviking_sync_status": "test_synced"})):
            client = TestClient(app)
            extract_response = client.post(
                "/memories/extract",
                json={
                    "question": "Please reply in English from now on.",
                    "answer": "",
                    "sources": [],
                    "history": [],
                    "persist": True,
                },
            )
            self.assertEqual(extract_response.status_code, 200)
            memory_id = extract_response.json()["memories"][0]["id"]

            delete_response = client.delete(f"/memories/{memory_id}")
            list_response = client.get("/memories")

        self.assertEqual(delete_response.status_code, 200)
        delete_payload = delete_response.json()
        self.assertEqual(delete_payload["status"], "rolled_back")
        self.assertEqual(delete_payload["memory"]["status"], "rolled_back")

        self.assertEqual(list_response.status_code, 200)
        list_payload = list_response.json()
        self.assertEqual(list_payload["memories"][0]["status"], "rolled_back")


if __name__ == "__main__":
    unittest.main()
