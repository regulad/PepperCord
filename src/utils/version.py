import os
from typing import cast
from git import Repo, GitCommandError

GIT_REPO = Repo()


def get_version() -> tuple[str, str | None]:
    """Get the current version of the bot."""
    if os.path.exists("/.dockerenv") and "PEPPERCORD_DOCKER_VERSION" in os.environ:
        return os.environ["PEPPERCORD_DOCKER_VERSION"], (
            "debug" if "PEPPERCORD_DEBUG" in os.environ else None
        )
    try:
        version = cast(str, GIT_REPO.git.describe("--tags", "--abbrev=0"))
        commit = GIT_REPO.head.commit.hexsha[:7]
        return version, commit
    except GitCommandError:
        return "unknown", "unknown"


__all__ = ("get_version",)
