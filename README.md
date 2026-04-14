# Local Knowledge Base QA Assistant

## Project Goal

Build `askRAg` as a sustainable-memory knowledge workbench with a clear boundary:

- `Chroma` serves static uploaded document evidence
- `OpenViking` serves assistant memory and answer-time context

## Current Features

- Streaming chat with persistent conversation threads and a separate library page
- Upload and delete `.txt` / `.md` files from the UI
- md5-based duplicate detection before indexing
- Local Chroma vector storage with source tracking
- Multi-turn chat with question rewriting and recent-history context
- Reopen saved conversations after refresh or restart from a conversation list in the chat UI
- Summary flow that resolves the target file from the current question, recent sources, or summary follow-up history
- Layered `L0/L1/L2` trace output for summary and retrieval flows
- Layered memory types: `raw_turn_log`, `working_summary`, `recent_task_state`, `pinned_preference`, `stable_profile_fact`, `approved_long_term_fact`
- Automatic turn writeback plus explicit approval/rollback for durable memory
- User-facing memory center for reviewing, editing, approving, and removing stored memory entries
- In-chat memory notices when the assistant remembers or reuses relevant context
- Library-side ops controls for Chroma index rebuild plus loop-state inspection
- Machine-readable loop state plus a deterministic regression dataset/script
- Real OpenViking runtime for memory/context work

## Project Structure

- `app/main.py`: FastAPI app, API routes, memory endpoints, ops endpoints
- `app/conversations.py`: persisted conversation thread store and helpers
- `app/pipeline.py`: direct answer flow, summary flow, detailed answer wrapper
- `app/workflow.py`: bounded retrieval workflow with optional web supplement
- `app/context_layers.py`: `L0/L1/L2` context planning and trace building
- `app/session_memory.py`: layered memory provider, migration, approval/rollback, turn writeback, context reuse
- `app/runtime_state.py`: persisted loop state, guardrails, verification/evaluation metadata
- `app/documents.py`: upload flow, delete flow, registry refresh, and index rebuild helpers
- `app/openviking_runtime.py`: OpenViking health/runtime helpers for memory and context infrastructure
- `app/retrievers/`: chunk retrieval, parent selection, backend seam, reranking
- `app/frontend/`: chat/library HTML, CSS, and client logic
- `data/conversation_threads.json`: persisted conversation thread store
- `data/document_registry.json`: indexed file registry
- `data/loop_state.json`: canonical verification/evaluation state
- `data/eval/regression_cases.json`: deterministic regression cases
- `scripts/run_regression_eval.py`: local regression runner
- `.project-loop/PLAN.md`: canonical short plan
- `PROJECT_STATUS.md`: current status snapshot

## Structure Notes

- The canonical project-memory files are `AGENTS.md`, `.project-loop/PLAN.md`, `PROJECT_STATUS.md`, and `data/loop_state.json`.
- Static document retrieval is locked to Chroma on the main runtime path.
- OpenViking is part of the project for memory/context work only, not as a document backend.

## Backend Boundary

- `Chroma` is the only intended backend for uploaded documents, chunking, vector indexing, and file-evidence retrieval.
- `OpenViking` is the intended backend for assistant memory, answer-time context assembly, and durable remembered state.
- Conversation history in `data/conversation_threads.json` is user-facing replay state, not the primary reasoning context store.

## Run The Core App

Install dependencies:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Set provider environment variables before running the app. The current code path supports OpenAI-compatible chat and embedding providers for the core local-document flow.

For GLM, the minimal working setup is:

```powershell
$env:OPENAI_BASE_URL="https://open.bigmodel.cn/api/paas/v4"
$env:OPENAI_API_KEY="your-glm-key"
$env:CHAT_MODEL="glm-4.5-air"
$env:EMBEDDING_MODEL="embedding-3"
```

Notes:

- If `OPENAI_BASE_URL` points to `bigmodel.cn`, the app now treats GLM as the active provider family.
- Under GLM, web search now uses the official `POST /api/paas/v4/web_search` API instead of the older DashScope-specific `responses + tools` path.
- If you switch embedding providers or embedding dimensions, rebuild the local Chroma index before testing document retrieval again.

Build or rebuild the local vector index:

```powershell
.\.venv\Scripts\python.exe -m app.rag index
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

At this point, the Chroma-backed document workflow is available even if OpenViking is unavailable.
When using GLM, both the core local-document path and the built-in web-search path are supported, but local document retrieval may require an index rebuild after changing embedding models.

Canonical verification command:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests
```

Deterministic regression run:

```powershell
.\.venv\Scripts\python.exe scripts\run_regression_eval.py
```

## OpenViking Readiness

OpenViking is required for the full assistant-memory and answer-time-context experience, but it is not required for the basic Chroma document workflow.

### What still works without OpenViking

- document upload and delete
- Chroma index rebuild
- Chroma-backed document retrieval
- the basic chat/library shell

### What depends on a healthy OpenViking runtime

- assistant-memory synchronization and reuse
- OpenViking-first answer-time context assembly
- the full recent-context versus long-term-memory experience
- OpenViking runtime readiness shown through `GET /ops/state`

### Local paths used in this repo

- OpenViking CLI: `D:\py\askRAg\.venv\Scripts\ov.exe`
- OpenViking server binary: `D:\py\askRAg\.venv\Scripts\openviking-server.exe`
- Server config: `C:\Users\Lenovo\.openviking\ov.conf`
- CLI config: `C:\Users\Lenovo\.openviking\ovcli.conf`
- Workspace: `D:\py\askRAg\data\openviking_workspace`

`ov` is not currently assumed to be on the system `PATH`, so the repo-local binary path is the safest documented entrypoint.

### Start OpenViking

```powershell
.\.venv\Scripts\openviking-server.exe --config C:\Users\Lenovo\.openviking\ov.conf
```

### Health-check OpenViking

```powershell
.\.venv\Scripts\ov.exe health
```

Expected healthy output today, on April 3, 2026, includes:

- `status: ok`
- `healthy: true`
- `version: 0.3.2`

### Check readiness from askRAg

After both OpenViking and FastAPI are running:

```powershell
Invoke-RestMethod http://127.0.0.1:8001/ops/state | ConvertTo-Json -Depth 6
```

The `state.openviking` object should report:

- `role: memory_context_infrastructure`
- `required_for: ["assistant_memory", "answer_time_context"]`
- `not_required_for: ["document_upload", "document_index_rebuild", "chroma_document_retrieval"]`

### Local-security note

- The local OpenViking config is expected to contain provider credentials and should stay local to the machine.
- Do not commit machine-specific config values or API keys into the repository.
- Prefer overriding CLI location with `ASKRAG_OPENVIKING_CLI` if your environment uses a different install path.

## API

`GET /health`

`GET /conversations`

Returns saved conversation thread summaries.

`POST /conversations`

Creates a new empty conversation thread.

`GET /conversations/{conversation_id}`

Returns a saved conversation and its stored messages.

`DELETE /conversations/{conversation_id}`

Deletes a saved conversation thread.

`GET /documents`

Returns the current indexed document registry for the Chroma-backed document library.

`POST /documents/upload`

Uploads a UTF-8 `.txt` or `.md` file, indexes it into Chroma, and appends the registry record.

`DELETE /documents?source=...`

Deletes the file, removes matching Chroma entries, and updates the registry.

`POST /ask`

Returns:

- `answer`
- `sources`
- `trace`
- `conversation_id`
- `memory_notices`

The `trace` payload exposes the current route, layer usage, candidate sources, selected source, and drill-down path.

`POST /ask/stream`

Returns a `text/event-stream` response. The stream can emit:

- `conversation`
- `progress`
- `sources`
- `trace`
- `memory_notices`
- `delta`
- `done`
- `error`

`GET /memories`

Lists layered memory entries plus recent audit events.

`POST /memories/extract`

Explicitly extracts low-risk memory candidates from a completed turn.

`POST /memories/{memory_id}/approve`

Marks a pending memory as approved.

`POST /memories/{memory_id}/rollback`

Rolls back a memory entry without deleting its audit trail.

`PATCH /memories/{memory_id}`

Edits a memory entry title/summary.

`DELETE /memories/{memory_id}`

Marks a memory entry as user-removed via rollback semantics.

`GET /ops/state`

Returns the persisted loop state, memory count, document count, and layered memory summary.

`POST /ops/rebuild-index`

Rebuilds the local Chroma index from the current docs directory.

## Highlights

- The app is no longer a plain `retrieve -> answer` demo; it now exposes a layered `L0/L1/L2` reasoning path for locate, overview, and deep-read behavior.
- Multi-turn work can accumulate controlled long-term memory through explicit extraction, approval, and rollback instead of implicit auto-write behavior.
- The repo has a loop-safe operating surface: canonical verification command, persisted loop state, deterministic regression dataset, and frontend-visible ops status.
- The repo enforces a clear split: Chroma for static knowledge evidence, OpenViking for structured memory/context, and explicit approval/rollback for durable memory writes.

## Current Limitations

- OpenViking memory synchronization is still best-effort and not yet productized as a full readiness flow.
- The documented local OpenViking setup is based on a machine-local config under `C:\Users\Lenovo\.openviking\`, so other contributors may need their own config path and credentials before the full memory path is available.
- The chat frontend is much closer to an assistant surface, but conversation management and memory UX still need broader product polish.
- The evaluation set is intentionally small and deterministic; it is useful as a regression gate, not as a full benchmark.

## Resume Framing

If you need a short project description for a resume or portfolio, a good current framing is:

> Built a sustainable-memory knowledge workbench on FastAPI, LangChain, Chroma, and OpenViking, with layered retrieval traces, explicit long-term memory controls, streaming QA, and loop-safe regression/ops tooling.
