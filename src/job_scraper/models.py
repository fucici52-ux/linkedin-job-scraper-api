from datetime import date

from pydantic import BaseModel, HttpUrl


class JobListing(BaseModel):
    """Source-independent representation of one job listing."""

    title: str
    company: str
    location: str
    description: str = ""
    job_url: HttpUrl
    posted_date: date | None = None
    source: str = "unknown"


class SourceStat(BaseModel):
    source: str
    keyword: str
    location: str
    status: str
    raw_jobs: int = 0
    attempts: int = 1
    latency_ms: int = 0
    error: str | None = None

