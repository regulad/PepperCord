import typing

import discord
from discord.ext import commands

from utils.checks import LowPrivilege, has_permission_level
from utils.permissions import Permission, get_permission
from utils import bots, checks


class ReactionRoles(commands.Cog):
    """Creates messages that give roles when reacted to."""

    def __init__(self, bot: bots.BOT_TYPES) -> None:
        self.bot = bot

    async def cog_check(self, ctx: bots.CustomContext):
        if not await has_permission_level(ctx, Permission.ADMINISTRATOR):
            raise LowPrivilege(Permission.ADMINISTRATOR, get_permission(ctx))
        else:
            return True

    async def _reaction_processor(self, payload: discord.RawReactionActionEvent) -> None:
        if payload.guild_id is None or payload.user_id == self.bot.user.id:
            return

        guild: discord.Guild = self.bot.get_guild(payload.guild_id)
        channel: discord.TextChannel = guild.get_channel(payload.channel_id)
        ctx: bots.CustomContext = await self.bot.get_context(await channel.fetch_message(payload.message_id))
        reactor: discord.Member = guild.get_member(payload.user_id)
        emoji: discord.PartialEmoji = payload.emoji

        reaction_dict = ctx.guild_document.get("reactions", {})
        if reaction_dict:
            for key_channel, channel_dict in reaction_dict.items():
                if int(key_channel) == ctx.channel.id:
                    for key_message, message_dict in channel_dict.items():
                        if int(key_message) == ctx.message.id:
                            for role_emoji, role_id in message_dict.items():
                                if role_emoji == emoji.name:
                                    role = guild.get_role(int(role_id))
                                    if payload.event_type == "REACTION_ADD":
                                        await reactor.add_roles(role)
                                    elif payload.event_type == "REACTION_REMOVE":
                                        await reactor.remove_roles(role)

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent) -> None:
        await self._reaction_processor(payload)

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent) -> None:
        await self._reaction_processor(payload)

    @commands.group(
        invoke_without_command=True,
        case_insensitive=True,
        name="reactionrole",
        aliases=["reaction", "rr"],
        brief="Configures reaction roles.",
        description="Configures reaction roles.",
    )
    async def reactionrole(self, ctx):
        pass

    @reactionrole.command(
        name="disable",
        aliases=["off", "delete"],
        brief="Deletes reaction roles.",
        description="Deletes all reaction roles.",
    )
    async def sdisable(self, ctx):
        if ctx.guild_document.get("reactions") is None:
            raise bots.NotConfigured
        else:
            await ctx.guild_document.update_db({"$unset": {"reactions": 1}})

    @reactionrole.command(
        name="add",
        brief="Adds reaction roles.",
        description="Adds reaction roles. The bots must have permissions to add rections in the desired channel.",
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
        if isinstance(emoji, (discord.Emoji, discord.PartialEmoji)):
            emoji_name = emoji.name
        elif isinstance(emoji, str):
            emoji_name = emoji
        else:
            emoji_name = None
        await message.add_reaction(emoji)
        await ctx.guild_document.update_db({"$set": {f"reactions.{channel.id}.{message.id}.{emoji_name}": role.id}})


def setup(bot: bots.BOT_TYPES) -> None:
    bot.add_cog(ReactionRoles(bot))
