from __future__ import annotations

from typing import Any

ATS_SOURCES = ("greenhouse", "lever", "ashby", "workday", "smartrecruiters")


def search_dataset(ats: str, keyword: str, location: str, limit: int) -> list[dict[str, Any]]:
    from ats_scrapers import search

    frame = search(query=keyword, location=location, ats=ats, limit=limit)
    return frame.where(frame.notna(), None).to_dict(orient="records")


def search_company(url: str) -> list[dict[str, Any]]:
    from ats_scrapers import get_scraper_for_url

    jobs = get_scraper_for_url(url).fetch()
    return [job.model_dump(mode="json") if hasattr(job, "model_dump") else dict(job) for job in jobs]
