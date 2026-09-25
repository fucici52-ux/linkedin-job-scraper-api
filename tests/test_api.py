from fastapi.testclient import TestClient

from job_scraper import api
from job_scraper.models import JobListing, SourceStat


def test_legacy_location_request_and_response_contract(monkeypatch) -> None:
    async def fake_collect(*args, **kwargs):
        job = JobListing(title="Product Operations Intern", company="Acme", location="Vancouver", job_url="https://example.com/apply", source="greenhouse")
        stat = SourceStat(source="ats:greenhouse", keyword="Product Operations Intern", location="Vancouver", status="ok", raw_jobs=1)
        return [job], [stat], 1, 1

    monkeypatch.setattr(api, "collect_jobs", fake_collect)
    response = TestClient(api.app).post("/api/jobs", json={"keywords": ["Product Operations Intern"], "location": "Vancouver", "max_results": 15})
    assert response.status_code == 200
    body = response.json()
    assert body["jobs"][0]["job_url"] == "https://example.com/apply"
    assert body["raw_job_count"] == body["deduplicated_job_count"] == 1


def test_rejects_more_than_four_keywords() -> None:
    response = TestClient(api.app).post("/api/jobs", json={"keywords": ["a", "b", "c", "d", "e"], "location": "Vancouver"})
    assert response.status_code == 422
