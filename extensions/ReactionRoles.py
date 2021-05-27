import typing

import discord
from discord.ext import commands
from utils import checks, errors


class ReactionRoles(
    commands.Cog, name="Reaction Roles", description="Reactions that give/remove a role when clicked on."
):
    def __init__(self, bot):
        self.bot = bot

    async def cog_check(self, ctx):
        return await checks.is_admin(ctx)

    async def reaction_processor(self, payload: discord.RawReactionActionEvent):
        # Setup
        if payload.guild_id is None or payload.user_id == self.bot.user.id:
            return
        guild = self.bot.get_guild(payload.guild_id)
        channel = guild.get_channel(payload.channel_id)
        ctx = await self.bot.get_context(await channel.fetch_message(payload.message_id))
        reactor: discord.Member = guild.get_member(payload.user_id)
        emoji: discord.PartialEmoji = payload.emoji
        # Fetch info
        reaction_dict = ctx.guild_doc.setdefault("reactions", {})
        if reaction_dict:
            for key_channel in reaction_dict.keys():
                channel_dict = reaction_dict[key_channel]
                if int(key_channel) == ctx.channel.id:
                    for key_message in channel_dict.keys():
                        message_dict = channel_dict[key_message]
                        if int(key_message) == ctx.message.id:
                            for role_pair in message_dict.keys():
                                if role_pair == emoji.name:
                                    role = guild.get_role(message_dict[role_pair])
                                    if payload.event_type == "REACTION_ADD":
                                        await reactor.add_roles(role)
                                    elif payload.event_type == "REACTION_REMOVE":
                                        await reactor.remove_roles(role)

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
        name="disable",
        aliases=["off", "delete"],
        brief="Deletes reaction roles.",
        description="Deletes all reaction roles.",
    )
    async def sdisable(self, ctx):
        try:
            del ctx.guild_doc["reactions"]
        except KeyError:
            raise errors.NotConfigured()
        await ctx.guild_doc.replace_db()

    @reactionrole.command(
        name="add",
        brief="Adds reaction roles.",
        description="Adds reaction roles. The bot must have permissions to add rections in the desired channel.",
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
        reaction_dict = ctx.guild_doc.setdefault("reactions", {})
        if isinstance(emoji, (discord.Emoji, discord.PartialEmoji)):
            emoji_name = emoji.name
        elif isinstance(emoji, str):
            emoji_name = emoji
        else:
            emoji_name = None
        reaction_dict.update({str(channel.id): {str(message.id): {emoji_name: role.id}}})
        await message.add_reaction(emoji)
        await ctx.guild_doc.replace_db()


def setup(bot):
    bot.add_cog(ReactionRoles(bot))
