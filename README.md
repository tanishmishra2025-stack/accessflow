# AccessFlow

AccessFlow is a backend accessibility auditing service built with FastAPI, PostgreSQL, SQLAlchemy, Alembic, Playwright, and axe-core.

It accepts a website URL, launches a headless Chromium browser, runs automated accessibility checks with axe-core, stores structured results in PostgreSQL, and exposes audit history through REST API endpoints.

AccessFlow is designed as a backend engineering project focused on API design, database modeling, browser automation, persistence, security-aware URL handling, and testable service architecture.

---

## Features

- FastAPI REST API
- PostgreSQL persistence
- SQLAlchemy ORM models
- Alembic database migrations
- Playwright headless Chromium scanning
- axe-core accessibility analysis
- Structured WCAG-related issue storage
- Audit history
- Severity filtering
- Pagination
- Failed-scan persistence
- SSRF-oriented URL validation
- Automated API tests

---

## Architecture

```text
Client
  |
  v
FastAPI
  |
  v
POST /audits
  |
  +--> URL validation
  |
  +--> Website lookup / creation
  |
  +--> Audit creation
  |
  v
scanner.py
  |
  v
Playwright
  |
  v
Headless Chromium
  |
  v
axe-core
  |
  v
Normalized accessibility issues
  |
  v
SQLAlchemy
  |
  +--> Website
  +--> Audit
  +--> AccessibilityIssue
  |
  v
PostgreSQL