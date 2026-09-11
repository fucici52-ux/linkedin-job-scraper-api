# Job Scraper

A deliberately small Python experiment that collects metadata from LinkedIn's publicly
accessible, logged-out job search page and writes normalized JSON. It does not sign in,
use private APIs, rotate identities, solve CAPTCHAs, or retry access-control responses.

## Architecture

```text
CLI / HTTP API -> collection service -> JobSource contract -> LinkedInPublicSource
                                      -> JobListing model -> JSON response/file
```

- `models.py` defines the source-independent output shape.
- `sources/base.py` defines the contract future sources should follow.
- `sources/linkedin_public.py` owns all LinkedIn-specific HTTP and HTML parsing logic.
- `service.py` combines keyword searches and removes duplicate URLs.
- `api.py` validates n8n requests and returns the normalized response.
- `cli.py` handles user input and file output, without knowing LinkedIn's HTML structure.

To add another source later, create another module under `sources/` that returns a list of
`JobListing` objects.

## Setup

From PowerShell:

```powershell
cd work/job-scraper
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
Copy-Item .env.example .env
```

If PowerShell blocks activation, the environment can be used directly:

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m job_scraper.cli
```

## Checks

```powershell
pytest
ruff check .
job-scraper --help
```

## Run

This makes one public search-page request and keeps at most 10 results:

```powershell
job-scraper "python developer" "Vancouver, BC"
```

Choose a smaller result count or a different output path:

```powershell
job-scraper "data analyst" "Canada" --limit 5 --output data/analyst_jobs.json
```

The output is a JSON array. `posted_date` is an ISO `YYYY-MM-DD` string when the public page
provides it, otherwise `null`. Tracking query parameters are removed from job URLs.

## HTTP API for n8n

Start the local server:

```powershell
job-scraper-api
```

The endpoint is `http://localhost:8000/api/jobs`. Interactive API documentation is available
at `http://localhost:8000/docs`.

PowerShell-friendly curl test (use `curl.exe`, not PowerShell's `curl` alias):

```powershell
curl.exe -X POST "http://localhost:8000/api/jobs" -H "Content-Type: application/json" -d '{"keywords":["AI","Data Analyst"],"location":"Vancouver","max_results":10}'
```

For n8n, create an **HTTP Request** node with method `POST`, URL
`http://host.docker.internal:8000/api/jobs` when n8n runs in Docker on the same computer
(`http://localhost:8000/api/jobs` when n8n runs directly on the host), and send the body as JSON.

## Public deployment on Render

The repository includes `render.yaml`, so Render can read the build command, start command,
environment settings, and health-check path automatically.

Deployment files:

- `requirements.txt` lists every Python runtime dependency.
- `render.yaml` tells Render how to build and start the service.
- `GET /health` returns `{"status":"ok"}` without contacting LinkedIn.

The production start command is:

```text
uvicorn --app-dir src job_scraper.api:app --host 0.0.0.0 --port $PORT
```

`0.0.0.0` allows the hosting platform to reach the process. `$PORT` is the port Render assigns.
For local use, `job-scraper-api` uses port 8000 when `PORT` is not set.

### Deploy steps

1. Create a new GitHub repository and upload this project folder. Do not upload `.env` or
   `.venv`; both are intentionally excluded by `.gitignore`.
2. Sign in to Render and connect the GitHub account containing the repository.
3. In the Render dashboard, click **New +**, then **Blueprint**.
4. Select the GitHub repository and branch containing `render.yaml`.
5. Give the Blueprint a name if requested, then click **Apply** or **Deploy Blueprint**.
6. Wait for the deploy log to show that the service is live.
7. Open `https://YOUR-SERVICE-NAME.onrender.com/health`. A working service returns
   `{"status":"ok"}`.
8. In n8n Cloud, use `POST https://YOUR-SERVICE-NAME.onrender.com/api/jobs` with a JSON body.

The service is public and currently has no API key. Do not share its URL widely. A cloud-hosted
IP can receive different LinkedIn responses than a home connection; the scraper will still stop
instead of bypassing any access control.

LinkedIn can change its markup or guest access at any time. Each public detail request is made
sequentially with a delay and without cookies. HTTP 401, 403, or 429 responses, login walls,
and CAPTCHA pages cause an immediate stop. Before continued or scheduled use, review LinkedIn's
current terms and `robots.txt`; prefer an official API when available.
