from typing import Tuple, cast

import discord
from discord import Message
from discord.app_commands import describe
from discord.app_commands import guild_only as ac_guild_only
from discord.ext import commands
from discord.ext.commands import (
    hybrid_group,
    EmojiConverter,
    BadArgument,
    MessageConverter,
    guild_only,
)

from utils import bots, checks


class ReactionRoles(commands.Cog):
    """Creates messages that give roles when reacted to."""

    def __init__(self, bot: bots.BOT_TYPES) -> None:
        self.bot = bot

    async def cog_check(self, ctx: bots.CustomContext):
        if not ctx.author.guild_permissions.administrator:
            raise commands.MissingPermissions(["administrator"])
        else:
            return True

    async def _assemble_reaction(
        self,
        payload: discord.RawReactionActionEvent,
    ) -> Tuple[discord.Message, discord.Member]:
        guild: discord.Guild = self.bot.get_guild(payload.guild_id)

        return await self.bot.smart_fetch_message(
            guild.get_channel_or_thread(payload.channel_id), payload.message_id
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

    @hybrid_group()
    @ac_guild_only()
    @guild_only()
    @checks.check_members_enabled
    async def reactionrole(self, ctx: bots.CustomContext) -> None:
        """
        Reaction Roles are a system that allow users to get a role by reacting to a message.
        """
        pass

    @reactionrole.command()
    @guild_only()
    @checks.check_members_enabled
    async def disable(self, ctx: bots.CustomContext) -> None:
        """Disables all existing reaction roles. You will need to readd them to have them work again"""
        if ctx["guild_document"].get("reactions") is None:
            raise bots.NotConfigured
        else:
            await ctx["guild_document"].update_db({"$unset": {"reactions": 1}})
            await ctx.send("Deleted all reaction roles.")

    @reactionrole.command()
    @guild_only()
    @describe(
        message="A reference to the message that will have a reaction role attached.",
        emoji="The emoji that will trigger the reaction role.",
        role="The role that will be given to the user.",
    )
    @checks.check_members_enabled
    async def add(
        self,
        ctx: bots.CustomContext,
        message: MessageConverter,
        emoji: str,
        role: discord.Role,
    ) -> None:
        """
        Adds a reaction role to a message.
        The message parameter must be a link to the message.
        """
        try:
            converter: EmojiConverter = EmojiConverter()
            emoji: discord.Emoji = await converter.convert(ctx, emoji)
        except BadArgument:
            pass

        message: Message = cast(Message, message)

        await message.add_reaction(emoji)
        await ctx["guild_document"].update_db(
            {
                "$set": {
                    f"reactions.{message.channel.id}.{message.id}.{emoji.name if not isinstance(emoji, str) else emoji}": role.id
                }
            }
        )
        await ctx.send("Reaction role added.", ephemeral=True)


async def setup(bot: bots.BOT_TYPES) -> None:
    await bot.add_cog(ReactionRoles(bot))
