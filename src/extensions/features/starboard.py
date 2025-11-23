from typing import Optional, cast

import discord
from discord import (
    ClientUser,
    DeletedReferencedMessage,
    Interaction,
    Message,
    AppCommandType,
    TextChannel,
)
from discord.app_commands import describe, context_menu
from discord.app_commands import guild_only as ac_guild_only
from discord.ext import commands
from discord.ext.commands import (
    hybrid_group,
    EmojiConverter,
    BadArgument,
    MessageConverter,
    guild_only,
    Command,
)

from utils import database
from utils.attachments import find_url, NoMedia
from utils.bots.bot import CustomBot
from utils.commands import NotConfigured
from utils.bots.context import CustomContext


class AlreadyPinned(RuntimeError):
    """This message is already pinned to the starboard."""


async def send_star(
    document: database.PCDocument,
    message: discord.Message,
    bot: CustomBot,
) -> discord.Message:
    assert message.guild is not None  # will not get called in dm environment

    send_channel_id: Optional[int] = document.get("starboard", {}).get("channel")

    if send_channel_id is None:
        raise NotConfigured

    send_channel = message.guild.get_channel(send_channel_id)

    if send_channel is None:
        raise RuntimeError("Channel couldn't be found!")
    elif not isinstance(send_channel, TextChannel):
        raise RuntimeError("Channel was not a TextChannel!")

    messages = document.get("starboard", {}).get("messages", [])

    if message.id in messages:
        raise AlreadyPinned

    embed = discord.Embed(
        colour=message.author.colour, description=message.clean_content
    ).set_author(
        name=f"Sent by {message.author.display_name} in {getattr(message.channel, "name", f"Channel ID {message.channel.id}")}",
        url=message.jump_url,
        icon_url=message.author.display_avatar.url,
    )

    try:
        url, source = await find_url(message, bot)
    except NoMedia:
        url, source = None, None
    else:
        if (
            isinstance(source, discord.Attachment)
            and source.content_type is not None
            and source.content_type.startswith("image")
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
@ac_guild_only()
async def pin_cm(interaction: Interaction[CustomBot], message: Message) -> None:
    """Pins a message to the starboard. You must link to the message."""

    ctx = await CustomContext.from_interaction(interaction)
    await ctx.invoke(
        # this Command cast is needed because it cannot infer the type from the below definition of Starboard.pin
        cast(Command[Starboard, ..., None], ctx.bot.get_command("starboard pin")),
        message=message,
    )


class Starboard(commands.Cog):
    """Alternative way to "pin" messages."""

    def __init__(self, bot: CustomBot) -> None:
        self.bot = bot

    async def cog_check(self, ctx: CustomContext) -> bool:  # type: ignore[override]  # bad d.py type
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
        if (
            payload.guild_id is None
            or payload.user_id == cast(ClientUser, self.bot.user).id
        ):  # can't be None if we are receiving these events
            return

        guild = self.bot.get_guild(payload.guild_id)

        if guild is None:
            # Don't need to do any handling in a DM.
            return

        send_channel = guild.get_channel_or_thread(payload.channel_id)

        if send_channel is None:
            raise RuntimeError("Channel couldn't be found!")
        elif not isinstance(send_channel, TextChannel):
            raise RuntimeError("Channel was not a TextChannel!")

        message = await send_channel.fetch_message(payload.message_id)
        ctx: CustomContext = cast(CustomContext, await self.bot.get_context(message))

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
            except NotConfigured:
                pass
        else:
            return

    @hybrid_group(fallback="status", aliases=["sb"])  # type: ignore[arg-type]  # bad d.py export
    @ac_guild_only()
    @guild_only()
    async def starboard(self, ctx: CustomContext) -> None:
        """Shows all the settings of the currently configured starboard."""
        assert ctx.guild is not None  # guaranteed at runtime by check

        if ctx["guild_document"].get("starboard", {}).get("channel") is None:
            raise NotConfigured
        channel = ctx.guild.get_channel(ctx["guild_document"]["starboard"]["channel"])
        if not isinstance(channel, TextChannel):
            raise RuntimeError(
                "This server has a Starboard configured, but I can't access it. You'll need to reconfigure the starboard."
            )

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
                value=channel.mention,
            )
            .add_field(name="Emoji:", value=emoji)
            .add_field(
                name="Threshold:",
                value=ctx["guild_document"]["starboard"].get("threshold", 3),
            )
        )

        await ctx.send(embed=embed, ephemeral=True)

    @starboard.group(name="config", fallback="status", aliases=["sbconf"])  # type: ignore[arg-type]  # bad d.py export
    @commands.has_permissions(administrator=True)
    @guild_only()
    async def sbconfig(self, ctx: CustomContext) -> None:
        """
        Commands for configuring the starboard.
        """

    @sbconfig.command()  # type: ignore[arg-type]  # bad d.py export
    @guild_only()
    async def disable(self, ctx: CustomContext) -> None:
        """
        Disables and deletes all starboard data.
        You'll need to reconfigure it before you use it again.
        """
        if ctx["guild_document"].get("starboard") is None:
            raise NotConfigured
        else:
            await ctx["guild_document"].update_db({"$unset": {"starboard": 1}})
            await ctx.send("Starboard disabled.", ephemeral=True)

    @sbconfig.command()  # type: ignore[arg-type]  # bad d.py export
    @describe(channel="The channel to be used as a starboard.")
    @guild_only()
    async def channel(
        self,
        ctx: CustomContext,
        *,
        channel: discord.TextChannel,
    ) -> None:
        """
        Sets the channel that will be used as a starboard.
        To activate the starboard, change this setting.
        """
        await ctx["guild_document"].update_db(
            {"$set": {"starboard.channel": channel.id}}
        )
        await ctx.send(f"Channel set to {channel.mention}.", ephemeral=True)

    @sbconfig.command()  # type: ignore[arg-type]  # bad d.py export
    @guild_only()
    @describe(emoji="The emoji that people can react to a message with to pin it.")
    async def emoji(
        self,
        ctx: CustomContext,
        *,
        emoji: str,
    ) -> None:
        """
        Sets the emoji that people can react with to attempt to pin a message to the starboard.
        This (rather intuitively) defaults to a star.
        """

        # There's a chance this is a custom emoji, we need to do some processing if this is the case.
        converted_emoji: discord.Emoji | discord.PartialEmoji | None
        try:
            converter = EmojiConverter()
            converted_emoji = await converter.convert(ctx, emoji)
        except BadArgument:
            converted_emoji = None
        if isinstance(converted_emoji, (discord.Emoji, discord.PartialEmoji)):
            emoji = converted_emoji.name

        await ctx["guild_document"].update_db({"$set": {"starboard.emoji": emoji}})
        await ctx.send(f"Emoji set to :{emoji}:.", ephemeral=True)

    @sbconfig.command()  # type: ignore[arg-type]  # bad d.py export
    @guild_only()
    @describe(
        threshold="The amount of people that must react to the message in order for it to be pinned."
    )
    async def threshold(
        self,
        ctx: CustomContext,
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
        await ctx.send(f"Threshold set to {threshold}.", ephemeral=True)

    @starboard.command()  # type: ignore[arg-type]  # bad d.py export
    @guild_only()
    @describe(
        message="The message to be pinned to the starboard. Can be provided as a link, or by shift clicking. You can omit this if you are replying to a message."
    )
    @commands.bot_has_guild_permissions(read_message_history=True)
    async def pin(
        self,
        ctx: CustomContext,
        *,
        message: MessageConverter | None,
    ) -> None:
        """Pins a message to the starboard. You must link to the message."""
        message_converter = message
        del message  # I don't want to juggle this, it's confusing to have a variable named message that is not a message.

        message_to_pin: discord.Message
        if isinstance(message_converter, discord.Message):
            message_to_pin = message_converter  # type: ignore  # these converters don't work into typing systems well
        elif isinstance(message_converter, discord.PartialMessage):
            message_to_pin = await message_converter.fetch()  # type: ignore  # these converters don't work into typing systems well
        elif ctx.message.reference and ctx.message.reference.cached_message is not None:
            message_to_pin = ctx.message.reference.cached_message
        elif ctx.message.reference and isinstance(
            ctx.message.reference.resolved, Message
        ):
            message_to_pin = ctx.message.reference.resolved
        elif ctx.message.reference and isinstance(
            ctx.message.reference.resolved, DeletedReferencedMessage
        ):
            raise RuntimeError("Can't pin a deleted message.")
        elif ctx.message.reference and ctx.message.reference.resolved is None:
            raise RuntimeError(
                "This message can't be pinned."
            )  # Not sure when this would occur, but the docs said it can...
        else:
            # Nothing for us to use directly, pull from the history
            messages_aiter = ctx.channel.history(before=ctx.message.created_at, limit=1)
            # The async iterator returned used to have a "flatten" method, but no longer does. This will do instead.
            async for historical_message in messages_aiter:
                message_to_pin = historical_message
                break

        star_message = await send_star(ctx["guild_document"], message_to_pin, ctx.bot)
        await ctx.send(
            f"Your pinned message can now be found at {star_message.jump_url}",
            ephemeral=True,
        )

    @starboard.command(  # type: ignore[arg-type]  # bad d.py export
        name="convert",
        brief="Converts pins in channel to pins on starboard.",
        description="Converts pins in channel to pins on starboard. Does not unpin channels.",
    )
    @guild_only()
    @describe(channel="The channel to convert pins from.")
    async def sconvert(
        self,
        ctx: CustomContext,
        *,
        channel: discord.TextChannel,
    ) -> None:
        async with ctx.typing(ephemeral=True):
            for pin in (await channel.pins())[::-1]:
                try:
                    await send_star(ctx["guild_document"], pin, ctx.bot)
                except AlreadyPinned:
                    continue
            await ctx.send("Done moving pins!", ephemeral=True)


async def setup(bot: CustomBot) -> None:
    await bot.add_cog(Starboard(bot))
