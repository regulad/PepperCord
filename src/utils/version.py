import os
from typing import cast


def get_version() -> tuple[str, str | None]:
    """
    Get the bot's version and short commit hash.

    The Docker image carries both in its environment: it is built from a git tree without the .git directory, and
    ships without the git binary. Anywhere else they come from the local checkout.
    """
    if "PEPPERCORD_DOCKER_VERSION" in os.environ:
        commit = os.environ.get("PEPPERCORD_GIT_SHA")
        return os.environ["PEPPERCORD_DOCKER_VERSION"], commit[:7] if commit else None

    # Imported here, not at the top: GitPython refuses to import at all when there is no git binary.
    try:
        from git import GitCommandError, InvalidGitRepositoryError, Repo
    except ImportError:
        return "unknown", "unknown"

    try:
        repo = Repo()
        version = cast(str, repo.git.describe("--tags", "--abbrev=0"))
        return version, repo.head.commit.hexsha[:7]
    except (GitCommandError, InvalidGitRepositoryError):
        return "unknown", "unknown"


__all__ = ("get_version",)
