import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class NoteCreate(BaseModel):
    passage_reference: str | None = Field(default=None, max_length=100)
    content: str = Field(min_length=1, max_length=100_000)


class NoteUpdate(BaseModel):
    passage_reference: str | None = Field(default=None, max_length=100)
    content: str = Field(min_length=1, max_length=100_000)


class NoteRead(NoteCreate):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class MessageCreate(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str = Field(min_length=1, max_length=100_000)


class MessageRead(MessageCreate):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    created_at: datetime


class StudyCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)


class StudyUpdate(StudyCreate):
    pass


class StudyRead(StudyCreate):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime
    messages: list[MessageRead] = []


class SourceCreate(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    url: str | None = Field(default=None, max_length=2048)
    citation: str | None = Field(default=None, max_length=10_000)


class SourceRead(SourceCreate):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
