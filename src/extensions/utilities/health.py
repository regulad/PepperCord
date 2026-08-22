import logging
from datetime import UTC, datetime
from math import isnan
from typing import Final

from aiohttp import web
from discord.ext.commands import Cog
from pymongo.errors import PyMongoError

from utils.bots.bot import CustomBot
from utils.version import get_version

logger: logging.Logger = logging.getLogger(__name__)

HEALTH_HOST: Final[str] = "0.0.0.0"
# Must be >1024: the container runs as an unprivileged user (UID 1008), not root.
HEALTH_PORT: Final[int] = 8080


class Health(Cog):
    """
    Hoists an HTTP server exposing a health check endpoint for external supervisors.
    No user-facing commands.
    """

    def __init__(self, bot: CustomBot) -> None:
        self.bot: CustomBot = bot

        self._app: web.Application | None = None
        self._runner: web.AppRunner | None = None
        self._site: web.TCPSite | None = None

        self._draining: bool = False

    async def cog_load(self) -> None:
        self._app = web.Application()
        self._app.add_routes([web.get("/health", self.handle_health)])

        # access_log=None: a probe polled every few seconds would otherwise flood the log.
        self._runner = web.AppRunner(self._app, access_log=None)
        await self._runner.setup()

        self._site = web.TCPSite(self._runner, HEALTH_HOST, HEALTH_PORT)
        await self._site.start()

        logger.info(f"Health endpoint listening on {HEALTH_HOST}:{HEALTH_PORT}/health.")

    async def cog_unload(self) -> None:
        if self._runner is not None:
            await self._runner.cleanup()
            self._runner = None
        self._site = None
        self._app = None

    @Cog.listener("on_graceful_shutdown")
    async def begin_draining(self) -> None:
        # Dispatched before the bot disconnects, so a load balancer can pull this
        # instance out of rotation while it is still able to answer.
        self._draining = True

    async def handle_health(self, request: web.Request) -> web.Response:
        """
        Reports on the two subsystems the bot cannot function without.

        503 is a lifecycle state (not serving yet, or no longer serving).
        500 means a dependency that should be working is broken.
        """

        if self._draining:
            return web.json_response({"status": "draining"}, status=503)

        bot_user = self.bot.user
        if not self.bot.is_ready() or bot_user is None:
            return web.json_response({"status": "starting"}, status=503)

        # Client.latency is nan whenever the gateway websocket is absent. Since the
        # readiness gate above already caught "never connected", a nan here means the
        # socket was established and has since been lost.
        latency = self.bot.latency
        if isnan(latency):
            return web.json_response(
                {"status": "unhealthy", "gateway": "disconnected"}, status=500
            )
        latency_ms = round(latency * 1000, 2)

        try:
            # get_user_document reads the document; update_db upserts it and reads it
            # back, so serving this request is a real round trip to the database.
            document = await self.bot.get_user_document(bot_user)
            await document.update_db(
                {
                    "$set": {
                        "last_health_check": datetime.now(UTC),
                        "gateway_latency": latency_ms,
                    },
                    "$inc": {"health_checks": 1},
                }
            )
            health_checks = await document.safe_get("health_checks", 0)
        except PyMongoError:
            logger.exception("Health check could not reach the database.")
            return web.json_response(
                {"status": "unhealthy", "database": "error"}, status=500
            )

        version, commit = get_version()

        return web.json_response(
            {
                "status": "ok",
                "version": version,
                "commit": commit,
                "gateway": {
                    "latency_ms": latency_ms,
                    "shard_id": self.bot.shard_id,
                    "guilds": len(self.bot.guilds),
                    "users": self.bot.perceivable_users,
                },
                "database": {"health_checks": health_checks},
            }
        )


async def setup(bot: CustomBot) -> None:
    await bot.add_cog(Health(bot))
