from typing import Literal

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(..., min_length=1, description="Conversation message content")
    sources: list[str] = Field(default_factory=list, description="Optional source files tied to the message")


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, description="User question")
    history: list[ChatMessage] = Field(default_factory=list, description="Recent conversation history")


class AskResponse(BaseModel):
    answer: str
    sources: list[str] = Field(default_factory=list)


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
