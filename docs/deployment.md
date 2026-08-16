# Deployment

This doc covers a production-style deployment behind Traefik with TLS and optional GPU scheduling.
For a minimal local setup with directly-exposed ports and no reverse proxy, see the
[README quick start](../README.md#getting-started) and `docker-compose.quickstart.yml`.

## Overview

Immich Dog Tagger runs as two Docker services: `dog-tagger`, the FastAPI backend, and
`dog-tagger-ui`, the React frontend served by nginx. Traefik exposes the frontend, and nginx
proxies `/api/*` requests to the backend over the Docker network. The example deployment URL used
throughout this doc is `https://dog-tagger.schnorbit.home.arpa` — replace it with your own host.

```
Browser → Traefik → dog-tagger-ui (nginx) → /api/* → dog-tagger (FastAPI) → state.db
```

## Docker Compose

Deployment uses the project's `docker-compose.yml`.

**Backend** (`immich-dog-tagger`) runs the FastAPI API: review queue endpoints, corrections,
learning actions, and the only process with access to `state.db`. It listens internally on
`http://dog-tagger:8000` and exposes `GET /health`:

```bash
curl http://dog-tagger:8000/health
# {"status": "ok"}
```

**Frontend** (`immich-dog-tagger-ui`) serves the React review interface and proxies API requests
to the backend. nginx listens internally on port 80; it doesn't need to expose ports directly
since Traefik handles external routing.

## Docker network

Both services join the external `proxy` network, so Traefik can reach the frontend and nginx can
reach the backend by Docker DNS (`dog-tagger`, `dog-tagger-ui`) — for example,
`http://dog-tagger:8000` from inside the frontend container.

## nginx configuration

The frontend container's nginx (`/etc/nginx/conf.d/default.conf`) serves the built React assets
and proxies API calls:

```nginx
location / {
    try_files $uri /index.html;
}

location /api/ {
    proxy_pass http://dog-tagger:8000/;
}
```

So a browser request to `https://dog-tagger.schnorbit.home.arpa/api/health` becomes
`http://dog-tagger:8000/health` inside the Docker network.

## Traefik configuration

Traefik picks this up via its dynamic file provider, e.g.
`/tank/apps/traefik/dynamic/traefik-dog-tagger.yml`:

```yaml
http:
  routers:
    dog-tagger:
      rule: "Host(`dog-tagger.schnorbit.home.arpa`)"
      entryPoints:
        - websecure
      service: dog-tagger
      tls: {}
      middlewares:
        - secure-headers@file

  services:
    dog-tagger:
      loadBalancer:
        servers:
          - url: "http://dog-tagger-ui:80"
```

Traefik routes browser traffic to the frontend container, which then forwards `/api/*` traffic to
the backend.

## Verifying a deployment

Check both containers are up:

```bash
docker ps | grep dog-tagger
# immich-dog-tagger
# immich-dog-tagger-ui
```

Check the backend from inside the UI container:

```bash
docker exec -it immich-dog-tagger-ui wget -qO- http://dog-tagger:8000/health
# {"status":"ok"}
```

Check nginx is serving the frontend:

```bash
docker exec -it immich-dog-tagger-ui wget -qO- http://127.0.0.1
# <!doctype html> ...
```

Check both through Traefik:

```bash
curl -k https://dog-tagger.schnorbit.home.arpa            # React app HTML
curl -k https://dog-tagger.schnorbit.home.arpa/api/health  # {"status":"ok"}
```

## Making changes

Frontend changes need a rebuild of the UI image:

```bash
docker compose build dog-tagger-ui
docker compose up -d dog-tagger-ui
```

Backend changes need a rebuild of the API image:

```bash
docker compose build dog-tagger
docker compose up -d dog-tagger
```

Or rebuild everything at once:

```bash
docker compose up -d --build
```

## Unattended operation

The backend runs a built-in scheduler as a background thread — no browser session needed. Every
60 seconds it loads enabled schedules from `state.db`, finds any whose cron expression matches
the current minute, creates a `PipelineJob` for each, and runs it through the existing job runner.
It skips occurrences already covered by an existing job, so nothing double-runs. On startup it
also runs one reconciliation tick to catch anything missed while the container was down.

### Setting it up

1. Create at least one schedule in Overview → Automation Schedules. A full pipeline run on an
   hourly cadence (`0 * * * *`) is a reasonable default; add a sync schedule (e.g. `30 * * * *`)
   once confident labels start accumulating.
2. Keep the container running and set it to restart automatically:

   ```yaml
   # docker-compose.yml
   services:
     dog-tagger:
       restart: unless-stopped
   ```

3. Confirm the scheduler is healthy:

   ```bash
   curl http://dog-tagger:8000/health
   ```

   ```json
   {
     "status": "ok",
     "scheduler": {
       "healthy": true,
       "ticks": 3,
       "errors": 0,
       "started_at": "2026-08-10T00:00:00+00:00",
       "last_tick_at": "2026-08-10T00:02:00+00:00",
       "last_error_at": null,
       "last_error": null
     }
   }
   ```

### Scheduler health fields

| Field | Meaning |
|---|---|
| `healthy` | `true` when the most recent tick succeeded after the most recent error (or there have been no errors) |
| `ticks` | Evaluation ticks completed since startup |
| `errors` | Ticks that raised an unexpected exception |
| `started_at` | When the scheduler thread started |
| `last_tick_at` | Timestamp of the last successful tick |
| `last_error_at` | Timestamp of the most recent error, or null |
| `last_error` | Error message from the most recent failed tick |

### Failure isolation

One schedule failing doesn't stop the others — each dispatch is isolated, and a failure is logged
and skipped while the rest of that tick's due schedules still run. If the whole tick fails (for
example, the database is unavailable), the error is logged and the scheduler sleeps until the
next interval instead of exiting.

### Missed occurrences

If the container was down when a schedule was due, the startup reconciliation tick dispatches it
immediately on restart — but only the most recent missed occurrence, not a full replay of
everything missed during the downtime.

## Automated image builds

`.github/workflows/docker-publish.yml` builds and pushes both images to GitHub Container Registry
(`ghcr.io/<owner>/immich-dog-tagger` and `ghcr.io/<owner>/immich-dog-tagger-ui`) on every push to
`main`, tagged `latest` and with the short commit SHA. It can also be run manually via
`workflow_dispatch`. This publishes prebuilt images to the registry; it does not deploy them —
pulling a new image into a running deployment is still a manual `docker compose pull && docker
compose up -d` (or update `docker-compose.yml` to reference the registry image instead of building
locally).

## Possible future improvements

- Docker health checks on the frontend container
- Version information surfaced in the UI
- A dedicated production environment configuration file
- Traefik middleware for application-level authentication, if that becomes necessary
