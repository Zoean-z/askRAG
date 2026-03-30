from collections.abc import Iterator
from typing import Any

from langchain_core.documents import Document
from openai import APIConnectionError, AuthenticationError, BadRequestError, RateLimitError

from app.rag import (
    EMPTY_ANSWER_MESSAGE,
    REFUSAL_MESSAGE,
    build_chat_messages,
    build_summary_chunk_messages,
    build_summary_messages,
    build_summary_reduce_messages,
    extract_stream_text,
    get_chat_client,
    get_chat_model,
    get_responses_client,
    get_web_search_model,
    normalize_history,
    split_documents,
)
from app.retrievers.chunk_retriever import build_context, prepare_chunk_answer_material
from app.retrievers.parent_retriever import choose_summary_document
from app.tool_router import ToolPlan, decide_tool_plan
from app.validators import should_fallback_to_summary, validate_chunk_results

DIRECT_ANSWER_SYSTEM_PROMPT = (
    "You are the assistant for a local RAG demo application. "
    "Answer brief small-talk or product capability questions directly. "
    "Handle safe text transformation requests such as translation, polishing, or rewriting. "
    "Do not claim to have searched the knowledge base unless retrieval was actually used. "
    "Keep the answer concise."
)
DIRECT_ANSWER_NOTICE = "[direct_answer] 以下回答未使用知识库。"
WEB_SEARCH_DISABLED_MESSAGE = "[web_search] \u5f53\u524d\u672a\u542f\u7528\u7f51\u9875\u67e5\u8be2\u5de5\u5177\uff0c\u65e0\u6cd5\u56de\u7b54\u8fd9\u7c7b\u9700\u8981\u8054\u7f51\u6216\u6700\u65b0\u4fe1\u606f\u7684\u95ee\u9898\u3002"
LONG_SUMMARY_DIRECT_THRESHOLD = 4200
SUMMARY_CHUNK_SIZE = 2200
SUMMARY_CHUNK_OVERLAP = 180
WEB_SEARCH_TOOLS = [
    {"type": "web_search"},
    {"type": "web_extractor"},
]
WEB_SEARCH_EXTRA_BODY = {"enable_thinking": True}
WEB_SEARCH_PROGRESS_MESSAGE = "[web_search] Searching the web..."
WEB_SEARCH_FAILURE_MESSAGE = "[web_search] Web search is temporarily unavailable. Check the DashScope Responses endpoint, model support, and tool permissions."


def build_web_search_failure_message(detail: str | None = None) -> str:
    message = WEB_SEARCH_FAILURE_MESSAGE
    normalized = (detail or "").strip()
    if normalized:
        return f"{message}\n\nDetail: {normalized}"
    return message


def _to_plain_data(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(key): _to_plain_data(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_plain_data(item) for item in value]
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        return _to_plain_data(model_dump())
    dict_method = getattr(value, "dict", None)
    if callable(dict_method):
        return _to_plain_data(dict_method())
    if hasattr(value, "__dict__"):
        return {str(key): _to_plain_data(item) for key, item in vars(value).items()}
    return value


def _collect_web_source_values(node: Any, collected: list[str]) -> None:
    if isinstance(node, dict):
        title = node.get("title") or node.get("name")
        url = node.get("url")
        if isinstance(url, str) and url.startswith(("http://", "https://")):
            collected.append(f"{title} ({url})" if isinstance(title, str) and title.strip() else url)

        for key in ("sources", "results", "citations"):
            child = node.get(key)
            if isinstance(child, list):
                for item in child:
                    _collect_web_source_values(item, collected)

        for value in node.values():
            if isinstance(value, (dict, list, tuple)):
                _collect_web_source_values(value, collected)
        return

    if isinstance(node, (list, tuple)):
        for item in node:
            _collect_web_source_values(item, collected)


def extract_web_search_sources(payload: Any) -> list[str]:
    plain = _to_plain_data(payload)
    collected: list[str] = []
    _collect_web_source_values(plain, collected)

    deduped: list[str] = []
    seen: set[str] = set()
    for item in collected:
        normalized = item.strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(normalized)
    return deduped[:5]


def extract_web_search_text(response: Any) -> str:
    output_text = getattr(response, "output_text", None)
    if isinstance(output_text, str) and output_text.strip():
        return output_text.strip()

    plain = _to_plain_data(response)
    outputs = plain.get("output", []) if isinstance(plain, dict) else []
    texts: list[str] = []
    for item in outputs:
        if not isinstance(item, dict) or item.get("type") != "message":
            continue
        for content in item.get("content", []):
            if isinstance(content, dict) and content.get("type") in {"output_text", "text", "input_text"}:
                text = content.get("text")
                if isinstance(text, str) and text.strip():
                    texts.append(text.strip())
    return "\n\n".join(texts).strip()


def build_web_search_request(question: str) -> dict[str, Any]:
    return {
        "model": get_web_search_model(),
        "input": question.strip(),
        "tools": WEB_SEARCH_TOOLS,
        "extra_body": dict(WEB_SEARCH_EXTRA_BODY),
    }


DIRECT_ANSWER_MAP = {
    "你好": "你好，我可以帮你基于本地知识库问答、总结文档，并管理已上传的文本文件。",
    "您好": "您好，我可以帮你基于本地知识库问答、总结文档，并管理已上传的文本文件。",
    "谢谢": "不客气。",
    "多谢": "不客气。",
    "你是谁": "我是这个本地知识库问答项目里的助手，负责基于知识库回答、总结文档和处理简单对话。",
    "你能做什么": "我可以基于当前知识库回答问题、总结文档，并支持上传和删除 `.txt`、`.md` 文件。",
    "你支持上传什么文件": "当前支持上传 UTF-8 编码的 `.txt` 和 `.md` 文件。",
    "这个项目支持上传什么文件": "当前支持上传 UTF-8 编码的 `.txt` 和 `.md` 文件。",
    "hello": "Hello. I can answer questions from the local knowledge base, summarize documents, and manage uploaded text files.",
    "hi": "Hello. I can answer questions from the local knowledge base, summarize documents, and manage uploaded text files.",
    "thanks": "You're welcome.",
    "thank you": "You're welcome.",
}


def normalize_direct_answer_key(question: str) -> str:
    return question.strip().casefold().replace("？", "").replace("?", "").replace("！", "").replace("!", "").replace("。", "")


def format_direct_answer(answer: str) -> str:
    body = answer.strip() or EMPTY_ANSWER_MESSAGE
    return f"{DIRECT_ANSWER_NOTICE}\n\n{body}"


def build_direct_answer_messages(question: str, history: list[dict[str, str]] | None = None) -> list[dict[str, str]]:
    history_block = ""
    normalized_history = normalize_history(history)
    if normalized_history:
        history_block = "\n".join(f"{item['role']}: {item['content']}" for item in normalized_history)

    content_parts = [f"Current question: {question.strip()}"]
    if history_block:
        content_parts.insert(0, f"Recent history:\n{history_block}")
    return [
        {"role": "system", "content": DIRECT_ANSWER_SYSTEM_PROMPT},
        {"role": "user", "content": "\n\n".join(content_parts)},
    ]


def answer_directly(question: str, history: list[dict[str, str]] | None = None) -> tuple[str, list[str]]:
    normalized_key = normalize_direct_answer_key(question)
    if normalized_key in DIRECT_ANSWER_MAP:
        return format_direct_answer(DIRECT_ANSWER_MAP[normalized_key]), []

    client = get_chat_client()
    response = client.chat.completions.create(
        model=get_chat_model(),
        temperature=0.2,
        messages=build_direct_answer_messages(question, history=history),
    )
    answer = response.choices[0].message.content or EMPTY_ANSWER_MESSAGE
    return format_direct_answer(answer), []


def stream_direct_answer(question: str, history: list[dict[str, str]] | None = None) -> Iterator[tuple[str, dict]]:
    answer, _ = answer_directly(question, history=history)
    yield "sources", {"sources": []}
    yield "delta", {"text": answer}
    yield "done", {}


def split_summary_document(document: Document) -> list[Document]:
    return split_documents(
        [Document(page_content=document.page_content, metadata={"source": document.metadata.get("source", "unknown")})],
        chunk_size=SUMMARY_CHUNK_SIZE,
        chunk_overlap=SUMMARY_CHUNK_OVERLAP,
    )


def summarize_loaded_document(document: Document, question: str) -> tuple[str, list[str]]:
    source = document.metadata.get("source", "unknown")
    content = document.page_content.strip()
    if not content:
        raise ValueError("The target document is empty.")

    client = get_chat_client()
    if len(content) <= LONG_SUMMARY_DIRECT_THRESHOLD:
        response = client.chat.completions.create(
            model=get_chat_model(),
            temperature=0.2,
            messages=build_summary_messages(question, source, content),
        )
        answer = response.choices[0].message.content or EMPTY_ANSWER_MESSAGE
        return answer.strip(), [source]

    summary_chunks = split_summary_document(document)
    partial_summaries: list[str] = []
    total = len(summary_chunks)
    for index, chunk in enumerate(summary_chunks, start=1):
        response = client.chat.completions.create(
            model=get_chat_model(),
            temperature=0.2,
            messages=build_summary_chunk_messages(question, source, chunk.page_content, index, total),
        )
        partial = response.choices[0].message.content or ""
        partial_summaries.append(partial.strip() or f"Chunk {index} did not return a summary.")

    response = client.chat.completions.create(
        model=get_chat_model(),
        temperature=0.2,
        messages=build_summary_reduce_messages(question, source, partial_summaries),
    )
    answer = response.choices[0].message.content or EMPTY_ANSWER_MESSAGE
    return answer.strip(), [source]


def stream_summarize_loaded_document(document: Document, question: str) -> Iterator[tuple[str, dict]]:
    source = document.metadata.get("source", "unknown")
    content = document.page_content.strip()
    if not content:
        raise ValueError("The target document is empty.")

    yield "sources", {"sources": [source]}
    yield "progress", {"stage": "summary_start", "source": source}

    client = get_chat_client()
    if len(content) <= LONG_SUMMARY_DIRECT_THRESHOLD:
        messages = build_summary_messages(question, source, content)
        yield "progress", {"stage": "summary_generating", "source": source}
    else:
        summary_chunks = split_summary_document(document)
        partial_summaries: list[str] = []
        total = len(summary_chunks)
        yield "progress", {"stage": "summary_chunking", "source": source, "total": total}
        for index, chunk in enumerate(summary_chunks, start=1):
            yield "progress", {
                "stage": "summary_chunk",
                "source": source,
                "current": index,
                "total": total,
            }
            response = client.chat.completions.create(
                model=get_chat_model(),
                temperature=0.2,
                messages=build_summary_chunk_messages(question, source, chunk.page_content, index, total),
            )
            partial = response.choices[0].message.content or ""
            partial_summaries.append(partial.strip() or f"Chunk {index} did not return a summary.")
        yield "progress", {"stage": "summary_reduce", "source": source, "total": total}
        messages = build_summary_reduce_messages(question, source, partial_summaries)

    stream = client.chat.completions.create(
        model=get_chat_model(),
        temperature=0.2,
        messages=messages,
        stream=True,
    )

    has_text = False
    for chunk in stream:
        if not chunk.choices:
            continue

        delta = getattr(chunk.choices[0], "delta", None)
        text = extract_stream_text(getattr(delta, "content", None))
        if not text:
            continue

        has_text = True
        yield "delta", {"text": text}

    if not has_text:
        yield "delta", {"text": EMPTY_ANSWER_MESSAGE}

    yield "done", {}


def answer_local_summary(
    question: str,
    history: list[dict[str, str]] | None = None,
    *,
    require_strong_parent_match: bool = True,
    child_results: list[tuple[Document, float]] | None = None,
) -> tuple[str, list[str]]:
    document = choose_summary_document(
        question,
        history=history,
        require_strong_parent_match=require_strong_parent_match,
        child_results=child_results,
    )
    return summarize_loaded_document(document, question)


def stream_local_summary(
    question: str,
    history: list[dict[str, str]] | None = None,
    *,
    require_strong_parent_match: bool = True,
    child_results: list[tuple[Document, float]] | None = None,
) -> Iterator[tuple[str, dict]]:
    document = choose_summary_document(
        question,
        history=history,
        require_strong_parent_match=require_strong_parent_match,
        child_results=child_results,
    )
    yield from stream_summarize_loaded_document(document, question)


def execute_chunk_path(
    question: str,
    tool_plan: ToolPlan,
    history: list[dict[str, str]] | None = None,
    k: int = 3,
) -> tuple[str, list[str]]:
    bundle = prepare_chunk_answer_material(question, history=history, k=k)
    validation = validate_chunk_results(bundle.vector_results, bundle.keyword_results)
    if should_fallback_to_summary(tool_plan, validation):
        try:
            return answer_local_summary(
                question,
                history=history,
                require_strong_parent_match=True,
                child_results=bundle.merged_results,
            )
        except ValueError:
            return REFUSAL_MESSAGE, bundle.sources

    if not validation.is_sufficient:
        return REFUSAL_MESSAGE, bundle.sources

    context = build_context(bundle.results)
    client = get_chat_client()
    response = client.chat.completions.create(
        model=get_chat_model(),
        temperature=0.2,
        messages=build_chat_messages(
            question,
            context,
            history=bundle.history,
            standalone_question=bundle.rewritten_question,
        ),
    )

    answer = response.choices[0].message.content or EMPTY_ANSWER_MESSAGE
    return answer.strip(), bundle.sources


def execute_chunk_stream_path(
    question: str,
    tool_plan: ToolPlan,
    history: list[dict[str, str]] | None = None,
    k: int = 3,
) -> Iterator[tuple[str, dict]]:
    bundle = prepare_chunk_answer_material(question, history=history, k=k)
    validation = validate_chunk_results(bundle.vector_results, bundle.keyword_results)
    if should_fallback_to_summary(tool_plan, validation):
        try:
            yield from stream_local_summary(
                question,
                history=history,
                require_strong_parent_match=True,
                child_results=bundle.merged_results,
            )
            return
        except ValueError:
            yield "sources", {"sources": bundle.sources}
            yield "delta", {"text": REFUSAL_MESSAGE}
            yield "done", {}
            return

    yield "sources", {"sources": bundle.sources}

    if not validation.is_sufficient:
        yield "delta", {"text": REFUSAL_MESSAGE}
        yield "done", {}
        return

    context = build_context(bundle.results)
    client = get_chat_client()
    stream = client.chat.completions.create(
        model=get_chat_model(),
        temperature=0.2,
        messages=build_chat_messages(
            question,
            context,
            history=bundle.history,
            standalone_question=bundle.rewritten_question,
        ),
        stream=True,
    )

    has_text = False
    for chunk in stream:
        if not chunk.choices:
            continue

        delta = getattr(chunk.choices[0], "delta", None)
        text = extract_stream_text(getattr(delta, "content", None))
        if not text:
            continue

        has_text = True
        yield "delta", {"text": text}

    if not has_text:
        yield "delta", {"text": EMPTY_ANSWER_MESSAGE}

    yield "done", {}


def answer_web_search(question: str, tool_plan: ToolPlan) -> tuple[str, list[str]]:
    try:
        client = get_responses_client()
        response = client.responses.create(**build_web_search_request(question))
    except (ValueError, AuthenticationError, RateLimitError, BadRequestError, APIConnectionError) as error:
        return build_web_search_failure_message(str(error)), []

    answer = extract_web_search_text(response) or EMPTY_ANSWER_MESSAGE
    sources = extract_web_search_sources(response)
    return answer, sources


def stream_web_search(question: str, tool_plan: ToolPlan) -> Iterator[tuple[str, dict]]:
    yield "progress", {"stage": "web_search_start"}

    try:
        client = get_responses_client()
        stream = client.responses.create(stream=True, **build_web_search_request(question))
    except (ValueError, AuthenticationError, RateLimitError, BadRequestError, APIConnectionError) as error:
        yield "progress", {"stage": "web_search_failed", "detail": str(error)}
        yield "sources", {"sources": []}
        yield "delta", {"text": build_web_search_failure_message(str(error))}
        yield "done", {}
        return

    buffered_text = False
    final_sources: list[str] = []

    for event in stream:
        event_type = getattr(event, "type", "")
        if event_type == "response.output_text.delta":
            delta = getattr(event, "delta", "") or ""
            if delta:
                if not buffered_text:
                    yield "sources", {"sources": []}
                    buffered_text = True
                yield "delta", {"text": delta}
        elif event_type == "response.completed":
            response = getattr(event, "response", None)
            final_sources = extract_web_search_sources(response)
            if not buffered_text:
                answer = extract_web_search_text(response) or EMPTY_ANSWER_MESSAGE
                yield "sources", {"sources": final_sources}
                yield "delta", {"text": answer}
                buffered_text = True
            else:
                yield "sources", {"sources": final_sources}

    if not buffered_text:
        yield "sources", {"sources": final_sources}
        yield "delta", {"text": EMPTY_ANSWER_MESSAGE}
    yield "done", {}


def answer_question(question: str, history: list[dict[str, str]] | None = None, k: int = 3) -> tuple[str, list[str]]:
    normalized_history = normalize_history(history)
    tool_plan = decide_tool_plan(question, history=normalized_history)

    if tool_plan.primary_tool == "direct_answer":
        return answer_directly(question, history=normalized_history)

    if tool_plan.primary_tool == "local_doc_summary":
        return answer_local_summary(question, history=normalized_history, require_strong_parent_match=True)

    if tool_plan.primary_tool == "web_search":
        return answer_web_search(question, tool_plan)

    return execute_chunk_path(question, tool_plan, history=normalized_history, k=k)


def stream_answer_question(
    question: str,
    history: list[dict[str, str]] | None = None,
    k: int = 3,
) -> Iterator[tuple[str, dict]]:
    normalized_history = normalize_history(history)
    tool_plan = decide_tool_plan(question, history=normalized_history)

    if tool_plan.primary_tool == "direct_answer":
        yield from stream_direct_answer(question, history=normalized_history)
        return

    if tool_plan.primary_tool == "local_doc_summary":
        yield from stream_local_summary(question, history=normalized_history, require_strong_parent_match=True)
        return

    if tool_plan.primary_tool == "web_search":
        yield from stream_web_search(question, tool_plan)
        return

    yield from execute_chunk_stream_path(question, tool_plan, history=normalized_history, k=k)
