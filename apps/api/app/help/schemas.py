from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

ContactMethod = Literal["phone", "website", "email", "in_person", "multiple"]


class HelpInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)


class HelpResourceCreate(HelpInput):
    jurisdiction_id: uuid.UUID
    source_id: uuid.UUID
    name: str = Field(min_length=2, max_length=200)
    category: str = Field(min_length=2, max_length=80)
    resource_type: str = Field(min_length=2, max_length=60)
    assistance_type: str = Field(min_length=2, max_length=80)
    contact_method: ContactMethod
    description: str | None = Field(default=None, max_length=2000)
    contact_url: str | None = Field(default=None, max_length=2048)
    phone: str | None = Field(default=None, max_length=40)
    contact_email: EmailStr | None = None
    expires_at: datetime | None = None

    @field_validator("contact_url")
    @classmethod
    def require_http_url(cls, value: str | None) -> str | None:
        if value is not None:
            parsed = urlsplit(value)
            if parsed.scheme not in {"http", "https"} or not parsed.hostname:
                raise ValueError("Contact URL must be an absolute HTTP or HTTPS URL.")
        return value

    @field_validator("expires_at")
    @classmethod
    def require_expiry_timezone(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.utcoffset() is None:
            raise ValueError("Expiry date must include a timezone.")
        return value

    @model_validator(mode="after")
    def validate_contact(self) -> HelpResourceCreate:
        if self.contact_method == "phone" and not self.phone:
            raise ValueError("A phone contact is required for phone resources.")
        if self.contact_method == "website" and not self.contact_url:
            raise ValueError("A URL is required for website resources.")
        if self.contact_method == "email" and not self.contact_email:
            raise ValueError("An email contact is required for email resources.")
        if (
            self.contact_method == "multiple"
            and sum(bool(value) for value in (self.phone, self.contact_url, self.contact_email)) < 2
        ):
            raise ValueError("Multiple contact methods require at least two contact details.")
        return self


class HelpResourceUpdate(HelpInput):
    jurisdiction_id: uuid.UUID | None = None
    source_id: uuid.UUID | None = None
    name: str | None = Field(default=None, min_length=2, max_length=200)
    category: str | None = Field(default=None, min_length=2, max_length=80)
    resource_type: str | None = Field(default=None, min_length=2, max_length=60)
    assistance_type: str | None = Field(default=None, min_length=2, max_length=80)
    contact_method: ContactMethod | None = None
    description: str | None = Field(default=None, max_length=2000)
    contact_url: str | None = Field(default=None, max_length=2048)
    phone: str | None = Field(default=None, max_length=40)
    contact_email: EmailStr | None = None
    expires_at: datetime | None = None

    @field_validator("contact_url")
    @classmethod
    def require_http_url(cls, value: str | None) -> str | None:
        if value is not None:
            parsed = urlsplit(value)
            if parsed.scheme not in {"http", "https"} or not parsed.hostname:
                raise ValueError("Contact URL must be an absolute HTTP or HTTPS URL.")
        return value

    @field_validator("expires_at")
    @classmethod
    def require_expiry_timezone(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.utcoffset() is None:
            raise ValueError("Expiry date must include a timezone.")
        return value

    @model_validator(mode="after")
    def reject_null_required_values(self) -> HelpResourceUpdate:
        required = {
            "jurisdiction_id",
            "source_id",
            "name",
            "category",
            "resource_type",
            "assistance_type",
            "contact_method",
        }
        for name in self.model_fields_set & required:
            if getattr(self, name) is None:
                raise ValueError(f"{name} cannot be null.")
        return self


class VerifyHelpResource(HelpInput):
    verification_due_at: datetime

    @model_validator(mode="after")
    def require_timezone(self) -> VerifyHelpResource:
        if self.verification_due_at.utcoffset() is None:
            raise ValueError("verification_due_at must include a timezone.")
        return self


class HelpResourceAdminRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    jurisdiction_id: uuid.UUID
    source_id: uuid.UUID | None = None
    name: str
    category: str
    resource_type: str
    assistance_type: str
    contact_method: str
    description: str | None = None
    contact_url: str | None = None
    phone: str | None = None
    contact_email: str | None = None
    verified_at: datetime | None = None
    verification_due_at: datetime | None = None
    expires_at: datetime | None = None
    status: str
    created_at: datetime
    updated_at: datetime


class HelpJurisdictionRead(BaseModel):
    code: str
    name: str


class StudentHelpResourceRead(BaseModel):
    id: uuid.UUID
    name: str
    category: str
    resource_type: str
    assistance_type: str
    contact_method: ContactMethod
    description: str | None = None
    contact_url: str | None = None
    phone: str | None = None
    contact_email: EmailStr | None = None
    jurisdiction: HelpJurisdictionRead
    source_title: str
    source_publisher: str | None = None
    source_url: str
    source_citation: str | None = None
    source_retrieved_at: datetime
    verified_at: datetime
    status: Literal["verified_current"] = "verified_current"
