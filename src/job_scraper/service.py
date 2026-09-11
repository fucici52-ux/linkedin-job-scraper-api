from job_scraper.models import JobListing
from job_scraper.sources.base import JobSource


def collect_jobs(
    source: JobSource,
    keywords: list[str],
    location: str,
    max_results: int,
) -> list[JobListing]:
    """Collect across keywords, de-duplicate by canonical URL, and enforce a total limit."""
    jobs: list[JobListing] = []
    seen_urls: set[str] = set()

    for index, keyword in enumerate(keywords):
        remaining = max_results - len(jobs)
        if remaining == 0:
            break
        keywords_left = len(keywords) - index
        per_keyword_limit = max(1, (remaining + keywords_left - 1) // keywords_left)
        for job in source.search(keyword, location, per_keyword_limit):
            key = str(job.job_url)
            if key not in seen_urls:
                seen_urls.add(key)
                jobs.append(job)
                if len(jobs) == max_results:
                    break

    return jobs

