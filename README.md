# Local Knowledge Base QA Assistant

## Project Goal

Build a minimal local RAG demo with:

- Python
- LangChain
- Chroma
- FastAPI
- LLM API

## Current Features

- Homepage focused on streaming chat
- Separate knowledge-base management page
- Upload `.txt` / `.md` files from the UI
- md5-based duplicate detection before indexing
- Local Chroma vector storage with source tracking
- Delete files from the library UI and remove their vector entries
- Basic multi-turn chat via question rewriting and recent-history context
- Chat-triggered document summaries using an explicit file name, a recently cited file, or a summary-style follow-up request from recent chat history

## Project Structure

- `app/main.py`: FastAPI entry, page routing, API endpoints
- `app/rag.py`: document loading, splitting, retrieval, question rewriting, and QA logic
- `app/documents.py`: upload flow, md5 duplicate detection, registry management
- `app/schemas.py`: request and response models
- `app/frontend/`: chat page, library page, styles, scripts
- `data/docs/`: local knowledge base files
- `data/chroma/`: local vector store
- `data/document_registry.json`: indexed file registry generated at runtime

## Run

Create the vector index first if you are starting from the seed docs only:

```powershell
.\.venv\Scripts\python.exe -m app.rag index
```

Install dependencies:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Start the API server:

```powershell
.\.venv\Scripts\python.exe app\main.py
```

Open the pages:

```text
Chat:    http://127.0.0.1:8001/
Library: http://127.0.0.1:8001/library
```

## API

`GET /health`

`GET /documents`

Returns the current indexed document registry.

`DELETE /documents?source=...`

Remove a file from the local docs directory, registry, and Chroma collection by its source path.

`POST /documents/upload`

Upload a UTF-8 `.txt` or `.md` file. The backend will:

- calculate md5
- reject duplicates
- save new files into `data/docs/`
- split the file into chunks
- append the chunks into Chroma

`POST /ask`

Returns the full answer as JSON.

Request body supports:

- `question`: current user question
- `history`: recent `user` / `assistant` messages for multi-turn context

If the question asks for a document summary or a summary-style follow-up, the backend switches from normal RAG QA to a document-summary flow. It can resolve the target from an explicit file name in the current question, a recently cited file in chat history, or the latest document-summary context.

`POST /ask/stream`

Returns a `text/event-stream` response. The stream sends:

- `sources`: source file list
- `delta`: incremental answer text
- `done`: stream finished
- `error`: upstream or local failure detail

The streaming endpoint also accepts `history`, and the backend rewrites follow-up questions into standalone retrieval queries before searching the knowledge base.
