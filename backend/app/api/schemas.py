"""HTTP-only input shapes. Evidence and response types come from contracts."""
from typing import Annotated
from pydantic import Field, model_validator
from app.contracts.models import DTO, Id, Role, SearchFilters, PageRequest

class LoginInput(DTO):
    email: Annotated[str, Field(min_length=1, max_length=320)]
    password: Annotated[str, Field(min_length=1, max_length=4096)]
class RegisterInput(DTO):
    email: Annotated[str, Field(min_length=3, max_length=320)]
    password: Annotated[str, Field(min_length=10, max_length=4096)]
    display_name: Annotated[str, Field(min_length=1, max_length=255)]
class ConversationInput(DTO):
    title: Annotated[str, Field(min_length=1, max_length=120)] = "New Chat"
class MemberInput(DTO):
    user_id: Id | None = None
    email: Annotated[str, Field(min_length=3, max_length=320)] | None = None
    role: Role
    @model_validator(mode="after")
    def identity(self):
        if (self.user_id is None) == (self.email is None):
            raise ValueError("Supply exactly one account ID or email")
        return self
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


class PrivacyResolutionInput(DTO):
    resolution: Annotated[str, Field(min_length=1, max_length=500)]

class ProjectTypeInput(DTO):
    name: Annotated[str, Field(min_length=1, max_length=64, pattern=r"^[a-z0-9][a-z0-9 _-]*$")]

class ProjectTypeInput(DTO):
    name: Annotated[str, Field(min_length=1, max_length=64, pattern=r"^[a-z0-9][a-z0-9 _-]*$")]
