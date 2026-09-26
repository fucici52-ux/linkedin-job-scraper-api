import asyncio

import pytest

from job_scraper.config import Settings
from job_scraper import service


def make_settings() -> Settings:
    return Settings(source_timeout_seconds=0.05, source_attempts=1, source_concurrency=12)


@pytest.mark.asyncio
async def test_one_failed_source_preserves_other_results(monkeypatch) -> None:
    monkeypatch.setattr(service.jobspy, "SITES", ("indeed", "linkedin"))
    monkeypatch.setattr(service.ats, "ATS_SOURCES", ())

    def fake_search(site: str, keyword: str, location: str, limit: int):
        if site == "linkedin":
            raise RuntimeError("429")
        return [{"title": keyword, "company": "Acme", "location": location, "job_url": "https://example.com/job"}]

    monkeypatch.setattr(service.jobspy, "search", fake_search)
    jobs, stats, raw_count, unique_count = await service.collect_jobs(["AI Product Intern"], ["Vancouver"], 15, [], make_settings())
    assert len(jobs) == raw_count == unique_count == 1
    assert {stat.status for stat in stats} == {"ok", "failed"}


@pytest.mark.asyncio
async def test_all_twelve_keyword_location_pairs_are_dispatched(monkeypatch) -> None:
    monkeypatch.setattr(service.jobspy, "SITES", ("indeed",))
    monkeypatch.setattr(service.ats, "ATS_SOURCES", ())
    seen: set[tuple[str, str]] = set()

    def fake_search(site: str, keyword: str, location: str, limit: int):
        seen.add((keyword, location))
        return [{"title": keyword, "company": "Acme", "location": location, "job_url": f"https://example.com/{len(seen)}"}]

    monkeypatch.setattr(service.jobspy, "search", fake_search)
    keywords = ["AI Product Intern", "Product Operations Intern", "Business Analyst Intern", "Data Strategy Intern"]
    locations = ["Vancouver", "Toronto", "Remote Canada"]
    jobs, stats, _, _ = await service.collect_jobs(keywords, locations, 25, [], make_settings())
    assert seen == {(keyword, location) for keyword in keywords for location in locations}
    assert len(stats) == 12
    assert len(jobs) == 12


@pytest.mark.asyncio
async def test_each_ats_slice_is_loaded_once_for_all_combinations(monkeypatch) -> None:
    monkeypatch.setattr(service.jobspy, "SITES", ())
    monkeypatch.setattr(service.ats, "ATS_SOURCES", ("greenhouse", "lever"))
    calls: list[tuple[str, tuple[str, ...], tuple[str, ...]]] = []

    def fake_bulk(ats_name, keywords, locations, limit):
        calls.append((ats_name, tuple(keywords), tuple(locations)))
        return []

    monkeypatch.setattr(service.ats, "search_dataset_bulk", fake_bulk)
    keywords = ["AI Product Intern", "Business Analyst Intern"]
    locations = ["Vancouver", "Toronto", "Remote Canada"]
    await service.collect_jobs(keywords, locations, 15, [], make_settings())

    assert set(calls) == {
        ("greenhouse", tuple(keywords), tuple(locations)),
        ("lever", tuple(keywords), tuple(locations)),
    }


@pytest.mark.asyncio
async def test_timeout_is_reported_without_raising(monkeypatch) -> None:
    monkeypatch.setattr(service.jobspy, "SITES", ("indeed",))
    monkeypatch.setattr(service.ats, "ATS_SOURCES", ())

    def slow(*args, **kwargs):
        import time
        time.sleep(0.2)
        return []

    monkeypatch.setattr(service.jobspy, "search", slow)
    jobs, stats, _, _ = await service.collect_jobs(["Business Analyst Intern"], ["Toronto"], 15, [], make_settings())
    assert jobs == []
    assert stats[0].status == "failed"
    assert "TimeoutError" in (stats[0].error or "")
