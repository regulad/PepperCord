"""Error, log and trace reporting to Sentry."""

import logging
from collections.abc import Mapping
from typing import Any

import sentry_sdk

from utils.version import get_version

logger: logging.Logger = logging.getLogger(__name__)


def init_sentry(config: Mapping[str, str], *, debug: bool) -> None:
    """
    Start reporting to Sentry when PEPPERCORD_SENTRY_DSN is set. Without it, errors are only logged.

    The default logging integration turns every record at ERROR or above into a Sentry event. That covers the
    failures discord.py logs itself: background task loops, the app command tree, and unretrieved task exceptions.
    Records at INFO and above are also sent to Sentry Logs.

    Each command is traced as a transaction by CustomContext; see start_sentry_transaction.
    """
    dsn = config.get("PEPPERCORD_SENTRY_DSN")
    if not dsn:
        logger.info("PEPPERCORD_SENTRY_DSN is not set, so errors will only be logged.")
        return

    traces_sample_rate = 1.0 if debug else 0.1

    def traces_sampler(sampling_context: dict[str, Any]) -> float:
        # The health endpoint is the only aiohttp server. Its probes would otherwise use up the trace quota.
        if "aiohttp_request" in sampling_context:
            return 0.0
        return traces_sample_rate

    version, _ = get_version()
    sentry_sdk.init(
        dsn=dsn,
        release=f"peppercord@{version}",
        environment="development" if debug else "production",
        traces_sampler=traces_sampler,
        enable_logs=True,
        # Events carry the user's ID and the guild's ID, set explicitly by CustomContext.
        # Nothing else that identifies a person is collected.
        send_default_pii=False,
    )
    logger.info(f"Reporting to Sentry, tracing {traces_sample_rate:.0%} of commands.")


__all__ = ("init_sentry",)
