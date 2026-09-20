# Deployment

This doc covers a production-style deployment behind Traefik with TLS and GPU scheduling, layered
on top of the base `docker-compose.yml` via `docker-compose.prod.yml`. For a minimal local setup
with directly-exposed ports and no reverse proxy, see the
[README quick start](../README.md#getting-started) — that's just `docker-compose.yml` on its own.

## Overview

Immich Dog Tagger runs as two Docker services: `dog-tagger`, the FastAPI backend, and
`dog-tagger-ui`, the React frontend served by nginx. Traefik exposes the frontend, and nginx
proxies `/api/*` requests to the backend over the Docker network. The example deployment URL used
throughout this doc is `https://dog-tagger.schnorbit.home.arpa` — replace it with your own host.

```
Browser → Traefik → dog-tagger-ui (nginx) → /api/* → dog-tagger (FastAPI) → state.db
```

## Docker Compose

Deployment layers two files: the base `docker-compose.yml` (image references, environment,
volumes, health check — shared with the plain local setup in the README) and
`docker-compose.prod.yml`, an override that adds the `proxy` network, drops the base's directly
published host ports (Traefik reaches the containers over the Docker network instead), and
reserves a GPU. Always pass both, base first:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

Everything below in this doc assumes that combined invocation. Consider a shell alias or a
`COMPOSE_FILE=docker-compose.yml:docker-compose.prod.yml` entry in a local `.env` if typing both
`-f` flags each time is tedious (`docker compose` also picks up `COMPOSE_FILE` from the
environment).

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

## Immich configuration

Two environment variables describe Immich, because two different clients talk to it:

| Variable | Used by | Example |
| --- | --- | --- |
| `IMMICH_URL` | the backend container, calling the Immich API | `http://immich-server:2283` |
| `IMMICH_EXTERNAL_URL` | the reviewer's browser, following **View in Immich** links | `https://immich.example.com` |

`IMMICH_EXTERNAL_URL` is optional and falls back to `IMMICH_URL` when unset, so a deployment where
Immich answers at one address everywhere needs only `IMMICH_URL`. Set it when the backend reaches
Immich over a Docker network or a private hostname the browser can't resolve — otherwise the review
card's **View in Immich** link points at an address that only exists inside the container.

The UI reads this value at runtime from `GET /api/settings`, so changing it needs a backend restart
(`docker compose up -d dog-tagger`) — not a frontend image rebuild.

`IMMICH_TIMEOUT_SECONDS` (default `60`) bounds how long the backend waits on any single Immich API
request. Bulk sync writes (tagging or albuming many assets in one identity) can legitimately take
Immich longer to process than a typical read; raise this if `sync` jobs fail with a timeout on a
large library.

### JSON config file (alternative to the `IMMICH_*` variables)

Instead of the environment variables above, Immich configuration can live in a JSON file mounted
into the container — the same bind-mount pattern already used for `state`/`cache`/`models`. This
is the only way to declare more than one Immich account, and is generally the preferred format
going forward (see [docs/specs/json-config-file.md](specs/json-config-file.md)).

To adopt it:

1. Copy [`config.example.json`](../config.example.json) to a host path of your choice, e.g.
   `./data/config.json`, and fill in `immich.url` and at least one `immich.accounts` entry
   (`name`/`api_key`).
2. Set `HOST_CONFIG_FILE` in `.env` to that path.
3. Restart the backend: `docker compose up -d dog-tagger`.

```json
{
  "immich": {
    "url": "https://immich.example.com",
    "external_url": "",
    "timeout_seconds": 60,
    "accounts": [{ "name": "default", "api_key": "..." }]
  }
}
```

`docker-compose.yml` always sets `CONFIG_FILE=/app/config/config.json` inside the container and
mounts `${HOST_CONFIG_FILE:-./data/config.json}` there. If that host path doesn't exist, the mount
is an empty directory and the backend falls back to the `IMMICH_*` variables with no error — this
is the expected state for a deployment that hasn't migrated, not a misconfiguration. If both the
config file and `IMMICH_*` variables are present, the file wins outright and the backend logs a
warning naming the environment variables it ignored, so a mid-migration deployment is never left
guessing which source is live. A config file that exists but is invalid (malformed JSON, a missing
`immich.url`, zero accounts, or two accounts sharing a name) fails startup immediately, naming the
file and the specific problem, rather than falling back silently.

Running from source instead of Docker: set `CONFIG_FILE` directly in `.env` (e.g. `./config.json`)
rather than `HOST_CONFIG_FILE`, which only matters to `docker-compose.yml`'s volume mount.

### Multiple Immich accounts

With two or more entries under `immich.accounts` in the config file above, this app scans,
downloads, and syncs each one against its own Immich library, while identity, classification,
review, and Insights stay fully shared across all of them — see
[docs/specs/multi-immich-account-sync.md](specs/multi-immich-account-sync.md) for the full
architecture. Nothing further needs configuring; the backend registers an account per entry
automatically on startup.

The CLI's `scan`, `download`, `sync`, and `pipeline` commands accept an optional
`--account <name>`; omitted, each runs against **every** configured account in turn, continuing
past a failed account (a revoked key, a network error) rather than aborting the whole run:

```bash
docker compose exec dog-tagger immich-dog-tagger scan --account alice
docker compose exec dog-tagger immich-dog-tagger sync
```

The Job Queue and Automation Schedules pages currently start a scan/sync/full-pipeline job against
the *first* configured account only — a fast-follow UI update will add an account picker there.
Until then, use the CLI (or the equivalent `account_id` field on `POST /jobs`/`POST /schedules`)
to target a specific account from a multi-account deployment.

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

## Picking up a new release

Both files reference the published GHCR images (`ghcr.io/<owner>/immich-dog-tagger` and
`-ui`), not a local build, so there's nothing to compile — pull the latest tag and recreate:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml pull
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

### Schema and data upgrades

Schema changes are applied automatically. `create_database()` runs on every startup and every CLI
command: it creates any missing tables and applies each additive column/table migration in
`src/immich_dog_tagger/database.py` in place. Existing rows are preserved — assets, detections,
crops, classifications, review actions, and learned embedding examples are never dropped or
recreated. Nothing needs to be run by hand, and `state.db` should not be deleted to pick up a new
schema.

Two things a release can need that a schema migration cannot do for itself, because they depend on
data that lives in Immich or has to be recomputed:

- **Cached Immich metadata** (capture location, recognized people, favorite flag on `Asset`). A
  scan refreshes these for every asset it has already seen, not just new ones, so running `scan`
  (CLI or the Scan job) after an upgrade backfills them. This is what populates the Insights
  page's place and person facts.
- **Pet occurrence facts.** `immich-dog-tagger backfill-occurrences` rebuilds `PetOccurrence` from
  current classification state. Needed once when upgrading a library whose classification history
  predates v1.6.0; after that the table is kept in sync as classifications settle.

Both are idempotent and derived — running either again is safe, and neither touches reviewed
labels.

## Testing an unreleased local change

Neither compose file has a `build:` section, so `docker compose ... up -d --build` has nothing to
build against. To try out a change before it's merged to `main` and published:

- Fastest: run it from source instead (see the README's "Running from source" section) — no image
  build involved.
- To actually exercise it inside a container, add a temporary local override, e.g.
  `docker-compose.local.yml`:

  ```yaml
  services:
    dog-tagger:
      build:
        context: .
      image: immich-dog-tagger:local
  ```

  then `docker compose -f docker-compose.yml -f docker-compose.prod.yml -f docker-compose.local.yml
  up -d --build dog-tagger`. Don't commit that file — it's a local-only override.

## Unattended operation

The backend runs a built-in scheduler as a background thread — no browser session needed. Every
60 seconds it loads enabled schedules from `state.db`, finds any whose cron expression matches
the current minute, creates a `PipelineJob` for each, and runs it through the existing job runner.
It skips occurrences already covered by an existing job, so nothing double-runs. On startup it
also runs one reconciliation tick to catch anything missed while the container was down.

### Setting it up

1. Turn on automation in Settings → Automation. A full pipeline run on an hourly cadence
   (`0 * * * *`) is a reasonable default; enable syncing (e.g. `30 * * * *`) once confident labels
   start accumulating.
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
`workflow_dispatch`. This publishes prebuilt images to the registry; it does not deploy them — see
"Picking up a new release" above to pull a new image into a running deployment.

## Possible future improvements

- Docker health checks on the frontend container
- Version information surfaced in the UI
- A dedicated production environment configuration file
- Traefik middleware for application-level authentication, if that becomes necessary
