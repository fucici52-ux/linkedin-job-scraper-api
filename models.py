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
