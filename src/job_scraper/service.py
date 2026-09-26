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
            timeout = settings.ats_timeout_seconds if source.startswith("ats:") else settings.source_timeout_seconds
            rows = await asyncio.wait_for(asyncio.to_thread(operation), timeout=timeout)
            latency = int((monotonic() - started) * 1000)
            log.info("source_complete source=%s attempt=%s rows=%s latency_ms=%s", source, attempt, len(rows), latency)
            return rows, SourceStat(source=source, keyword=keyword, location=location, status="ok", raw_jobs=len(rows), attempts=attempt, latency_ms=latency)
        except Exception as error:
            last_error = error
            log.warning("source_failed source=%s attempt=%s error_type=%s", source, attempt, type(error).__name__)
            # asyncio.to_thread cannot stop the underlying blocking scraper.
            # Starting another copy after our deadline only leaves more work
            # running in the background and makes the whole request less stable.
            if isinstance(error, TimeoutError):
                break
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
    # Keep every board independent: a blocked/slow board must not discard rows
    # already returned by another board for the same keyword/location pair.
    per_query_limit = min(3, max_results)
    for keyword in keywords:
        for location in locations:
            for site in jobspy.SITES:
                tasks.append(
                    limited(
                        f"jobspy:{site}",
                        keyword,
                        location,
                        lambda s=site, k=keyword, loc=location: jobspy.search(
                            s, k, loc, per_query_limit
                        ),
                        settings,
                    )
                )
                descriptors.append(("jobspy", site))
    # The hosted ATS dataset is partitioned by ATS. Download each slice once,
    # then deterministically apply every keyword-location combination locally.
    if settings.enable_ats_dataset:
        for ats_name in ats.ATS_SOURCES:
            tasks.append(
                limited(
                    f"ats:{ats_name}",
                    " | ".join(keywords),
                    " | ".join(locations),
                    lambda a=ats_name: ats.search_dataset_bulk(
                        a, keywords, locations, per_query_limit
                    ),
                    settings,
                )
            )
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
