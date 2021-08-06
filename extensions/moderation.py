import datetime
from typing import Optional, Union, cast

import discord
from discord.ext import commands, tasks

from utils.checks import LowPrivilege, has_permission_level
from utils.permissions import Permission, get_permission
from utils import bots, database, converters


async def mute(
    member: discord.Member,
    *,
    guild_document: Optional[database.Document] = None,
    bot: Optional[bots.BOT_TYPES] = None,
) -> None:
    """Mutes a user. Requires a bot or a guild document."""

    if guild_document is None and bot is None:
        raise TypeError("Either a bot or a document is required to call this function.")
    elif guild_document is None:
        guild_document: database.Document = await bot.get_guild_document(member.guild)

    if guild_document.get("mute_role") is None:
        raise bots.NotConfigured("Mute must be configured.")
    else:
        mute_role: discord.Role = member.guild.get_role(guild_document["mute_role"])
        await member.add_roles(mute_role, reason="Mute")


async def unmute(
    member: discord.Member,
    *,
    guild_document: Optional[database.Document] = None,
    bot: Optional[bots.BOT_TYPES] = None,
) -> None:
    """Unmutes a user. Requires a bot or a guild document."""

    if guild_document is None and bot is None:
        raise TypeError("Either a bot or a document is required to call this function.")
    elif guild_document is None:
        guild_document: database.Document = await bot.get_guild_document(member.guild)

    if guild_document.get("mute_role") is None:
        raise bots.NotConfigured("Mute must be configured.")
    else:
        mute_role: discord.Role = member.guild.get_role(guild_document["mute_role"])
        await member.remove_roles(mute_role, reason="Unmute")


class Moderation(commands.Cog):
    """Tools for moderation in guilds."""

    def __init__(self, bot: bots.BOT_TYPES) -> None:
        self.bot = bot

        self.unpunish.start()

    def cog_unload(self) -> None:
        self.unpunish.stop()

    @tasks.loop(seconds=120)
    async def unpunish(self) -> None:
        for guild in self.bot.guilds:
            guild_doc: database.Document = await self.bot.get_guild_document(guild)
            if guild_doc.get("punishments") is not None:
                for user_id, user_dict in guild_doc["punishments"].items():
                    for punishment, unpunish_time in user_dict.items():
                        if unpunish_time < datetime.datetime.utcnow():
                            try:  # Messy.
                                if punishment == "mute":
                                    await unmute(
                                        await guild.fetch_member(int(user_id)),
                                        guild_document=guild_doc,
                                    )
                                elif punishment == "ban":
                                    user: discord.User = self.bot.get_user(user_id)
                                    await guild.unban(
                                        user=user, reason="Timeban expired."
                                    )
                            finally:
                                await guild_doc.update_db(
                                    {
                                        "$unset": {
                                            f"punishments.{user_id}.{punishment}": 1
                                        }
                                    }
                                )

    async def cog_check(self, ctx: bots.CustomContext) -> bool:
        if not await has_permission_level(ctx, Permission.MODERATOR):
            raise LowPrivilege(Permission.MODERATOR, get_permission(ctx))
        else:
            return True

    @commands.command(
        name="purge",
        aliases=["purgemessages", "deletemessages"],
        brief="Delete a set amount of messages.",
        description="Delete a specified amount of messages in the current channel.",
    )
    @commands.bot_has_permissions(manage_messages=True)
    async def purge(self, ctx: bots.CustomContext, messages: int) -> None:
        await ctx.channel.purge(limit=messages + 1)

    @commands.command(
        name="kick",
        brief="Kicks user from the server.",
        description="Kicks user from the server.",
    )
    @commands.bot_has_permissions(kick_members=True)
    async def kick(
        self, ctx: bots.CustomContext, member: discord.Member, *, reason: Optional[str]
    ) -> None:
        await member.kick(reason=reason)

    @commands.command(
        name="ban",
        brief="Bans user from the server.",
        description="Bans user from the server.",
    )
    @commands.bot_has_permissions(ban_members=True)
    async def ban(
        self,
        ctx: bots.CustomContext,
        member: Union[discord.Member, discord.User],
        *,
        reason: Optional[str],
    ) -> None:
        await member.ban(reason=reason)

    @commands.command(
        name="unban",
        brief="Unbans user from the server.",
        description="Unbans user from the server.",
    )
    @commands.bot_has_permissions(ban_members=True)
    async def unban(
        self, ctx: bots.CustomContext, member: discord.Member, *, reason: Optional[str]
    ) -> None:
        await member.unban(reason=reason)

    @commands.command(
        name="mute",
        aliases=["gulag"],
        brief="Mutes user from typing in text channels.",
        description="Mutes user from typing in text channels. Must be configured first.",
    )
    @commands.bot_has_permissions(manage_roles=True)
    async def mute(self, ctx: bots.CustomContext, *, member: discord.Member) -> None:
        await mute(member, guild_document=ctx.guild_document)

    @commands.command(
        name="unmute",
        aliases=["ungulag"],
        brief="Unmutes user from typing in text channels.",
        description="Unmutes user from typing in text channels. Must be configured first.",
    )
    @commands.bot_has_permissions(manage_roles=True)
    async def unmute(self, ctx: bots.CustomContext, *, member: discord.Member) -> None:
        await unmute(member, guild_document=ctx.guild_document)

    @commands.command(
        name="timemute",
        aliases=["timegulag"],
        brief="Mutes a user and unmutes them later",
        description="Mutes a user then schedueles their unmuting",
        usage="<Member> [Time (Seconds)]",
    )
    @commands.bot_has_permissions(manage_roles=True)
    async def timemute(
        self,
        ctx: bots.CustomContext,
        member: discord.Member,
        unpunishtime: converters.TimedeltaShorthand,
    ) -> None:
        unpunishtime: datetime.timedelta = cast(datetime.timedelta, unpunishtime)
        await ctx.invoke(self.mute, member=member)
        await ctx.guild_document.update_db(
            {
                "$set": {
                    f"punishments.{member.id}.mute": (
                        datetime.datetime.utcnow() + unpunishtime
                    )
                }
            }
        )
        await ctx.message.add_reaction(emoji="⏰")

    @commands.command(
        name="timeban",
        brief="Mutes a user and unmutes them later",
        description="Mutes a user then schedueles their unmuting",
        usage="<Member> [Time (Seconds)]",
    )
    @commands.bot_has_permissions(ban_members=True)
    async def timeban(
        self,
        ctx: bots.CustomContext,
        member: discord.Member,
        unpunishtime: converters.TimedeltaShorthand,
    ) -> None:
        unpunishtime: datetime.timedelta = cast(datetime.timedelta, unpunishtime)
        await ctx.invoke(self.mute, member=member)
        await ctx.guild_document.update_db(
            {
                "$set": {
                    f"punishments.{member.id}.ban": (
                        datetime.datetime.utcnow() + unpunishtime
                    )
                }
            }
        )
        await ctx.message.add_reaction(emoji="⏰")


def setup(bot):
    bot.add_cog(Moderation(bot))
