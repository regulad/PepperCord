import typing

import discord
from discord.ext import commands
from utils import checks, errors
from utils.database import Document


class Starboard(commands.Cog, name="Starboard", description="An alternative to pinning messages."):
    def __init__(self, bot):
        self.bot = bot

    async def cog_check(self, ctx):
        if not ctx.guild:
            raise commands.NoPrivateMessage()
        return True

    async def _sendstar(self, document: Document, message: discord.Message):
        # Get channel
        try:
            sendchannel = message.guild.get_channel(document.setdefault("starboard", {})["channel"])
        except:
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
        await sendchannel.send(embed=embed)
        messages.append(message.id)

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        # Setup
        if payload.guild_id == None or payload.user_id == self.bot.user.id:
            return
        guild = self.bot.get_guild(payload.guild_id)
        ctx = await self.bot.get_context(
            await guild.get_channel(payload.channel_id).get_partial_message(payload.message_id).fetch()
        )
        emoji: discord.PartialEmoji = payload.emoji
        # Get documents
        sendemoji = ctx.guild_doc.setdefault("starboard", {}).setdefault("emoji", "⭐")
        threshold = ctx.guild_doc.setdefault("starboard", {}).setdefault("threshold", 3)
        # See if reaction is correct
        if not emoji.name == sendemoji:
            return
        # See if reaction count meets threshold
        for reaction in ctx.message.reactions:
            if isinstance(reaction.emoji, (discord.Emoji, discord.PartialEmoji)):
                reaction_name = reaction.emoji.name
            else:
                reaction_name = reaction.emoji
            if reaction_name == sendemoji:
                react_count = reaction.count
        if react_count >= threshold:
            await self._sendstar(ctx.guild_doc, ctx.message)
            await ctx.guild_doc.update_db()
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
        raise errors.SubcommandNotFound()

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
        raise errors.SubcommandNotFound()

    @sconfig.command(
        name="channel",
        aliases=["board"],
        brief="Sets channel.",
        description="Sets channel to be used as the starboard.",
        usage="[Channel]",
    )
    async def schannel(self, ctx, *, channel: typing.Optional[discord.TextChannel]):
        channel = channel or ctx.channel
        ctx.guild_doc.setdefault("starboard", {})["channel"] = channel.id
        await ctx.guild_doc.update_db()
        await ctx.message.add_reaction("✅")

    @sconfig.command(
        name="emoji",
        brief="Sets emoji people can react with to star a message.",
        description="Sets emoji people can react with to star a message. Defaults to ⭐. If a manager placed the reaction, it will get pinned to the starboard instantly.",
        usage="<Emoji>",
    )
    async def semoji(self, ctx, *, emoji: typing.Union[discord.Emoji, discord.PartialEmoji, str]):
        if isinstance(emoji, (discord.Emoji, discord.PartialEmoji)):
            emoji = emoji.name
        ctx.guild_doc.setdefault("starboard", {})["emoji"] = emoji
        await ctx.guild_doc.update_db()
        await ctx.message.add_reaction("✅")

    @sconfig.command(
        name="threshold",
        brief="Sets the reaction threshold for being pinned.",
        description="Sets the reaction threshold for being pinned. Defaults to 3.",
        usage="<Threshold>",
    )
    async def sthreshold(self, ctx, *, threshold: int):
        ctx.guild_doc.setdefault("starboard", {})["threshold"] = threshold
        await ctx.guild_doc.update_db()
        await ctx.message.add_reaction("✅")

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
        await self._sendstar(ctx.guild_doc, message)
        await ctx.guild_doc.update_db()
        await ctx.message.add_reaction("✅")

    @starboard.command(
        name="convert",
        brief="Converts pins in channel to pins on starboard.",
        description="Converts pins in channel to pins on starboard. Does not unpin channels.",
    )
    async def sconvert(self, ctx, *, channel: typing.Optional[discord.TextChannel]):
        channel = channel or ctx.channel
        for pin in (await channel.pins())[::-1]:
            await self._sendstar(ctx.guild_doc, pin)
        await ctx.guild_doc.update_db()
        await ctx.message.add_reaction("✅")


def setup(bot):
    bot.add_cog(Starboard(bot))
