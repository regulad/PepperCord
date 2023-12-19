FROM python:3.11.2-slim-bullseye

LABEL name="peppercord" \
  version="9.2.0" \
  maintainer="Parker Wahle <regulad@regulad.xyz>"

ENV DEBIAN_FRONTEND=noninteractive \
  PYTHONFAULTHANDLER=1 \
  PYTHONUNBUFFERED=1 \
  PYTHONHASHSEED=random \
  PIP_NO_CACHE_DIR=off \
  PIP_DISABLE_PIP_VERSION_CHECK=on \
  PIP_DEFAULT_TIMEOUT=100 \
  POETRY_HOME=/opt/poetry \
  POETRY_VERSION=1.3.1

ARG USERNAME=peppercord
ARG USER_UID=1008
ARG USER_GID=$USER_UID

# Add dependencies & do setup
RUN groupadd --gid $USER_GID $USERNAME \
    && useradd --uid $USER_UID --gid $USER_GID -m $USERNAME \
    && apt update -y \
    && apt upgrade -y \
    && apt install -y curl git ffmpeg gcc python3-dev g++ \
    && apt autoremove -y \
    && apt clean

# Install poetry
RUN curl -sSL https://install.python-poetry.org | python3 -

# Safe working directory for our user
WORKDIR /app
RUN chown -R $USERNAME:$USERNAME /app

# Switch to our user (mainly for security)
USER $USERNAME

# Copy packaging files
COPY poetry.lock pyproject.toml /app/

# Download dependencies and setup venv
RUN /opt/poetry/bin/poetry install --only main --no-interaction --no-ansi --no-root

# Copy in rest of project excluding packaging files
COPY . /app

# Run
CMD ["/opt/poetry/bin/poetry", "run", "python", "src/main.py"]
