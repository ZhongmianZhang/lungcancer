#!/usr/bin/env python3
"""Exercise the generated offline report in Chromium; requires Playwright.

This optional browser check is deliberately not named ``test_*.py`` so that
standard-library test discovery does not acquire a browser dependency.
The report is loaded with set_content: managed Chromium can prohibit file URLs.
"""

from __future__ import annotations

import argparse
from collections import Counter
from html.parser import HTMLParser
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


class ReportDataParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=False)
        self.reading = False
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "script" and dict(attrs).get("id") == "report-data":
            self.reading = True

    def handle_endtag(self, tag: str) -> None:
        if tag == "script":
            self.reading = False

    def handle_data(self, data: str) -> None:
        if self.reading:
            self.parts.append(data)


def expect(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def is_verified(reference: dict[str, Any]) -> bool:
    value = str(reference.get("verification", "")).lower()
    return value in {
        "metadata_verified", "abstract_verified", "fulltext_verified",
        "verified_metadata", "verified_abstract", "verified_fulltext",
    }


def check_report(report: Path, browser_path: Path) -> dict[str, Any]:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as error:
        raise RuntimeError("Playwright is not installed; browser smoke checks did not run") from error

    contents = report.read_text(encoding="utf-8")
    parser = ReportDataParser()
    parser.feed(contents)
    data = json.loads("".join(parser.parts))
    references = data["references"]
    mechanisms = data["mechanisms"]
    loops = data.get("overview", {}).get("crosstalk", [])
    expect(bool(references) and bool(mechanisms), "The report contains no references or mechanisms")
    if not browser_path.is_file():
        raise RuntimeError("Chromium executable is missing: " + str(browser_path))

    result: dict[str, Any] = {
        "status": "running", "report": str(report), "browser": str(browser_path),
        "load_method": "set_content", "offline": True,
        "data_counts": {"references": len(references), "mechanisms": len(mechanisms), "crosstalk": len(loops)},
        "checks": [], "page_errors": [], "external_requests": [],
    }

    def passed(name: str) -> None:
        result["checks"].append(name)

    def attach(page: Any) -> None:
        page.on("pageerror", lambda error: result["page_errors"].append(str(error)))
        page.on("request", lambda request: result["external_requests"].append(request.url)
                if request.url.startswith(("http://", "https://")) else None)

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(
                executable_path=str(browser_path), headless=True, args=["--no-sandbox"])
            try:
                context = browser.new_context(viewport={"width": 1440, "height": 1050}, offline=True)
                context.set_default_timeout(10_000)
                page = context.new_page()
                attach(page)
                page.set_content(contents, wait_until="domcontentloaded", timeout=15_000)
                page.wait_for_selector(".mechanism-card")

                def mechanism_count() -> int:
                    return page.locator(".mechanism-card").count()

                def reference_count() -> int:
                    return page.locator('#reference-table-body tr[id^="ref-"]').count()

                expect(mechanism_count() == len(mechanisms), "Initial mechanism count differs from embedded data")
                expect(reference_count() == len(references), "Initial reference count differs from embedded data")
                expect(page.locator(".crosstalk-card").count() == len(loops), "Feedback-loop count differs from data")
                expect(page.locator("#static-report").is_hidden(), "Static fallback was not hidden after successful rendering")
                passed("initial_dynamic_counts_and_fallback")

                page.locator("#report-search").fill(str(mechanisms[0]["title"]))
                expect(0 < mechanism_count() <= len(mechanisms), "Full-text search did not retain the matching mechanism")
                page.locator("#clear-filters").click()
                expect(mechanism_count() == len(mechanisms), "Clearing search did not restore all mechanisms")
                passed("full_text_search_and_clear")

                categories = Counter(m["category"] for m in mechanisms)
                category = min(categories, key=categories.get)
                page.locator("#category-filter").select_option(category)
                expect(mechanism_count() == categories[category], "Category filter returned an incorrect mechanism count")
                page.locator("#clear-filters").click()
                passed("category_filter")

                years = Counter(str(ref["year"]) for ref in references if ref.get("year"))
                year = min(years, key=years.get)
                page.locator("#year-filter").select_option(year)
                expect(reference_count() == years[year], "Year filter returned an incorrect reference count")
                page.locator("#year-filter").select_option("")
                scopes = Counter(ref["evidence_scope"] for ref in references)
                scope = min(scopes, key=scopes.get)
                page.locator("#evidence-filter").select_option(scope)
                expect(reference_count() == scopes[scope], "Evidence filter returned an incorrect reference count")
                page.locator("#evidence-filter").select_option("")
                passed("year_and_evidence_filters")

                expected_verified = sum(is_verified(ref) for ref in references)
                page.locator("#verified-only").check()
                expect(reference_count() == expected_verified, "Verified-only filtering differs from reference metadata")
                if expected_verified == 0:
                    expect(page.locator("#reference-table-body .empty-state").count() == 1,
                           "Zero verified references did not produce an explicit empty state")
                page.locator("#verified-only").uncheck()
                passed("verified_only_filter_and_empty_state")

                page.locator("#graph-select").select_option(str(mechanisms[0]["id"]))
                expect(page.locator(".graph-node").count() > 0, "Selected mechanism has no graph nodes")
                page.locator(".graph-node").first.click()
                expect(page.locator("#node-filter").is_visible(), "Graph node selection did not activate its filter")
                expect(0 < mechanism_count() <= len(mechanisms), "Graph node selection produced no related mechanisms")
                page.locator("#node-filter").click()
                expect(mechanism_count() == len(mechanisms), "Clearing the node filter did not restore mechanisms")
                passed("graph_selection_and_node_filter")

                page.locator("#expand-all").click()
                expect(page.locator(".mechanism-body[open]").count() == len(mechanisms),
                       "Expand-all did not open every mechanism")
                page.locator("#report-search").fill(str(mechanisms[0]["title"]))
                page.locator("#year-filter").select_option(year)
                page.locator("#evidence-filter").select_option(scope)
                page.locator("#verified-only").check()
                page.locator(".citation-link").first.click()
                expect(page.locator("#report-search").input_value() == "", "Citation did not clear global search")
                expect(page.locator("#year-filter").input_value() == "", "Citation did not clear year filtering")
                expect(page.locator("#evidence-filter").input_value() == "", "Citation did not clear evidence filtering")
                expect(not page.locator("#verified-only").is_checked(), "Citation did not clear verified-only filtering")
                expect(reference_count() == len(references), "Citation did not restore the full reference table")
                expect(page.evaluate("location.hash").startswith("#ref-"), "Citation did not navigate to a reference anchor")
                target = page.evaluate("decodeURIComponent(location.hash.slice(1))")
                expect(page.locator('[id="' + target + '"]').count() == 1, "Citation target is missing")
                passed("expand_details_and_citation_clears_filters")

                mobile_context = browser.new_context(viewport={"width": 390, "height": 844}, offline=True)
                mobile_context.set_default_timeout(10_000)
                mobile = mobile_context.new_page()
                attach(mobile)
                mobile.set_content(contents, wait_until="domcontentloaded", timeout=15_000)
                expect(mobile.locator(".mechanism-card").count() == len(mechanisms), "Mobile rendering is incomplete")
                expect(mobile.evaluate("document.documentElement.scrollWidth <= window.innerWidth"),
                       "The 390px mobile layout overflows the page horizontally")
                passed("mobile_390px_no_page_overflow")

                static_context = browser.new_context(java_script_enabled=False,
                    viewport={"width": 1200, "height": 800}, offline=True)
                static_context.set_default_timeout(10_000)
                static = static_context.new_page()
                attach(static)
                static.set_content(contents, wait_until="domcontentloaded", timeout=15_000)
                expect(static.locator("#static-report").is_visible(), "No-JavaScript static fallback is hidden")
                for mechanism in mechanisms:
                    expect(static.locator('[id="static-' + mechanism["id"] + '"]').count() == 1,
                           "Static fallback is missing mechanism " + mechanism["id"])
                for reference in references:
                    expect(static.locator('[id="static-ref-' + reference["id"] + '"]').count() == 1,
                           "Static fallback is missing reference " + reference["id"])
                passed("no_javascript_full_static_content")

                expect(not result["page_errors"], "Browser JavaScript errors: " + json.dumps(result["page_errors"]))
                expect(not result["external_requests"], "Report attempted external HTTP requests: "
                       + json.dumps(result["external_requests"]))
                passed("no_javascript_errors_or_external_requests")
            finally:
                browser.close()
    except Exception as error:
        result.update(status="failed", error=type(error).__name__ + ": " + str(error))
        return result
    result["status"] = "passed"
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, default=ROOT / "reports/egfr_tme_resistance.html")
    parser.add_argument("--browser", type=Path, default=Path("/usr/bin/chromium"))
    args = parser.parse_args()
    try:
        result = check_report(args.report.resolve(), args.browser.resolve())
    except Exception as error:
        print(json.dumps({"status": "error", "error": type(error).__name__ + ": " + str(error),
                          "report": str(args.report)}, ensure_ascii=False))
        return 2
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    sys.exit(main())
