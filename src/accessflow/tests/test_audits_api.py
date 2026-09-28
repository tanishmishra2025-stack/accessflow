from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from accessflow.database import Base
from accessflow.dependencies import get_db
from accessflow.main import app
from accessflow.models import AccessibilityIssue, Audit, Website


# ---------------------------------------------------------
# Test database
# ---------------------------------------------------------

TEST_DATABASE_URL = "sqlite://"


test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)


TestingSessionLocal = sessionmaker(
    bind=test_engine,
    autoflush=False,
    autocommit=False,
)


# ---------------------------------------------------------
# Fake scanner results
# ---------------------------------------------------------

FAKE_SCAN_RESULT = {
    "status": "completed",
    "url": "https://example.com/",
    "summary": {
        "total_issues": 3,
        "critical": 1,
        "serious": 1,
        "moderate": 1,
        "minor": 0,
    },
    "issues": [
        {
            "rule": "image-alt",
            "severity": "critical",
            "element_html": "<img src='hero.jpg'>",
            "description": "Image does not have an alt attribute",
            "wcag_ref": "1.1.1",
        },
        {
            "rule": "color-contrast",
            "severity": "serious",
            "element_html": "<p>Low contrast text</p>",
            "description": "Text does not meet contrast requirements",
            "wcag_ref": "1.4.3",
        },
        {
            "rule": "landmark-one-main",
            "severity": "moderate",
            "element_html": "<body>",
            "description": "Document should contain one main landmark",
            "wcag_ref": None,
        },
    ],
}


# ---------------------------------------------------------
# Fixtures
# ---------------------------------------------------------

@pytest.fixture(autouse=True)
def reset_database() -> Generator[None, None, None]:
    """
    Create a fresh database before every test.
    """
    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)

    yield

    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    """
    Replace the application's PostgreSQL session with
    our temporary SQLite test database.
    """

    def override_get_db():
        db = TestingSessionLocal()

        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


@pytest.fixture
def db() -> Generator[Session, None, None]:
    session = TestingSessionLocal()

    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def successful_scan(monkeypatch):
    """
    Replace the real Playwright scanner with a predictable fake.
    """

    async def fake_scan_url(url: str):
        result = FAKE_SCAN_RESULT.copy()
        result["url"] = url
        return result

    monkeypatch.setattr(
        "accessflow.routers.audits.scan_url",
        fake_scan_url,
    )

    # Avoid DNS/network access during tests.
    monkeypatch.setattr(
        "accessflow.routers.audits.validate_public_url",
        lambda url: url,
    )


# ---------------------------------------------------------
# POST /audits
# ---------------------------------------------------------

def test_create_audit_successfully(
    client,
    db,
    successful_scan,
):
    response = client.post(
        "/audits",
        json={
            "url": "https://example.com",
        },
    )

    assert response.status_code == 201

    data = response.json()

    assert data["status"] == "completed"
    assert data["total_issues"] == 3
    assert data["critical"] == 1
    assert data["serious"] == 1
    assert data["moderate"] == 1
    assert data["minor"] == 0

    audit = db.get(Audit, data["id"])

    assert audit is not None
    assert audit.status == "completed"


def test_create_audit_saves_issues(
    client,
    db,
    successful_scan,
):
    response = client.post(
        "/audits",
        json={
            "url": "https://example.com",
        },
    )

    assert response.status_code == 201

    audit_id = response.json()["id"]

    issue_count = db.scalar(
        select(func.count(AccessibilityIssue.id)).where(
            AccessibilityIssue.audit_id == audit_id
        )
    )

    assert issue_count == 3


def test_same_website_is_reused(
    client,
    db,
    successful_scan,
):
    first = client.post(
        "/audits",
        json={"url": "https://example.com"},
    )

    second = client.post(
        "/audits",
        json={"url": "https://example.com"},
    )

    assert first.status_code == 201
    assert second.status_code == 201

    website_count = db.scalar(
        select(func.count(Website.id))
    )

    audit_count = db.scalar(
        select(func.count(Audit.id))
    )

    assert website_count == 1
    assert audit_count == 2


def test_failed_scan_is_saved(
    client,
    db,
    monkeypatch,
):
    async def fake_failed_scan(url: str):
        return {
            "status": "failed",
            "url": url,
            "error": "Page could not be reached",
        }

    monkeypatch.setattr(
        "accessflow.routers.audits.scan_url",
        fake_failed_scan,
    )

    monkeypatch.setattr(
        "accessflow.routers.audits.validate_public_url",
        lambda url: url,
    )

    response = client.post(
        "/audits",
        json={
            "url": "https://example.com",
        },
    )

    assert response.status_code == 201

    data = response.json()

    assert data["status"] == "failed"
    assert data["total_issues"] == 0

    audit = db.get(Audit, data["id"])

    assert audit is not None
    assert audit.status == "failed"


def test_localhost_url_is_blocked(
    client,
):
    response = client.post(
        "/audits",
        json={
            "url": "http://localhost:8000",
        },
    )

    assert response.status_code == 422


# ---------------------------------------------------------
# GET /audits/{id}
# ---------------------------------------------------------

def test_get_existing_audit(
    client,
    successful_scan,
):
    created = client.post(
        "/audits",
        json={
            "url": "https://example.com",
        },
    )

    audit_id = created.json()["id"]

    response = client.get(
        f"/audits/{audit_id}"
    )

    assert response.status_code == 200

    data = response.json()

    assert data["id"] == audit_id
    assert data["status"] == "completed"
    assert data["total_issues"] == 3


def test_get_missing_audit_returns_404(
    client,
):
    response = client.get(
        "/audits/99999"
    )

    assert response.status_code == 404


# ---------------------------------------------------------
# GET /audits/{id}/issues
# ---------------------------------------------------------

def test_get_audit_issues(
    client,
    successful_scan,
):
    created = client.post(
        "/audits",
        json={
            "url": "https://example.com",
        },
    )

    audit_id = created.json()["id"]

    response = client.get(
        f"/audits/{audit_id}/issues"
    )

    assert response.status_code == 200

    issues = response.json()

    assert len(issues) == 3

    assert {
        issue["severity"]
        for issue in issues
    } == {
        "critical",
        "serious",
        "moderate",
    }


def test_filter_issues_by_severity(
    client,
    successful_scan,
):
    created = client.post(
        "/audits",
        json={
            "url": "https://example.com",
        },
    )

    audit_id = created.json()["id"]

    response = client.get(
        f"/audits/{audit_id}/issues",
        params={
            "severity": "critical",
        },
    )

    assert response.status_code == 200

    issues = response.json()

    assert len(issues) == 1
    assert issues[0]["severity"] == "critical"
    assert issues[0]["rule"] == "image-alt"


def test_invalid_severity_returns_422(
    client,
    successful_scan,
):
    created = client.post(
        "/audits",
        json={
            "url": "https://example.com",
        },
    )

    audit_id = created.json()["id"]

    response = client.get(
        f"/audits/{audit_id}/issues",
        params={
            "severity": "extreme",
        },
    )

    assert response.status_code == 422


# ---------------------------------------------------------
# GET /audits
# ---------------------------------------------------------

def test_list_audits(
    client,
    successful_scan,
):
    client.post(
        "/audits",
        json={"url": "https://example.com"},
    )

    client.post(
        "/audits",
        json={"url": "https://example.com"},
    )

    response = client.get(
        "/audits"
    )

    assert response.status_code == 200

    audits = response.json()

    assert len(audits) == 2


def test_audit_pagination(
    client,
    successful_scan,
):
    for _ in range(3):
        client.post(
            "/audits",
            json={
                "url": "https://example.com",
            },
        )

    response = client.get(
        "/audits",
        params={
            "skip": 1,
            "limit": 1,
        },
    )

    assert response.status_code == 200

    audits = response.json()

    assert len(audits) == 1