# Vibe Coder Flashcards

This mono-repo hosts the entire **Vibe Coder Flashcards** application.

## Layout

```
apps/               – deployable applications  
  web/              – Next.js PWA (front-end + thin API routes)  
  worker/           – FastAPI async worker that ingests feeds, calls LLM, and saves flashcards  
packages/           – shared code that can be imported by web & worker  
docs/               – product docs (PRD, architecture, etc.)  
infra/github/       – CI / CD workflows
```

## Quick start (local)

```bash
# Back-end worker
python -m venv .venv && source .venv/bin/activate
pip install -r apps/worker/requirements.txt
uvicorn apps.worker.main:app --reload

# Front-end (needs Node ≥ 18)
cd apps/web
npm install
npm run dev
```

## Environment variables

| Variable     | Purpose                               | Default                   |
| ------------ | ------------------------------------- | ------------------------- |
| `WORKER_URL` | Base URL of the worker API consumed by the Next.js routes | `http://localhost:8000` |

## Engineering Principles (Elon Musk’s 5 steps)

1. **Question every requirement** – keep only what drives engagement.  
2. **Delete / consolidate** – minimal microservices, mono-repo.  
3. **Simplify & optimise** – use managed services, serverless cron.  
4. **Accelerate cycle time** – CI, preview deploys, Codespaces.  
5. **Automate** – GitHub Actions for tests, ingestion, deploy, and auto merging of passing pull requests.
