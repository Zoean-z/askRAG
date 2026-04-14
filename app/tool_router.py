import json
import re
from dataclasses import dataclass
from typing import Literal

from app.rag import format_history, get_chat_client, get_chat_model, is_summary_flow_request, normalize_history

ToolName = Literal["direct_answer", "local_doc_query", "local_doc_summary", "web_search"]
ToolIntent = Literal[
    "memory_command",
    "chat_followup",
    "direct_answer",
    "rewrite_or_transform",
    "doc_query",
    "doc_summary",
    "web_search",
    "clarification_needed",
]
WebSearchMode = Literal["general", "summary_verify"]

TOOL_CLASSIFIER_PROMPT = (
    "You are a tool router for a lightweight RAG assistant. "
    "Classify the user's request into exactly one intent from: "
    "memory_command, chat_followup, direct_answer, rewrite_or_transform, doc_query, doc_summary, web_search, clarification_needed. "
    "Use memory_command only for explicit remember/save-preference requests. "
    "Use chat_followup for questions about the previous answer, conversation meta-questions, or requests to revise the last answer. "
    "Use direct_answer for small talk, thanks, capability questions, or lightweight assistant answers that do not need retrieval. "
    "Use rewrite_or_transform for translation, polishing, rewriting, shortening, or reformatting requests. "
    "Use doc_summary for summarizing or compressing a whole document. "
    "Use doc_query for local document-grounded questions or explanations. "
    "Use web_search only for explicit website search, fresh information, news, prices, releases, or official-site lookups. "
    "Use clarification_needed when the target is too unclear to choose safely. "
    "Return strict JSON with keys: intent, confidence, reason. "
    "You may also include target_source_hint, needs_freshness, and needs_history."
)

DIRECT_GREETING_PATTERNS = (
    "^(\u4f60\u597d|\u60a8\u597d|hello|hi|hey)[!\uff01\u3002.\\s]*$",
    "^(\u65e9\u4e0a\u597d|\u4e0b\u5348\u597d|\u665a\u4e0a\u597d)[!\uff01\u3002.\\s]*$",
)
DIRECT_THANKS_PATTERNS = (
    "^(\u8c22\u8c22|\u591a\u8c22|thanks|thank you)[!\uff01\u3002.\\s]*$",
    "^(\u8f9b\u82e6\u4e86|\u9ebb\u70e6\u4e86)[!\uff01\u3002.\\s]*$",
)
DIRECT_CAPABILITY_PATTERNS = (
    "^\u4f60\u662f\u8c01[?\uff1f!\uff01\u3002.\\s]*$",
    "^\u4f60\u80fd\u505a\u4ec0\u4e48[?\uff1f!\uff01\u3002.\\s]*$",
    "^\u4f60\u652f\u6301\u4e0a\u4f20\u4ec0\u4e48\u6587\u4ef6[?\uff1f!\uff01\u3002.\\s]*$",
    "^\u8fd9\u4e2a\u9879\u76ee\u652f\u6301\u4e0a\u4f20\u4ec0\u4e48\u6587\u4ef6[?\uff1f!\uff01\u3002.\\s]*$",
)
DIRECT_ANSWER_PATTERNS = DIRECT_GREETING_PATTERNS + DIRECT_THANKS_PATTERNS + DIRECT_CAPABILITY_PATTERNS
DIRECT_TASK_TERMS = (
    "\u7ffb\u8bd1",
    "translate",
    "\u6da6\u8272",
    "polish",
    "\u6539\u5199",
    "rewrite",
    "\u91cd\u5199",
    "paraphrase",
    "\u6539\u6210\u82f1\u6587",
    "\u6539\u6210\u4e2d\u6587",
    "\u7ffb\u6210\u82f1\u6587",
    "\u7ffb\u6210\u4e2d\u6587",
    "\u8bd1\u6210\u82f1\u6587",
    "\u8bd1\u6210\u4e2d\u6587",
)
KNOWLEDGE_BASE_TERMS = (
    "\u77e5\u8bc6\u5e93",
    "\u6587\u6863",
    "\u6587\u4ef6",
    "\u8d44\u6599",
    "project_intro",
    ".txt",
    ".md",
)
ASSISTANT_AMBIGUOUS_TERMS = (
    "\u4f60\u53ef\u4ee5",
    "\u4f60\u80fd",
    "\u4f60\u4f1a",
    "\u4f60\u652f\u6301",
    "\u4f60\u8fd8\u652f\u6301",
    "\u4f60\u64c5\u957f",
    "\u4f60\u4e86\u89e3",
    "\u4f60\u77e5\u9053",
    "\u4f60\u89c9\u5f97",
    "\u4f60\u6709\u6ca1\u6709",
    "can you",
    "could you",
    "what can you",
    "who are you",
)
FOLLOWUP_REFERENCE_TERMS = (
    "上次",
    "刚才",
    "刚刚",
    "前面",
    "上一条",
    "上一个回答",
    "刚才那个回答",
    "那个回答",
    "这个回答",
    "继续",
    "接着",
    "继续刚才",
    "上一段",
    "上面的回答",
    "last answer",
    "previous answer",
    "that answer",
    "this answer",
    "continue",
)
FOLLOWUP_META_TERMS = (
    "太长",
    "太短",
    "超过",
    "不对",
    "有问题",
    "改短",
    "改长",
    "缩短",
    "重说",
    "重写",
    "换个说法",
    "重新说",
    "summarize that",
    "shorter",
    "longer",
    "too long",
    "too short",
)
WEB_SEARCH_EXPLICIT_TERMS = (
    "\u8054\u7f51",
    "\u4e0a\u7f51",
    "\u7f51\u9875",
    "\u7f51\u7ad9",
    "\u7f51\u7edc\u641c\u7d22",
    "\u7528\u7f51\u7edc\u641c\u7d22",
    "\u4f7f\u7528\u7f51\u7edc\u641c\u7d22",
    "\u53ea\u67e5\u7f51\u7edc",
    "\u53ea\u67e5\u7f51\u4e0a",
    "\u4e0d\u8981\u672c\u5730",
    "\u5fc5\u987b\u8054\u7f51",
    "\u5b98\u7f51",
    "\u5b98\u65b9\u7f51\u7ad9",
    "\u65b0\u95fb",
    "official website",
    "official site",
    "web search",
    "search the web",
    "search online",
)
WEB_SEARCH_FRESHNESS_TERMS = (
    "\u6700\u65b0",
    "\u4eca\u5929",
    "\u4eca\u65e5",
    "\u8fd1\u671f",
    "\u6700\u8fd1",
    "\u65b0\u95fb",
    "\u4ef7\u683c",
    "\u80a1\u4ef7",
    "\u6c47\u7387",
    "\u7248\u672c",
    "\u53d1\u5e03\u65e5\u671f",
    "latest",
    "today",
    "recent",
    "news",
    "price",
    "stock price",
    "exchange rate",
    "release date",
)
WEB_ONLY_EXPLICIT_TERMS = (
    "\u53ea\u67e5\u7f51\u7edc",
    "\u53ea\u67e5\u7f51\u4e0a",
    "\u4e0d\u8981\u672c\u5730",
    "\u5fc5\u987b\u8054\u7f51",
    "web only",
    "only web",
    "must search web",
)
LOCAL_ONLY_EXPLICIT_TERMS = (
    "\u53ea\u7528\u672c\u5730",
    "\u4ec5\u7528\u672c\u5730",
    "\u53ea\u67e5\u672c\u5730",
    "\u4e0d\u8981\u8054\u7f51",
    "\u4e0d\u8981\u7f51\u7edc",
    "\u4e0d\u8981web",
    "local only",
    "only local",
    "no web",
)
SUMMARY_WEB_VERIFY_TERMS = (
    "\u786e\u8ba4",
    "\u6838\u5b9e",
    "\u67e5\u8bc1",
    "\u6c42\u8bc1",
    "\u9a8c\u8bc1",
    "verify",
    "fact check",
    "cross-check",
    "double check",
    "\u662f\u5426\u5c5e\u5b9e",
    "\u662f\u5426\u51c6\u786e",
    "\u662f\u771f\u7684\u5417",
    "\u5bf9\u5417",
    "\u5bf9\u4e0d\u5bf9",
    "\u9760\u8c31\u5417",
    "\u6709\u8bef\u5417",
)
SUMMARY_WEB_VERIFY_REFERENCE_TERMS = (
    "\u8fd9\u4e2a\u603b\u7ed3",
    "\u4e0a\u9762\u7684\u603b\u7ed3",
    "\u521a\u624d\u7684\u603b\u7ed3",
    "\u8fd9\u4e2a\u8bf4\u6cd5",
    "\u8fd9\u4e9b\u8bf4\u6cd5",
    "\u8fd9\u4e2a\u5185\u5bb9",
    "\u4e0a\u9762",
    "\u521a\u624d",
    "it",
    "this",
    "that",
    "summary",
)
SOURCE_HINT_PATTERN = re.compile(r"([A-Za-z0-9_./-]+\.(?:txt|md))", flags=re.IGNORECASE)


@dataclass(slots=True)
class ToolPlan:
    intent: ToolIntent
    primary_tool: ToolName
    fallback_tool: ToolName | None
    confidence: float
    reason: str
    use_history: bool
    target_source_hint: str | None = None
    needs_freshness: bool = False
    needs_external_knowledge: bool = False
    web_search_mode: WebSearchMode = "general"


@dataclass(frozen=True, slots=True)
class SummaryContext:
    user_question: str
    assistant_answer: str
    sources: list[str]


@dataclass(frozen=True, slots=True)
class RouterHints:
    target_source_hint: str | None
    summary_candidate: bool
    doc_candidate: bool
    web_candidate: bool
    direct_answer_candidate: bool
    followup_candidate: bool
    needs_freshness: bool
    use_history: bool
    force_web_only: bool
    force_local_only: bool


def _clamp_confidence(value: object, default: float = 0.5) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return max(0.0, min(1.0, parsed))


def _is_direct_text_task_request(question: str) -> bool:
    normalized = question.strip().casefold()
    if not normalized:
        return False
    if any(term in normalized for term in KNOWLEDGE_BASE_TERMS):
        return False
    return any(term in normalized for term in DIRECT_TASK_TERMS)


def is_direct_answer_request(question: str) -> bool:
    normalized = question.strip()
    if not normalized:
        return False
    if any(re.match(pattern, normalized, flags=re.IGNORECASE) for pattern in DIRECT_ANSWER_PATTERNS):
        return True
    return _is_direct_text_task_request(normalized)


def _question_has_doc_shape(question: str, *, target_source_hint: str | None = None) -> bool:
    normalized = question.strip().casefold()
    if not normalized:
        return False
    if target_source_hint:
        return True
    return any(term in normalized for term in KNOWLEDGE_BASE_TERMS)


def _looks_like_chat_followup(question: str, history: list[dict[str, str]] | None = None) -> bool:
    normalized = question.strip().casefold()
    if not normalized:
        return False
    if any(term in normalized for term in FOLLOWUP_REFERENCE_TERMS):
        return True
    if normalize_history(history) and any(term in normalized for term in FOLLOWUP_META_TERMS):
        return True
    return False


def is_explicit_doc_query_request(question: str) -> bool:
    target_source_hint = extract_target_source_hint(question)
    if target_source_hint:
        return True
    normalized = question.strip().casefold()
    if not normalized:
        return False
    if is_direct_answer_request(question):
        return False
    if is_web_search_request(question):
        return False
    if is_summary_flow_request(question, history=[]):
        return False
    return any(term in normalized for term in KNOWLEDGE_BASE_TERMS)


def is_web_search_request(question: str, history: list[dict[str, str]] | None = None) -> bool:
    normalized = question.strip().casefold()
    if not normalized:
        return False

    if normalize_history(history):
        latest_sources = any(message.get("sources") for message in normalize_history(history))
    else:
        latest_sources = False

    if any(term in normalized for term in WEB_SEARCH_EXPLICIT_TERMS):
        return True

    if any(term in normalized for term in WEB_SEARCH_FRESHNESS_TERMS):
        if any(term in normalized for term in KNOWLEDGE_BASE_TERMS) or latest_sources:
            return False
        return True

    return False


def find_recent_summary_context(history: list[dict[str, str]] | None = None) -> SummaryContext | None:
    try:
        from app.session_memory import find_recent_summary_memory_context

        memory_context = find_recent_summary_memory_context()
        if memory_context is not None:
            return SummaryContext(
                user_question=memory_context.user_question,
                assistant_answer=memory_context.assistant_answer,
                sources=list(memory_context.sources),
            )
    except Exception:
        pass

    normalized_history = normalize_history(history)
    if len(normalized_history) < 2:
        return None

    for index in range(len(normalized_history) - 1, 0, -1):
        assistant_message = normalized_history[index]
        if assistant_message.get("role") != "assistant":
            continue

        sources = assistant_message.get("sources", [])
        if not sources:
            continue

        user_message = normalized_history[index - 1]
        if user_message.get("role") != "user":
            continue

        previous_history = normalized_history[: index - 1]
        if not is_summary_flow_request(user_message.get("content", ""), history=previous_history):
            continue

        return SummaryContext(
            user_question=user_message.get("content", ""),
            assistant_answer=assistant_message.get("content", ""),
            sources=list(sources),
        )

    return None


def is_summary_web_verify_request(question: str, history: list[dict[str, str]] | None = None) -> bool:
    normalized = question.strip().casefold()
    if not normalized:
        return False

    if find_recent_summary_context(history) is None:
        return False

    if any(term in normalized for term in SUMMARY_WEB_VERIFY_TERMS):
        return True

    if any(term in normalized for term in WEB_SEARCH_EXPLICIT_TERMS):
        return any(term in normalized for term in SUMMARY_WEB_VERIFY_REFERENCE_TERMS)

    return False


def extract_target_source_hint(question: str) -> str | None:
    match = SOURCE_HINT_PATTERN.search(question)
    if match:
        return match.group(1)
    return None


def is_explicit_web_only_constraint(question: str) -> bool:
    normalized = question.strip().casefold()
    if not normalized:
        return False
    return any(term in normalized for term in WEB_ONLY_EXPLICIT_TERMS)


def is_explicit_local_only_constraint(question: str) -> bool:
    normalized = question.strip().casefold()
    if not normalized:
        return False
    return any(term in normalized for term in LOCAL_ONLY_EXPLICIT_TERMS)


def extract_router_hints(
    question: str,
    history: list[dict[str, str]] | None = None,
) -> RouterHints:
    normalized_history = normalize_history(history)
    target_source_hint = extract_target_source_hint(question)
    force_web_only = is_explicit_web_only_constraint(question)
    force_local_only = is_explicit_local_only_constraint(question)
    summary_candidate = is_summary_flow_request(question, history=normalized_history)
    doc_candidate = force_local_only or is_explicit_doc_query_request(question)
    web_candidate = force_web_only or is_web_search_request(question, history=normalized_history)
    direct_answer_candidate = is_direct_answer_request(question)
    followup_candidate = _looks_like_chat_followup(question, history=normalized_history)
    needs_freshness = web_candidate and any(
        term in question.strip().casefold() for term in WEB_SEARCH_FRESHNESS_TERMS
    )
    return RouterHints(
        target_source_hint=target_source_hint,
        summary_candidate=summary_candidate,
        doc_candidate=doc_candidate,
        web_candidate=web_candidate,
        direct_answer_candidate=direct_answer_candidate,
        followup_candidate=followup_candidate,
        needs_freshness=needs_freshness,
        use_history=bool(normalized_history),
        force_web_only=force_web_only,
        force_local_only=force_local_only,
    )


def _tool_intent(tool_name: ToolName) -> ToolIntent:
    if tool_name == "direct_answer":
        return "direct_answer"
    if tool_name == "local_doc_summary":
        return "doc_summary"
    if tool_name == "web_search":
        return "web_search"
    return "doc_query"


def build_tool_plan(
    primary_tool: ToolName,
    reason: str,
    *,
    intent: ToolIntent | None = None,
    confidence: float = 1.0,
    fallback_tool: ToolName | None = None,
    use_history: bool = True,
    target_source_hint: str | None = None,
    needs_freshness: bool = False,
    needs_external_knowledge: bool = False,
    web_search_mode: WebSearchMode = "general",
) -> ToolPlan:
    return ToolPlan(
        intent=intent or _tool_intent(primary_tool),
        primary_tool=primary_tool,
        fallback_tool=fallback_tool,
        confidence=confidence,
        reason=reason,
        use_history=use_history,
        target_source_hint=target_source_hint,
        needs_freshness=needs_freshness,
        needs_external_knowledge=needs_external_knowledge,
        web_search_mode=web_search_mode,
    )


def rule_tool_plan(
    question: str,
    history: list[dict[str, str]] | None = None,
) -> ToolPlan | None:
    normalized_history = normalize_history(history)
    target_source_hint = extract_target_source_hint(question)

    if is_explicit_web_only_constraint(question):
        return build_tool_plan(
            "web_search",
            reason="matched_explicit_web_only_constraint",
            confidence=1.0,
            fallback_tool=None,
            use_history=bool(normalized_history),
            target_source_hint=target_source_hint,
            needs_freshness=True,
            needs_external_knowledge=True,
        )

    if is_explicit_local_only_constraint(question):
        return build_tool_plan(
            "local_doc_query",
            reason="matched_explicit_local_only_constraint",
            confidence=1.0,
            fallback_tool="local_doc_summary",
            use_history=bool(normalized_history),
            target_source_hint=target_source_hint,
            intent="doc_query",
            needs_freshness=False,
            needs_external_knowledge=False,
        )

    return None


def build_tool_messages(question: str, history: list[dict[str, str]] | None = None) -> list[dict[str, str]]:
    normalized_history = normalize_history(history)
    history_block = format_history(normalized_history)
    content_parts = [f"Current question:\n{question.strip()}"]
    if history_block:
        content_parts.insert(0, f"Recent conversation history:\n{history_block}")
    return [
        {"role": "system", "content": TOOL_CLASSIFIER_PROMPT},
        {"role": "user", "content": "\n\n".join(content_parts)},
    ]


def _normalize_tool_name(value: object) -> ToolName:
    raw = str(value or "local_doc_query").strip()
    route_mapping = {
        "local_chunk": "local_doc_query",
        "local_summary": "local_doc_summary",
    }
    normalized = route_mapping.get(raw, raw)
    if normalized not in {"direct_answer", "local_doc_query", "local_doc_summary", "web_search"}:
        normalized = "local_doc_query"
    return normalized  # type: ignore[return-value]


def _normalize_intent_name(value: object) -> ToolIntent:
    raw = str(value or "direct_answer").strip()
    route_mapping = {
        "local_chunk": "doc_query",
        "local_summary": "doc_summary",
        "assistant": "direct_answer",
        "followup": "chat_followup",
    }
    normalized = route_mapping.get(raw, raw)
    if normalized not in {
        "memory_command",
        "chat_followup",
        "direct_answer",
        "rewrite_or_transform",
        "doc_query",
        "doc_summary",
        "web_search",
        "clarification_needed",
    }:
        normalized = "direct_answer"
    return normalized  # type: ignore[return-value]


def _primary_tool_for_intent(intent: ToolIntent) -> ToolName:
    if intent == "doc_query":
        return "local_doc_query"
    if intent == "doc_summary":
        return "local_doc_summary"
    if intent == "web_search":
        return "web_search"
    return "direct_answer"


def _build_plan_for_intent(
    intent: ToolIntent,
    *,
    reason: str,
    confidence: float,
    question: str,
    history: list[dict[str, str]] | None = None,
    target_source_hint: str | None = None,
    needs_freshness: bool = False,
    needs_external_knowledge: bool = False,
) -> ToolPlan:
    primary_tool = _primary_tool_for_intent(intent)
    fallback_tool = "local_doc_summary" if primary_tool == "local_doc_query" else None
    return build_tool_plan(
        primary_tool,
        reason=reason,
        intent=intent,
        confidence=confidence,
        fallback_tool=fallback_tool,
        use_history=bool(normalize_history(history)),
        target_source_hint=target_source_hint,
        needs_freshness=needs_freshness,
        needs_external_knowledge=needs_external_knowledge,
    )


def _typed_fallback_plan(
    *,
    question: str,
    history: list[dict[str, str]] | None = None,
    fallback_intent: ToolIntent | None = None,
    confidence: float = 0.0,
    reason: str,
) -> ToolPlan:
    normalized_history = normalize_history(history)
    target_source_hint = extract_target_source_hint(question)
    intent = fallback_intent
    if intent is None:
        if is_summary_flow_request(question, history=normalized_history):
            intent = "doc_summary"
        elif is_web_search_request(question, history=normalized_history):
            intent = "web_search"
        elif _looks_like_chat_followup(question, history=normalized_history):
            intent = "chat_followup"
        elif _question_has_doc_shape(question, target_source_hint=target_source_hint):
            intent = "doc_query"
        elif is_direct_answer_request(question):
            intent = "direct_answer"
        else:
            intent = "direct_answer"

    if intent in {"chat_followup", "direct_answer", "rewrite_or_transform", "clarification_needed"}:
        return _build_plan_for_intent(
            intent,
            reason=reason,
            confidence=confidence,
            question=question,
            history=normalized_history,
            target_source_hint=None,
        )

    if intent == "doc_summary":
        if is_summary_flow_request(question, history=normalized_history) or target_source_hint:
            return _build_plan_for_intent(
                "doc_summary",
                reason=reason,
                confidence=confidence,
                question=question,
                history=normalized_history,
                target_source_hint=target_source_hint,
            )
        return _build_plan_for_intent(
            "clarification_needed",
            reason=f"{reason}_clarification_needed",
            confidence=confidence,
            question=question,
            history=normalized_history,
        )

    if intent == "doc_query":
        if _question_has_doc_shape(question, target_source_hint=target_source_hint):
            return _build_plan_for_intent(
                "doc_query",
                reason=reason,
                confidence=confidence,
                question=question,
                history=normalized_history,
                target_source_hint=target_source_hint,
            )
        return _build_plan_for_intent(
            "direct_answer",
            reason=f"{reason}_fallback_direct_answer",
            confidence=confidence,
            question=question,
            history=normalized_history,
        )

    if intent == "web_search":
        if is_web_search_request(question, history=normalized_history):
            return _build_plan_for_intent(
                "web_search",
                reason=reason,
                confidence=confidence,
                question=question,
                history=normalized_history,
                needs_freshness=True,
                needs_external_knowledge=True,
            )
        return _build_plan_for_intent(
            "direct_answer",
            reason=f"{reason}_fallback_direct_answer",
            confidence=confidence,
            question=question,
            history=normalized_history,
        )

    return _build_plan_for_intent(
        "direct_answer",
        reason=f"{reason}_fallback_direct_answer",
        confidence=confidence,
        question=question,
        history=normalized_history,
    )


def parse_tool_response(
    content: str,
    *,
    question: str,
    history: list[dict[str, str]] | None = None,
) -> ToolPlan:
    raw = content.strip()
    if not raw:
        raise ValueError("Tool router returned empty content.")

    json_start = raw.find("{")
    json_end = raw.rfind("}")
    if json_start >= 0 and json_end > json_start:
        raw = raw[json_start : json_end + 1]

    payload = json.loads(raw)
    intent = _normalize_intent_name(payload.get("intent") or payload.get("tool") or payload.get("route"))
    confidence = _clamp_confidence(payload.get("confidence"), default=0.5)
    reason = str(payload.get("reason") or "llm_classified").strip()
    target_source_hint = str(payload.get("target_source_hint") or "").strip() or None
    needs_freshness = bool(payload.get("needs_freshness"))
    needs_external_knowledge = intent == "web_search" or needs_freshness
    return _build_plan_for_intent(
        intent,
        reason=f"llm:{reason}",
        confidence=confidence,
        question=question,
        history=history,
        target_source_hint=target_source_hint,
        needs_freshness=needs_freshness,
        needs_external_knowledge=needs_external_knowledge,
    )


def llm_tool_plan(
    question: str,
    history: list[dict[str, str]] | None = None,
) -> ToolPlan:
    client = get_chat_client()
    response = client.chat.completions.create(
        model=get_chat_model(),
        temperature=0,
        messages=build_tool_messages(question, history=history),
    )
    content = response.choices[0].message.content or ""
    return parse_tool_response(content, question=question, history=history)


def decide_tool_plan(
    question: str,
    history: list[dict[str, str]] | None = None,
) -> ToolPlan:
    normalized_history = normalize_history(history)
    ruled = rule_tool_plan(question, history=normalized_history)
    if ruled is not None:
        return ruled

    try:
        classified = llm_tool_plan(question, history=normalized_history)
    except (json.JSONDecodeError, ValueError):
        return _typed_fallback_plan(
            question=question,
            history=normalized_history,
            confidence=0.0,
            reason="typed_fallback_after_invalid_llm_route",
        )

    if classified.confidence < 0.7:
        return _typed_fallback_plan(
            question=question,
            history=normalized_history,
            fallback_intent=classified.intent,
            confidence=classified.confidence,
            reason="typed_fallback_after_low_confidence_llm_route",
        )

    return classified
