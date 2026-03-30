import json
import os
import sys
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from openai import APIConnectionError, AuthenticationError, BadRequestError, RateLimitError

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.documents import delete_document, list_documents, store_uploaded_document
from app.rag import answer_question, stream_answer_question
from app.schemas import (
    AskRequest,
    AskResponse,
    DeleteDocumentResponse,
    DocumentListResponse,
    DocumentRecord,
    UploadDocumentResponse,
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


@app.get("/")
async def root() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "index.html")


@app.get("/library")
async def library_page() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "library.html")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"message": "Local RAG assistant is running."}


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

    return UploadDocumentResponse(status=status, document=DocumentRecord(**record))


@app.post("/ask", response_model=AskResponse)
async def ask(request: AskRequest) -> AskResponse:
    question = request.question.strip()
    history = normalize_history(request.history)
    if not question:
        raise HTTPException(status_code=422, detail="Question must not be empty.")

    try:
        answer, sources = answer_question(question, history=history)
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

    return AskResponse(answer=answer, sources=sources)


@app.post("/ask/stream")
async def ask_stream(request: AskRequest) -> StreamingResponse:
    question = request.question.strip()
    history = normalize_history(request.history)
    if not question:
        raise HTTPException(status_code=422, detail="Question must not be empty.")

    def event_stream():
        done_sent = False

        try:
            for event_name, payload in stream_answer_question(question, history=history):
                if event_name == "done":
                    done_sent = True
                yield sse_event(event_name, payload)
        except ValueError as error:
            yield sse_event("error", {"detail": str(error), "status_code": 400})
        except AuthenticationError:
            yield sse_event(
                "error",
                {"detail": "Upstream model authentication failed. Check API key and base URL.", "status_code": 502},
            )
        except RateLimitError:
            yield sse_event(
                "error",
                {"detail": "Upstream model quota is unavailable or rate limited.", "status_code": 503},
            )
        except BadRequestError:
            yield sse_event(
                "error",
                {"detail": "Upstream model request was rejected. Check model and endpoint settings.", "status_code": 502},
            )
        except APIConnectionError:
            yield sse_event(
                "error",
                {"detail": "Cannot connect to the upstream model service.", "status_code": 503},
            )
        finally:
            if not done_sent:
                yield sse_event("done", {})

    headers = {
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
    }
    return StreamingResponse(event_stream(), media_type="text/event-stream", headers=headers)


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "8001"))
    uvicorn.run(app, host="127.0.0.1", port=port, reload=False)
