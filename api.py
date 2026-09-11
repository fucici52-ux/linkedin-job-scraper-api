import os

import httpx
import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, field_validator

from job_scraper.config import settings
from job_scraper.models import JobListing
from job_scraper.service import collect_jobs
from job_scraper.sources.linkedin_public import LinkedInPublicSource, PublicAccessStopped

app = FastAPI(title="Job Scraper API", version="0.1.0")


class JobRequest(BaseModel):
    keywords: list[str] = Field(min_length=1, max_length=5)
    location: str = Field(min_length=1, max_length=200)
    max_results: int = Field(default=10, ge=1, le=25)

    @field_validator("keywords")
    @classmethod
    def clean_keywords(cls, values: list[str]) -> list[str]:
        cleaned = [value.strip() for value in values if value.strip()]
        if not cleaned:
            raise ValueError("at least one non-empty keyword is required")
        return cleaned


class JobResponse(BaseModel):
    jobs: list[JobListing]


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/jobs", response_model=JobResponse)
def get_jobs(request: JobRequest) -> JobResponse:
    try:
        jobs = collect_jobs(
            LinkedInPublicSource(settings),
            request.keywords,
            request.location.strip(),
            request.max_results,
        )
    except (PublicAccessStopped, httpx.HTTPError) as error:
        raise HTTPException(status_code=502, detail=f"Scrape stopped: {error}") from error

    return JobResponse(jobs=jobs)


def run() -> None:
    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run("job_scraper.api:app", host="0.0.0.0", port=port)
