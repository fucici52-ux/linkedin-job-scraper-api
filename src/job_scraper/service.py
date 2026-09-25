from __future__ import annotations

import asyncio
import logging
import random
from collections.abc import Callable
from time import monotonic
from typing import Any

from job_scraper.config import Settings
from job_scraper.models import JobListing, SourceStat
from job_scraper.normalize import deduplicate, normalize_ats, normalize_jobspy
from job_scraper.sources import ats, jobspy

log = logging.getLogger("job_scraper.retrieval")


async def _bounded_call(
    source: str,
    keyword: str,
    location: str,
    operation: Callable[[], list[dict[str, Any]]],
    settings: Settings,
) -> tuple[list[dict[str, Any]], SourceStat]:
    started = monotonic()
    last_error: Exception | None = None
    for attempt in range(1, settings.source_attempts + 1):
        try:
            rows = await asyncio.wait_for(asyncio.to_thread(operation), timeout=settings.source_timeout_seconds)
            latency = int((monotonic() - started) * 1000)
            log.info("source_complete source=%s attempt=%s rows=%s latency_ms=%s", source, attempt, len(rows), latency)
            return rows, SourceStat(source=source, keyword=keyword, location=location, status="ok", raw_jobs=len(rows), attempts=attempt, latency_ms=latency)
        except Exception as error:
            last_error = error
            log.warning("source_failed source=%s attempt=%s error_type=%s", source, attempt, type(error).__name__)
            if attempt < settings.source_attempts:
                await asyncio.sleep(min(2.0, 0.4 * (2 ** (attempt - 1))) + random.uniform(0, 0.25))
    latency = int((monotonic() - started) * 1000)
    message = f"{type(last_error).__name__}: {str(last_error)[:180]}" if last_error else "unknown error"
    return [], SourceStat(source=source, keyword=keyword, location=location, status="failed", attempts=settings.source_attempts, latency_ms=latency, error=message)


async def collect_jobs(
    keywords: list[str],
    locations: list[str],
    max_results: int,
    company_career_urls: list[str],
    settings: Settings,
) -> tuple[list[JobListing], list[SourceStat], int, int]:
    semaphore = asyncio.Semaphore(settings.source_concurrency)

    async def limited(*args: Any, **kwargs: Any) -> tuple[list[dict[str, Any]], SourceStat]:
        async with semaphore:
            return await _bounded_call(*args, **kwargs)

    tasks = []
    descriptors: list[tuple[str, str]] = []
    per_query_limit = max(3, min(10, max_results))
    for keyword in keywords:
        for location in locations:
            for site in jobspy.SITES:
                tasks.append(limited(f"jobspy:{site}", keyword, location, lambda s=site, k=keyword, loc=location: jobspy.search(s, k, loc, per_query_limit), settings))
                descriptors.append(("jobspy", site))
            for ats_name in ats.ATS_SOURCES:
                tasks.append(limited(f"ats:{ats_name}", keyword, location, lambda a=ats_name, k=keyword, loc=location: ats.search_dataset(a, k, loc, per_query_limit), settings))
                descriptors.append(("ats", ats_name))
    for url in company_career_urls:
        tasks.append(limited("ats:direct", "", "", lambda u=url: ats.search_company(u), settings))
        descriptors.append(("ats", "direct"))

    results = await asyncio.gather(*tasks)
    raw_jobs: list[JobListing] = []
    stats: list[SourceStat] = []
    for (rows, stat), (kind, source) in zip(results, descriptors, strict=True):
        stats.append(stat)
        normalizer = normalize_jobspy if kind == "jobspy" else normalize_ats
        raw_jobs.extend(job for row in rows if (job := normalizer(row, source)) is not None)
    unique_jobs = deduplicate(raw_jobs)
    return unique_jobs[:max_results], stats, len(raw_jobs), len(unique_jobs)
