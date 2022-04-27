import asyncio
from typing import Optional, cast

import discord
from discord import Interaction, Message, AppCommandType
from discord.app_commands import describe, context_menu
from discord.ext import commands
from discord.ext.commands import (
    hybrid_group,
    EmojiConverter,
    BadArgument,
    MessageConverter,
)

from utils import bots, database
from utils.attachments import find_url, NoMedia
from utils.bots import CustomContext


class AlreadyPinned(RuntimeError):
    """This message is already pinned to the starboard."""

    pass


async def send_star(
        document: database.Document,
        message: discord.Message,
        bot: bots.BOT_TYPES,
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

    bot.dispatch("star_sent", message)

    await document.update_db({"$push": {"starboard.messages": message.id}})
    return await send_channel.send(embed=embed)


PIN_CM_NAME: str = "Pin to Starboard"


@context_menu(name=PIN_CM_NAME)
async def pin_cm(interaction: Interaction, message: Message) -> None:
    """Pins a message to the starboard. You must link to the message."""

    ctx: CustomContext = await CustomContext.from_interaction(interaction)
    try:
        message: discord.Message = await send_star(
            ctx["guild_document"], message, ctx.bot
        )
        await ctx.send(
            f"Your pinned message can now be found at {message.jump_url}",
            ephemeral=True,
        )
    except AlreadyPinned:
        await ctx.send(
            "This message is already pinned to the starboard.", ephemeral=True
        )
    except bots.NotConfigured:
        await ctx.send("This server has not configured the starboard.", ephemeral=True)


class Starboard(commands.Cog):
    """Alternative way to "pin" messages."""

    def __init__(self, bot: bots.BOT_TYPES) -> None:
        self.bot = bot

    async def cog_check(self, ctx: bots.CustomContext) -> bool:
        if not ctx.guild:
            raise commands.NoPrivateMessage
        return True

    async def cog_load(self) -> None:
        self.bot.tree.add_command(pin_cm)

    async def cog_unload(self) -> None:
        self.bot.tree.remove_command(PIN_CM_NAME, type=AppCommandType.message)

    @commands.Cog.listener()
    async def on_raw_reaction_add(
            self, payload: discord.RawReactionActionEvent
    ) -> None:
        if payload.guild_id is None or payload.user_id == self.bot.user.id:
            return

        guild = self.bot.get_guild(payload.guild_id)
        channel: discord.TextChannel = guild.get_channel_or_thread(payload.channel_id)
        message: discord.Message = await channel.fetch_message(payload.message_id)
        ctx: bots.CustomContext = cast(
            bots.CustomContext, await self.bot.get_context(message)
        )

        if not isinstance(ctx.author, discord.Member) or ctx.guild is None:
            return

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

        manager: bool = ctx.channel.permissions_for(ctx.author).moderate_members

        if react_count is None:
            return
        if react_count >= threshold or manager:
            try:
                await send_star(ctx["guild_document"], ctx.message, self.bot)
            except bots.NotConfigured:
                pass
        else:
            return

    @hybrid_group(fallback="status", aliases=["sb"])
    async def starboard(self, ctx: bots.CustomContext) -> None:
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

    @starboard.group(fallback="status", aliases=["sbconf"])
    @commands.has_permissions(administrator=True)
    async def sbconfig(self, ctx: bots.CustomContext) -> None:
        """
        Commands for configuring the starboard.
        """
        pass

    @sbconfig.command()
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

    @sbconfig.command()
    @describe(channel="The channel to be used as a starboard.")
    async def channel(
            self,
            ctx: bots.CustomContext,
            *,
            channel: discord.TextChannel,
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

    @sbconfig.command()
    @describe(emoji="The emoji that people can react to a message with to pin it.")
    async def emoji(
            self,
            ctx: bots.CustomContext,
            *,
            emoji: str,
    ) -> None:
        """
        Sets the emoji that people can react with to attempt to pin a message to the starboard.
        This (rather intuitively) defaults to a star.
        """

        try:
            converter: EmojiConverter = EmojiConverter()
            emoji: discord.Emoji = await converter.convert(ctx, emoji)
        except BadArgument:
            pass

        if isinstance(emoji, (discord.Emoji, discord.PartialEmoji)):
            emoji = emoji.name
        await ctx["guild_document"].update_db({"$set": {"starboard.emoji": emoji}})
        await ctx.send(f"Emoji set to :{emoji}:.", ephemeral=True)

    @sbconfig.command()
    @describe(
        threshold="The amount of people that must react to the message in order for it to be pinned."
    )
    async def threshold(
            self,
            ctx: bots.CustomContext,
            *,
            threshold: int,
    ) -> None:
        """
        Sets the minimum amount of stars that must be placed on a message before it gets pinned.
        Defaults to 3.
        """
        await ctx["guild_document"].update_db(
            {"$set": {"starboard.threshold": threshold}}
        )

    @starboard.command()
    @describe(
        message="The message to be pinned to the starboard. Can be provided as a link, or by shift clicking. You can omit this if you are replying to a message."
    )
    async def pin(
            self,
            ctx: bots.CustomContext,
            *,
            message: MessageConverter | None,
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
        message: discord.Message = await send_star(
            ctx["guild_document"], message, ctx.bot
        )
        await ctx.send(
            f"Your pinned message can now be found at {message.jump_url}",
            ephemeral=True,
        )

    @starboard.command(
        name="convert",
        brief="Converts pins in channel to pins on starboard.",
        description="Converts pins in channel to pins on starboard. Does not unpin channels.",
    )
    @describe(channel="The channel to convert pins from.")
    async def sconvert(
            self,
            ctx: bots.CustomContext,
            *,
            channel: discord.TextChannel,
    ) -> None:
        await ctx.defer(ephemeral=True)
        for pin in (await channel.pins())[::-1]:
            await send_star(ctx["guild_document"], pin, ctx.bot)
            await asyncio.sleep(1)  # Prevents rate-limiting
        await ctx.send("Done moving pins!", ephemeral=True)


async def setup(bot: bots.BOT_TYPES) -> None:
    await bot.add_cog(Starboard(bot))
