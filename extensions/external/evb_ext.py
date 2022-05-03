from io import BytesIO
from os.path import splitext

import discord
import evb
from aiohttp import ClientSession
from discord.ext import commands
from discord.ext.commands import hybrid_command
from evb import AsyncEditVideoBotSession, StatsResponse

from utils.attachments import find_url_recurse
from utils.bots import CustomContext, BOT_TYPES


class EditVideoBot(commands.Cog):
    """Commands for editing media using the EditVideoBot API."""

    def __init__(self, bot: BOT_TYPES):
        self.bot: BOT_TYPES = bot

        self.evb_session: AsyncEditVideoBotSession = (
            AsyncEditVideoBotSession.from_api_key(self.bot.config.get("PEPPERCORD_EVB"))
        )

        self.cooldown = commands.CooldownMapping.from_cooldown(
            30, 86400, commands.BucketType.default
        )

        self.client_session: ClientSession | None = None

    async def cog_load(self) -> None:
        self.client_session = ClientSession()
        await self.evb_session.open(client_session=self.client_session)

    async def cog_unload(self) -> None:
        await self.evb_session.close()

    async def cog_check(self, ctx: CustomContext) -> bool:
        cooldown: commands.Cooldown = self.cooldown.get_bucket(ctx.message)
        retry_after: float = cooldown.update_rate_limit()

        if retry_after:
            raise commands.CommandOnCooldown(cooldown, retry_after, self.cooldown.type)
        else:
            return True

    @hybrid_command()
    @describe(
        evb_commands="The commands that will be applied to the video. You can find a list here: https://bit.ly/3GBkKqx."
    )
    async def edit(self, ctx: CustomContext, *, evb_commands: str) -> None:
        """Edit media with EditVideoBot."""

        await ctx.defer()

        url, source = await find_url_recurse(ctx.message)

        async with self.client_session.get(url) as resp:
            attachment_bytes = await resp.read()

        if (
                isinstance(source, discord.Embed) and source.type == "gifv"
        ):  # deprecated!... kinda
            extension: str = "mp4"
        else:
            extension: str = splitext(url)[1].strip(".")

        response: evb.EditResponse = await self.evb_session.edit(
            attachment_bytes, evb_commands, extension
        )

        file = discord.File(
            BytesIO(await response.download()),
            f"output{splitext(response.media_url)[1]}",
        )
        await ctx.send(files=[file])

    @hybrid_command()
    async def editsleft(self, ctx: CustomContext) -> None:
        """Shows the number of remaining EditVideoBot edits."""
        await ctx.defer(ephemeral=True)

        stats: StatsResponse = await self.evb_session.stats()

        await ctx.send(stats.remaining_daily_requests, ephemeral=True)


async def setup(bot: BOT_TYPES) -> None:
    if bot.config.get("PEPPERCORD_EVB") is not None:
        await bot.add_cog(EditVideoBot(bot))
