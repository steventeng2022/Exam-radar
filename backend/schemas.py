from datetime import date
from typing import Literal
from urllib.parse import urlparse
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

class StrictInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

class SubjectInput(StrictInput):
    name: str = Field(min_length=1, max_length=50)
    scope: str = Field(min_length=1, max_length=2000)
    page_number: int | None = Field(None, ge=1, le=1000)

class ReviewEdit(StrictInput):
    expected_revision: str
    start_date: date | None = None
    end_date: date | None = None
    subjects: list[SubjectInput] = Field(min_length=1, max_length=40)
    reason: str = Field(min_length=1, max_length=1000)

class DecisionInput(StrictInput):
    expected_revision: str | None = None
    reason: str = Field(default="", max_length=1000)

class SchoolInput(StrictInput):
    id: str = Field(pattern=r"^[a-zA-Z0-9_-]{1,80}$")
    name: str = Field(min_length=1, max_length=150)
    short_name: str = Field(min_length=1, max_length=80)
    city: str = Field(min_length=1, max_length=40)
    district: str = Field(default="", max_length=40)
    type: Literal["high_school", "junior_high"] = "high_school"
    website: str = Field(max_length=2000)
    domains: list[str] = Field(min_length=1, max_length=10)
    crawl_enabled: bool = False

    @field_validator("domains")
    @classmethod
    def domains_normalized(cls, domains):
        import re
        cleaned = list(dict.fromkeys(d.lower().strip().rstrip('.') for d in domains))
        if any(not re.fullmatch(r"(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+edu\.tw", d) for d in cleaned):
            raise ValueError("Registry requires official .edu.tw domains")
        return cleaned

    @model_validator(mode="after")
    def official_url(self):
        parsed = urlparse(self.website)
        host = (parsed.hostname or '').lower()
        if parsed.scheme not in ('https', 'http') or parsed.username or parsed.password or parsed.port not in (None, 80, 443):
            raise ValueError("Website must be public HTTP(S) without credentials")
        if not any(host == d or host.endswith('.'+d) for d in self.domains):
            raise ValueError("Website must match registered domain")
        return self

class SchoolBatch(StrictInput):
    schools: list[SchoolInput] = Field(min_length=1, max_length=200)

class SchoolSettings(StrictInput):
    crawl_enabled: bool
