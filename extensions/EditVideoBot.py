from os.path import splitext
from io import BytesIO

import discord
from discord.ext import commands
from aiohttp import ClientSession
from evb import AsyncEditVideoBotSession

from utils.attachments import find_url_recurse


class EditVideoBot(commands.Cog):
    """Commands for editing media using the EditVideoBot API."""

    def __init__(self, bot):
        self.bot = bot

        self.client_session = ClientSession()
        self.evb_session = AsyncEditVideoBotSession.from_api_key(
            self.bot.config.get("PEPPERCORD_EVB"),
            client_session=self.client_session,
        )

        self.cooldown = commands.CooldownMapping.from_cooldown(30, 86400, commands.BucketType.default)

    async def cog_check(self, ctx):
        cooldown: commands.Cooldown = self.cooldown.get_bucket(ctx.message)
        retry_after: float = cooldown.update_rate_limit()

        if retry_after:
            raise commands.CommandOnCooldown(cooldown, retry_after)
        else:
            return True

    @commands.command(
        name="edit",
        aliases=["evb"],
        brief="Edit media using EditVideoBot.",
        description="Edit supported media using EditVideoBot.",
        usage="<Commands>",
    )
    async def edit(self, ctx, *, evb_commands: str):
        async with ctx.typing():
            url, source = await find_url_recurse(ctx.message)

            async with self.client_session.get(url) as resp:
                attachment_bytes = await resp.read()

            if isinstance(source, discord.Embed) and source.type == "gifv":  # deprecated!... kinda
                extension: str = "mp4"
            else:
                extension: str = splitext(url)[1].strip(".")

            output_bytes, response = await self.evb_session.edit(attachment_bytes, evb_commands, extension)

            file = discord.File(BytesIO(output_bytes), f"output{splitext(response.media_url)[1]}")
            await ctx.send(files=[file])

    @commands.command(
        name="editsleft",
        aliases=["evbleft"],
        brief="Gets the number of edits remaining today.",
        description="Gets the amount of edits that can still be made today.",
    )
    async def left(self, ctx):
        async with ctx.typing():
            stats = await self.evb_session.stats()

            await ctx.send(stats.remaining_daily_requests)


def setup(bot):
    if bot.config.get("PEPPERCORD_EVB") is not None:
        bot.add_cog(EditVideoBot(bot))
