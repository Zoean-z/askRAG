import json
import os
import sys
from pathlib import Path
from time import perf_counter

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from openai import APIConnectionError, AuthenticationError, BadRequestError, RateLimitError

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.conversations import (
    append_conversation_message,
    create_conversation,
    delete_conversation,
    ensure_conversation,
    get_conversation,
    list_conversations,
)
from app.agent_tools import log_diagnostic_event
from app.documents import delete_document, list_documents, rebuild_vector_index, store_uploaded_document
from app.openviking_runtime import describe_openviking_runtime
from app.rag import get_chat_model, get_web_search_model, stream_answer_question
from app.runtime_state import read_loop_state, record_operation
from app.schemas import (
    AskRequest,
    AskResponse,
    ConversationCreateRequest,
    ConversationDeleteResponse,
    ConversationListResponse,
    ConversationMessageRecord,
    ConversationRecord,
    ConversationResponse,
    DeleteDocumentResponse,
    DocumentListResponse,
    DocumentRecord,
    MemoryActionResponse,
    MemoryEntryRecord,
    MemoryExtractRequest,
    MemoryExtractResponse,
    MemoryListResponse,
    MemoryNoticeRecord,
    MemoryUpdateRequest,
    MemoryUpdateResponse,
    OperationResponse,
    OpsStateResponse,
    UploadDocumentResponse,
)
from app.session_memory import (
    approve_memory_entry,
    build_explicit_memory_command_reply,
    delete_memory_entries_for_conversation,
    extract_explicit_memory_command_candidates,
    extract_memory_candidates,
    list_memory_entries,
    persist_memory_candidates,
    read_memory_store,
    remove_memory_entry,
    rollback_memory_entry,
    summarize_memory_store,
    update_memory_entry,
)

BASE_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = BASE_DIR / "frontend"

app = FastAPI(
    title="Local Knowledge Base QA Assistant",
    description="A minimal FastAPI wrapper for the local RAG demo.",
)
app.mount("/assets", StaticFiles(directory=FRONTEND_DIR), name="assets")


def normalize_history(messages) -> list[dict[str, str]]:
    normalized: list[dict[str, str]] = []
    for message in messages:
        content = message.content.strip()
        if not content:
            continue
        entry = {"role": message.role, "content": content}
        sources = [source.strip() for source in message.sources if source and source.strip()]
        if sources:
            entry["sources"] = sources
        normalized.append(entry)
    return normalized


def sse_event(event_name: str, data: dict) -> str:
    payload = json.dumps(data, ensure_ascii=False)
    return f"event: {event_name}\ndata: {payload}\n\n"


def _conversation_record(conversation: dict) -> ConversationRecord:
    messages = [item for item in conversation.get("messages") or [] if isinstance(item, dict)]
    last_preview = ""
    for item in reversed(messages):
        content = str(item.get("content") or "").strip()
        if content:
            last_preview = content[:140]
            break
    return ConversationRecord(
        id=str(conversation.get("id") or ""),
        title=str(conversation.get("title") or "New chat"),
        created_at=conversation.get("created_at"),
        updated_at=conversation.get("updated_at"),
        message_count=len(messages),
        last_message_preview=last_preview,
    )


def _conversation_message_record(message: dict) -> ConversationMessageRecord:
    notices = [MemoryNoticeRecord(**item) for item in message.get("memory_notices") or [] if isinstance(item, dict)]
    return ConversationMessageRecord(
        id=str(message.get("id") or ""),
        role=str(message.get("role") or "assistant"),
        content=str(message.get("content") or ""),
        sources=[str(item) for item in message.get("sources") or [] if str(item).strip()],
        created_at=message.get("created_at"),
        memory_notices=notices,
        trace=dict(message.get("trace") or {}),
    )


def _serialize_memory_notices(items: list[dict]) -> list[MemoryNoticeRecord]:
    return [MemoryNoticeRecord(**item) for item in items if isinstance(item, dict)]


def _build_memory_notices(entries: list[dict] | None = None, trace: dict | None = None) -> list[dict]:
    notices: list[dict] = []
    if trace and bool(((trace.get("debug") or {}).get("memory_context_used"))):
        notices.append({"kind": "used", "summary": "Used assistant memory such as saved preferences or task context for this answer."})

    for entry in entries or []:
        memory_type = str(entry.get("memory_type") or "")
        if memory_type not in {"pinned_preference", "stable_profile_fact", "recent_task_state", "approved_long_term_fact"}:
            continue
        summary = str(entry.get("summary") or "").strip()
        if not summary:
            continue
        status = str(entry.get("status") or "")
        notices.append(
            {
                "kind": "remembered" if status == "approved" else "candidate",
                "summary": summary,
                "memory_type": memory_type,
                "status": status,
            }
        )
    return notices[:3]


def _build_explicit_memory_trace(question: str, stored_entries: list[dict] | None = None) -> dict:
    return {
        "mode": "memory_command",
        "question": question,
        "layers_used": ["memory"],
        "selected_source": None,
        "candidate_sources": [],
        "drilldown_path": ["memory_command"],
        "debug": {
            "memory_command": True,
            "stored_entry_count": len(stored_entries or []),
            "memory_context_used": False,
        },
    }


def _handle_explicit_memory_command(
    question: str,
    history: list[dict[str, str]],
    *,
    conversation_id: str | None = None,
) -> tuple[str, list[dict], dict] | None:
    candidates = extract_explicit_memory_command_candidates(question=question, history=history)
    if not candidates:
        return None
    stored_entries = persist_memory_candidates(candidates, conversation_id=conversation_id)
    trace = _build_explicit_memory_trace(question, stored_entries)
    display_entries = stored_entries or candidates
    answer = build_explicit_memory_command_reply(question, display_entries)
    return answer, display_entries, trace


@app.get("/")
async def root() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "index.html")


@app.get("/library")
async def library_page() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "library.html")


@app.get("/memory")
async def memory_page() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "memory.html")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"message": "Local RAG assistant is running."}


@app.get("/conversations", response_model=ConversationListResponse)
async def get_conversation_list() -> ConversationListResponse:
    return ConversationListResponse(conversations=[ConversationRecord(**item) for item in list_conversations()])


@app.post("/conversations", response_model=ConversationResponse)
async def create_conversation_route(request: ConversationCreateRequest | None = None) -> ConversationResponse:
    conversation = create_conversation(title=(request.title if request else None))
    return ConversationResponse(conversation=_conversation_record(conversation), messages=[])


@app.get("/conversations/{conversation_id}", response_model=ConversationResponse)
async def get_conversation_route(conversation_id: str) -> ConversationResponse:
    try:
        conversation = get_conversation(conversation_id)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    messages = [_conversation_message_record(item) for item in conversation.get("messages") or [] if isinstance(item, dict)]
    return ConversationResponse(conversation=_conversation_record(conversation), messages=messages)


@app.delete("/conversations/{conversation_id}", response_model=ConversationDeleteResponse)
async def delete_conversation_route(conversation_id: str) -> ConversationDeleteResponse:
    try:
        conversation = delete_conversation(conversation_id)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    try:
        delete_memory_entries_for_conversation(
            conversation_id,
            conversation_messages=conversation.get("messages") or [],
        )
    except Exception:
        pass
    return ConversationDeleteResponse(status="deleted", conversation=_conversation_record(conversation))


@app.get("/documents", response_model=DocumentListResponse)
async def get_documents() -> DocumentListResponse:
    try:
        records = [DocumentRecord(**record) for record in list_documents()]
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    return DocumentListResponse(documents=records)


@app.delete("/documents", response_model=DeleteDocumentResponse)
async def remove_document(source: str = Query(..., min_length=1)) -> DeleteDocumentResponse:
    try:
        record = delete_document(source)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    record_operation("delete_document", "success", source=record["source"])
    return DeleteDocumentResponse(status="deleted", document=DocumentRecord(**record))


@app.post("/documents/upload", response_model=UploadDocumentResponse)
async def upload_document(file: UploadFile = File(...)) -> UploadDocumentResponse:
    try:
        status, record = store_uploaded_document(file.filename, await file.read())
    except UnicodeDecodeError as error:
        raise HTTPException(status_code=400, detail="Uploaded file must be UTF-8 encoded text.") from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except AuthenticationError as error:
        raise HTTPException(
            status_code=502,
            detail="Upstream embedding authentication failed. Check API key and base URL.",
        ) from error
    except RateLimitError as error:
        raise HTTPException(
            status_code=503,
            detail="Upstream embedding quota is unavailable or rate limited.",
        ) from error
    except BadRequestError as error:
        raise HTTPException(
            status_code=502,
            detail="Upstream embedding request was rejected. Check embedding model, endpoint, dimensions, and EMBEDDING_BATCH_SIZE.",
        ) from error
    except APIConnectionError as error:
        raise HTTPException(
            status_code=503,
            detail="Cannot connect to the upstream embedding service.",
        ) from error
    finally:
        await file.close()

    record_operation("upload_document", "success", source=record["source"], upload_status=status)
    return UploadDocumentResponse(status=status, document=DocumentRecord(**record))


@app.post("/ask", response_model=AskResponse)
async def ask(request: AskRequest) -> AskResponse:
    question = request.question.strip()
    history = normalize_history(request.history)
    if not question:
        raise HTTPException(status_code=422, detail="Question must not be empty.")
    conversation = ensure_conversation(request.conversation_id)
    append_conversation_message(conversation["id"], role="user", content=question)

    explicit_memory_result = _handle_explicit_memory_command(question, history, conversation_id=conversation["id"])
    if explicit_memory_result is not None:
        answer, stored_entries, trace = explicit_memory_result
        memory_notices = _build_memory_notices(stored_entries, trace)
        append_conversation_message(
            conversation["id"],
            role="assistant",
            content=answer,
            sources=[],
            trace=trace,
            memory_notices=memory_notices,
        )
        return AskResponse(
            answer=answer,
            sources=[],
            trace=trace,
            conversation_id=conversation["id"],
            memory_notices=_serialize_memory_notices(memory_notices),
        )

    collected_answer: list[str] = []
    collected_sources: list[str] = []
    collected_trace: dict = {}
    collected_memory_notices: list[dict] = []

    try:
        for event_name, payload in stream_answer_question(
            question,
            history=history,
            allow_web_search=bool(request.use_web_search),
            conversation_id=conversation["id"],
        ):
            if event_name == "sources":
                collected_sources = [str(item) for item in payload.get("sources", []) if str(item).strip()]
            elif event_name == "delta":
                text = str(payload.get("text") or "")
                if text:
                    collected_answer.append(text)
            elif event_name == "trace":
                collected_trace = dict(payload or {})
            elif event_name == "memory_notices":
                collected_memory_notices = [item for item in payload.get("items", []) if isinstance(item, dict)]
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except AuthenticationError as error:
        raise HTTPException(
            status_code=502,
            detail="Upstream model authentication failed. Check API key and base URL.",
        ) from error
    except RateLimitError as error:
        raise HTTPException(
            status_code=503,
            detail="Upstream model quota is unavailable or rate limited.",
        ) from error
    except BadRequestError as error:
        raise HTTPException(
            status_code=502,
            detail="Upstream model request was rejected. Check model and endpoint settings.",
        ) from error
    except APIConnectionError as error:
        raise HTTPException(
            status_code=503,
            detail="Cannot connect to the upstream model service.",
        ) from error

    answer = "".join(collected_answer)
    append_conversation_message(
        conversation["id"],
        role="assistant",
        content=answer,
        sources=collected_sources,
        trace=collected_trace,
        memory_notices=collected_memory_notices,
    )

    return AskResponse(
        answer=answer,
        sources=collected_sources,
        trace=collected_trace,
        conversation_id=conversation["id"],
        memory_notices=_serialize_memory_notices(collected_memory_notices),
    )


@app.post("/ask/stream")
async def ask_stream(request: AskRequest) -> StreamingResponse:
    request_started_at = perf_counter()
    question = request.question.strip()
    history = normalize_history(request.history)
    if not question:
        raise HTTPException(status_code=422, detail="Question must not be empty.")
    conversation = ensure_conversation(request.conversation_id)
    append_conversation_message(conversation["id"], role="user", content=question)

    explicit_memory_result = _handle_explicit_memory_command(question, history, conversation_id=conversation["id"])
    if explicit_memory_result is not None:
        answer, stored_entries, trace = explicit_memory_result
        memory_notices = _build_memory_notices(stored_entries, trace)

        def explicit_memory_event_stream():
            yield sse_event("conversation", {"conversation_id": conversation["id"], "title": conversation.get("title") or "New chat"})
            yield sse_event("trace", trace)
            yield sse_event("sources", {"sources": []})
            yield sse_event("delta", {"text": answer})
            if memory_notices:
                yield sse_event("memory_notices", {"items": memory_notices})
            append_conversation_message(
                conversation["id"],
                role="assistant",
                content=answer,
                sources=[],
                trace=trace,
                memory_notices=memory_notices,
            )
            yield sse_event("done", {})

        headers = {
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
        return StreamingResponse(explicit_memory_event_stream(), media_type="text/event-stream", headers=headers)

    def event_stream():
        done_sent = False
        should_record_turn = True
        collected_answer: list[str] = []
        collected_sources: list[str] = []
        collected_trace: dict = {}
        collected_memory_notices: list[dict] = []

        try:
            log_diagnostic_event(
                "ask_stream_request",
                question=question,
                conversation_id=conversation["id"],
                use_web_search=bool(request.use_web_search),
                history_count=len(history),
            )
            yield sse_event("conversation", {"conversation_id": conversation["id"], "title": conversation.get("title") or "New chat"})
            for event_name, payload in stream_answer_question(
                question,
                history=history,
                allow_web_search=bool(request.use_web_search),
                conversation_id=conversation["id"],
            ):
                if event_name == "sources":
                    collected_sources = [str(item) for item in payload.get("sources", []) if str(item).strip()]
                elif event_name == "delta":
                    text = str(payload.get("text") or "")
                    if text:
                        collected_answer.append(text)
                elif event_name == "trace":
                    collected_trace = dict(payload or {})
                elif event_name == "memory_notices":
                    collected_memory_notices = [item for item in payload.get("items", []) if isinstance(item, dict)]
                if event_name == "done":
                    done_sent = True
                yield sse_event(event_name, payload)
        except ValueError as error:
            should_record_turn = False
            yield sse_event("error", {"detail": str(error), "status_code": 400})
        except AuthenticationError:
            should_record_turn = False
            yield sse_event(
                "error",
                {"detail": "Upstream model authentication failed. Check API key and base URL.", "status_code": 502},
            )
        except RateLimitError:
            should_record_turn = False
            yield sse_event(
                "error",
                {"detail": "Upstream model quota is unavailable or rate limited.", "status_code": 503},
            )
        except BadRequestError:
            should_record_turn = False
            yield sse_event(
                "error",
                {"detail": "Upstream model request was rejected. Check model and endpoint settings.", "status_code": 502},
            )
        except APIConnectionError:
            should_record_turn = False
            yield sse_event(
                "error",
                {"detail": "Cannot connect to the upstream model service.", "status_code": 503},
            )
        finally:
            if should_record_turn and collected_answer:
                append_conversation_message(
                    conversation["id"],
                    role="assistant",
                    content="".join(collected_answer),
                    sources=collected_sources,
                    trace=collected_trace,
                    memory_notices=collected_memory_notices,
                )
            log_diagnostic_event(
                "ask_stream_complete",
                started_at=request_started_at,
                question=question,
                conversation_id=conversation["id"],
                use_web_search=bool(request.use_web_search),
                history_count=len(history),
                answer_chars=sum(len(chunk) for chunk in collected_answer),
                source_count=len(collected_sources),
                trace_mode=collected_trace.get("mode"),
                done_sent=done_sent,
                recorded_turn=bool(should_record_turn and collected_answer),
            )
            if not done_sent:
                yield sse_event("done", {})

    headers = {
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
    }
    return StreamingResponse(event_stream(), media_type="text/event-stream", headers=headers)


@app.get("/memories", response_model=MemoryListResponse)
async def get_memories() -> MemoryListResponse:
    store = read_memory_store()
    memories = [MemoryEntryRecord(**entry) for entry in list_memory_entries(include_pending=True, include_rolled_back=True)]
    return MemoryListResponse(memories=memories, audit=list(store.get("audit") or []))


@app.post("/memories/extract", response_model=MemoryExtractResponse)
async def extract_memories(request: MemoryExtractRequest) -> MemoryExtractResponse:
    history = normalize_history(request.history)
    candidates = extract_memory_candidates(
        question=request.question.strip(),
        answer=request.answer,
        sources=request.sources,
        history=history,
    )
    if request.persist:
        candidates = persist_memory_candidates(candidates)
        record_operation("memory_extract", "success", created=len(candidates))
    return MemoryExtractResponse(memories=[MemoryEntryRecord(**entry) for entry in candidates])


@app.post("/memories/{memory_id}/approve", response_model=MemoryActionResponse)
async def approve_memory(memory_id: str) -> MemoryActionResponse:
    try:
        memory = approve_memory_entry(memory_id)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    record_operation("memory_approve", "success", memory_id=memory_id)
    return MemoryActionResponse(status="approved", memory=MemoryEntryRecord(**memory))


@app.post("/memories/{memory_id}/rollback", response_model=MemoryActionResponse)
async def rollback_memory(memory_id: str, detail: str = Query("manual rollback")) -> MemoryActionResponse:
    try:
        memory = rollback_memory_entry(memory_id, detail=detail)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    record_operation("memory_rollback", "success", memory_id=memory_id, detail=detail)
    return MemoryActionResponse(status="rolled_back", memory=MemoryEntryRecord(**memory))


@app.patch("/memories/{memory_id}", response_model=MemoryUpdateResponse)
async def update_memory(memory_id: str, request: MemoryUpdateRequest) -> MemoryUpdateResponse:
    try:
        memory = update_memory_entry(memory_id, title=request.title, summary=request.summary, tags=request.tags)
    except ValueError as error:
        detail = str(error)
        status_code = 404 if "not found" in detail.casefold() else 400
        raise HTTPException(status_code=status_code, detail=detail) from error
    record_operation("memory_edit", "success", memory_id=memory_id)
    return MemoryUpdateResponse(status="updated", memory=MemoryEntryRecord(**memory))


@app.delete("/memories/{memory_id}", response_model=MemoryActionResponse)
async def delete_memory(memory_id: str) -> MemoryActionResponse:
    try:
        memory = remove_memory_entry(memory_id)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    record_operation("memory_delete", "success", memory_id=memory_id)
    return MemoryActionResponse(status="rolled_back", memory=MemoryEntryRecord(**memory))


@app.get("/ops/state", response_model=OpsStateResponse)
async def get_ops_state() -> OpsStateResponse:
    documents = [DocumentRecord(**record) for record in list_documents()]
    memories = list_memory_entries(include_pending=True, include_rolled_back=True)
    state = dict(read_loop_state())
    state["openviking"] = describe_openviking_runtime()
    return OpsStateResponse(
        state=state,
        memory_count=len(memories),
        document_count=len(documents),
        memory_summary=summarize_memory_store(),
        chat_model=get_chat_model(),
        web_search_model=get_web_search_model(),
    )


@app.post("/ops/rebuild-index", response_model=OperationResponse)
async def rebuild_index() -> OperationResponse:
    try:
        result = rebuild_vector_index()
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except AuthenticationError as error:
        raise HTTPException(status_code=502, detail="Upstream embedding authentication failed.") from error
    except RateLimitError as error:
        raise HTTPException(status_code=503, detail="Upstream embedding quota is unavailable.") from error
    except BadRequestError as error:
        raise HTTPException(status_code=502, detail="Upstream embedding request was rejected.") from error
    except APIConnectionError as error:
        raise HTTPException(status_code=503, detail="Cannot connect to the upstream embedding service.") from error

    operation = record_operation(
        "rebuild_index",
        "success",
        document_count=result["document_count"],
        chunk_count=result["chunk_count"],
        collection_count=result["collection_count"],
    )
    documents = [DocumentRecord(**record) for record in result["documents"]]
    return OperationResponse(status="success", operation=operation, documents=documents)


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "8001"))
    uvicorn.run(app, host="127.0.0.1", port=port, reload=False)
