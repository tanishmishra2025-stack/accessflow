# AccessFlow

![CI](https://github.com/tanishmishra2025-stack/accessflow/actions/workflows/ci.yml/badge.svg)

**AccessFlow is a backend service that scans a website for common accessibility
problems, stores the findings, and serves them through a REST API.**

It does not certify WCAG compliance — see [Limitations](#limitations).
## Why this exists
Automated accessibility tools can identify issues such as missing alt text, unlabeled form controls, invalid ARIA usage, missing document language, and insufficient color contrast.

However, those findings are often presented as one-off browser reports with no persistent history and no API for querying past results.

AccessFlow turns an accessibility scan into a persistent backend workflow:
```text
Submit URL
    ↓
Run browser-based accessibility scan
    ↓
Normalize axe-core findings
    ↓
Persist structured results
    ↓
Query current and historical audits
```
## Architecture

```
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
```
## At a higher level
```
Client
   |
   v
FastAPI
   |
   +-------------------+
   |                   |
   v                   v
Scanner Engine      PostgreSQL
Playwright          Website
Chromium            Audit
axe-core            AccessibilityIssue
```
- **FastAPI** — routing, request validation (Pydantic)
- **Playwright** — headless-browser page loading (handles JS-rendered sites)
- **axe-core** — accessibility rules engine, injected and run in-page
- **PostgreSQL + SQLAlchemy** — persistence
- **Alembic** — schema migrations
- **Docker Compose** — local API + database

## Data model

```
Website (id, url, first_seen_at)
   │
   └── Audit (id, website_id, url, scanned_at, status,
       │      total_issues, critical, serious, moderate, minor)
       │
       └── AccessibilityIssue (id, audit_id, rule, severity,
                                element_html, description, wcag_ref)
```

A `Website` is reused across scans of the same URL, so `GET /audits?url=...`
gives you that site's audit history over time.

## Run it

```bash
docker compose up --build
```
Then visit `http://localhost:8000/docs` for the interactive API explorer.
## API

| Endpoint | Method | Purpose |
|---|---|---|
| `/audits` | `POST` | Submit a URL, run a scan, store the result |
| `/audits` | `GET` | List past audits (`skip`, `limit`, optional `url` filter) |
| `/audits/{id}` | `GET` | Get one audit's summary |
| `/audits/{id}/issues` | `GET` | Get that audit's issues (optional `severity` filter) |

`POST /audits` is synchronous — the request blocks until the scan finishes.
That's a deliberate v1 simplification; see [What's next](#whats-next).

### Example Request

`POST /audits`

```json
{
  "url": "https://www.w3.org/WAI/demos/bad/before/home.html"
}
```

Response (`201`) — real output from a live run against this URL:
```json
{
  "id": 1,
  "website_id": 1,
  "url": "https://www.w3.org/WAI/demos/bad/before/home.html",
  "scanned_at": "2026-09-28T13:50:25.658613Z",
  "status": "completed",
  "total_issues": 67,
  "critical": 34,
  "serious": 10,
  "moderate": 23,
  "minor": 0
}
```

A failed scan (unreachable URL, timeout, or a crash inside the scanner) is
still saved as an `Audit` row with `status: "failed"` instead of raising an
error — the failure itself is part of the history.

### What it detects

axe-core's rule set, including (not exhaustive): missing image alt text,
unlabeled form inputs, missing document language, invalid ARIA attributes,
unnamed form controls (e.g. a `<select>` with no accessible name), and
insufficient color contrast.

Note on the numbers above: the 34 "critical" issues here are mostly one
repeated rule (`image-alt`) firing on many small decorative/spacer images
reused across the page layout, not 34 unrelated bugs. Reading a tool's own
output critically, rather than just reporting the total, matters as much as
running the scan.

## Security

`POST /audits` triggers a real browser to visit whatever URL is submitted.
Without a check, that's a server-side request forgery (SSRF) risk — someone
could submit an internal address (`localhost`, `169.254.169.254`, etc.) and
use this service to probe a network it can reach, but they can't. URLs are
validated before the browser ever loads them; requests targeting private or
internal addresses are rejected with a `422`.

**Known limitation:** this check resolves the hostname once, before the
scan. A hostname that resolves to a public address at validation time and a
private one moment later (DNS rebinding), or a public page that redirects
to an internal address mid-scan, isn't caught by this check alone. Fully
closing that gap needs request interception inside the browser itself.

## Testing

```bash
uv run pytest -v
```

12 tests, covering: successful scan → stored audit + issues, website reuse
across repeat scans, failed scans being saved (not raised), blocked/unsafe
URLs, 404s on missing audits, severity filtering (valid and invalid), and
pagination.

## Limitations

- **This does not certify WCAG compliance.** Automated tools like axe-core
  catch a meaningful subset of accessibility issues — things like whether
  alt text is *meaningful*, reading order is logical, or a keyboard trap
  exists still require human review.
- Scans a single URL per request — no full-site crawling yet.
- `POST /audits` is synchronous; a slow-loading site makes the request wait.
- The SSRF check has the DNS-rebinding/redirect gap noted above.

## What's next

- Async scanning: `POST /audits` returns `202 Accepted` immediately, client
  polls `/audits/{id}` for status (`pending` → `running` → `completed`)
- Full-site crawling instead of a single URL
- AI-assisted remediation suggestions per violation