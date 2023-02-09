FROM python:3.11-slim

LABEL name="peppercord" \
  version="9.0.0" \
  maintainer="Parker Wahle"

ENV DEBIAN_FRONTEND=noninteractive \
  PYTHONFAULTHANDLER=1 \
  PYTHONUNBUFFERED=1 \
  PYTHONHASHSEED=random \
  PIP_NO_CACHE_DIR=off \
  PIP_DISABLE_PIP_VERSION_CHECK=on \
  PIP_DEFAULT_TIMEOUT=100 \
  POETRY_HOME=/opt/poetry \
  POETRY_VERSION=1.3.1

# Add dependencies
RUN apt update && apt upgrade -y && apt install -y curl git ffmpeg gcc python3-dev g++

# Install poetry
RUN curl -sSL https://install.python-poetry.org | python3 -

# Safe working directory
WORKDIR /app

# Copy dependencies
COPY poetry.lock pyproject.toml /app/

# Project initialization:
RUN /opt/poetry/bin/poetry install --only main --no-interaction --no-ansi --no-root

# Creating folders, and files for a project:
COPY . /app

# TODO: Configure environment variables

# Startup command:
CMD ["/opt/poetry/bin/poetry", "run", "python", "src/main.py"]
