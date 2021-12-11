import asyncio
from typing import Optional, Union

import discord
from discord.ext import commands

from utils import checks, bots, database
from utils.attachments import find_url, NoMedia
from utils.permissions import Permission


class AlreadyPinned(Exception):
    pass


async def send_star(
    document: database.Document, message: discord.Message
) -> discord.Message:
    send_channel_id: Optional[int] = document.get("starboard", {}).get("channel")

    if send_channel_id is None:
        raise bots.NotConfigured

    send_channel: discord.TextChannel = message.guild.get_channel(send_channel_id)

    messages = document.get("starboard", {}).get("messages", [])

    if message.id in messages:
        raise AlreadyPinned

    embed = discord.Embed(
        colour=message.author.colour, description=message.clean_content
    ).set_author(
        name=f"Sent by {message.author.display_name} in {message.channel.name}",
        url=message.jump_url,
        icon_url=(message.author.guild_avatar or message.author.avatar).url,
    )

    try:
        url, source = await find_url(message)
    except NoMedia:
        url, source = None, None
    else:
        if isinstance(source, discord.Attachment) and source.content_type.startswith(
            "image"
        ):
            embed.set_image(url=url)
        elif (
            isinstance(source, discord.Embed) and source.type == "image"
        ):  # deprecated!... kinda
            embed.set_image(url=url)

    await document.update_db({"$push": {"starboard.messages": message.id}})
    return await send_channel.send(embed=embed)


class Starboard(commands.Cog):
    """Alternative way to "pin" messages."""

    def __init__(self, bot: bots.BOT_TYPES) -> None:
        self.bot = bot

    async def cog_check(self, ctx: bots.CustomContext) -> bool:
        if not ctx.guild:
            raise commands.NoPrivateMessage
        return True

    @commands.Cog.listener()
    async def on_raw_reaction_add(
        self, payload: discord.RawReactionActionEvent
    ) -> None:
        if payload.guild_id is None or payload.user_id == self.bot.user.id:
            return

        guild = self.bot.get_guild(payload.guild_id)
        ctx = await self.bot.get_context(
            await guild.get_channel_or_thread(payload.channel_id).fetch_message(
                payload.message_id
            )
        )

        send_emoji = ctx["guild_document"].get("starboard", {}).get("emoji", "⭐")
        threshold = ctx["guild_document"].get("starboard", {}).get("threshold", 3)

        for reaction in ctx.message.reactions:
            if isinstance(reaction.emoji, (discord.Emoji, discord.PartialEmoji)):
                reaction_name = reaction.emoji.name
            else:
                reaction_name = reaction.emoji
            if reaction_name == send_emoji:
                react_count = reaction.count
                break
        else:
            react_count = None

        manager: bool = await checks.has_permission_level(ctx, Permission.MANAGER)

        if react_count is None:
            return
        if react_count >= threshold or manager:
            await send_star(ctx["guild_document"], ctx.message)
        else:
            return

    @commands.group()
    async def starboard(self, ctx: bots.CustomContext) -> None:
        """
        Starboards are an alternative to pinning messages to a channel.
        """
        pass

    @starboard.command()
    async def settings(self, ctx: bots.CustomContext) -> None:
        """Shows all the settings of the currently configured starboard."""
        if ctx["guild_document"].get("starboard", {}).get("channel") is None:
            raise bots.NotConfigured

        try:
            emoji = await commands.EmojiConverter().convert(
                ctx, ctx["guild_document"]["starboard"].get("emoji", "⭐")
            )
        except commands.EmojiNotFound:
            emoji = ctx["guild_document"]["starboard"].get("emoji", "⭐")

        embed = (
            discord.Embed(title="Starboard Config")
            .add_field(
                name="Channel:",
                value=ctx.guild.get_channel(
                    ctx["guild_document"]["starboard"]["channel"]
                ).mention,
            )
            .add_field(name="Emoji:", value=emoji)
            .add_field(
                name="Threshold:",
                value=ctx["guild_document"]["starboard"].get("threshold", 3),
            )
        )

        await ctx.send(embed=embed, ephemeral=True)

    @starboard.group()
    @commands.check(checks.check_is_admin)
    async def config(self, ctx: bots.CustomContext) -> None:
        """
        Commands for configuring the starboard.
        """
        pass

    @config.command()
    async def disable(self, ctx: bots.CustomContext) -> None:
        """
        Disables and deletes all starboard data.
        You'll need to reconfigure it before you use it again.
        """
        if ctx["guild_document"].get("starboard") is None:
            raise bots.NotConfigured
        else:
            await ctx["guild_document"].update_db({"$unset": {"starboard": 1}})
            await ctx.send("Starboard disabled.", ephemeral=True)

    @config.command()
    async def channel(
        self,
        ctx: bots.CustomContext,
        *,
        channel: discord.TextChannel = commands.Option(
            description="The channel to be used as a starboard."
        ),
    ) -> None:
        """
        Sets the channel that will be used as a starboard.
        To activate the starboard, change this setting.
        """
        channel = channel or ctx.channel
        await ctx["guild_document"].update_db(
            {"$set": {"starboard.channel": channel.id}}
        )
        await ctx.send(f"Channel set to {channel.mention}.", ephemeral=True)

    @config.command()
    async def emoji(
        self,
        ctx: bots.CustomContext,
        *,
        emoji: Union[discord.Emoji, discord.PartialEmoji, str] = commands.Option(
            description="The emoji that people can react to a message with to pin it."
        ),
    ) -> None:
        """
        Sets the emoji that people can react with to attempt to pin a message to the starboard.
        This (rather intuitively) defaults to a star.
        """
        if isinstance(emoji, (discord.Emoji, discord.PartialEmoji)):
            emoji = emoji.name
        await ctx["guild_document"].update_db({"$set": {"starboard.emoji": emoji}})
        await ctx.send(f"Emoji set to :{emoji}:.", ephemeral=True)

    @config.command()
    async def threshold(
        self,
        ctx: bots.CustomContext,
        *,
        threshold: int = commands.Option(
            description="The amount of people that must react to the message in order for it to be pinned."
        ),
    ) -> None:
        """
        Sets the minimum amount of stars that must be placed on a message before it gets pinned.
        Defaults to 3.
        """
        await ctx["guild_document"].update_db(
            {"$set": {"starboard.threshold": threshold}}
        )

    @starboard.command()
    async def pin(
        self,
        ctx: bots.CustomContext,
        *,
        message: Optional[
            Union[discord.Message, discord.PartialMessage]
        ] = commands.Option(
            description="A link to a message that will be pinned to the starboard."
        ),
    ) -> None:
        """Pins a message to the starboard. You must link to the message."""
        if not isinstance(message, (discord.Message, discord.PartialMessage)):
            if ctx.message.reference:
                message = ctx.message.reference.resolved
            else:
                messages = await ctx.channel.history(
                    before=ctx.message.created_at, limit=1
                ).flatten()
                message = messages[0]
        message: discord.Message = await send_star(ctx["guild_document"], message)
        await ctx.send(
            f"Your pinned message can now be found at {message.jump_url}",
            ephemeral=True,
        )

    @starboard.command(
        name="convert",
        brief="Converts pins in channel to pins on starboard.",
        description="Converts pins in channel to pins on starboard. Does not unpin channels.",
    )
    async def sconvert(
        self,
        ctx: bots.CustomContext,
        *,
        channel: discord.TextChannel = commands.Option(
            description="The channel that will have it's pins converted."
        ),
    ) -> None:
        await ctx.defer(ephemeral=True)
        for pin in (await channel.pins())[::-1]:
            await send_star(ctx["guild_document"], pin)
            await asyncio.sleep(1)  # Prevents rate-limiting
        await ctx.send("Done moving pins!", ephemeral=True)


def setup(bot: bots.BOT_TYPES):
    bot.add_cog(Starboard(bot))
