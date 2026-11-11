"""Validated request models for the HTTP API."""

from pydantic import BaseModel, Field

from app.settings import MAX_INPUT_CHARS, MAX_PERSONALITY_CHARS, MAX_PROMPT_CHARS

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=MAX_INPUT_CHARS)
    session_id: str | None = None
    request_id: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_-]{1,128}$")

class AvatarRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=MAX_PROMPT_CHARS)
    session_id: str | None = None
    request_id: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_-]{1,128}$")

class PersonalityRequest(BaseModel):
    personality: str = Field(..., min_length=1, max_length=MAX_PERSONALITY_CHARS)
    session_id: str | None = None


class ResetRequest(BaseModel):
    session_id: str | None = None


class PasswordLoginRequest(BaseModel):
    password: str = Field(..., pattern=r"^\d{4}$")
