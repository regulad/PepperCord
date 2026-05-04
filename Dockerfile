# hadolint global ignore=DL3008  # DL3008 is fit for us, python3-dev is pinned by the image's repositories; and ca-certificates should always be the newest bc CoT
# deno is needed for yt-dlp
FROM denoland/deno:bin-2.7.14 AS deno
FROM python:3.14.3-slim-trixie
LABEL name="peppercord" \
  version="10.0.0" \
  maintainer="Parker Wahle <regulad@regulad.xyz>"

# Git can't reliably be queried from inside Docker, so we just pass this in instead.
# Should match the most recent major version tag.
ENV PEPPERCORD_DOCKER_VERSION="v10.0.0"
ENV DEBIAN_FRONTEND=noninteractive \
  PYTHONFAULTHANDLER=1 \
  PYTHONUNBUFFERED=1 \
  PYTHONOPTIMIZE=1 \
  PYTHONDONTWRITEBYTECODE=1 \
  PYTHONHASHSEED=random \
  PYTHONWARNINGS=default \
  PIP_DISABLE_PIP_VERSION_CHECK=1 \
  PIP_DEFAULT_TIMEOUT=100 \
  PIP_CACHE_DIR=/var/cache/buildkit/pip \
  POETRY_HOME=/opt/poetry \
  POETRY_VERSION=1.8.2 \
  POETRY_CACHE_DIR=/var/cache/buildkit/poetry

ARG USERNAME=peppercord
ARG USER_UID=1008
ARG USER_GID=$USER_UID

COPY --from=deno /deno /usr/local/bin/deno

# Apt cache setup: disable docker-clean, create and own buildkit cache dirs
RUN rm -f /etc/apt/apt.conf.d/docker-clean \
  && echo 'Binary::apt::APT::Keep-Downloaded-Packages "true";' > /etc/apt/apt.conf.d/keep-cache \
  && mkdir -p \
    /var/cache/buildkit/pip \
    /var/cache/buildkit/poetry

# Add dependencies & do setup
# NOTE: tini is so stable an update would probably only be to fix a security patch. I'm leaving it updated.
RUN --mount=type=tmpfs,destination=/tmp \
  --mount=type=cache,target=/var/cache/apt,sharing=locked \
  --mount=type=cache,target=/var/lib/apt,sharing=locked \
  groupadd --gid $USER_GID $USERNAME \
  && useradd --uid $USER_UID --gid $USER_GID -m $USERNAME \
  && apt-get update -y \
  && apt-get install -y --no-install-recommends \
  tini \
  ca-certificates \
  \
  python3-dev \
  \
  python3-poetry \
  git \
  ffmpeg \
  \
  gcc \
  gcc-12 \
  g++ \
  pkg-config \
  cmake \
  \
  libfreetype-dev \
  libjpeg-dev \
  libxml2 \
  libcairo2-dev

# Safe working directory for our user
WORKDIR /app
RUN chown -R $USERNAME:$USERNAME /app \
  && chown -R $USER_UID:$USER_GID /var/cache/buildkit

# Switch to our user (mainly for security)
USER $USERNAME

# Copy packaging files
COPY poetry.lock pyproject.toml /app/

# Download dependencies and setup venv
RUN --mount=type=tmpfs,destination=/tmp \
  --mount=type=cache,target=/var/cache/buildkit/pip,uid=$USER_UID,gid=$USER_GID \
  --mount=type=cache,target=/var/cache/buildkit/poetry,uid=$USER_UID,gid=$USER_GID \
  poetry install --only main --no-interaction --no-ansi --no-root

# Copy in rest of project excluding packaging files
COPY . /app

# Run
ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["poetry", "run", "python", "src/main.py"]
