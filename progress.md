# Progress

## Current Snapshot
- Current focus: split local retrieval relevance from local answer sufficiency so incomplete local hits can still fall back to web.
- The local sufficiency layer now carries separate relevance / answer-sufficiency signals.
- Ordinary requests still enter graph with router hints plus a lightweight local-doc probe before final planning.
- Summary/doc/web strategy decisions remain graph-owned.

## 2026-04-12 Local Sufficiency Split
- Split the local retrieval layer into:
  - `local_retrieval_relevant`
  - `local_answer_sufficient`
- Kept `validate_chunk_results()` as the retrieval-relevance gate and moved answer coverage into the assess step.
- Added a lightweight answer-coverage heuristic so doc-hit questions can continue to web when local evidence is relevant but incomplete.

### decision_audit
- Files changed:
  - `app/validators.py`
  - `app/workflow.py`
  - `app/agent_tools.py`
  - `app/agent_graph.py`
  - `tests/test_agent_tools.py`
  - `.project-loop/PLAN.md`
  - `PROJECT_STATUS.md`
  - `progress.md`
- Planning mapping:
  - split local retrieval relevance from local answer sufficiency
  - keep assess as the place where local evidence decides whether to stop or continue to web
  - preserve graph shape, query rewrite, and retrieval internals
- Tradeoffs:
  - added a small heuristic for answer coverage instead of changing the retrieval pipeline
  - kept backward compatibility for existing `RetrievalValidation` callers by exposing `is_relevant`
- Potential drift:
  - the answer-sufficiency heuristic is intentionally conservative; if it misses a niche doc pattern, we may need a later refinement pass
- Next step:
  - run the focused doc / web regression cases and confirm the new local-fallback behavior is stable

## 2026-04-12 Sidebar Width Adjustment
- Increased the chat workspace left column width and added a minimum width to the sidebar.
- Kept the change purely in CSS so the delete button remains in the same place and the interaction logic stays untouched.

### decision_audit
- Files changed:
  - `app/frontend/styles.css`
  - `.project-loop/PLAN.md`
  - `PROJECT_STATUS.md`
  - `progress.md`
- Planning mapping:
  - widen the chat sidebar so the conversation delete buttons are visibly accessible
  - keep the change limited to frontend layout styling
- Tradeoffs:
  - used a layout-only widening rather than changing the row content or button placement
  - avoided JS or backend changes so the behavior stays stable
- Potential drift:
  - none noted; this is a contained visual/layout adjustment
- Next step:
  - smoke-check the chat sidebar at common desktop widths to confirm the delete button is visible

## 2026-04-12 Pre-Plan Parallel Fan-Out
- Changed the graph so the three pre-plan nodes run as parallel branches after `init_request`.
- Kept the node implementations unchanged and only adjusted the graph wiring / state schema.
- Added the missing graph state fields needed by the parallel summary / retrieval paths to avoid KeyErrors.

### decision_audit
- Files changed:
  - `app/agent_graph.py`
  - `.project-loop/PLAN.md`
  - `PROJECT_STATUS.md`
  - `progress.md`
- Planning mapping:
  - parallelize the pre-plan graph nodes without changing node internals
  - keep `plan_request` as the join point after all three updates land in state
- Tradeoffs:
  - added a few missing typed state fields so the existing summary / retrieval branches keep their data across the parallel fan-out
  - preserved the rest of the graph shape instead of introducing a new join node
- Potential drift:
  - none noted after the state-schema repair; the parallel fan-out now preserves downstream state expectations
- Next step:
  - keep validating the graph after this structural change, especially summary and retrieval branches under the new pre-plan fan-out

## 2026-04-12 Conversation Delete UI
- Added a delete action to each chat conversation row in the sidebar.
- Reused the existing `/conversations/{id}` DELETE endpoint instead of changing storage behavior.
- When the active conversation is deleted, the UI now switches to the next available thread or clears the chat state if none remain.
- Kept the change limited to the chat frontend and the existing conversation API.

### decision_audit
- Files changed:
  - `app/frontend/app.js`
  - `app/frontend/styles.css`
  - `.project-loop/PLAN.md`
  - `PROJECT_STATUS.md`
  - `progress.md`
- Planning mapping:
  - add a small history-conversation delete action in the chat sidebar
  - keep backend storage and chat logic unchanged
- Tradeoffs:
  - reused the current conversation list UI with a small split button layout instead of redesigning the rail
  - kept deletion confirmation and state refresh local to the frontend
- Potential drift:
  - none noted; this is a frontend-only UX addition using an existing backend endpoint
- Next step:
  - smoke-test the delete action in the browser and make sure the empty-state / active-thread transitions feel correct

## 2026-04-12 Web Query Rewrite
- Added a lightweight web-query rewrite/normalize helper that cleans raw search questions before they hit the provider.
- Direct web-search paths now rewrite the query using recent conversation history only when the question is context-dependent or ambiguous.
- Added diagnostics for:
  - `raw_query`
  - `normalized_query`
  - `rewrite_used`
  - `rewritten_query`
  - `resolved_references`
  - `selected_query`
- Kept web relevance, assess, routing, and retrieval internals unchanged.

### decision_audit
- Files changed:
  - `app/rag.py`
  - `app/pipeline.py`
  - `app/agent_tools.py`
  - `app/agent_graph.py`
  - `tests/test_pipeline.py`
  - `tests/test_agent_tools.py`
  - `.project-loop/PLAN.md`
  - `PROJECT_STATUS.md`
  - `progress.md`
- Planning mapping:
  - query rewrite before web_search provider calls
  - lightweight normalization first, LLM rewrite only when needed
  - preserve existing graph/retrieval/web relevance behavior
- Tradeoffs:
  - reused existing history and logging paths instead of adding a new web query subsystem
  - direct graph web paths now reconstruct recent history when available so pronoun resolution can work without graph changes
- Potential drift:
  - none noted; the patch is restricted to query generation and logging
- Next step:
  - run the focused web rewrite tests and one or two live prompt checks to confirm the cleaned query is what reaches the provider

## 2026-04-11 Diagnostic Timing Instrumentation
- Added `DIAG` timing logs for:
  - `pre_router`
  - `init_request`
  - `local_doc_probe`
  - `plan_request`
  - `web_search`
  - `web_extract`
  - `assess`
  - `finalize`
- Logged diagnostic fields for raw query, rewritten query, router hints, planner path, result counts, source previews, extract triggers, and rejection reasons.
- Kept business logic unchanged.

### decision_audit
- Files changed:
  - `app/agent_tools.py`
  - `app/pipeline.py`
  - `app/agent_graph.py`
  - `.project-loop/PLAN.md`
  - `PROJECT_STATUS.md`
  - `progress.md`
- Planning mapping:
  - diagnostic-only instrumentation for the current graph/web bottleneck investigation
  - no strategy or threshold changes
- Tradeoffs:
  - used lightweight logging helpers plus existing state/results instead of introducing a new diagnostics subsystem
  - kept logs in the graph/tool layers so timing reflects real execution instead of post-hoc reconstruction
- Potential drift:
  - diagnostic helper logs are intentionally verbose, but they do not change runtime behavior
- Next step:
  - reproduce the three sample prompts, then inspect `DIAG` logs for the slowest step and the first refusal reason

## 2026-04-11 Local Doc Probe Planning Slice
- Added `RouterHints` extraction so pre-router behavior can stay as lightweight hint gathering.
- Added `local_doc_probe` to graph startup and wired planning to use:
  - query
  - router hints
  - lightweight Chroma probe results
- Ordinary doc-like requests can now be promoted into the retrieval path even without an explicit filename/doc-rule match.
- Kept graph main structure intact; only the pre-plan portion changed.

## 2026-04-11 Local Doc Probe Planning Slice
- Added `RouterHints` extraction so pre-router behavior can stay as lightweight hint gathering.
- Added `local_doc_probe` to graph startup and wired planning to use:
  - query
  - router hints
  - lightweight Chroma probe results
- Ordinary doc-like requests can now be promoted into the retrieval path even without an explicit filename/doc-rule match.
- Kept graph main structure intact; only the pre-plan portion changed.

### decision_audit
- Files changed:
  - `app/tool_router.py`
  - `app/agent_tools.py`
  - `app/agent_graph.py`
  - `tests/test_tool_router.py`
  - `tests/test_agent_graph.py`
  - `tests/test_pipeline.py`
  - `.project-loop/PLAN.md`
  - `PROJECT_STATUS.md`
  - `progress.md`
- Planning mapping:
  - graph becomes the ordinary business-request orchestrator
  - router downgraded to hint extraction for normal requests
  - add `local_doc_probe` before `plan_request`
- Tradeoffs:
  - kept `decide_tool_plan()` for compatibility, but graph no longer depends on it for ordinary planning
  - reused `search_kb_chroma()` with very small `k` instead of introducing a separate probe backend
  - kept graph preloading of long-term context and response constraints after the probe to avoid widening the change
- Potential drift:
  - non-graph compatibility helpers still exist in `tool_router.py`, but ordinary request entry now depends on graph hint+probe planning
- Next step:
  - continue slimming router-owned doc/web rules so more remaining intent decisions become graph-owned rather than router-owned

## 2026-04-11 Router Hard-Rule Thinning Slice
- Reduced `tool_router.rule_tool_plan()` to strong constraints only:
  - explicit `web-only`
  - explicit `local-only`
- Downgraded ordinary `summary/doc/web/direct` routing behavior to hint-level signals via `extract_router_hints()`.
- Added explicit force flags into router hints:
  - `force_web_only`
  - `force_local_only`
- Updated graph planning to consume these force flags while keeping graph main structure intact.

### decision_audit
- Files changed:
  - `app/tool_router.py`
  - `app/agent_graph.py`
  - `tests/test_tool_router.py`
  - `.project-loop/PLAN.md`
  - `PROJECT_STATUS.md`
  - `progress.md`
- Planning mapping:
  - keep router as hint extraction layer for ordinary traffic
  - keep graph as final decision point for normal business requests
  - preserve only strong-signal router rules
- Tradeoffs:
  - kept `decide_tool_plan()` compatibility path for legacy callers, but removed ordinary hard-rule short-circuits from `rule_tool_plan()`
  - did not touch `main.py` memory short-circuit and security/illegal entry handling in this slice
- Potential drift:
  - none found for current target; ordinary branching now depends on graph planning with hints/probe
- Next step:
  - continue auditing remaining router fallback behavior to further reduce legacy coupling

## 2026-04-11 Router-To-Graph Direction Reset
- Reframed the active target so router keeps only minimal intent labeling.
- Confirmed the new product rule: except for explicit memory short-circuit and simple direct answers, requests should enter graph-owned context/memory-aware strategy planning.
- Locked the summary direction change: `doc_summary` should become an intent label, while graph decides pure local summary vs summarize-then-verify vs summarize+web supplement.

### decision_audit
- Files changed:
  - `.project-loop/PLAN.md`
  - `PROJECT_STATUS.md`
  - `PROJECT_PLAN.md`
  - `progress.md`
- Planning mapping:
  - target-direction reset from router-heavy branching to graph-owned summary/doc/web strategy
  - preserve explicit memory short-circuit and lightweight direct-answer path
- Tradeoffs:
  - did not start implementation in this turn
  - deliberately changed planning direction before more router work to avoid reinforcing the old ownership split
- Potential drift:
  - none noted; this turn only updates planning/state files
- Next step:
  - implement the first slice of the new direction by reducing router-owned summary branching and moving summary strategy selection into graph

## 2026-04-11 Summary Strategy Graph Slice
- Kept router behavior at the intent-label level for `doc_summary`.
- Added graph-owned summary strategy handling so summary requests can now choose between pure local summary and summary plus web supplement.
- Added tool-layer support for:
  - deciding summary strategy
  - running summary-related web supplementation
  - composing the final answer from local summary and web findings
- Tightened graph planning so current summary requests are not accidentally misclassified as prior-summary verification just because a recent summary exists elsewhere.

### decision_audit
- Files changed:
  - `app/agent_tools.py`
  - `app/agent_graph.py`
  - `tests/test_agent_graph.py`
  - `tests/test_pipeline.py`
  - `.project-loop/PLAN.md`
  - `PROJECT_STATUS.md`
  - `progress.md`
- Planning mapping:
  - move summary strategy selection into graph
  - keep `doc_summary` as an intent label instead of a final router-owned execution decision
  - route non-trivial summary requests through graph-owned context and memory-aware execution
- Tradeoffs:
  - reused the existing local summary and web search tools instead of introducing a separate summary subgraph module
  - implemented a minimal summary-web supplement query builder so the new flow can work without redesigning the whole web stack
- Potential drift:
  - summary plus web supplement currently uses a lightweight generated web query from the selected summary source, which is good enough for this slice but may need refinement later
- Next step:
  - continue shrinking router-owned doc/web branching so more non-trivial requests become graph-owned strategy decisions

## 2026-04-11 Router Registry Plumbing Cleanup
- Removed leftover `registry` plumbing from `tool_router.py`.
- Dropped obsolete `ToolPlan.target_scope` and `ToolPlan.tool_available` fields from the router plan shape.
- Kept the remaining top-level routing behavior intact while thinning the router toward a minimal intent splitter.

### decision_audit
- Files changed:
  - `app/tool_router.py`
  - `tests/test_tool_router.py`
  - `.project-loop/PLAN.md`
  - `PROJECT_STATUS.md`
  - `progress.md`
- Planning mapping:
  - router shrink / minimal intent routing
  - prune obsolete router-only fields from `ToolPlan`
- Tradeoffs:
  - preserved the current graph-owned execution semantics
  - avoided touching any graph or stream ownership in this slice
- Potential drift:
  - none noted; the removed fields were no longer used anywhere in the codebase
- Next step:
  - continue auditing the remaining router fields and prune any more that should be graph-owned only

## 2026-04-11 Router Summary Verify Shrink
- Moved the summary-web-verify special case out of `tool_router.py` and into graph-owned planning.
- Kept the rest of the summary / web / doc routing behavior unchanged.
- Added coverage to assert the router no longer short-circuits summary verification directly.

### decision_audit
- Files changed:
  - `app/tool_router.py`
  - `app/agent_graph.py`
  - `tests/test_tool_router.py`
  - `tests/test_agent_graph.py`
  - `tests/test_pipeline.py`
  - `.project-loop/PLAN.md`
  - `PROJECT_STATUS.md`
  - `progress.md`
- Planning mapping:
  - router shrink / minimal intent routing
  - move summary-web-verify special case into graph planning
- Tradeoffs:
  - kept the overall summary/web execution semantics intact
  - added a small graph precheck instead of rewriting the broader routing model
- Potential drift:
  - none noted; the router is thinner and the graph now owns the special-case summary verification branch
- Next step:
  - audit whether any other router special-cases should move into graph planning

## 2026-04-11 Direct Web Quality Gate Adjustment
- Relaxed the direct explicit web-search freshness gate so relevant answers no longer hard-fail solely due to missing official-like sources.
- Restored clean Chinese official/freshness query terms for direct web-search suffix generation.
- Kept the irrelevant-result refusal behavior unchanged.

### decision_audit
- Files changed:
  - `app/pipeline.py`
  - `tests/test_pipeline.py`
  - `.project-loop/PLAN.md`
  - `PROJECT_STATUS.md`
  - `progress.md`
- Planning mapping:
  - direct web-search quality correction
  - explicit freshness query behavior adjustment
- Tradeoffs:
  - retained the existing relevance gate
  - only softened the official-source requirement for direct explicit web-search
  - introduced clean active Chinese constants instead of relying on the older corrupted literals
- Potential drift:
  - none noted; retrieval fallback logic was intentionally left unchanged
- Next step:
  - verify the live Chinese explicit latest-model query and then return to the remaining legacy ownership cleanup

## 2026-04-11 Turn Persistence And Finalize Cleanup
- Moved shared turn persistence out of `main.py` and into the shared answer core used by `/ask` and `/ask/stream`.
- Non-stream retrieval finalize is now tool-backed through `app.agent_tools.finalize_retrieval_result()`.
- `main.py` now consumes `memory_notices` from the shared stream events instead of calling `record_completed_turn()` itself.

### decision_audit
- Files changed:
  - `app/agent_tools.py`
  - `app/agent_graph.py`
  - `app/workflow.py`
  - `app/main.py`
  - `tests/test_agent_tools.py`
  - `tests/test_agent_graph.py`
  - `tests/test_main_api.py`
  - `tests/test_pipeline.py`
  - `.project-loop/PLAN.md`
  - `PROJECT_STATUS.md`
  - `progress.md`
- Planning mapping:
  - move shared turn persistence out of API entry handling
  - move non-stream retrieval final summarize/compose behind the tool layer
- Tradeoffs:
  - kept explicit `remember...` short-circuit at API entry
  - did not flatten the remaining non-stream non-`general` `web_search` legacy fallback in this slice
- Potential drift:
  - none noted; this slice matches the planned cleanup targets
- Next step:
  - audit the remaining non-deliberate legacy ownership and decide whether non-stream non-`general` `web_search` is the next cut

## 2026-04-11 Memory Context Node Slice
- Implemented the immediately safe graph-owned preplan context nodes:
  - `load_long_term_context`
  - `load_response_constraints`
- These now run before graph planning on both stream and non-stream paths.
- The graph now receives loaded long-term context and response constraints before deciding the next action.

### decision_audit
- Files changed:
  - `app/agent_tools.py`
  - `app/pipeline.py`
  - `app/agent_graph.py`
  - `tests/test_agent_graph.py`
  - `.project-loop/PLAN.md`
  - `PROJECT_STATUS.md`
  - `progress.md`
- Planning mapping:
  - graph-owned memory/context node audit
  - immediate node candidates: load long-term context, load response constraints
- Tradeoffs:
  - kept `persist_turn_memory` deferred to avoid widening the API-boundary scope
  - kept final summarize/compose deferred as the next cleanup cut
- Potential drift:
  - none noted; the new graph preplan nodes match the planned immediate candidate set
- Next step:
  - decide whether `persist_turn_memory` should become the next nodeized capability or stay at the API boundary

## 2026-04-11 Local Doc Probe Lightening
- Replaced the probe path's rewrite/history-heavy summary probing with a direct lightweight hybrid candidate search.
- Added per-step timing logs inside `probe_local_docs` for vector search, keyword search, merge, rerank, and finalize.
- The probe now reports `rewrite_applied=False` so it is easier to distinguish the lightweight probe from the full retrieval path.

### decision_audit
- Files changed:
  - `app/agent_tools.py`
  - `tests/test_agent_tools.py`
  - `.project-loop/PLAN.md`
  - `PROJECT_STATUS.md`
  - `progress.md`
- Planning mapping:
  - make `local_doc_probe` a true lightweight probe
  - add timing logs for probe substeps without changing thresholds or assess logic
- Tradeoffs:
  - probe recall is intentionally lighter because the full retrieval path still handles the deeper search after planning
  - explicit history is no longer used inside probe candidate search
- Potential drift:
  - none noted; the probe still reuses the existing Chroma-backed vector and keyword search helpers
- Next step:
  - compare probe timing against the remaining retrieval/local-search latency on the repro prompts

## 2026-04-11 Retrieval Local Search Optimization
- `retrieval_local_search` now has its own detailed timing diagnostics for rewrite, vector, keyword, merge, rerank, material/chunk prepare, and finalize.
- The graph now passes loaded reference history into the retrieval path to avoid rebuilding it again.
- The retrieval path uses a cached vector store in the tool layer so repeated searches do not pay the Chroma instantiation cost every time.
- Repro timing on the three prompts showed the retrieval path itself is now much smaller than the full request latency; the remaining slow pieces are still the later assess/web/finalize stages on web-ish prompts.

### decision_audit
- Files changed:
  - `app/agent_tools.py`
  - `app/agent_graph.py`
  - `tests/test_agent_tools.py`
  - `tests/test_agent_graph.py`
  - `.project-loop/PLAN.md`
  - `PROJECT_STATUS.md`
  - `progress.md`
- Planning mapping:
  - keep `retrieval_local_search` as the core doc/retrieval step
  - add detailed timing logs for retrieval substeps
  - reuse graph-loaded reference history
  - cache the retrieval vector store in the tool layer
- Tradeoffs:
  - vector-store caching is process-local and assumes the corpus does not change mid-run
  - the retrieval path keeps its existing semantics; this is a performance and observability pass, not a routing change
- Potential drift:
  - none noted; the optimization stays inside the retrieval path and does not change web thresholds or local probe logic
- Next step:
  - compare the new retrieval timings against the remaining assess/web/finalize latency on the repro prompts

## 2026-04-12 Trace Context Split
- The heavy trace/context rebuild is no longer part of the main assess path.
- `_assess_local_step()` and `_assess_combined_step()` now keep only judgment-critical state and a lightweight snapshot.
- Full trace/context reconstruction now happens after finalize, when the answer is already committed.

### decision_audit
- Files changed:
  - `app/workflow.py`
  - `.project-loop/PLAN.md`
  - `PROJECT_STATUS.md`
  - `progress.md`
- Planning mapping:
  - split `_refresh_trace()` so assess keeps only judgment-critical fields
  - add a post-finalize trace/context completion step
- Tradeoffs:
  - the lightweight assessment trace keeps enough information for routing and diagnostics, while deferring the expensive context plan rebuild
  - finalize now absorbs the heavier trace snapshotting cost after the answer is ready
- Potential drift:
  - none noted; answer content and routing semantics are unchanged
- Next step:
  - verify the deferred trace snapshot still surfaces the data needed by answer consumers and diagnostics

## 2026-04-12 Doc-First Routing Probe Promotion
- `local_doc_probe` hits now act as an explicit doc-first signal in graph planning when the request is not explicit web-only and not freshness-sensitive.
- The graph logs the probe hit, chosen route, and whether local retrieval should be attempted before web fallback.
- The temporary doc-shape local-lock behavior was removed so local retrieval can still be followed by web supplementation when assess says local evidence is insufficient.

### decision_audit
- Files changed:
  - `app/agent_graph.py`
  - `app/agent_tools.py`
  - `app/workflow.py`
  - `tests/test_agent_graph.py`
  - `tests/test_pipeline.py`
  - `.project-loop/PLAN.md`
  - `PROJECT_STATUS.md`
  - `progress.md`
- Planning mapping:
  - promote probe hits to doc-first routing before web-only fallback
  - keep `retrieval_local_search` as the first retrieval step for doc-hit questions
  - add diagnostics for probe hit, chosen route, and web fallback reason
- Tradeoffs:
  - removed the temporary doc-shape local lock so web supplementation can still happen after assess when local evidence is insufficient
  - kept the router thin; the graph still owns the final ordinary-request decision
- Potential drift:
  - low; the patch only changes ordering and diagnostics, not the retrieval internals or web threshold logic
- Next step:
  - watch the new routing logs on doc-shaped questions without filename hints and confirm the probe-hit path consistently enters retrieval before web

## 2026-04-12 Web Provider Failure Classification
- Web provider failures are now separated from empty/irrelevant web results.
- GLM HTTP failures now surface the provider status in the error detail instead of collapsing into a generic evidence-insufficient fallback.
- The workflow web-search path now records provider name, request-sent, provider status, provider error, raw/parsed result counts, and a failure category so provider failures can be distinguished from irrelevant or empty results.
- Stream/web fallback still behaves the same for irrelevant results, but provider failures now surface the real failure detail instead of being masked as generic evidence insufficiency.

### decision_audit
- Files changed:
  - `app/rag.py`
  - `app/pipeline.py`
  - `app/workflow.py`
  - `tests/test_pipeline.py`
  - `.project-loop/PLAN.md`
  - `PROJECT_STATUS.md`
  - `progress.md`
- Planning mapping:
  - expose GLM provider failure details with HTTP status
  - distinguish provider failure from empty/irrelevant web results
  - add diagnostic fields for provider name, request sent, provider status/error, raw/parsed result counts, failure category, and final failure reason
- Tradeoffs:
  - kept relevance / rewrite / routing unchanged
  - kept the existing generic insufficient wording for irrelevant/empty results, while making provider failures explicit
- Potential drift:
  - low; the patch only changes failure classification and logging, not the search or ranking logic
- Next step:
  - run the live web repro cases again and confirm provider failures now surface as provider failures instead of generic evidence insufficiency
