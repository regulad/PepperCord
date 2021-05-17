import copy
import typing

import discord
import instances
import pymongo
from discord.ext import commands
from utils import checks, errors, managers


class GuildReactionManager(managers.CommonConfigManager):
    def __init__(self, guild: discord.Guild, collection: pymongo.collection.Collection):
        super().__init__(guild, collection, "reactions", {})

    def write(
        self,
        channel: discord.TextChannel,
        message: typing.Union[discord.Message, discord.PartialMessage],
        emoji: typing.Union[discord.Emoji, discord.PartialEmoji, str],
        role: discord.Role,
    ):
        if isinstance(emoji, (discord.Emoji, discord.PartialEmoji)):
            emoji_name = emoji.name
        elif isinstance(emoji, str):
            emoji_name = emoji
        working_key = copy.deepcopy(self.active_key)
        working_key.update({str(channel.id): {str(message.id): {emoji_name: role.id}}})
        super().write(working_key)


class ReactionRoles(commands.Cog, name="Reaction Roles", description="Reactions that give/remove a role when clicked on."):
    def __init__(self, bot):
        self.bot = bot

    async def cog_check(self, ctx):
        return await checks.has_permission_level(ctx, 3)

    async def reaction_processor(self, payload: discord.RawReactionActionEvent):
        if payload.guild_id == None or payload.user_id == self.bot.user.id:
            return
        guild: discord.Guild = self.bot.get_guild(payload.guild_id)
        channel: discord.TextChannel = guild.get_channel(payload.channel_id)
        message: discord.PartialMessage = channel.get_partial_message(payload.message_id)
        author: discord.Member = guild.get_member(payload.user_id)
        emoji: discord.PartialEmoji = payload.emoji
        reaction_dict = GuildReactionManager(guild, instances.guild_collection).read()
        if reaction_dict:
            for key_channel in reaction_dict.keys():
                channel_dict = reaction_dict[key_channel]
                if int(key_channel) == channel.id:
                    for key_message in channel_dict.keys():
                        message_dict = channel_dict[key_message]
                        if int(key_message) == message.id:
                            for role_pair in message_dict.keys():
                                if role_pair == emoji.name:
                                    role = guild.get_role(message_dict[role_pair])
                                    if payload.event_type == "REACTION_ADD":
                                        await author.add_roles(role)
                                    elif payload.event_type == "REACTION_REMOVE":
                                        await author.remove_roles(role)

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        await self.reaction_processor(payload)

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent):
        await self.reaction_processor(payload)

    @commands.group(
        invoke_without_command=True,
        case_insensitive=True,
        name="reactionrole",
        aliases=["reaction", "rr"],
        brief="Configures reaction roles.",
        description="Configures reaction roles.",
    )
    async def reactionrole(self, ctx):
        raise errors.SubcommandNotFound()

    @reactionrole.command(
        name="add",
        brief="Adds reactions.",
        description="The bot must have permissions to add rections in the desired channel.",
        usage="<Channel> <Message> <Emoji> <Role>",
    )
    async def add(
        self,
        ctx,
        channel: discord.TextChannel,
        message: typing.Union[discord.Message, discord.PartialMessage],
        emoji: typing.Union[discord.Emoji, discord.PartialEmoji, str],
        role: discord.Role,
    ):
        GuildReactionManager(ctx.guild, instances.guild_collection).write(channel, message, emoji, role)
        message_model = channel.get_partial_message(message.id)
        await message_model.add_reaction(emoji)
        await ctx.message.add_reaction(emoji="✅")


def setup(bot):
    bot.add_cog(ReactionRoles(bot))
