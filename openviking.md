# OpenViking Runtime Notes

## Current Role In askRAg

As of April 3, 2026, `askRAg` uses OpenViking only for assistant memory and answer-time context.

- `Chroma` owns uploaded documents, chunking, indexing, and static file-evidence retrieval
- `OpenViking` owns assistant memory, cross-turn context, and durable remembered state
- local conversation history remains replay/history UX, not the primary reasoning context store

This file intentionally reflects the current runtime contract only. Older document-backend experiments and migration planning notes have been removed from the active repo state.

## Verified Local Paths

- OpenViking CLI: `D:\py\askRAg\.venv\Scripts\ov.exe`
- OpenViking server binary: `D:\py\askRAg\.venv\Scripts\openviking-server.exe`
- Server config: `C:\Users\Lenovo\.openviking\ov.conf`
- CLI config: `C:\Users\Lenovo\.openviking\ovcli.conf`
- Workspace: `D:\py\askRAg\data\openviking_workspace`
- Default local endpoint: `http://127.0.0.1:1933`

Notes:

- `ov` is not assumed to be on the system `PATH`
- the repo runtime first checks `ASKRAG_OPENVIKING_CLI`, then falls back to the repo-local virtualenv path

## Start OpenViking

```powershell
.\.venv\Scripts\openviking-server.exe --config C:\Users\Lenovo\.openviking\ov.conf
```

## Health Check

```powershell
.\.venv\Scripts\ov.exe health
```

Expected healthy output today includes:

- `status: ok`
- `healthy: true`
- `version: 0.3.2`

## askRAg Runtime Expectations

When OpenViking is healthy:

- assistant-memory writeback and reuse should work
- answer-time context should prefer OpenViking-backed memory lookups
- `GET /ops/state` should report OpenViking as `memory_context_infrastructure`

When OpenViking is unavailable:

- Chroma document upload, delete, and index rebuild should still work
- Chroma document-evidence retrieval should still work
- memory reuse and full answer-time context enrichment will degrade

## Check From askRAg

```powershell
Invoke-RestMethod http://127.0.0.1:8001/ops/state | ConvertTo-Json -Depth 6
```

Expected `state.openviking` shape:

- `role: memory_context_infrastructure`
- `required_for: ["assistant_memory", "answer_time_context"]`
- `not_required_for: ["document_upload", "document_index_rebuild", "chroma_document_retrieval"]`

## Local Security Notes

- `ov.conf` and `ovcli.conf` are machine-local files and may contain credentials
- do not commit local credentials or machine-specific config contents into the repo
- document config locations and prerequisites, not secret values
