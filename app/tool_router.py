import json
import re
from dataclasses import dataclass
from typing import Literal

from app.rag import format_history, get_chat_client, get_chat_model, is_summary_flow_request, normalize_history

ToolName = Literal["direct_answer", "local_doc_query", "local_doc_summary", "web_search"]
ToolIntent = Literal["direct_answer", "doc_query", "doc_summary", "web_search"]
TargetScope = Literal["assistant", "corpus", "single_document", "web"]

TOOL_CLASSIFIER_PROMPT = (
    "You are a tool router for a lightweight RAG assistant. "
    "Choose exactly one tool from: direct_answer, local_doc_query, local_doc_summary, web_search. "
    "Use local_doc_summary only when the user is asking to summarize, compress, rewrite, or restate a whole document. "
    "Use direct_answer only for small talk, thanks, safe text-transformation tasks, or product capability questions that do not require the knowledge base. "
    "Use web_search only when the user explicitly needs external websites, fresh information, news, prices, release details, or other information that is unlikely to exist in the local knowledge base. "
    "Use local_doc_query for normal document-grounded questions, explanations, or follow-up questions that should retrieve local chunks. "
    "Return strict JSON with keys: tool, confidence, reason."
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
WEB_SEARCH_EXPLICIT_TERMS = (
    "\u8054\u7f51",
    "\u4e0a\u7f51",
    "\u7f51\u9875",
    "\u7f51\u7ad9",
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
SOURCE_HINT_PATTERN = re.compile(r"([A-Za-z0-9_./-]+\.(?:txt|md))", flags=re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class ToolRegistry:
    direct_answer: bool = True
    local_doc_query: bool = True
    local_doc_summary: bool = True
    web_search: bool = True

    def is_enabled(self, tool_name: ToolName) -> bool:
        return bool(getattr(self, tool_name))


DEFAULT_TOOL_REGISTRY = ToolRegistry()


@dataclass(slots=True)
class ToolPlan:
    intent: ToolIntent
    primary_tool: ToolName
    fallback_tool: ToolName | None
    confidence: float
    reason: str
    use_history: bool
    target_scope: TargetScope
    target_source_hint: str | None = None
    needs_freshness: bool = False
    needs_external_knowledge: bool = False
    tool_available: bool = True


def get_tool_registry() -> ToolRegistry:
    return DEFAULT_TOOL_REGISTRY


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


def extract_target_source_hint(question: str) -> str | None:
    match = SOURCE_HINT_PATTERN.search(question)
    if match:
        return match.group(1)
    return None


def _tool_intent(tool_name: ToolName) -> ToolIntent:
    if tool_name == "direct_answer":
        return "direct_answer"
    if tool_name == "local_doc_summary":
        return "doc_summary"
    if tool_name == "web_search":
        return "web_search"
    return "doc_query"


def _target_scope(tool_name: ToolName, target_source_hint: str | None = None) -> TargetScope:
    if tool_name == "direct_answer":
        return "assistant"
    if tool_name == "local_doc_summary":
        return "single_document" if target_source_hint else "corpus"
    if tool_name == "web_search":
        return "web"
    return "corpus"


def build_tool_plan(
    primary_tool: ToolName,
    reason: str,
    *,
    confidence: float = 1.0,
    fallback_tool: ToolName | None = None,
    use_history: bool = True,
    target_source_hint: str | None = None,
    needs_freshness: bool = False,
    needs_external_knowledge: bool = False,
    registry: ToolRegistry | None = None,
) -> ToolPlan:
    resolved_registry = registry or get_tool_registry()
    return ToolPlan(
        intent=_tool_intent(primary_tool),
        primary_tool=primary_tool,
        fallback_tool=fallback_tool,
        confidence=confidence,
        reason=reason,
        use_history=use_history,
        target_scope=_target_scope(primary_tool, target_source_hint),
        target_source_hint=target_source_hint,
        needs_freshness=needs_freshness,
        needs_external_knowledge=needs_external_knowledge,
        tool_available=resolved_registry.is_enabled(primary_tool),
    )


def should_use_llm_tool_plan(question: str, history: list[dict[str, str]] | None = None) -> bool:
    normalized = question.strip().casefold()
    if not normalized:
        return False

    if normalize_history(history):
        return False

    if any(term in normalized for term in KNOWLEDGE_BASE_TERMS):
        return False

    if any(term in normalized for term in DIRECT_TASK_TERMS):
        return False

    if is_web_search_request(question, history=history):
        return False

    return any(term in normalized for term in ASSISTANT_AMBIGUOUS_TERMS)


def rule_tool_plan(
    question: str,
    history: list[dict[str, str]] | None = None,
    *,
    registry: ToolRegistry | None = None,
) -> ToolPlan | None:
    normalized_history = normalize_history(history)
    target_source_hint = extract_target_source_hint(question)

    if is_summary_flow_request(question, history=normalized_history):
        return build_tool_plan(
            "local_doc_summary",
            reason="matched_summary_rule",
            confidence=1.0,
            fallback_tool=None,
            use_history=bool(normalized_history),
            target_source_hint=target_source_hint,
            registry=registry,
        )

    if is_direct_answer_request(question):
        return build_tool_plan(
            "direct_answer",
            reason="matched_direct_answer_rule",
            confidence=1.0,
            fallback_tool=None,
            use_history=bool(normalized_history),
            registry=registry,
        )

    if is_web_search_request(question, history=normalized_history):
        return build_tool_plan(
            "web_search",
            reason="matched_web_search_rule",
            confidence=1.0,
            fallback_tool=None,
            use_history=bool(normalized_history),
            needs_freshness=True,
            needs_external_knowledge=True,
            registry=registry,
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


def parse_tool_response(content: str, *, registry: ToolRegistry | None = None) -> ToolPlan:
    raw = content.strip()
    if not raw:
        raise ValueError("Tool router returned empty content.")

    json_start = raw.find("{")
    json_end = raw.rfind("}")
    if json_start >= 0 and json_end > json_start:
        raw = raw[json_start : json_end + 1]

    payload = json.loads(raw)
    primary_tool = _normalize_tool_name(payload.get("tool") or payload.get("route"))
    confidence = _clamp_confidence(payload.get("confidence"), default=0.5)
    reason = str(payload.get("reason") or "llm_classified").strip()
    fallback_tool = "local_doc_summary" if primary_tool == "local_doc_query" else None
    return build_tool_plan(
        primary_tool,
        reason=f"llm:{reason}",
        confidence=confidence,
        fallback_tool=fallback_tool,
        registry=registry,
    )


def llm_tool_plan(
    question: str,
    history: list[dict[str, str]] | None = None,
    *,
    registry: ToolRegistry | None = None,
) -> ToolPlan:
    client = get_chat_client()
    response = client.chat.completions.create(
        model=get_chat_model(),
        temperature=0,
        messages=build_tool_messages(question, history=history),
    )
    content = response.choices[0].message.content or ""
    return parse_tool_response(content, registry=registry)


def decide_tool_plan(
    question: str,
    history: list[dict[str, str]] | None = None,
    *,
    registry: ToolRegistry | None = None,
) -> ToolPlan:
    normalized_history = normalize_history(history)
    resolved_registry = registry or get_tool_registry()
    ruled = rule_tool_plan(question, history=normalized_history, registry=resolved_registry)
    if ruled is not None:
        return ruled

    target_source_hint = extract_target_source_hint(question)
    if not should_use_llm_tool_plan(question, history=normalized_history):
        return build_tool_plan(
            "local_doc_query",
            reason="default_local_doc_query_rule",
            confidence=0.8,
            fallback_tool="local_doc_summary",
            use_history=bool(normalized_history),
            target_source_hint=target_source_hint,
            registry=resolved_registry,
        )

    try:
        classified = llm_tool_plan(question, history=normalized_history, registry=resolved_registry)
    except (json.JSONDecodeError, ValueError):
        return build_tool_plan(
            "local_doc_query",
            reason="default_local_doc_query_after_invalid_llm_route",
            confidence=0.0,
            fallback_tool="local_doc_summary",
            use_history=bool(normalized_history),
            target_source_hint=target_source_hint,
            registry=resolved_registry,
        )

    if classified.primary_tool in {"direct_answer", "local_doc_summary", "web_search"} and classified.confidence < 0.7:
        return build_tool_plan(
            "local_doc_query",
            reason="default_local_doc_query_after_low_confidence_llm_route",
            confidence=classified.confidence,
            fallback_tool="local_doc_summary",
            use_history=bool(normalized_history),
            target_source_hint=target_source_hint,
            registry=resolved_registry,
        )

    return classified
