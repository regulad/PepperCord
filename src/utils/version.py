import os
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from git import Repo

# The Docker image carries the version and commit in its environment: it is built from a git tree without the .git
# directory, and ships without the git binary. Anywhere else they come from the local checkout.
IN_DOCKER_IMAGE = "PEPPERCORD_DOCKER_VERSION" in os.environ


def _local_repo() -> "Repo | None":
    # Imported here, not at the top: GitPython refuses to import at all when there is no git binary.
    try:
        from git import InvalidGitRepositoryError, Repo
    except ImportError:
        return None
    try:
        return Repo()
    except InvalidGitRepositoryError:
        return None


def get_commit() -> str | None:
    """Get the full hash of the commit the bot is running, or None if it can't be told."""
    if IN_DOCKER_IMAGE:
        return os.environ.get("PEPPERCORD_GIT_SHA") or None
    repo = _local_repo()
    return repo.head.commit.hexsha if repo is not None else None


def get_version() -> tuple[str, str | None]:
    """Get the bot's version and short commit hash."""
    commit = get_commit()
    short_commit = commit[:7] if commit else None
    if IN_DOCKER_IMAGE:
        return os.environ["PEPPERCORD_DOCKER_VERSION"], short_commit

    repo = _local_repo()
    if repo is None:
        return "unknown", "unknown"
    # Safe now: a repo only opens once GitPython has imported.
    from git import GitCommandError

    try:
        version = cast(str, repo.git.describe("--tags", "--abbrev=0"))
    except GitCommandError:
        version = "unknown"
    return version, short_commit or "unknown"


__all__ = ("get_commit", "get_version")
