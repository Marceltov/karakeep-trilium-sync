# karakeep-trilium-sync: copies Karakeep bookmarks into Trilium notes.
#
# Multi-stage: resolve dependencies into a venv with uv in the builder, then
# ship only the venv + script on a plain python-slim runtime.

FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder

# Use the image's system CPython, so the venv references /usr/local/bin/python3.12,
# which also exists in the runtime image.
ENV UV_PYTHON_PREFERENCE=only-system \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

FROM python:3.12-slim-bookworm

# curl fetches Reddit posts: Reddit blocks Python's TLS client but serves curl.
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY --from=builder /app/.venv /app/.venv
COPY karakeep_sync.py ./

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1

# Runs as nobody: the sync needs no files, only the network.
USER 65534:65534

# All configuration is via environment variables (see README).
CMD ["python", "karakeep_sync.py"]
