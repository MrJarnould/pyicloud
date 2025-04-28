# syntax=docker/dockerfile:1
FROM mcr.microsoft.com/devcontainers/python:1-3.13-bookworm

# OverlayFS blocks cross-mount hard-links, so tell uv to copy wheels
ENV UV_LINK_MODE=copy

# ─── base OS packages (cached) ────────────────────────────────────────
RUN --mount=type=cache,target=/var/cache/apt \
    apt-get update \
    && apt-get install -y --no-install-recommends openjdk-17-jre-headless \
    && rm -rf /var/lib/apt/lists/*
# ───────────────────────────────────────────────────────────────────────
