"""HTTP-only input shapes. Evidence and response types come from contracts."""
from typing import Annotated
from pydantic import Field, model_validator
from app.contracts.models import DTO, Id, Role, SearchFilters, PageRequest

class LoginInput(DTO):
    email: Annotated[str, Field(min_length=1, max_length=320)]
    password: Annotated[str, Field(min_length=1, max_length=4096)]
class ConversationInput(DTO):
    title: Annotated[str, Field(min_length=1, max_length=120)] = "New Chat"
class MemberInput(DTO):
    user_id: Id
    role: Role
class SearchBody(DTO):
    query: Annotated[str, Field(min_length=1, max_length=8000)]
    filters: SearchFilters
    cursor: str | None = None
    limit: Annotated[int, Field(strict=True, ge=1, le=100)] = 25
    @model_validator(mode="after")
    def dates(self):
        if self.filters.date_from and self.filters.date_to and self.filters.date_from > self.filters.date_to:
            raise ValueError("invalid date range")
        return self
