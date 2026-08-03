# Immich Dog Tagger Deployment

## Overview

Immich Dog Tagger runs as two Docker services:

* `dog-tagger`: FastAPI backend service
* `dog-tagger-ui`: React frontend served by nginx

The frontend is exposed through Traefik, while nginx proxies `/api/*` requests to the backend service over the Docker network.

The intended deployment URL is:

```
https://dog-tagger.schnorbit.home.arpa
```

Architecture:

```
Browser
   |
   v
Traefik
   |
   v
dog-tagger-ui (nginx)
   |
   +---- /api/* ----> dog-tagger (FastAPI)
                         |
                         v
                      state.db
```

## Docker Compose

The application is deployed using the project `docker-compose.yml`.

Services:

### Backend

Container:

```
immich-dog-tagger
```

Purpose:

* Runs the FastAPI API
* Provides review queue endpoints
* Handles corrections and learning actions
* Owns access to the state database

The backend listens internally on:

```
http://dog-tagger:8000
```

Health endpoint:

```
GET /health
```

Example:

```bash
curl http://dog-tagger:8000/health
```

Expected response:

```json
{
  "status": "ok"
}
```

### Frontend

Container:

```
immich-dog-tagger-ui
```

Purpose:

* Serves the React review interface
* Provides browser access to review workflows
* Proxies API requests to the backend

The container exposes nginx internally on:

```
port 80
```

The frontend container does not need to expose ports directly because Traefik handles external routing.

## Docker Network

Both services join the external Docker network:

```
proxy
```

This allows:

* Traefik to reach the frontend
* nginx to reach the backend
* Internal service discovery using Docker DNS

The important service names are:

```
dog-tagger
dog-tagger-ui
```

Example internal backend URL:

```
http://dog-tagger:8000
```

## nginx Configuration

The frontend container uses nginx to serve static React assets and proxy API requests.

Configuration:

```
/etc/nginx/conf.d/default.conf
```

Important routing behavior:

```nginx
location / {
    try_files $uri /index.html;
}

location /api/ {
    proxy_pass http://dog-tagger:8000/;
}
```

This means:

Browser request:

```
https://dog-tagger.schnorbit.home.arpa/api/health
```

becomes:

```
http://dog-tagger:8000/health
```

inside Docker.

## Traefik Configuration

Traefik uses a dynamic file provider configuration.

Example:

```
/tank/apps/traefik/dynamic/traefik-dog-tagger.yml
```

Configuration:

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

Traefik routes all browser traffic to the frontend container.

The frontend then forwards API traffic to the backend.

## Verification

### Check containers

```bash
docker ps | grep dog-tagger
```

Expected:

```
immich-dog-tagger
immich-dog-tagger-ui
```

### Check backend health

From the UI container:

```bash
docker exec -it immich-dog-tagger-ui wget -qO- http://dog-tagger:8000/health
```

Expected:

```json
{"status":"ok"}
```

### Check nginx frontend

```bash
docker exec -it immich-dog-tagger-ui wget -qO- http://127.0.0.1
```

Expected:

React HTML:

```html
<!doctype html>
<html lang="en">
...
```

### Check through Traefik

Frontend:

```bash
curl -k https://dog-tagger.schnorbit.home.arpa
```

Expected:

React application HTML.

Backend API:

```bash
curl -k https://dog-tagger.schnorbit.home.arpa/api/health
```

Expected:

```json
{"status":"ok"}
```

## Development Workflow

Frontend changes require rebuilding the UI image:

```bash
docker compose build dog-tagger-ui
docker compose up -d dog-tagger-ui
```

Backend changes require rebuilding the API image:

```bash
docker compose build dog-tagger
docker compose up -d dog-tagger
```

Full restart:

```bash
docker compose up -d --build
```

## Future Deployment Improvements

Potential future improvements:

* Add Docker health checks to the frontend container
* Add version information to the UI
* Add a production environment configuration file
* Add automated image builds
* Add Traefik middleware specific to application authentication if required
