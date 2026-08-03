FROM python:3.14-slim

WORKDIR /app
ENV YOLO_CONFIG_DIR=/tmp/ultralytics

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    libglib2.0-0 \
    libgl1 \
    libsm6 \
    libxext6 \
    libxrender1 \
    libxcb1 \
 && rm -rf /var/lib/apt/lists/*

COPY certs/mkcert-rootCA.crt /usr/local/share/ca-certificates/mkcert-rootCA.crt

RUN update-ca-certificates

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
COPY pyproject.toml uv.lock README.md ./
COPY src ./src

RUN uv sync --frozen --no-dev
RUN uv pip install --system .

RUN mkdir -p /tmp/ultralytics/Ultralytics \
    && chmod -R 777 /tmp/ultralytics

ENTRYPOINT ["immich-dog-tagger"]