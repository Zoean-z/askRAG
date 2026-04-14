from typing import Any, Literal

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(..., min_length=1, description="Conversation message content")
    sources: list[str] = Field(default_factory=list, description="Optional source files tied to the message")


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, description="User question")
    history: list[ChatMessage] = Field(default_factory=list, description="Recent conversation history")
    conversation_id: str | None = None
    use_web_search: bool = False


class MemoryNoticeRecord(BaseModel):
    kind: Literal["remembered", "candidate", "used"]
    summary: str
    memory_type: str | None = None
    status: str | None = None


class AskResponse(BaseModel):
    answer: str
    sources: list[str] = Field(default_factory=list)
    trace: dict[str, Any] = Field(default_factory=dict)
    conversation_id: str | None = None
    memory_notices: list[MemoryNoticeRecord] = Field(default_factory=list)


class DocumentRecord(BaseModel):
    file_name: str
    source: str
    md5: str
    uploaded_at: str | None = None
    chunk_count: int | None = None


class DocumentListResponse(BaseModel):
    documents: list[DocumentRecord] = Field(default_factory=list)


class UploadDocumentResponse(BaseModel):
    status: Literal["indexed", "duplicate"]
    document: DocumentRecord


class DeleteDocumentResponse(BaseModel):
    status: Literal["deleted"]
    document: DocumentRecord


class MemoryEntryRecord(BaseModel):
    id: str
    memory_type: Literal[
        "raw_turn_log",
        "working_summary",
        "recent_task_state",
        "pinned_preference",
        "stable_profile_fact",
        "approved_long_term_fact",
    ]
    layer: Literal["L0", "L1", "L2"]
    scope: Literal["session", "cross_thread"]
    status: Literal["pending", "approved", "rolled_back", "superseded"]
    title: str
    summary: str
    payload: dict[str, Any] = Field(default_factory=dict)
    subject_key: str | None = None
    source_refs: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    confidence: float | None = None
    created_at: str | None = None
    updated_at: str | None = None
    expires_at: str | None = None
    approved_at: str | None = None
    rolled_back_at: str | None = None
    superseded_at: str | None = None
    superseded_by: str | None = None
    openviking_resource_uri: str | None = None
    openviking_sync_status: str | None = None
    openviking_last_synced_at: str | None = None
    openviking_last_sync_error: str | None = None


class MemoryExtractRequest(BaseModel):
    question: str = Field(..., min_length=1)
    answer: str = ""
    sources: list[str] = Field(default_factory=list)
    history: list[ChatMessage] = Field(default_factory=list)
    persist: bool = True


class MemoryUpdateRequest(BaseModel):
    title: str | None = None
    summary: str | None = None
    tags: list[str] | None = None


class MemoryListResponse(BaseModel):
    memories: list[MemoryEntryRecord] = Field(default_factory=list)
    audit: list[dict[str, Any]] = Field(default_factory=list)


class MemoryExtractResponse(BaseModel):
    memories: list[MemoryEntryRecord] = Field(default_factory=list)


class MemoryActionResponse(BaseModel):
    status: Literal["approved", "rolled_back"]
    memory: MemoryEntryRecord


class MemoryUpdateResponse(BaseModel):
    status: Literal["updated"]
    memory: MemoryEntryRecord


class ConversationMessageRecord(BaseModel):
    id: str
    role: Literal["user", "assistant"]
    content: str
    sources: list[str] = Field(default_factory=list)
    created_at: str | None = None
    memory_notices: list[MemoryNoticeRecord] = Field(default_factory=list)
    trace: dict[str, Any] = Field(default_factory=dict)


class ConversationRecord(BaseModel):
    id: str
    title: str
    created_at: str | None = None
    updated_at: str | None = None
    message_count: int = 0
    last_message_preview: str = ""


class ConversationListResponse(BaseModel):
    conversations: list[ConversationRecord] = Field(default_factory=list)


class ConversationResponse(BaseModel):
    conversation: ConversationRecord
    messages: list[ConversationMessageRecord] = Field(default_factory=list)


class ConversationCreateRequest(BaseModel):
    title: str | None = None


class ConversationDeleteResponse(BaseModel):
    status: Literal["deleted"]
    conversation: ConversationRecord


class OpsStateResponse(BaseModel):
    state: dict[str, Any] = Field(default_factory=dict)
    memory_count: int = 0
    document_count: int = 0
    memory_summary: dict[str, Any] = Field(default_factory=dict)
    chat_model: str = ""
    web_search_model: str = ""


class OperationResponse(BaseModel):
    status: str
    operation: dict[str, Any] = Field(default_factory=dict)
    documents: list[DocumentRecord] = Field(default_factory=list)
