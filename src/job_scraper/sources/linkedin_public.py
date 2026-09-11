from datetime import date
from time import monotonic, sleep
from urllib.parse import urljoin, urlsplit, urlunsplit

import httpx
from bs4 import BeautifulSoup, Tag

from job_scraper.config import Settings
from job_scraper.models import JobListing


class PublicAccessStopped(RuntimeError):
    """Raised when LinkedIn does not provide an ordinary public response."""


class LinkedInPublicSource:
    """Parse job cards from LinkedIn's public, logged-out search page."""

    search_url = "https://www.linkedin.com/jobs/search/"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._last_request_at: float | None = None

    def search(self, keywords: str, location: str, limit: int) -> list[JobListing]:
        if not 1 <= limit <= self.settings.max_results:
            raise ValueError(f"limit must be between 1 and {self.settings.max_results}")

        response = self._get_without_cookies(
            self.search_url,
            params={"keywords": keywords, "location": location},
        )
        self._ensure_public_response(response)
        jobs = self.parse_html(response.text)[:limit]

        for job in jobs:
            detail_response = self._get_without_cookies(str(job.job_url))
            self._ensure_public_response(detail_response)
            job.description = self.parse_description(detail_response.text)

        return jobs

    def _get_without_cookies(
        self, url: str, params: dict[str, str] | None = None
    ) -> httpx.Response:
        """Follow ordinary redirects without carrying cookies between requests."""
        headers = {
            "Accept": "text/html,application/xhtml+xml",
            "User-Agent": self.settings.user_agent,
        }
        current_url = url
        current_params = params

        for _ in range(4):
            if self._last_request_at is not None:
                elapsed = monotonic() - self._last_request_at
                sleep(max(0.0, self.settings.request_delay_seconds - elapsed))
            response = httpx.get(
                current_url,
                params=current_params,
                headers=headers,
                follow_redirects=False,
                timeout=self.settings.request_timeout_seconds,
            )
            self._last_request_at = monotonic()
            if response.status_code not in {301, 302, 303, 307, 308}:
                return response

            location = response.headers.get("location")
            if not location:
                return response
            current_url = urljoin(str(response.url), location)
            current_params = None
            if not self._is_linkedin_url(current_url):
                raise PublicAccessStopped("LinkedIn redirected outside linkedin.com; stopping.")

        raise PublicAccessStopped("LinkedIn returned too many redirects; stopping.")

    @staticmethod
    def _is_linkedin_url(url: str) -> bool:
        hostname = (urlsplit(url).hostname or "").lower()
        return hostname == "linkedin.com" or hostname.endswith(".linkedin.com")

    @staticmethod
    def _ensure_public_response(response: httpx.Response) -> None:
        if response.status_code in {401, 403, 429}:
            raise PublicAccessStopped(
                f"LinkedIn returned HTTP {response.status_code}; stopping without retrying."
            )
        response.raise_for_status()

        final_path = response.url.path.lower()
        page = BeautifulSoup(response.text, "lxml")
        challenge_form = page.select_one(
            'form[action*="challenge"], form[action*="captcha"], .g-recaptcha'
        )
        if "/login" in final_path or "/authwall" in final_path or challenge_form:
            raise PublicAccessStopped(
                "LinkedIn presented a login wall or CAPTCHA; stopping without bypassing it."
            )

    @classmethod
    def parse_html(cls, html: str) -> list[JobListing]:
        soup = BeautifulSoup(html, "lxml")
        jobs: list[JobListing] = []

        for card in soup.select("div.base-card"):
            title = cls._text(card, ".base-search-card__title")
            company = cls._text(card, ".base-search-card__subtitle")
            location = cls._text(card, ".job-search-card__location")
            link = card.select_one("a.base-card__full-link")
            href = link.get("href") if isinstance(link, Tag) else None

            if not all((title, company, location, href)) or not isinstance(href, str):
                continue

            time_element = card.select_one("time[datetime]")
            raw_date = time_element.get("datetime") if isinstance(time_element, Tag) else None

            jobs.append(
                JobListing(
                    title=title,
                    company=company,
                    location=location,
                    job_url=cls._without_tracking(href),
                    posted_date=cls._parse_date(raw_date),
                )
            )

        return jobs

    @staticmethod
    def parse_description(html: str) -> str:
        page = BeautifulSoup(html, "lxml")
        description = page.select_one(".show-more-less-html__markup")
        if not description:
            return ""
        return " ".join(description.get_text(" ", strip=True).split())

    @staticmethod
    def _text(card: Tag, selector: str) -> str:
        element = card.select_one(selector)
        return element.get_text(" ", strip=True) if element else ""

    @staticmethod
    def _without_tracking(url: str) -> str:
        parts = urlsplit(url)
        return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))

    @staticmethod
    def _parse_date(value: object) -> date | None:
        if not isinstance(value, str):
            return None
        try:
            return date.fromisoformat(value[:10])
        except ValueError:
            return None

