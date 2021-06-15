import asyncio
from typing import Optional, Union

import discord
from discord.ext import commands

from utils import checks, bots, database
from utils.attachments import find_url, NoMedia


class AlreadyPinned(Exception):
    pass


async def send_star(document: database.Document, message: discord.Message) -> discord.Message:
    send_channel_id: Optional[int] = document.get("starboard", {}).get("channel")

    if send_channel_id is None:
        raise bots.NotConfigured

    send_channel: discord.TextChannel = message.guild.get_channel(send_channel_id)

    messages = document.get("starboard", {}).get("messages", [])

    if message.id in messages:
        raise AlreadyPinned

    embed = discord.Embed(colour=message.author.colour, description=message.content).set_author(
        name=f"Sent by {message.author.display_name} in {message.channel.name}",
        url=message.jump_url,
        icon_url=message.author.avatar_url,
    )

    try:
        url, source = await find_url(message)
    except NoMedia:
        url, source = (None, None)
    else:
        if isinstance(source, discord.Attachment) and source.content_type.startswith("image"):
            embed.set_image(url=url)
        elif isinstance(source, discord.Embed) and source.type == "image":  # deprecated!... kinda
            embed.set_image(url=url)

    await document.update_db({"$push": {"starboard.messages": message.id}})
    return await send_channel.send(embed=embed)


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
        if payload.guild_id is None or payload.user_id == self.bot.user.id:
            return

        guild = self.bot.get_guild(payload.guild_id)
        ctx = await self.bot.get_context(
            await guild.get_channel(payload.channel_id).get_partial_message(payload.message_id).fetch()
        )

        send_emoji = ctx.guild_document.get("starboard", {}).get("emoji", "⭐")
        threshold = ctx.guild_document.get("starboard", {}).get("threshold", 3)

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
        if ctx.guild_document.get("starboard", {}).get("channe") is None:
            raise bots.NotConfigured
        else:
            await ctx.send(ctx.guild.get_channel(ctx.guild_document["starboard"]["channel"]).mention)

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
        if ctx.guild_document.get("starboard", {}).get("channel") is None:
            raise bots.NotConfigured

        try:
            emoji = await commands.EmojiConverter().convert(
                ctx, ctx.guild_document["starboard"].get("emoji", "⭐")
            )
        except discord.NotFound:
            emoji = ctx.guild_document["starboard"].get("emoji", "⭐")

        embed = (
            discord.Embed(title="Starboard Config")
            .add_field(name="Channel:", value=ctx.guild.get_channel(ctx.guild_document["starboard"]["channel"]).mention)
            .add_field(name="Emoji:", value=emoji)
            .add_field(name="Threshold:", value=ctx.guild_document["starboard"].get("threshold", 3))
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
    async def schannel(self, ctx, *, channel: Optional[discord.TextChannel]):
        channel = channel or ctx.channel
        await ctx.guild_document.update_db({"$set": {"starboard.channel": channel.id}})

    @sconfig.command(
        name="emoji",
        brief="Sets emoji people can react with to star a message.",
        description="Sets emoji people can react with to star a message. Defaults to ⭐. If a manager placed the reaction, it will get pinned to the starboard instantly.",
        usage="<Emoji>",
    )
    async def semoji(self, ctx, *, emoji: Union[discord.Emoji, discord.PartialEmoji, str]):
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
    async def spin(self, ctx, *, message: Optional[Union[discord.Message, discord.PartialMessage]]):
        if not isinstance(message, (discord.Message, discord.PartialMessage)):
            if ctx.message.reference:
                message = ctx.message.reference.resolved
            else:
                messages = await ctx.channel.history(before=ctx.message.created_at, limit=1).flatten()
                message = messages[0]
        message: discord.Message = await send_star(ctx.guild_document, message)
        await ctx.send(message.jump_url)

    @starboard.command(
        name="convert",
        brief="Converts pins in channel to pins on starboard.",
        description="Converts pins in channel to pins on starboard. Does not unpin channels.",
    )
    async def sconvert(self, ctx, *, channel: Optional[discord.TextChannel]):
        channel = channel or ctx.channel
        for pin in (await channel.pins())[::-1]:
            await send_star(ctx.guild_document, pin)
            await asyncio.sleep(1)  # Prevents rate-limiting


def setup(bot):
    bot.add_cog(Starboard(bot))
