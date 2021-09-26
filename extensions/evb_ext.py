import asyncio
from io import BytesIO
from os.path import splitext
from typing import Optional

import discord
import evb
from discord.ext import commands
from evb import AsyncEditVideoBotSession
from aiohttp import ClientSession

from utils.attachments import find_url_recurse
from utils.bots import CustomContext, BOT_TYPES


class EditVideoBot(commands.Cog):
    """Commands for editing media using the EditVideoBot API."""

    def __init__(self, bot: BOT_TYPES):
        self.bot = bot

        self.evb_session: AsyncEditVideoBotSession = AsyncEditVideoBotSession.from_api_key(
            self.bot.config.get("PEPPERCORD_EVB"))
        self.client_session: Optional[ClientSession] = None

        self.cooldown = commands.CooldownMapping.from_cooldown(
            30, 86400, commands.BucketType.default
        )

    def cog_unload(self) -> None:
        asyncio.create_task(self.client_session.close())
        asyncio.create_task(self.evb_session.close())  # Not ideal.

    async def cog_before_invoke(self, ctx: CustomContext) -> None:
        if self.client_session is None:
            self.client_session = ClientSession()
        if self.evb_session._client_session is None or self.evb_session.closed:
            await self.evb_session.open(self.client_session)

    async def cog_check(self, ctx: CustomContext) -> bool:
        cooldown: commands.Cooldown = self.cooldown.get_bucket(ctx.message)
        retry_after: float = cooldown.update_rate_limit()

        if retry_after:
            raise commands.CommandOnCooldown(cooldown, retry_after, self.cooldown.type)
        else:
            return True

    @commands.command(
        name="edit",
        aliases=["evb"],
        description="Edit supported media using EditVideoBot.",
        usage="<Commands>",
    )
    async def edit(self, ctx: CustomContext, *, evb_commands: str) -> None:
        async with ctx.typing():
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

            file = discord.File(BytesIO(await response.download()), f"output{splitext(response.media_url)[1]}")
            await ctx.reply(files=[file])

    @commands.command(
        name="editsleft",
        aliases=["evbleft"],
        description="Gets the amount of edits that can still be made today.\n"
                    "This number is global.",
    )
    async def left(self, ctx: CustomContext) -> None:
        async with ctx.typing():
            stats = await self.evb_session.stats()

            await ctx.send(stats.remaining_daily_requests)


def setup(bot: BOT_TYPES):
    if bot.config.get("PEPPERCORD_EVB") is not None:
        bot.add_cog(EditVideoBot(bot))
