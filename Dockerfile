# hadolint global ignore=DL3008  # DL3008 is fit for us, python3-dev is pinned by the image's repositories; and ca-certificates should always be the newest bc CoT

# deno is needed for yt-dlp
FROM denoland/deno:bin-2.3.1 AS deno
FROM python:3.14.0-slim-trixie

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
  PIP_NO_CACHE_DIR=1 \
  PIP_DISABLE_PIP_VERSION_CHECK=1 \
  PIP_DEFAULT_TIMEOUT=100 \
  POETRY_HOME=/opt/poetry \
  POETRY_VERSION=1.8.2

ARG USERNAME=peppercord
ARG USER_UID=1008
ARG USER_GID=$USER_UID

# Add dependencies & do setup
COPY --from=deno /deno /usr/local/bin/deno
RUN --mount=type=tmpfs,destination=/tmp \
  groupadd --gid $USER_GID $USERNAME \
  && useradd --uid $USER_UID --gid $USER_GID -m $USERNAME \
  && apt-get update -y \
  && apt-get install -y --no-install-recommends \
  tini \
  \
  python3-dev \
  ca-certificates \
  \
  python3-poetry=2.1.2+dfsg-1 \
  git=1:2.47.3-0+deb13u1 \
  ffmpeg=7:7.1.2-0+deb13u1 \
  \
  gcc=4:14.2.0-1 \
  gcc-12=12.4.0-5 \
  g++=4:14.2.0-1 \
  pkg-config=1.8.1-4 \
  cmake=3.31.6-2 \
  \
  libfreetype-dev=2.13.3+dfsg-1 \
  libjpeg-dev=1:2.1.5-4 \
  libxml2=2.12.7+dfsg+really2.9.14-2.1+deb13u1 \
  libcairo2-dev=1.18.4-1+b1 \
  && rm -rf /var/lib/apt/lists/*
# NOTE: tini is so stable an update would probably only be to fix a security patch. I'm leaving it updated.

# Safe working directory for our user
WORKDIR /app
RUN chown -R $USERNAME:$USERNAME /app

# Switch to our user (mainly for security)
USER $USERNAME

# Copy packaging files
COPY poetry.lock pyproject.toml /app/

# Download dependencies and setup venv
RUN --mount=type=tmpfs,destination=/tmp \
  poetry install --only main --no-interaction --no-ansi --no-root

# Copy in rest of project excluding packaging files
COPY . /app

# Run
ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["poetry", "run", "python", "src/main.py"]
