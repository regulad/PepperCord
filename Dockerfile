# syntax=docker/dockerfile:1
# hadolint global ignore=DL3008
# DL3008 (pin apt package versions) doesn't fit: every package comes from the base image's Debian release, and
# ca-certificates should always be the newest.
#
# `python` installs the interpreter, `build` holds git and Poetry and builds the virtualenv, and
# `runtime` gets only the interpreter, that virtualenv, the source, and the libraries they load at runtime.
#
# docker-publish.yml builds from the git tree with docker/github-builder, which skips .dockerignore and strips .git.
# So nothing here may depend on either: files are copied by path, and git facts come in as build args.

# The Python minor version. uv installs the newest patch release of it that it knows.
ARG PYTHON_MINOR=3.15
ARG DEBIAN_RELEASE=trixie

# Images are named with their registry, so no builder has to guess one (podman refuses to without a TTY).

# uv only installs the interpreter; it ships in neither later stage. Each uv release pins the python-build-standalone
# builds it downloads, and their checksums, so this tag pins the interpreter's patch release and build too. Dependabot
# bumps it, and Python patch releases (and the OpenSSL and SQLite built into the interpreter) arrive with those bumps.
FROM ghcr.io/astral-sh/uv:0.13.8 AS uv

# yt-dlp runs deno for YouTube's JavaScript challenges.
FROM docker.io/denoland/deno:bin-2.9.8 AS deno

# python-build-standalone's CPython, built with Clang, PGO, full LTO, mimalloc and the tail-calling interpreter (and BOLT
# on x86-64). Measured about 1.4x faster than the official python image's GCC build on PepperCord-like workloads.
# amd64 gets the x86-64-v3 build: v3 is the minimum CPU level for every amd64 deployment. arm64 gets the aarch64 build.
# The "gnu" builds need glibc 2.17 or newer and nothing else from the system; OpenSSL, SQLite and the rest are built in.
FROM docker.io/library/debian:${DEBIAN_RELEASE}-slim AS python
ARG PYTHON_MINOR
ARG TARGETARCH
COPY --from=uv /uv /usr/local/bin/uv
# /opt/python/current is one path for every architecture and patch release, so later stages and the virtualenv never
# name the build. uv names the install by its full version (cpython-3.15.2-…), which the glob picks out.
RUN --mount=type=cache,target=/var/cache/buildkit/uv \
  case "$TARGETARCH" in \
  amd64) build=x86_64_v3 ;; \
  arm64) build=aarch64 ;; \
  *) echo "No python-build-standalone build is chosen for $TARGETARCH." >&2; exit 1 ;; \
  esac \
  && UV_CACHE_DIR=/var/cache/buildkit/uv uv python install --no-bin --install-dir /opt/python \
  "cpython-${PYTHON_MINOR}-linux-${build}-gnu" \
  && install=$(basename /opt/python/cpython-"${PYTHON_MINOR}".*-linux-"${build}"-gnu) \
  && ln -s "$install" /opt/python/current \
  && echo "Installed $install"

# The interpreter as the runtime gets it: without the C headers (only the build stage compiles anything), its own pip
# (the virtualenv has what it needs), or Tcl/Tk, tkinter, IDLE and turtledemo. About 30 MB lighter.
FROM python AS python-runtime
WORKDIR /opt/python/current
RUN rm -rf include share lib/pkgconfig \
  lib/tcl9* lib/tk9* lib/itcl* lib/thread* lib/libtcl* \
  lib/python3.15/idlelib lib/python3.15/tkinter lib/python3.15/turtledemo lib/python3.15/ensurepip \
  lib/python3.15/lib-dynload/_tkinter.* \
  lib/python3.15/site-packages/pip lib/python3.15/site-packages/pip-*.dist-info \
  bin/pip bin/pip3 bin/pip3.15 bin/idle3 bin/idle3.15

# Both stages below copy their interpreter to the same /opt/python, so the virtualenv built in one runs in the other.
FROM docker.io/library/debian:${DEBIAN_RELEASE}-slim AS base
# Keep downloaded packages, so the apt cache mounts below can reuse them across builds.
RUN rm -f /etc/apt/apt.conf.d/docker-clean \
  && echo 'Binary::apt::APT::Keep-Downloaded-Packages "true";' > /etc/apt/apt.conf.d/keep-cache
ENV PATH="/opt/python/current/bin:$PATH" \
  DEBIAN_FRONTEND=noninteractive \
  PYTHONFAULTHANDLER=1 \
  PYTHONUNBUFFERED=1 \
  PYTHONDONTWRITEBYTECODE=1 \
  PYTHONHASHSEED=random \
  PYTHONWARNINGS=default \
  PIP_DISABLE_PIP_VERSION_CHECK=1 \
  PIP_DEFAULT_TIMEOUT=100
WORKDIR /app

FROM base AS build
COPY --from=python /opt/python /opt/python
# ca-certificates: Poetry and pip fetch over HTTPS.
# git: three dependencies are installed from git repositories.
# No compiler: every other dependency installs from a wheel, on both architectures.
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
  --mount=type=cache,target=/var/lib/apt,sharing=locked \
  apt-get update \
  && apt-get install -y --no-install-recommends \
  ca-certificates \
  git
# Poetry only ever runs in this stage, from a virtualenv of its own. Its version is the one pyproject.toml pins in the dev
# group, which poetry.lock is generated with and Dependabot keeps current.
ENV PIP_CACHE_DIR=/var/cache/buildkit/pip \
  POETRY_CACHE_DIR=/var/cache/buildkit/poetry \
  POETRY_NO_INTERACTION=1 \
  POETRY_VIRTUALENVS_IN_PROJECT=true \
  POETRY_VIRTUALENVS_OPTIONS_NO_PIP=true
COPY pyproject.toml poetry.lock ./
# DL3042 wants --no-cache-dir, but pip's cache here is a BuildKit cache mount, which never lands in a layer.
# DL3013 wants a literal version, but the version is pyproject.toml's exact pin.
# hadolint ignore=DL3042,DL3013
RUN --mount=type=cache,target=/var/cache/buildkit/pip \
  version=$(python -c 'import tomllib; print(tomllib.load(open("pyproject.toml", "rb"))["tool"]["poetry"]["group"]["dev"]["dependencies"]["poetry"])') \
  && python -m venv /opt/poetry \
  && /opt/poetry/bin/pip install "poetry==$version"
RUN --mount=type=cache,target=/var/cache/buildkit/pip \
  --mount=type=cache,target=/var/cache/buildkit/poetry \
  --mount=type=tmpfs,target=/tmp \
  /opt/poetry/bin/poetry install --only main --no-root --no-ansi

FROM base AS runtime
LABEL name="peppercord" \
  version="10.0.0" \
  maintainer="Parker Wahle <regulad@regulad.xyz>"

# DL3064 matches the word USERNAME, but this is the container's Linux user, not a credential.
# hadolint ignore=DL3064
ARG USERNAME=peppercord
ARG USER_UID=1008
ARG USER_GID=$USER_UID

# ca-certificates, netbase, tzdata: what the official python image adds to Debian; the interpreter's OpenSSL reads
# Debian's certificate store.
# ffmpeg: audio playback; it also brings libopus, which discord.py loads for voice.
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
  --mount=type=cache,target=/var/lib/apt,sharing=locked \
  groupadd --gid "$USER_GID" "$USERNAME" \
  && useradd --uid "$USER_UID" --gid "$USER_GID" -m "$USERNAME" \
  && apt-get update \
  && apt-get install -y --no-install-recommends \
  tini \
  ca-certificates \
  netbase \
  tzdata \
  ffmpeg

# On an amd64 host below x86-64-v3, the interpreter would die with "Illegal instruction" before it could explain.
# The dynamic loader can tell first.
COPY --chmod=755 <<'EOF' /usr/local/bin/require-x86-64-v3
#!/bin/sh
if [ "$(uname -m)" = x86_64 ] && ! /lib64/ld-linux-x86-64.so.2 --help | grep -q 'x86-64-v3 (supported'; then
  echo "This image needs an x86-64-v3 CPU (AVX2, BMI1/2, FMA, MOVBE), and this host's CPU isn't one." >&2
  exit 1
fi
exec "$@"
EOF

COPY --from=python-runtime /opt/python /opt/python
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

ENTRYPOINT ["/usr/bin/tini", "--", "/usr/local/bin/require-x86-64-v3"]
CMD ["python", "src/main.py"]
