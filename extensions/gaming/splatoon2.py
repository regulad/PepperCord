from typing import Any, Type, Literal

from aiohttp import ClientSession
from discord.ext import tasks
from discord.ext.commands import Cog, CheckFailure

from utils.bots import BOT_TYPES, CustomContext


REGION_LITERAL: Type = Literal["na", "eu", "jp"]


class Splatoon2(Cog):
    """
    Get information about the current status of Splatoon 2.
    Powered by https://splatoon2.ink/ and https://splatoonwiki.org/wiki/
    """

    def __init__(self, bot: BOT_TYPES) -> None:
        self.bot: BOT_TYPES = bot
        self.cs: ClientSession | None = None

        self.cached_schedules: Any | None = None
        self.cached_coop_schedules: Any | None = None
        self.cached_merchandises: Any | None = None
        self.cached_festivals: Any | None = None
        self.cached_timeline: Any | None = None

    @tasks.loop(hours=1)
    async def update_cache(self) -> None:
        # https://github.com/misenhower/splatoon2.ink/wiki/Data-access-policy recommends caching, so we will cache.
        if self.cs is not None and not self.cs.closed:
            async with self.cs.get("https://splatoon2.ink/data/schedules.json") as resp:
                self.cached_schedules = await resp.json()
            async with self.cs.get("https://splatoon2.ink/data/coop-schedules.json") as resp:
                self.cached_coop_schedules = await resp.json()
            async with self.cs.get("https://splatoon2.ink/data/merchandises.json") as resp:
                self.cached_merchandises = await resp.json()
            async with self.cs.get("https://splatoon2.ink/data/festivals.json") as resp:
                self.cached_festivals = await resp.json()
            async with self.cs.get("https://splatoon2.ink/data/timeline.json") as resp:
                self.cached_timeline = await resp.json()
            # TODO: find the useful parts of this data

    async def get_splatfest_ranking(self, region: REGION_LITERAL, festival_id: str) -> Any:
        async with self.cs.get(f"https://splatoon2.ink/data/festivals/{region}-{festival_id}-rankings.json") as resp:
            return await resp.json()

    @property
    def is_ready(self) -> bool:
        return all(
            (
                self.cached_schedules is not None,
                self.cached_coop_schedules is not None,
                self.cached_merchandises is not None,
                self.cached_festivals is not None,
                self.cached_timeline is not None
            )
        )

    async def cog_check(self, ctx: CustomContext) -> bool:
        if self.is_ready:
            return True
        else:
            raise CheckFailure("We are still preparing, hold on! The cache is being populated.")

    @Cog.listener()
    async def on_ready(self) -> None:
        self.update_cache.start()

    async def cog_load(self) -> None:
        self.cs = ClientSession(
            headers={"User-Agent": "PepperCord/1.0 https://github.com/regulad/PepperCord @regulad#7959"})

    async def cog_unload(self) -> None:
        if self.cs is not None and not self.cs.closed:
            await self.cs.close()
        if self.update_cache.is_running():
            self.update_cache.cancel()

    # TODO: All of this. Maybe. Going to finish all of the Splatoon 3 stuff first, though.


async def setup(bot: BOT_TYPES) -> None:
    await bot.add_cog(Splatoon2(bot))
