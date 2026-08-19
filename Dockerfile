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

# 7. Bake in the commit this image was built from, so the running app's version
# string can include it (see immich_dog_tagger/version.py). CI passes
# --build-arg GIT_COMMIT=<short sha> on every push to main; a local `docker build`
# without the arg leaves this empty and get_version() falls back to the plain
# package version.
ARG GIT_COMMIT=""
ENV GIT_COMMIT=${GIT_COMMIT}

ENTRYPOINT ["immich-dog-tagger"]
