"""Error, log and trace reporting to Sentry."""

import logging
from collections.abc import Mapping
from typing import Any

import sentry_sdk

from utils.version import get_commit, get_version

logger: logging.Logger = logging.getLogger(__name__)

# The regulad/peppercord project. A DSN only lets a client send events, so it isn't a secret.
DEFAULT_SENTRY_DSN = "https://10ed6456acbd2e281613ad4f2364d8da@o4506961510596608.ingest.us.sentry.io/4512439188258816"


def init_sentry(config: Mapping[str, str], *, debug: bool) -> None:
    """
    Start reporting to Sentry, to PEPPERCORD_SENTRY_DSN if it's set or to the PepperCord project if it isn't.
    Setting PEPPERCORD_SENTRY_DSN to an empty value turns reporting off, leaving errors only logged.

    The default logging integration turns every record at ERROR or above into a Sentry event. That covers the
    failures discord.py logs itself: background task loops, the app command tree, and unretrieved task exceptions.
    Records at INFO and above are also sent to Sentry Logs.

    Each command is traced as a transaction by CustomContext; see start_sentry_transaction.
    """
    dsn = config.get("PEPPERCORD_SENTRY_DSN", DEFAULT_SENTRY_DSN)
    if not dsn:
        logger.info("PEPPERCORD_SENTRY_DSN is empty, so errors will only be logged.")
        return

    traces_sample_rate = 1.0 if debug else 0.1

    def traces_sampler(sampling_context: dict[str, Any]) -> float:
        # The health endpoint is the only aiohttp server. Its probes would otherwise use up the trace quota.
        if "aiohttp_request" in sampling_context:
            return 0.0
        return traces_sample_rate

    # Releases are named by the raw commit hash, which is what docker-publish.yml creates them as.
    # Without a commit (no image metadata and no checkout), fall back to the version.
    release = get_commit() or f"peppercord@{get_version()[0]}"
    sentry_sdk.init(
        dsn=dsn,
        release=release,
        environment="development" if debug else "production",
        traces_sampler=traces_sampler,
        enable_logs=True,
        # Events carry the user's ID and the guild's ID, set explicitly by CustomContext.
        # Nothing else that identifies a person is collected.
        send_default_pii=False,
    )
    logger.info(f"Reporting to Sentry, tracing {traces_sample_rate:.0%} of commands.")


def identify_bot(bot_id: int) -> None:
    """
    Mark everything sent to Sentry from now on with the bot's user ID.

    Every instance reports to the same project by default, so this is how their events are told apart.
    Errors and transactions read tags; logs read attributes.
    """
    scope = sentry_sdk.get_global_scope()
    scope.set_tag("bot_id", str(bot_id))
    scope.set_attribute("bot_id", str(bot_id))


__all__ = ("init_sentry", "identify_bot")
