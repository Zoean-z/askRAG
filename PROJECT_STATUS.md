# Project Status

## Current Goal
- Separate web provider failure from empty/irrelevant web results so failures are reported accurately.

## Current Memory Files
- `AGENTS.md`
- `.project-loop/PLAN.md`
- `PROJECT_STATUS.md`
- `PROJECT_PLAN.md`
- `progress.md`
- `data/loop_state.json`

## Current State
- The graph still owns the main execution path.
- Ordinary requests enter graph with router hints plus a lightweight local-doc probe before final planning.
- The pre-plan trio is now structurally parallelized so the three independent nodes can complete before `plan_request`.
- The router remains thin: strong constraints stay in the router, while ordinary doc/web/summary strategy decisions are graph-owned.
- Summary strategy is graph-owned and can choose pure local summary or summary plus web supplement.
- Explicit `remember ...` still short-circuits at the API entry.
- The chat UI still supports deleting a conversation thread from the history rail.
- The sidebar is now being widened so the delete affordance is easier to spot.
- The backend delete endpoint already existed; the frontend action and state refresh are unchanged.
- The local sufficiency layer now distinguishes retrieval relevance from answer sufficiency so doc-hit questions can still fall back to web when coverage is incomplete.
- Web provider failures are now classified separately from empty/irrelevant web results, and provider failure details are surfaced instead of being generalized into evidence insufficiency.

## Suggested Next Step
- Re-run the live web repros and verify provider failure details surface cleanly while irrelevant/empty web results still use the generic insufficient wording.
