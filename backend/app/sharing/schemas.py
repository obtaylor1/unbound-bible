import uuid
from typing import Literal
from pydantic import BaseModel, Field


Visibility = Literal['private', 'unlisted', 'public']


class ShareCreate(BaseModel):
    study_id: uuid.UUID
    visibility: Visibility = 'unlisted'
    title: str | None = Field(default=None, max_length=200)


class ShareUpdate(BaseModel):
    visibility: Visibility
