# medical-data-validator Railway Deployment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Connect medical-data-validator's GitHub repo to Railway as 2 services (API, background worker) on its own domain with HTTPS, such that pushing to `main` automatically rebuilds and redeploys.

**Architecture:** Two Railway services built from this repo, both from the existing multi-stage `Dockerfile`'s `runtime` target: `medvalidator-api` (gunicorn, custom domain `$MEDVALIDATOR_DOMAIN`) and `medvalidator-worker` (same image, different start command, no public domain). Both use the shared Redis service already running in the `homelab` Railway project via private networking. This app is SQLite-backed for its audit/registry/jobs stores (per its own Dockerfile) — it does not use the shared Postgres, so it needs a Railway Volume of its own for `/data`. Once linked to this GitHub repo, Railway rebuilds and redeploys automatically on every push to `main`.

**Tech Stack:** Railway, Docker (existing multi-stage `Dockerfile`, `runtime` target), Flask + gunicorn, Redis-backed job queue.

## Prerequisites (from the `homelab-infra` plan — do not start here first)

This plan assumes `homelab-infra`'s plan (`homelab-infra/docs/superpowers/plans/2026-08-01-railway-foundation-and-shared-services.md`) is already done. In particular, you need:
- The `homelab` Railway project already exists, with the Redis service running in it
- Redis's exact private networking domain (ends in `.railway.internal`) and its `REDISPASSWORD`
- Your purchased domain (referred to below as `$MEDVALIDATOR_DOMAIN`, e.g. `medvalidator.dev`) — not yet pointed at anything, that happens in Task 1

This app does not need a Postgres password from homelab-infra — it's SQLite-backed.

## Global Constraints

- Redis logical DB indices for this app on the shared instance: `4` (Celery broker) and `5` (Celery result backend) — fixed by the homelab-infra plan, do not change or reuse.
- The Dockerfile's `runtime` target must be selected explicitly in Railway's build settings — the `builder` stage isn't the deployable image.
- Secrets are generated with `openssl rand -hex <n>`, never hardcoded into a committed file — they're set as Railway service variables (dashboard), not `.env` files committed to this repo.

---

## File Structure

No file changes to this repo's code — Railway builds the existing `Dockerfile` as-is; there's no `docker-compose.prod.yml` or `.github/workflows/deploy.yml` to create, Railway's dashboard/GitHub integration replaces both entirely.

---

## Task 1: Create the 2 Railway services from this repo

**Files:** none (Railway dashboard configuration only)

- [ ] **Step 1: Create the API service**

In the `homelab` Railway project canvas: New → GitHub Repo → select `RanaEhtashamAli/medical-data-validator` (authorize Railway's GitHub App for this repo if prompted). Once created, rename the service to `medvalidator-api` and set:
- Settings → Source → Root Directory: `/`
- Settings → Build → Dockerfile Build Target: `runtime` (the Dockerfile has a `builder` stage and a `runtime` stage — Railway must target `runtime`, matching the existing local `docker-compose.yml`'s `target: runtime`)
- Settings → Deploy → Branch: `main`

- [ ] **Step 2: Attach a volume for the SQLite stores**

`medvalidator-api` → Settings → Volumes → New Volume → mount path `/data`.

- [ ] **Step 3: Set the API service's environment variables**

`medvalidator-api` → Variables tab → Raw Editor:

```
SECRET_KEY=<generate with: openssl rand -hex 32>
JWT_SECRET=<generate with: openssl rand -hex 32>
ADMIN_PASSWORD=<generate with: openssl rand -hex 16>
DEFAULT_TENANT_API_KEY=<generate with: openssl rand -hex 24>
AUDIT_DB_DIR=/data
JOBS_DB_DIR=/data
REGISTRY_DB_PATH=/data/registry.db
CELERY_BROKER_URL=redis://default:<REDISPASSWORD from homelab-infra Task 2>@<Redis private domain from homelab-infra Task 2>:6379/4
CELERY_RESULT_BACKEND=redis://default:<REDISPASSWORD from homelab-infra Task 2>@<Redis private domain from homelab-infra Task 2>:6379/5
FLASK_ENV=production
PORT=8000
GUNICORN_WORKERS=2
GUNICORN_THREADS=4
```

Save the generated `ADMIN_PASSWORD` somewhere safe — it's the login for the built-in admin user.

- [ ] **Step 4: Add the custom domain**

`medvalidator-api` → Settings → Networking → Custom Domain → enter `medvalidator.dev` (your actual `$MEDVALIDATOR_DOMAIN`) → Railway shows you the exact CNAME record to add. Add it in Porkbun's DNS panel for that domain.

- [ ] **Step 5: Create the worker service from the same repo**

New → GitHub Repo → select `RanaEhtashamAli/medical-data-validator` again. Rename it `medvalidator-worker` and set:
- Settings → Source → Root Directory: `/`
- Settings → Build → Dockerfile Build Target: `runtime`
- Settings → Deploy → Branch: `main`
- Settings → Deploy → Custom Start Command:

```
python -c "from medical_data_validator.jobs import _ensure_worker; import time; _ensure_worker(); [time.sleep(3600) for _ in iter(int, 1)]"
```

- Settings → Volumes → New Volume → mount path `/data` (same path, but this is a *separate* volume from the API service's — Railway volumes aren't shared across services. If the worker needs to see the same audit/job data as the API, mount a **shared** volume instead: Settings → Volumes → Attach Existing Volume → select the one created in Task 1 Step 2.)
- Variables tab: copy the exact same variables as Step 3
- No custom domain for this service

- [ ] **Step 6: Wait for DNS propagation and verify the deploy**

```bash
dig +short medvalidator.dev
```

Expected: resolves (may take a few minutes to an hour). In the Railway dashboard, confirm both `medvalidator-api` and `medvalidator-worker` show a green "Active" deployment.

```bash
curl -sf https://medvalidator.dev/api/health
```

Expected: returns a `200` with a JSON body (per the existing `HEALTHCHECK` in the Dockerfile).

---

## Task 2: Prove the auto-deploy loop works end to end

**Files:** none (verification only)

- [ ] **Step 1: Make a trivial, visible change and push it**

```bash
cd "/home/lenovo/Own Projects/medical-data-validator"
echo "<!-- deploy test $(date -u +%FT%TZ) -->" >> README.md
git add README.md
git commit -m "Test auto-deploy"
git push origin main
```

- [ ] **Step 2: Confirm it deploys automatically, with no manual step**

Watch the `medvalidator-api` service's Deployments tab — a new build should start within seconds of the push, with no manual trigger. Wait for it to go green, then:

```bash
curl -sf https://medvalidator.dev/api/health
```

Expected: still returns `200` after the redeploy.

- [ ] **Step 3: Confirm both services are stable**

In the Railway dashboard, check that `medvalidator-api` and `medvalidator-worker` both show "Active" with no crash/restart loop in their logs.

## Post-plan notes

- **Rollback**: Railway keeps every past deployment — Deployments tab → find the last good one → "Redeploy" to roll back a single service without touching the other.
- **Shared volume caveat**: double-check Step 5 actually attached the *same* Railway volume as the API service, not a second independent one — two separate volumes both mounted at `/data` would silently split the audit/job/registry state between the two services, which defeats the point of a shared job queue.
