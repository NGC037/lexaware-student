from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

GuideSection = Literal[
    "immediate_safety",
    "safety_considerations",
    "preserve_evidence",
    "reporting_options",
    "information_to_prepare",
    "checklist",
    "escalation",
]


class ComplaintInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)


class GuidanceStep(ComplaintInput):
    position: int = Field(ge=1, le=50)
    section: GuideSection
    title: str = Field(min_length=2, max_length=120)
    instruction: str = Field(min_length=2, max_length=2000)


class GuideContent(ComplaintInput):
    title: str = Field(min_length=3, max_length=240)
    category: str = Field(min_length=2, max_length=80)
    jurisdiction_id: uuid.UUID
    audience: str = Field(default="students", min_length=2, max_length=60)
    short_description: str = Field(default="", max_length=500)
    guidance_steps: list[GuidanceStep] = Field(default_factory=list, max_length=50)
    effective_from: datetime | None = None
    effective_until: datetime | None = None
    review_due_at: datetime | None = None
    change_summary: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def validate_positions(self) -> GuideContent:
        positions = [step.position for step in self.guidance_steps]
        if len(positions) != len(set(positions)):
            raise ValueError("Guidance step positions must be unique.")
        return self

    @field_validator("effective_from", "effective_until", "review_due_at")
    @classmethod
    def require_timezone(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.utcoffset() is None:
            raise ValueError("Dates must include a timezone.")
        return value


class ComplaintGuideCreate(GuideContent):
    slug: str = Field(min_length=2, max_length=160, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


class ComplaintGuideVersionCreate(GuideContent):
    pass


class ComplaintGuideUpdate(ComplaintInput):
    title: str | None = Field(default=None, min_length=3, max_length=240)
    category: str | None = Field(default=None, min_length=2, max_length=80)
    jurisdiction_id: uuid.UUID | None = None
    audience: str | None = Field(default=None, min_length=2, max_length=60)
    short_description: str | None = Field(default=None, max_length=500)
    guidance_steps: list[GuidanceStep] | None = Field(default=None, max_length=50)
    effective_from: datetime | None = None
    effective_until: datetime | None = None
    review_due_at: datetime | None = None
    change_summary: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def validate_positions(self) -> ComplaintGuideUpdate:
        if self.guidance_steps is not None:
            positions = [step.position for step in self.guidance_steps]
            if len(positions) != len(set(positions)):
                raise ValueError("Guidance step positions must be unique.")
        return self

    @field_validator("effective_from", "effective_until", "review_due_at")
    @classmethod
    def require_timezone(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.utcoffset() is None:
            raise ValueError("Dates must include a timezone.")
        return value

    @model_validator(mode="after")
    def require_content_for_dates(self) -> ComplaintGuideUpdate:
        required = {
            "title",
            "category",
            "jurisdiction_id",
            "audience",
            "short_description",
            "guidance_steps",
        }
        for name in self.model_fields_set & required:
            if getattr(self, name) is None:
                raise ValueError(f"{name} cannot be null.")
        for name in ("effective_from", "effective_until", "review_due_at"):
            if name in self.model_fields_set and getattr(self, name) is None:
                raise ValueError(f"{name} cannot be cleared once set.")
        return self


class GuideReviewDecision(ComplaintInput):
    decision: Literal["approve", "reject"]
    notes: str | None = Field(default=None, max_length=1000)


class JurisdictionSummary(BaseModel):
    id: uuid.UUID
    code: str
    name: str


class ComplaintGuideRead(BaseModel):
    id: uuid.UUID
    slug: str
    version_number: int
    title: str
    category: str
    audience: str
    short_description: str
    jurisdiction: JurisdictionSummary
    guidance_steps: list[GuidanceStep]
    reviewed_at: datetime


class ComplaintGuideVersionAdminRead(BaseModel):
    id: uuid.UUID
    version_number: int
    title: str
    category: str
    jurisdiction_id: uuid.UUID
    audience: str
    short_description: str
    guidance_steps: list[GuidanceStep]
    publication_state: str
    effective_from: datetime | None = None
    effective_until: datetime | None = None
    reviewed_at: datetime | None = None
    published_at: datetime | None = None
    review_due_at: datetime | None = None
    change_summary: str | None = None
    created_at: datetime
    updated_at: datetime


class ComplaintGuideAdminRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    slug: str
    status: str
    versions: list[ComplaintGuideVersionAdminRead]
    created_at: datetime
    updated_at: datetime
