import unittest
from types import SimpleNamespace
from unittest.mock import patch

from langchain_core.documents import Document

from app.pipeline import (
    DIRECT_ANSWER_NOTICE,
    WEB_SEARCH_FAILURE_MESSAGE,
    answer_directly,
    answer_question,
    execute_chunk_path,
    stream_answer_question,
    stream_summarize_loaded_document,
)
from app.retrievers.chunk_retriever import ChunkRetrievalBundle
from app.tool_router import build_tool_plan


class _FakeCompletions:
    def create(self, **kwargs):
        if kwargs.get("stream"):
            return [SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content="final summary"))])]
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="partial summary"))])


class _FakeChatClient:
    def __init__(self):
        self.chat = SimpleNamespace(completions=_FakeCompletions())


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


class PipelineDirectAnswerTests(unittest.TestCase):
    def test_direct_answer_includes_notice_prefix(self):
        answer, sources = answer_directly("hello")

        self.assertTrue(answer.startswith(DIRECT_ANSWER_NOTICE))
        self.assertEqual(sources, [])

    def test_stream_summary_emits_progress_events(self):
        document = Document(page_content="x" * 6000, metadata={"source": "data/docs/project_intro.txt"})
        with patch("app.pipeline.get_chat_client", return_value=_FakeChatClient()):
            events = list(stream_summarize_loaded_document(document, "summarize this file"))

        event_names = [name for name, _ in events]
        self.assertEqual(event_names[0], "sources")
        self.assertEqual(event_names[1], "progress")
        self.assertIn("progress", event_names)
        self.assertIn("delta", event_names)
        self.assertEqual(event_names[-1], "done")
        self.assertTrue(any(payload.get("stage") == "summary_chunk" for name, payload in events if name == "progress"))
        self.assertTrue(any(payload.get("stage") == "summary_reduce" for name, payload in events if name == "progress"))

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

    def test_answer_question_uses_qwen_responses_web_search(self):
        fake_client = _FakeResponsesClient()
        with patch("app.pipeline.get_responses_client", return_value=fake_client), patch(
            "app.pipeline.get_web_search_model", return_value="qwen3.5-plus"
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
        ):
            events = list(stream_answer_question("What is the latest OpenAI model today?"))

        self.assertEqual(events[0], ("progress", {"stage": "web_search_start"}))
        self.assertEqual(events[1], ("sources", {"sources": []}))
        self.assertEqual(events[2], ("delta", {"text": "Latest "}))
        self.assertEqual(events[3], ("delta", {"text": "model answer."}))
        self.assertEqual(events[4], ("sources", {"sources": ["OpenAI Models (https://platform.openai.com/docs/models)"]}))
        self.assertEqual(events[-1], ("done", {}))

    def test_answer_question_returns_web_search_fallback_message_on_failure(self):
        with patch("app.pipeline.get_responses_client", side_effect=ValueError("responses unavailable")):
            answer, sources = answer_question("What is the latest OpenAI model today?")

        self.assertIn(WEB_SEARCH_FAILURE_MESSAGE, answer)
        self.assertEqual(sources, [])

    def test_stream_answer_question_returns_web_search_fallback_message_on_failure(self):
        with patch("app.pipeline.get_responses_client", side_effect=ValueError("responses unavailable")):
            events = list(stream_answer_question("What is the latest OpenAI model today?"))

        self.assertEqual(events[0], ("progress", {"stage": "web_search_start"}))
        self.assertEqual(events[1], ("progress", {"stage": "web_search_failed", "detail": "responses unavailable"}))
        self.assertEqual(events[2], ("sources", {"sources": []}))
        self.assertIn(WEB_SEARCH_FAILURE_MESSAGE, events[3][1]["text"])
        self.assertEqual(events[-1], ("done", {}))


if __name__ == "__main__":
    unittest.main()
