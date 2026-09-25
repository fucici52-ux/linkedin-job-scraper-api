import os
import uuid

import uvicorn
from fastapi import FastAPI, Header
from pydantic import BaseModel, Field, field_validator, model_validator

from job_scraper.config import settings
from job_scraper.models import JobListing, SourceStat
from job_scraper.service import collect_jobs

app = FastAPI(title="Job Retrieval API", version="0.2.0")


class JobRequest(BaseModel):
    keywords: list[str] = Field(min_length=1, max_length=4)
    location: str | None = Field(default=None, max_length=200)
    locations: list[str] = Field(default_factory=list, max_length=3)
    max_results: int = Field(default=15, ge=1, le=25)
    company_career_urls: list[str] = Field(default_factory=list, max_length=25)

    @field_validator("keywords")
    @classmethod
    def clean_keywords(cls, values: list[str]) -> list[str]:
        cleaned = list(dict.fromkeys(value.strip() for value in values if value.strip()))
        if not cleaned:
            raise ValueError("at least one non-empty keyword is required")
        return cleaned

    @model_validator(mode="after")
    def clean_locations(self) -> "JobRequest":
        values = [value.strip() for value in self.locations if value.strip()]
        if self.location and self.location.strip():
            values.append(self.location.strip())
        self.locations = list(dict.fromkeys(values))[:3]
        if not self.locations:
            raise ValueError("location or locations is required")
        return self


class JobResponse(BaseModel):
    jobs: list[JobListing]
    raw_job_count: int
    deduplicated_job_count: int
    source_stats: list[SourceStat]
    partial_failures: list[SourceStat]
    request_id: str


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/jobs", response_model=JobResponse)
async def get_jobs(request: JobRequest, x_request_id: str | None = Header(default=None)) -> JobResponse:
    request_id = (x_request_id or str(uuid.uuid4()))[:128]
    jobs, stats, raw_count, deduplicated_count = await collect_jobs(
        request.keywords,
        request.locations,
        request.max_results,
        request.company_career_urls,
        settings,
    )
    return JobResponse(
        jobs=jobs,
        raw_job_count=raw_count,
        deduplicated_job_count=deduplicated_count,
        source_stats=stats,
        partial_failures=[stat for stat in stats if stat.status == "failed"],
        request_id=request_id,
    )


def run() -> None:
    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run("job_scraper.api:app", host="0.0.0.0", port=port)
