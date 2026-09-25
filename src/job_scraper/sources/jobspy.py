from __future__ import annotations

from typing import Any

SITES = ("indeed", "google", "zip_recruiter", "linkedin")


def search(site: str, keyword: str, location: str, limit: int) -> list[dict[str, Any]]:
    from jobspy import scrape_jobs

    arguments: dict[str, Any] = {"site_name": [site], "search_term": keyword, "location": location, "results_wanted": limit, "verbose": 0}
    if site == "indeed":
        arguments["country_indeed"] = "canada"
    if site == "google":
        arguments["google_search_term"] = f"{keyword} jobs near {location}"
    frame = scrape_jobs(**arguments)
    return frame.where(frame.notna(), None).to_dict(orient="records")
