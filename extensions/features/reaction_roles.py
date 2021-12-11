import typing
from typing import Tuple

import discord
from discord.ext import commands

from utils import bots
from utils.checks import LowPrivilege, has_permission_level
from utils.permissions import Permission, get_permission


class ReactionRoles(commands.Cog):
    """Creates messages that give roles when reacted to."""

    def __init__(self, bot: bots.BOT_TYPES) -> None:
        self.bot = bot

    async def cog_check(self, ctx: bots.CustomContext):
        if not await has_permission_level(ctx, Permission.ADMINISTRATOR):
            raise LowPrivilege(Permission.ADMINISTRATOR, get_permission(ctx))
        else:
            return True

    async def _assemble_reaction(
        self, payload: discord.RawReactionActionEvent
    ) -> Tuple[discord.Message, discord.Member]:
        guild: discord.Guild = self.bot.get_guild(payload.guild_id)

        return await (guild.get_channel_or_thread(payload.channel_id)).fetch_message(
            payload.message_id
        ), guild.get_member(payload.user_id)

    @commands.Cog.listener()
    async def on_raw_reaction_add(
        self, payload: discord.RawReactionActionEvent
    ) -> None:
        if payload.guild_id is None or payload.user_id == self.bot.user.id:
            return

        message, member = await self._assemble_reaction(payload)

        ctx: bots.CustomContext = await self.bot.get_context(message)

        reaction_dict = ctx["guild_document"].get("reactions", {})
        if reaction_dict:
            for key_channel, channel_dict in reaction_dict.items():
                if int(key_channel) == ctx.channel.id:
                    for key_message, message_dict in channel_dict.items():
                        if int(key_message) == ctx.message.id:
                            for role_emoji, role_id in message_dict.items():
                                if role_emoji == payload.emoji.name:
                                    await member.add_roles(
                                        ctx.guild.get_role(int(role_id))
                                    )

    @commands.Cog.listener()
    async def on_raw_reaction_remove(
        self, payload: discord.RawReactionActionEvent
    ) -> None:
        if payload.guild_id is None or payload.user_id == self.bot.user.id:
            return

        message, member = await self._assemble_reaction(payload)

        ctx: bots.CustomContext = await self.bot.get_context(message)

        reaction_dict = ctx["guild_document"].get("reactions", {})
        if reaction_dict:
            for key_channel, channel_dict in reaction_dict.items():
                if int(key_channel) == ctx.channel.id:
                    for key_message, message_dict in channel_dict.items():
                        if int(key_message) == ctx.message.id:
                            for role_emoji, role_id in message_dict.items():
                                if role_emoji == payload.emoji.name:
                                    await member.remove_roles(
                                        ctx.guild.get_role(role_id)
                                    )

    @commands.group()
    async def reactionrole(self, ctx: bots.CustomContext) -> None:
        """
        Reaction Roles are a system that allow users to get a role by reacting to a message.
        """
        pass

    @reactionrole.command()
    async def disable(self, ctx: bots.CustomContext) -> None:
        """Disables all existing reaction roles. You will need to readd them to have them work again"""
        if ctx["guild_document"].get("reactions") is None:
            raise bots.NotConfigured
        else:
            await ctx["guild_document"].update_db({"$unset": {"reactions": 1}})
            await ctx.send("Deleted all reaction roles.")

    @reactionrole.command()
    async def add(
        self,
        ctx: bots.CustomContext,
        message: typing.Union[
            discord.Message, discord.PartialMessage
        ] = commands.Option(
            description="A URL to the message that will be reacted to."
        ),
        emoji: typing.Union[discord.Emoji, discord.PartialEmoji, str] = commands.Option(
            description="The emoji that will be used. Send the emoji, do not just send it's name."
        ),
        role: discord.Role = commands.Option(
            description="The role that will be given/taken."
        ),
    ) -> None:
        """
        Adds a reaction role to a message.
        The message parameter must be a link to the message.
        """
        await message.add_reaction(emoji)
        await ctx["guild_document"].update_db(
            {
                "$set": {
                    f"reactions.{message.channel.id}.{message.id}.{emoji.name if not isinstance(emoji, str) else emoji}": role.id
                }
            }
        )
        await ctx.send("Reaction role added.", ephemeral=True)


def setup(bot: bots.BOT_TYPES) -> None:
    bot.add_cog(ReactionRoles(bot))
