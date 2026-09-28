# Deployment (Railway)

## What gets deployed

Railway builds the Docker image defined in `Dockerfile` (Python 3.13-slim, `uv sync --frozen`, runs `uvicorn main:app` bound to `$PORT`). Build and deploy settings — including the `/health` health check — come from `railway.json`.

## Option A — GitHub integration

1. Railway dashboard → **New Project** → **Deploy from GitHub repo**.
2. Select `HarielGiacomuzzi/CodeAnalyzerAgent`.
3. **Variables** tab → add `ANTHROPIC_API_KEY` (your Anthropic API key). `ANTHROPIC_MODEL` and `PORT` are optional; Railway sets `PORT` automatically.
4. **Settings** → **Networking** → **Generate Domain**.

Every push to the connected branch redeploys automatically.

## Option B — Railway CLI

```bash
npm i -g @railway/cli
railway login
railway init
railway variables --set ANTHROPIC_API_KEY=sk-ant-...
railway up
railway domain
```

`railway up` builds and deploys the current directory using `Dockerfile`; `railway domain` generates (or shows) the public URL.

## Verifying the deployment

```bash
curl https://<domain>/health
uv run python scripts/smoke.py https://<domain>
```

Then open `https://<domain>` in a browser and run an analysis through the UI.

## Running the container locally

```bash
docker build -t code-analyzer .
docker run --rm -p 8000:8000 --env-file .env code-analyzer
```

## Cost and security notes

- `/analyze` is public and unauthenticated — anyone who can reach the deployed URL can trigger a billed Claude call.
- Set a spend limit on the Anthropic API key in the [Anthropic Console](https://console.anthropic.com/) before deploying publicly.
- Rotate the key immediately if it leaks (e.g. committed to git, exposed in logs).

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| Health check failing | Confirm the app binds `$PORT` (the `Dockerfile` CMD uses `${PORT:-8000}`); check Railway's deploy logs for a crash on startup. |
| `/analyze` returns 503 | `ANTHROPIC_API_KEY` is not set on this environment. Set it in **Variables** and redeploy. |
| `/analyze` returns 502 | The Anthropic API returned an error, the model refused, or output didn't parse. Check the deploy logs for the provider's status and message. |
| Responses are slow | Expected — a full analysis (with tool call and reasoning) typically takes 20-60 seconds. |
