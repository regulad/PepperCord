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

    @commands.command(
        name="edit",
        aliases=["evb"],
        brief="Edit media using EditVideoBot.",
        description="Edit supported media using EditVideoBot.",
        usage="<Commands>",
    )
    @commands.cooldown(30, 86400, commands.BucketType.default)
    @commands.cooldown(1, 90, commands.BucketType.channel)
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

                if extension == "mp4" or extension == "gif" or extension == "mov" or extension == "webm":
                    out_extension = "mp4"
                elif extension == "png" or extension == "jpeg" or extension == "jpg":
                    out_extension = "png"
                else:
                    raise NoMedia
            elif message.attachments:
                attachment: discord.Attachment = message.attachments[0]

                media_url = attachment.url

                if attachment.content_type.endswith("gif") or attachment.content_type.startswith("video"):
                    out_extension = "mp4"
                elif attachment.content_type.startswith("image"):
                    out_extension = "png"
                else:
                    raise NoMedia
            else:
                raise NoMedia

            if "togif" in evb_commands:
                out_extension = "gif"

            if out_extension is None or media_url is None:
                raise NoMedia

            extension = splitext(media_url)[1].strip(".")

            async with self.client_session.get(media_url) as resp:
                attachment_bytes = await resp.read()

                output_bytes = await self.evb_session.edit(attachment_bytes, evb_commands, extension)

            file = discord.File(BytesIO(output_bytes), f"output.{out_extension}")
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
