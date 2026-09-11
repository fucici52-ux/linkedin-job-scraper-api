from typing import Protocol

from job_scraper.models import JobListing


class JobSource(Protocol):
    """Contract that every job source must implement."""

    def search(self, keywords: str, location: str, limit: int) -> list[JobListing]: ...


