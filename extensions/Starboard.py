import copy
import typing

import discord
import instances
import motor.motor_asyncio
from discord.ext import commands
from utils import checks, errors, managers


class StarboardConfigManager(managers.CommonConfigManager):
    def __init__(
        self,
        model: typing.Union[discord.Guild, discord.Member, discord.User],
        collection: motor.motor_asyncio.AsyncIOMotorCollection,
    ):
        super().__init__(model, collection, "starboard", {"emoji": "⭐", "threshold": 3})

    async def read(self, field):
        return self.active_key[field]

    async def write(self, field: str, value):
        working_key = copy.deepcopy(self.active_key)
        working_key.update({field: value})
        return await super().write(working_key)


class Starboard(commands.Cog, name="Starboard", description="An alternative to pinning messages."):
    def __init__(self, bot):
        self.bot = bot

    async def cog_check(self, ctx):
        if not ctx.guild:
            raise commands.NoPrivateMessage()
        return True

    async def sendstar(self, channel: discord.TextChannel, message: discord.Message):
        embed = (
            discord.Embed(
                colour=message.author.colour,
                description=f"> *[{message.content}]({message.jump_url})*",
            )
            .set_thumbnail(url=message.author.avatar_url)
            .add_field(name="Sent:", value=f"{message.created_at} UTC")
            .add_field(name="By:", value=message.author.mention)
            .add_field(name="In:", value=message.channel.mention)
        )
        if message.attachments:
            attachment = message.attachments[0]
            if (
                attachment.content_type == "image/png"
                or attachment.content_type == "image/jpeg"
                or attachment.content_type == "image/gif"
                or attachment.content_type == "image/webp"
            ):
                embed.set_image(url=attachment.url)
        await channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        # Setup
        if payload.guild_id == None or payload.user_id == self.bot.user.id:
            return
        guild: discord.Guild = self.bot.get_guild(payload.guild_id)
        channel: discord.TextChannel = guild.get_channel(payload.channel_id)
        message_partial: discord.PartialMessage = channel.get_partial_message(payload.message_id)
        message: discord.Message = await message_partial.fetch()
        author: discord.Member = guild.get_member(payload.user_id)
        emoji: discord.PartialEmoji = payload.emoji
        # Get documents
        config_manager = StarboardConfigManager(guild, instances.guild_collection)
        await config_manager.fetch_document()
        try:
            sendchannel = guild.get_channel(await config_manager.read("channel"))
        except:
            raise errors.NotConfigured()
        sendemoji = await config_manager.read("emoji")
        threshold = await config_manager.read("threshold")
        # See if reaction is correct
        if not emoji.name == sendemoji:
            return
        # See if reaction count meets threshold
        for reaction in message.reactions:
            if reaction.emoji == sendemoji:
                react_count = reaction.count
        if react_count >= threshold:
            await self.sendstar(sendchannel, message)
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
    async def schannel(self, ctx: commands.Context, *, channel: typing.Optional[discord.TextChannel]):
        channel = channel or ctx.channel
        config_manager = StarboardConfigManager(ctx.guild, instances.guild_collection)
        await config_manager.fetch_document()
        await config_manager.write("channel", channel.id)
        await ctx.message.add_reaction("✅")

    @sconfig.command(
        name="emoji",
        brief="Sets emoji people can react with to star a message.",
        description="Sets emoji people can react with to star a message. Defaults to ⭐. If a manager placed the reaction, it will get pinned to the starboard instantly.",
        usage="<Emoji>",
    )
    async def semoji(self, ctx: commands.Context, *, emoji: typing.Union[discord.Emoji, discord.PartialEmoji, str]):
        if isinstance(emoji, (discord.Emoji, discord.PartialEmoji)):
            emoji = emoji.name
        config_manager = StarboardConfigManager(ctx.guild, instances.guild_collection)
        await config_manager.fetch_document()
        await config_manager.write("emoji", emoji)
        await ctx.message.add_reaction("✅")

    @sconfig.command(
        name="threshold",
        brief="Sets the reaction threshold for being pinned.",
        description="Sets the reaction threshold for being pinned. Defaults to 3.",
        usage="<Threshold>",
    )
    async def sthreshold(self, ctx: commands.Context, *, threshold: int):
        config_manager = StarboardConfigManager(ctx.guild, instances.guild_collection)
        await config_manager.fetch_document()
        await config_manager.write("threshold", threshold)
        await ctx.message.add_reaction("✅")

    @starboard.command(
        name="pin",
        brief="Pins message to the starboard.",
        description="Pins a message of your choice to the starboard.",
        usage="[Message]",
    )
    async def spin(
        self, ctx: commands.Context, *, message: typing.Optional[typing.Union[discord.Message, discord.PartialMessage]]
    ):
        if not isinstance(message, (discord.Message, discord.PartialMessage)):
            messages = await ctx.channel.history(before=ctx.message.created_at, limit=1).flatten()
            message = messages[0]
        config_manager = StarboardConfigManager(ctx.guild, instances.guild_collection)
        await config_manager.fetch_document()
        try:
            channel = await config_manager.read("channel")
        except:
            raise errors.NotConfigured()
        await self.sendstar(ctx.guild.get_channel(channel), message)
        await ctx.message.add_reaction("✅")


def setup(bot):
    bot.add_cog(Starboard(bot))
