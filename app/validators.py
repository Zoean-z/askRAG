from dataclasses import dataclass

from app.tool_router import ToolPlan


@dataclass(slots=True)
class RetrievalValidation:
    is_sufficient: bool
    reason: str


@dataclass(slots=True)
class ParentValidation:
    is_sufficient: bool
    reason: str


def validate_chunk_results(
    vector_results: list[tuple[object, float]],
    keyword_results: list[tuple[object, float]] | None = None,
    threshold: float = 1.2,
) -> RetrievalValidation:
    if keyword_results:
        best_keyword_score = keyword_results[0][1]
        if best_keyword_score >= 3.0:
            return RetrievalValidation(is_sufficient=True, reason="keyword_match_strong_enough")

    if not vector_results:
        return RetrievalValidation(is_sufficient=False, reason="no_vector_results")

    best_score = vector_results[0][1]
    if best_score > threshold:
        return RetrievalValidation(is_sufficient=False, reason="best_vector_score_above_threshold")

    return RetrievalValidation(is_sufficient=True, reason="vector_match_strong_enough")


def validate_parent_candidates(
    candidates: list[object],
    *,
    min_hits: int = 2,
    min_score: float = 5.0,
    min_margin: float = 2.0,
) -> ParentValidation:
    if not candidates:
        return ParentValidation(is_sufficient=False, reason="no_parent_candidates")

    top = candidates[0]
    top_hits = int(getattr(top, "hits", 0) or 0)
    top_score = float(getattr(top, "score", 0.0) or 0.0)
    second_score = float(getattr(candidates[1], "score", 0.0) or 0.0) if len(candidates) > 1 else 0.0
    margin = top_score - second_score

    if top_hits >= min_hits and top_score >= min_score:
        return ParentValidation(is_sufficient=True, reason="parent_candidate_has_multiple_child_hits")

    if top_hits >= 1 and top_score >= min_score + 1.0 and margin >= min_margin:
        return ParentValidation(is_sufficient=True, reason="parent_candidate_is_clear_top_match")

    return ParentValidation(is_sufficient=False, reason="parent_candidate_signal_too_weak")


def should_fallback_to_summary(tool_plan: ToolPlan, validation: RetrievalValidation) -> bool:
    return (
        tool_plan.primary_tool == "local_doc_query"
        and tool_plan.fallback_tool == "local_doc_summary"
        and not validation.is_sufficient
    )
