# JUDGE ARENA — Cloud-deployable Online Judge

This build deploys the web app and database to Render and delegates compilation/execution to a Judge0-compatible service. The browser never executes submitted code locally.

## Included
- React-free static frontend with Monaco editor
- FastAPI backend and JWT authentication
- PostgreSQL support
- Problems, contests, submissions and leaderboard APIs
- C++17, C++20, Python 3 and Java 17 language mappings
- Judge0 submission polling and verdict mapping
- Render Blueprint (`render.yaml`) and Dockerfile

## Important deployment note
The default Judge0 URL (`https://ce.judge0.com`) is a public shared service intended for small projects/testing, not guaranteed production uptime. For a real public contest, configure a dedicated managed Judge0 endpoint or a self-hosted Judge0 deployment and place its URL/token in Render environment variables. Never expose a Judge0 token in frontend JavaScript or commit it to Git.

The app uses Judge0's sandboxed execution service rather than mounting the host Docker socket into the public web app. This is a safer separation for a public deployment, but production still needs rate limits, abuse controls, database backups, monitoring, and a review of contest scoring rules.

## Deploy to Render
1. Create a GitHub repository and upload the contents of this folder.
2. In Render, choose **New → Blueprint** and connect that repository.
3. Review the services in `render.yaml`, then apply the Blueprint.
4. Set `JUDGE0_URL` to the Judge0 endpoint you are authorized to use.
5. Set `JUDGE0_AUTH_TOKEN` in the Render dashboard if your Judge0 service requires it. Leave it blank only if the endpoint does not require authentication.
6. Wait for the web service to deploy. Render assigns an `onrender.com` URL and provides HTTPS. The included Blueprint uses free plans for a first trial; free services can have usage/availability limits, and the free Postgres database is temporary. For a long-running public site, select suitable paid plans and verify current pricing/retention in Render before confirming deployment.
7. Open `/healthz` to confirm the service responds with `{"status":"ok"}`.

Render docs: https://render.com/docs/blueprint-spec
Judge0 API docs: https://ce.judge0.com/docs

## Local development
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```
Open http://127.0.0.1:8000

## Make an admin
Register an account in the website, then run:
```bash
python scripts/make_admin.py YOUR_USERNAME
```
On Render, use the Render Shell for the web service and run the command there. Ensure it runs against the configured PostgreSQL database.

## Admin API
Open `/docs` and authenticate using the JWT bearer token. Admin endpoints:
- `POST /api/admin/problems`
- `POST /api/admin/contests`

Problem `tests` format:
```json
[
  {"input": "1 2\n", "output": "3\n"},
  {"input": "-5 8\n", "output": "3\n"}
]
```

## Known limitations to address before a large public contest
- The current submit endpoint waits for judge results synchronously; add a durable queue and background workers for higher concurrency.
- The current UI exposes a basic contest/leaderboard experience; implement contest-specific scoring/penalty policy and a full admin UI before official events.
- The demo seed contest is time-relative and intended for initial testing.
- Configure Judge0 language IDs against the exact Judge0 deployment/version you use.
