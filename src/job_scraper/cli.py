import argparse
import json
import sys
from pathlib import Path

import httpx

from job_scraper.config import settings
from job_scraper.sources.linkedin_public import LinkedInPublicSource, PublicAccessStopped


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Collect public job listing metadata.")
    parser.add_argument("keywords", help='Job keywords, for example: "python developer"')
    parser.add_argument("location", help='Search location, for example: "Vancouver, BC"')
    parser.add_argument("--limit", type=int, default=10, help="Results to keep (default: 10)")
    parser.add_argument("--output", type=Path, help="JSON path (default: data/linkedin_jobs.json)")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    output_path = args.output or settings.output_dir / "linkedin_jobs.json"

    try:
        jobs = LinkedInPublicSource(settings).search(args.keywords, args.location, args.limit)
    except (PublicAccessStopped, httpx.HTTPError, ValueError) as error:
        print(f"Scrape stopped: {error}", file=sys.stderr)
        raise SystemExit(1) from error

    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = [job.model_dump(mode="json") for job in jobs]
    output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Saved {len(payload)} jobs to {output_path.resolve()}")


if __name__ == "__main__":
    main()

