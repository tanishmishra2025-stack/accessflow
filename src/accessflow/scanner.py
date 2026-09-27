"""
What this does:
1. Launches a headless Chromium browser via Playwright
2. Loads a test page (intentionally inaccessible, for testing)
3. Injects axe-core from a CDN and runs it in-page
4. Pulls the violations out and reshapes them to match our AccessibilityIssue
   schema (rule, severity, element_html, description, wcag_ref)
5. Prints a summary + the structured issues as JSON

Run it directly (not through the API) with:
    uv run python -m accessflow.scanner
"""

import asyncio
import json
import re
from typing import Any

from playwright.async_api import async_playwright

# W3C's own "Before" accessibility demo page — deliberately built with
# real accessibility problems, so it's a reliable page to test a scanner
# against. Swap this for any URL once you wire in dynamic input on Day 4.
TEST_URL = "https://www.w3.org/WAI/demos/bad/before/home.html"

AXE_CORE_CDN_URL = "https://cdn.jsdelivr.net/npm/axe-core@4.10.2/axe.min.js"


def _extract_wcag_ref(tags: list[str]) -> str | None:
    """
    axe-core tags look like ['wcag2a', 'wcag111', 'cat.text-alternatives'].
    Pull the first WCAG success-criterion-shaped tag (e.g. 'wcag111') and
    format it as '1.1.1'. Returns None if no such tag is present.
    """
    for tag in tags:
        match = re.fullmatch(r"wcag(\d)(\d)(\d+)", tag)
        if match:
            return ".".join(match.groups())
    return None


def _flatten_violations(axe_results: dict[str, Any]) -> list[dict[str, Any]]:
    """
    axe-core groups results by rule, and each rule can match multiple
    elements on the page ('nodes'). We flatten that into one row per
    element, matching our AccessibilityIssue table (one issue = one
    element-level violation), the same way it'll be stored later.
    """
    issues = []
    for violation in axe_results.get("violations", []):
        rule = violation["id"]
        severity = violation["impact"]  # already 'minor'/'moderate'/'serious'/'critical'
        description = violation["description"]
        wcag_ref = _extract_wcag_ref(violation.get("tags", []))

        for node in violation.get("nodes", []):
            issues.append({
                "rule": rule,
                "severity": severity,
                "element_html": node.get("html", ""),
                "description": description,
                "wcag_ref": wcag_ref,
            })
    return issues


def _summarize(issues: list[dict[str, Any]]) -> dict[str, int]:
    counts = {"critical": 0, "serious": 0, "moderate": 0, "minor": 0}
    for issue in issues:
        if issue["severity"] in counts:
            counts[issue["severity"]] += 1
    return {"total_issues": len(issues), **counts}


async def scan_url(url: str) -> dict[str, Any]:
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()

        try:
            await page.goto(
                url,
                wait_until="domcontentloaded",
                timeout=30000,
            )

            await page.add_script_tag(url=AXE_CORE_CDN_URL)

            axe_results = await page.evaluate(
                "async () => await axe.run()"
            )

        except Exception as exc:
            return {
                "status": "failed",
                "error": str(exc),
                "url": url,
            }

        finally:
            await browser.close()

    issues = _flatten_violations(axe_results)
    summary = _summarize(issues)

    return {
        "status": "completed",
        "url": url,
        "summary": summary,
        "issues": issues,
    }

async def main():
    print(f"Scanning: {TEST_URL}\n")
    result = await scan_url(TEST_URL)

    if result["status"] == "failed":
        print(f"Scan failed: {result['error']}")
        return

    print("Summary:", json.dumps(result["summary"], indent=2))
    print(f"\nFirst 3 of {len(result['issues'])} issues:")
    print(json.dumps(result["issues"][:3], indent=2))


if __name__ == "__main__":
    asyncio.run(main())