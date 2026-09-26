from __future__ import annotations

from typing import Any

ATS_SOURCES = ("greenhouse", "lever", "ashby", "workday", "smartrecruiters")


def search_dataset(ats: str, keyword: str, location: str, limit: int) -> list[dict[str, Any]]:
    from ats_scrapers import search

    frame = search(query=keyword, location=location, ats=ats, limit=limit)
    return frame.where(frame.notna(), None).to_dict(orient="records")


def search_dataset_bulk(
    ats: str,
    keywords: list[str],
    locations: list[str],
    limit_per_query: int,
) -> list[dict[str, Any]]:
    """Download one ATS slice once, then expand keyword x location locally."""
    from ats_scrapers import Client

    frame = Client(prefer_parquet=False).load(ats=ats)
    matches = []
    for keyword in keywords:
        keyword_rows = frame[
            frame["title"].fillna("").str.contains(keyword, case=False, regex=False)
        ]
        for location in locations:
            location_value = location.strip().lower()
            if location_value.startswith("remote"):
                selected = keyword_rows[
                    keyword_rows["location"]
                    .fillna("")
                    .str.contains("remote", case=False, regex=False)
                ]
            else:
                selected = keyword_rows[
                    keyword_rows["location"]
                    .fillna("")
                    .str.contains(location, case=False, regex=False)
                ]
            matches.append(selected.head(limit_per_query))
    if not matches:
        return []
    import pandas as pd

    combined = pd.concat(matches, ignore_index=True).drop_duplicates()
    return combined.where(combined.notna(), None).to_dict(orient="records")


def search_company(url: str) -> list[dict[str, Any]]:
    from ats_scrapers import get_scraper_for_url

    jobs = get_scraper_for_url(url).fetch()
    return [job.model_dump(mode="json") if hasattr(job, "model_dump") else dict(job) for job in jobs]
