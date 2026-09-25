from job_scraper.models import JobListing
from job_scraper.normalize import canonical_url, deduplicate, normalize_ats, normalize_jobspy


def test_normalizers_preserve_existing_job_contract() -> None:
    jobspy_job = normalize_jobspy({"title": "Business Analyst Intern", "company": "Acme", "location": "Toronto", "job_url": "https://example.com/1"}, "indeed")
    ats_job = normalize_ats({"title": "AI Product Intern", "company": "Example", "location": "Vancouver", "apply_url": "https://example.com/2"}, "greenhouse")
    assert jobspy_job and ats_job
    assert str(jobspy_job.job_url) == "https://example.com/1"
    assert ats_job.source == "greenhouse"


def test_url_and_fallback_deduplication() -> None:
    first = JobListing(title="AI Product Intern", company="Acme", location="Vancouver", job_url="https://example.com/job?utm_source=a", source="indeed")
    same_url = first.model_copy(update={"job_url": "https://example.com/job?utm_source=b", "source": "google"})
    same_identity = first.model_copy(update={"job_url": "https://other.example/job", "source": "greenhouse"})
    assert deduplicate([first, same_url, same_identity]) == [first]
    assert canonical_url(first.job_url) == "https://example.com/job"
