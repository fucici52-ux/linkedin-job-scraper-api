from __future__ import annotations

import math
import re
from datetime import date, datetime
from typing import Any, Iterable
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from job_scraper.models import JobListing


TRACKING_PARAMETERS = {"ref", "refid", "trackingid", "trk", "source", "src"}


def text(value: Any) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return ""
    return str(value).strip()


def canonical_url(value: Any) -> str:
    raw = text(value)
    if not raw:
        return ""
    try:
        parts = urlsplit(raw)
        if parts.scheme not in {"http", "https"} or not parts.netloc:
            return ""
        query = urlencode([
            (key, val) for key, val in parse_qsl(parts.query, keep_blank_values=True)
            if key.lower() not in TRACKING_PARAMETERS and not key.lower().startswith("utm_")
        ])
        return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path.rstrip("/"), query, ""))
    except ValueError:
        return ""


def location_text(value: Any) -> str:
    if isinstance(value, dict):
        return ", ".join(text(value.get(key)) for key in ("city", "state", "country") if text(value.get(key)))
    return text(value)


def posted_date(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(text(value)[:10])
    except ValueError:
        return None


def normalize_jobspy(row: dict[str, Any], source: str) -> JobListing | None:
    url = canonical_url(row.get("job_url") or row.get("job_url_direct"))
    title, company = text(row.get("title")), text(row.get("company"))
    if not (url and title and company):
        return None
    return JobListing(title=title, company=company, location=location_text(row.get("location")), description=text(row.get("description")), job_url=url, posted_date=posted_date(row.get("date_posted")), source=source)


def normalize_ats(row: dict[str, Any], source: str) -> JobListing | None:
    url = canonical_url(row.get("apply_url") or row.get("url"))
    title, company = text(row.get("title")), text(row.get("company"))
    if not (url and title and company):
        return None
    return JobListing(title=title, company=company, location=location_text(row.get("location")), description=text(row.get("description")), job_url=url, posted_date=posted_date(row.get("posted_at")), source=source)


def deduplicate(jobs: Iterable[JobListing]) -> list[JobListing]:
    seen_urls: set[str] = set()
    seen_fallbacks: set[str] = set()
    output: list[JobListing] = []
    for job in jobs:
        url_key = canonical_url(job.job_url).lower()
        fallback = "|".join(re.sub(r"\W+", " ", value.lower()).strip() for value in (job.title, job.company, job.location))
        if (url_key and url_key in seen_urls) or fallback in seen_fallbacks:
            continue
        if url_key:
            seen_urls.add(url_key)
        seen_fallbacks.add(fallback)
        output.append(job)
    return output
