from __future__ import annotations

from typing import Any

SITES = ("indeed", "google", "zip_recruiter", "linkedin")


def warmup() -> None:
    """Load JobSpy and pandas once during process startup, not in user requests."""
    from jobspy import scrape_jobs  # noqa: F401


def search(site: str, keyword: str, location: str, limit: int) -> list[dict[str, Any]]:
    from jobspy import scrape_jobs

    arguments: dict[str, Any] = {"site_name": [site], "search_term": keyword, "location": location, "results_wanted": limit, "verbose": 0}
    if site == "indeed":
        arguments["country_indeed"] = "canada"
    if site == "google":
        arguments["google_search_term"] = f"{keyword} jobs near {location}"
    frame = scrape_jobs(**arguments)
    return frame.where(frame.notna(), None).to_dict(orient="records")


def search_many(sites: tuple[str, ...], keyword: str, location: str, limit: int) -> list[dict[str, Any]]:
    """Let JobSpy query its supported boards in one bounded operation."""
    from jobspy import scrape_jobs

    arguments: dict[str, Any] = {
        "site_name": list(sites),
        "search_term": keyword,
        "location": location,
        "results_wanted": limit,
        "country_indeed": "canada",
        "google_search_term": f"{keyword} jobs near {location}",
        "verbose": 0,
    }
    frame = scrape_jobs(**arguments)
    return frame.where(frame.notna(), None).to_dict(orient="records")
