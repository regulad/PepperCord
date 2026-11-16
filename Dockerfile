# syntax=docker/dockerfile:1
# hadolint global ignore=DL3008
# DL3008 (pin apt package versions) doesn't fit: every package comes from the base image's Debian release, and
# ca-certificates should always be the newest.
#
# Two stages share one base. `build` holds the compiler, headers, git and Poetry, and builds the virtualenv.
# `runtime` copies only that virtualenv and the source onto the base, plus the libraries they load at runtime.
#
# docker-publish.yml builds from the git tree with docker/github-builder, which skips .dockerignore and strips .git.
# So nothing here may depend on either: files are copied by path, and git facts come in as build args.

ARG PYTHON_VERSION=3.14.3
ARG DEBIAN_RELEASE=trixie

# Images are named with their registry, so no builder has to guess one (podman refuses to without a TTY).

# yt-dlp runs deno for YouTube's JavaScript challenges.
FROM docker.io/denoland/deno:bin-2.3.1 AS deno

FROM docker.io/library/python:${PYTHON_VERSION}-slim-${DEBIAN_RELEASE} AS base
# Keep downloaded packages, so the apt cache mounts below can reuse them across builds.
RUN rm -f /etc/apt/apt.conf.d/docker-clean \
  && echo 'Binary::apt::APT::Keep-Downloaded-Packages "true";' > /etc/apt/apt.conf.d/keep-cache
ENV DEBIAN_FRONTEND=noninteractive \
  PYTHONFAULTHANDLER=1 \
  PYTHONUNBUFFERED=1 \
  PYTHONDONTWRITEBYTECODE=1 \
  PYTHONHASHSEED=random \
  PYTHONWARNINGS=default \
  PIP_DISABLE_PIP_VERSION_CHECK=1 \
  PIP_DEFAULT_TIMEOUT=100
WORKDIR /app

FROM base AS build
# git: three dependencies are installed from git repositories.
# gcc, pkg-config, libcairo2-dev: pycairo has no wheels, so it builds from source on every architecture.
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
  --mount=type=cache,target=/var/lib/apt,sharing=locked \
  apt-get update \
  && apt-get install -y --no-install-recommends \
  git \
  gcc \
  pkg-config \
  libcairo2-dev
# Poetry only ever runs in this stage. Pinned to the version poetry.lock is generated with.
ENV PIP_CACHE_DIR=/var/cache/buildkit/pip \
  POETRY_CACHE_DIR=/var/cache/buildkit/poetry \
  POETRY_NO_INTERACTION=1 \
  POETRY_VIRTUALENVS_IN_PROJECT=true \
  POETRY_VIRTUALENVS_OPTIONS_NO_PIP=true
# DL3042 wants --no-cache-dir, but pip's cache here is a BuildKit cache mount, which never lands in a layer.
# hadolint ignore=DL3042
RUN --mount=type=cache,target=/var/cache/buildkit/pip \
  pip install --root-user-action=ignore poetry==2.1.2
COPY pyproject.toml poetry.lock ./
RUN --mount=type=cache,target=/var/cache/buildkit/pip \
  --mount=type=cache,target=/var/cache/buildkit/poetry \
  --mount=type=tmpfs,target=/tmp \
  poetry install --only main --no-root --no-ansi

FROM base AS runtime
LABEL name="peppercord" \
  version="10.0.0" \
  maintainer="Parker Wahle <regulad@regulad.xyz>"

ARG USERNAME=peppercord
ARG USER_UID=1008
ARG USER_GID=$USER_UID

# ffmpeg: audio playback; it also brings libopus, which discord.py loads for voice.
# libcairo2: what the pycairo built in the build stage links against.
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
  --mount=type=cache,target=/var/lib/apt,sharing=locked \
  groupadd --gid "$USER_GID" "$USERNAME" \
  && useradd --uid "$USER_UID" --gid "$USER_GID" -m "$USERNAME" \
  && apt-get update \
  && apt-get install -y --no-install-recommends \
  tini \
  ca-certificates \
  ffmpeg \
  libcairo2

COPY --from=deno /deno /usr/local/bin/deno
COPY --from=build /app/.venv /app/.venv
COPY src/ src/
COPY resources/ resources/

# The version should match the most recent major version tag. The commit is passed in by docker-publish.yml,
# since the image has no .git to read it from.
ARG GIT_SHA
ENV PATH="/app/.venv/bin:$PATH" \
  PYTHONOPTIMIZE=1 \
  PEPPERCORD_DOCKER_VERSION="v10.0.0" \
  PEPPERCORD_GIT_SHA="${GIT_SHA}"

USER $USERNAME

# Health check endpoint. Not configurable; see src/extensions/utilities/health.py
EXPOSE 8080

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["python", "src/main.py"]
