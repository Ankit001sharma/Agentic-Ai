"""OpenAI Chat Completions API-compatible Pydantic schemas."""

from __future__ import annotations

import time
import uuid
from typing import Any, Literal

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant", "tool", "function"]
    content: str | None = None
    name: str | None = None


class AttachmentInput(BaseModel):
    """Inline file attachment carried alongside a chat completion request.

    The payload is base64-encoded so the existing JSON ``/v1/chat/completions``
    endpoint can accept files without switching to ``multipart/form-data``.
    Supported file kinds: text, source code, PDF, DOCX, and images
    (with optional OCR if ``pytesseract`` is installed server-side).
    """

    filename: str = Field(..., description="Original filename, e.g. notes.pdf")
    mime_type: str | None = Field(default=None, description="IANA MIME type")
    data_b64: str = Field(
        ...,
        description=(
            "Base64-encoded file bytes. May be a raw base64 string or a "
            "RFC 2397 data URL (data:<mime>;base64,<payload>)."
        ),
    )


class ChatCompletionRequest(BaseModel):
    model: str
    messages: list[ChatMessage]
    temperature: float | None = Field(default=None, ge=0, le=2)
    top_p: float | None = Field(default=None, ge=0, le=1)
    max_tokens: int | None = Field(default=None, gt=0)
    stream: bool = False
    user: str | None = None
    metadata: dict[str, Any] | None = None
    attachments: list[AttachmentInput] | None = Field(
        default=None,
        description=(
            "Optional list of files attached to the prompt. Each file is "
            "extracted to text and threat-scanned alongside the user message."
        ),
    )


class Usage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class ChatCompletionChoice(BaseModel):
    index: int = 0
    message: ChatMessage
    finish_reason: str = "stop"


class ChatCompletionResponse(BaseModel):
    id: str = Field(default_factory=lambda: f"chatcmpl-{uuid.uuid4().hex[:12]}")
    object: str = "chat.completion"
    created: int = Field(default_factory=lambda: int(time.time()))
    model: str
    choices: list[ChatCompletionChoice]
    usage: Usage = Field(default_factory=Usage)
    sentinel: dict[str, Any] | None = None
