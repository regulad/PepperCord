from os.path import splitext
from io import BytesIO

import discord
from discord.ext import commands
from aiohttp import ClientSession
from evb import AsyncEditVideoBotSession


class NoMedia(Exception):
    pass


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
    async def edit(self, ctx, *, evb_commands: str) -> None:
        async with ctx.typing():
            if not (ctx.message.embeds or ctx.message.attachments):
                if ctx.message.reference:
                    message: discord.Message = ctx.message.reference.resolved
                else:
                    messages = await ctx.channel.history(before=ctx.message.created_at, limit=1).flatten()
                    message: discord.Message = messages[0]
            else:
                message: discord.Message = ctx.message

            if message.embeds and message.embeds[0].type == "rich":
                embed: discord.Embed = message.embeds[0]

                media_url = embed.url

                extension = splitext(media_url)[1].strip(".")
            elif message.attachments:
                attachment: discord.Attachment = message.attachments[0]

                media_url = attachment.url
            else:
                raise NoMedia

            if media_url is None:
                raise NoMedia

            extension = splitext(media_url)[1].strip(".")

            async with self.client_session.get(media_url) as resp:
                attachment_bytes = await resp.read()

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
