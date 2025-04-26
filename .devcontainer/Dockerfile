FROM mcr.microsoft.com/devcontainers/python:1-3.13-bookworm

# OverlayFS blocks cross-mount hard-links, so copy wheels instead
ENV UV_LINK_MODE=copy

# ---- system packages + CLI tools (cached) ---------------------
RUN --mount=type=cache,target=/root/.cache/uv \
    apt update \
    && apt install -y --no-install-recommends openjdk-17-jre-headless \
    && uv tool install pre-commit ruff isort tox \
    && rm -rf /var/lib/apt/lists/* /var/cache/apt/archives/*
# ---------------------------------------------------------------