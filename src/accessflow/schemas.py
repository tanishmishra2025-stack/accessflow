from datetime import datetime

from pydantic import BaseModel, ConfigDict, HttpUrl


class AuditCreate(BaseModel):
    url: HttpUrl


class AuditRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    website_id: int
    url: str
    scanned_at: datetime
    status: str
    total_issues: int
    critical: int
    serious: int
    moderate: int
    minor: int


class IssueRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    audit_id: int
    rule: str
    severity: str
    element_html: str
    description: str
    wcag_ref: str | None