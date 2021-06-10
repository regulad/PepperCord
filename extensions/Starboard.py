import asyncio
import typing

import discord
from discord.ext import commands

from utils import checks, bots, database


class AlreadyPinned(Exception):
    pass


async def send_star(document: database.Document, message: discord.Message):
    # Get channel
    try:
        send_channel = message.guild.get_channel(document.setdefault("starboard", {})["channel"])
    except KeyError:
        raise bots.NotConfigured
    # Get already pinned messages
    messages = document.setdefault("starboard", {}).get("messages", [])
    if message.id in messages:
        raise AlreadyPinned
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
    await document.update_db({"$push": {"starboard.messages": message.id}})  # Should use a transaction or smth


class Starboard(commands.Cog):
    """Alternative way to "pin" messages."""

    def __init__(self, bot):
        self.bot = bot

    async def cog_check(self, ctx):
        if not ctx.guild:
            raise commands.NoPrivateMessage
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
            await send_star(ctx.guild_document, ctx.message)
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
            raise bots.NotConfigured
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
            raise bots.NotConfigured
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
        if ctx.guild_document.get("starboard") is None:
            raise bots.NotConfigured
        else:
            await ctx.guild_document.update_db({"$unset": {"starboard": 1}})

    @sconfig.command(
        name="channel",
        aliases=["board"],
        brief="Sets channel.",
        description="Sets channel to be used as the starboard.",
        usage="[Channel]",
    )
    async def schannel(self, ctx, *, channel: typing.Optional[discord.TextChannel]):
        channel = channel or ctx.channel
        await ctx.guild_document.update_db({"$set": {"starboard.channel": channel.id}})

    @sconfig.command(
        name="emoji",
        brief="Sets emoji people can react with to star a message.",
        description="Sets emoji people can react with to star a message. Defaults to ⭐. If a manager placed the reaction, it will get pinned to the starboard instantly.",
        usage="<Emoji>",
    )
    async def semoji(self, ctx, *, emoji: typing.Union[discord.Emoji, discord.PartialEmoji, str]):
        if isinstance(emoji, (discord.Emoji, discord.PartialEmoji)):
            emoji = emoji.name
        await ctx.guild_document.update_db({"$set": {"starboard.emoji": emoji}})

    @sconfig.command(
        name="threshold",
        brief="Sets the reaction threshold for being pinned.",
        description="Sets the reaction threshold for being pinned. Defaults to 3.",
        usage="<Threshold>",
    )
    async def sthreshold(self, ctx, *, threshold: int):
        await ctx.guild_document.update_db({"$set": {"starboard.threshold": threshold}})

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
        await send_star(ctx.guild_document, message)

    @starboard.command(
        name="convert",
        brief="Converts pins in channel to pins on starboard.",
        description="Converts pins in channel to pins on starboard. Does not unpin channels.",
    )
    async def sconvert(self, ctx, *, channel: typing.Optional[discord.TextChannel]):
        channel = channel or ctx.channel
        for pin in (await channel.pins())[::-1]:
            await send_star(ctx.guild_document, pin)
            await asyncio.sleep(1)  # Prevents rate-limiting


def setup(bot):
    bot.add_cog(Starboard(bot))
