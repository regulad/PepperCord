import asyncio
import typing

import discord
from discord.ext import commands

from utils import checks, errors
from utils.database import Document


async def _sendstar(document: Document, message: discord.Message):
    # Get channel
    try:
        send_channel = message.guild.get_channel(document.setdefault("starboard", {})["channel"])
    except KeyError:
        raise errors.NotConfigured()
    # Get already pinned messages
    messages = document.setdefault("starboard", {}).setdefault("messages", [])
    if message.id in messages:
        raise errors.AlreadyPinned()
    # Setup embed
    embed = discord.Embed(colour=message.author.colour, description=message.content).set_author(
        name=f"Sent by {message.author.display_name} in {message.channel.name}",
        url=message.jump_url,
        icon_url=message.author.avatar_url,
    )
    # Setup attachments
    if message.attachments:
        attachment = message.attachments[0]
        if (
            attachment.content_type == "image/png"
            or attachment.content_type == "image/jpeg"
            or attachment.content_type == "image/gif"
            or attachment.content_type == "image/webp"
        ):
            embed.set_image(url=attachment.url)
    elif message.embeds:
        user_embed = message.embeds[0]
        if user_embed.type == "video" or embed.type == "rich":
            embed.set_image(url=user_embed.url)
    await send_channel.send(embed=embed)
    messages.append(message.id)


class Starboard(commands.Cog):
    """Alternative way to "pin" messages."""

    def __init__(self, bot):
        self.bot = bot

    async def cog_check(self, ctx):
        if not ctx.guild:
            raise commands.NoPrivateMessage()
        return True

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        # Setup
        if payload.guild_id is None or payload.user_id == self.bot.user.id:
            return
        guild = self.bot.get_guild(payload.guild_id)
        ctx = await self.bot.get_context(
            await guild.get_channel(payload.channel_id).get_partial_message(payload.message_id).fetch()
        )
        # Get documents
        send_emoji = ctx.guild_document.setdefault("starboard", {}).setdefault("emoji", "⭐")
        threshold = ctx.guild_document.setdefault("starboard", {}).setdefault("threshold", 3)
        # See if reaction count meets threshold
        react_count = None
        for reaction in ctx.message.reactions:
            if isinstance(reaction.emoji, (discord.Emoji, discord.PartialEmoji)):
                reaction_name = reaction.emoji.name
            else:
                reaction_name = reaction.emoji
            if reaction_name == send_emoji:
                react_count = reaction.count
                break
        if react_count is None:
            return
        if react_count >= threshold:
            await _sendstar(ctx.guild_document, ctx.message)
            await ctx.guild_document.replace_db()
        else:
            return

    @commands.group(
        invoke_without_command=True,
        case_insensitive=True,
        name="starboard",
        aliases=["sb", "sboard"],
        description="Starboards are an alternative to pinning messsages.",
        brief="Starboard setup.",
    )
    async def starboard(self, ctx):
        try:
            send_channel = ctx.guild.get_channel(ctx.guild_document.setdefault("starboard", {})["channel"])
        except KeyError:
            raise errors.NotConfigured()
        else:
            await ctx.send(send_channel.mention)

    @starboard.group(
        invoke_without_command=True,
        case_insensitive=True,
        name="config",
        aliases=["setup"],
        brief="Starboard setup.",
        description="Configures Starboard",
    )
    @commands.check(checks.is_admin)
    async def sconfig(self, ctx):
        try:
            send_channel = ctx.guild.get_channel(ctx.guild_document.setdefault("starboard", {})["channel"])
        except KeyError:
            raise errors.NotConfigured()
        try:
            emoji = await commands.EmojiConverter().convert(
                ctx, ctx.guild_document.setdefault("starboard", {}).setdefault("emoji", "⭐")
            )
        except discord.NotFound:
            emoji = ctx.guild_document.setdefault("starboard", {}).setdefault("emoji", "⭐")
        threshold = ctx.guild_document.setdefault("starboard", {}).setdefault("threshold", 3)
        embed = (
            discord.Embed(title="Starboard Config")
            .add_field(name="Channel:", value=send_channel.mention)
            .add_field(name="Emoji:", value=emoji)
            .add_field(name="Threshold:", value=threshold)
        )
        await ctx.send(embed=embed)

    @sconfig.command(
        name="disable",
        aliases=["off", "delete"],
        brief="Deletes starboard data.",
        description="Deletes all starboard data, including config and message cache.",
    )
    async def sdisable(self, ctx):
        try:
            del ctx.guild_document["starboard"]
        except KeyError:
            raise errors.NotConfigured()
        await ctx.guild_document.replace_db()

    @sconfig.command(
        name="channel",
        aliases=["board"],
        brief="Sets channel.",
        description="Sets channel to be used as the starboard.",
        usage="[Channel]",
    )
    async def schannel(self, ctx, *, channel: typing.Optional[discord.TextChannel]):
        channel = channel or ctx.channel
        ctx.guild_document.setdefault("starboard", {})["channel"] = channel.id
        await ctx.guild_document.replace_db()

    @sconfig.command(
        name="emoji",
        brief="Sets emoji people can react with to star a message.",
        description="Sets emoji people can react with to star a message. Defaults to ⭐. If a manager placed the reaction, it will get pinned to the starboard instantly.",
        usage="<Emoji>",
    )
    async def semoji(self, ctx, *, emoji: typing.Union[discord.Emoji, discord.PartialEmoji, str]):
        if isinstance(emoji, (discord.Emoji, discord.PartialEmoji)):
            emoji = emoji.name
        ctx.guild_document.setdefault("starboard", {})["emoji"] = emoji
        await ctx.guild_document.replace_db()

    @sconfig.command(
        name="threshold",
        brief="Sets the reaction threshold for being pinned.",
        description="Sets the reaction threshold for being pinned. Defaults to 3.",
        usage="<Threshold>",
    )
    async def sthreshold(self, ctx, *, threshold: int):
        ctx.guild_document.setdefault("starboard", {})["threshold"] = threshold
        await ctx.guild_document.replace_db()

    @starboard.command(
        name="pin",
        brief="Pins message to the starboard.",
        description="Pins a message of your choice to the starboard. You can also reply to a message with the command to pin it.",
        usage="[Message]",
    )
    async def spin(self, ctx, *, message: typing.Optional[typing.Union[discord.Message, discord.PartialMessage]]):
        if not isinstance(message, (discord.Message, discord.PartialMessage)):
            if ctx.message.reference:
                message = ctx.message.reference.resolved
            else:
                messages = await ctx.channel.history(before=ctx.message.created_at, limit=1).flatten()
                message = messages[0]
        await _sendstar(ctx.guild_document, message)
        await ctx.guild_document.replace_db()

    @starboard.command(
        name="convert",
        brief="Converts pins in channel to pins on starboard.",
        description="Converts pins in channel to pins on starboard. Does not unpin channels.",
    )
    async def sconvert(self, ctx, *, channel: typing.Optional[discord.TextChannel]):
        channel = channel or ctx.channel
        for pin in (await channel.pins())[::-1]:
            await _sendstar(ctx.guild_document, pin)
            await asyncio.sleep(1)  # Prevents rate-limiting
        await ctx.guild_document.replace_db()


def setup(bot):
    bot.add_cog(Starboard(bot))
