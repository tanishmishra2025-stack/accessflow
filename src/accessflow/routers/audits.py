from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from accessflow.dependencies import get_db
from accessflow.models.accessibility_issue import AccessibilityIssue
from accessflow.models.audit import Audit
from accessflow.models.website import Website
from accessflow.scanner import scan_url
from accessflow.schemas import AuditCreate, AuditRead, IssueRead
from accessflow.url_safety import UnsafeURLError, validate_public_url


router = APIRouter(
    prefix="/audits",
    tags=["Audits"],
)


@router.post(
    "",
    response_model=AuditRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_audit(
    payload: AuditCreate,
    db: Session = Depends(get_db),
):
    url = str(payload.url)

    # 1. Security check before Playwright is allowed to visit the URL
    try:
        validate_public_url(url)
    except UnsafeURLError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    # 2. Find existing Website or create one
    website = db.scalar(
        select(Website).where(Website.url == url)
    )

    if website is None:
        website = Website(url=url)
        db.add(website)
        db.flush()

    # 3. Create an Audit before starting the scan
    audit = Audit(
        website_id=website.id,
        url=url,
        status="running",
        total_issues=0,
        critical=0,
        serious=0,
        moderate=0,
        minor=0,
    )

    db.add(audit)
    db.commit()
    db.refresh(audit)

    # 4. Run Playwright + axe-core
    try:
        result = await scan_url(url)
    except Exception:
        audit.status = "failed"
        db.commit()
        db.refresh(audit)
        return audit

    # 5. Scanner itself can also report failure
    if result["status"] == "failed":
        audit.status = "failed"
        db.commit()
        db.refresh(audit)
        return audit

    # 6. Save every AccessibilityIssue
    for issue_data in result["issues"]:
        issue = AccessibilityIssue(
            audit_id=audit.id,
            rule=issue_data["rule"],
            severity=issue_data["severity"],
            element_html=issue_data["element_html"],
            description=issue_data["description"],
            wcag_ref=issue_data["wcag_ref"],
        )

        db.add(issue)

    # 7. Update Audit summary
    summary = result["summary"]

    audit.status = "completed"
    audit.total_issues = summary["total_issues"]
    audit.critical = summary["critical"]
    audit.serious = summary["serious"]
    audit.moderate = summary["moderate"]
    audit.minor = summary["minor"]

    db.commit()
    db.refresh(audit)

    return audit


@router.get(
    "/{audit_id}",
    response_model=AuditRead,
)
def get_audit(
    audit_id: int,
    db: Session = Depends(get_db),
):
    audit = db.get(Audit, audit_id)

    if audit is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Audit not found.",
        )

    return audit


@router.get(
    "/{audit_id}/issues",
    response_model=list[IssueRead],
)
def get_audit_issues(
    audit_id: int,
    severity: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    audit = db.get(Audit, audit_id)

    if audit is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Audit not found.",
        )

    statement = select(AccessibilityIssue).where(
        AccessibilityIssue.audit_id == audit_id
    )

    if severity is not None:
        allowed_severities = {
            "critical",
            "serious",
            "moderate",
            "minor",
        }

        if severity not in allowed_severities:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    "Severity must be critical, serious, "
                    "moderate, or minor."
                ),
            )

        statement = statement.where(
            AccessibilityIssue.severity == severity
        )

    return list(db.scalars(statement).all())


@router.get(
    "",
    response_model=list[AuditRead],
)
def list_audits(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    url: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    statement = (
        select(Audit)
        .order_by(Audit.id.desc())
        .offset(skip)
        .limit(limit)
    )

    if url is not None:
        statement = statement.where(Audit.url == url)

    return list(db.scalars(statement).all())