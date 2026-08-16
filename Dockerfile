FROM python:3.14-slim AS builder

WORKDIR /app
ENV YOLO_CONFIG_DIR=/tmp/ultralytics

# 1. System packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    libglib2.0-0 \
    libgl1 \
    libsm6 \
    libxext6 \
    libxrender1 \
    libxcb1 \
 && rm -rf /var/lib/apt/lists/*

# Optional: trust a local mkcert root CA if present (glob copy is a no-op when absent,
# so this doesn't require the untracked certs/ directory to exist, e.g. in CI).
COPY certs/mkcert-rootCA.cr[t] /usr/local/share/ca-certificates/
RUN update-ca-certificates

# 2. Get uv binary
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# 3. Copy ONLY lockfiles first
COPY pyproject.toml uv.lock README.md ./

# 4. Install dependencies without installing the project itself
RUN uv sync --frozen --no-dev --no-install-project

# 5. Copy source code LAST
COPY src ./src

# 6. Install the project code
RUN uv pip install --system .

RUN mkdir -p /tmp/ultralytics/Ultralytics && chmod -R 777 /tmp/ultralytics

ENTRYPOINT ["immich-dog-tagger"]