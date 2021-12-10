import copy
import datetime
import math
from typing import Optional, Union, cast, List, Dict

import discord
from discord.ext import commands, tasks

from utils import bots, database, converters
from utils.checks import LowPrivilege, has_permission_level
from utils.permissions import Permission, get_permission


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


async def get_any_id(
    ctx: commands.Context, uid: int
) -> Optional[Union[discord.Member, discord.User]]:
    possible_object: Optional[
        Union[discord.Member, discord.User]
    ] = ctx.guild.get_member(uid) or ctx.bot.get_user(uid)
    if possible_object is not None:
        return possible_object
    else:
        try:
            return await ctx.bot.fetch_user(uid)
        except discord.NotFound:
            return None


class Moderation(commands.Cog):
    """Tools for moderation in guilds."""

    def __init__(self, bot: bots.BOT_TYPES) -> None:
        self.bot = bot

        self.unpunish.start()

    def cog_unload(self) -> None:
        self.unpunish.stop()

    @tasks.loop(seconds=10)
    async def unpunish(self) -> None:
        for guild in self.bot.guilds:
            guild_doc: database.Document = await self.bot.get_guild_document(guild)
            if guild_doc.get("punishments") is not None:
                for user_id, user_dict in guild_doc["punishments"].items():
                    for punishment, unpunish_time in user_dict.items():
                        if (
                            unpunish_time
                            if isinstance(unpunish_time, datetime.datetime)
                            else datetime.datetime(
                                second=unpunish_time, day=0, month=0, year=0, tzinfo=datetime.timezone.utc
                            )
                        ) < datetime.datetime.utcnow():
                            try:  # Messy.
                                if punishment == "mute":
                                    await unmute(
                                        await guild.fetch_member(int(user_id)),
                                        guild_document=guild_doc,
                                    )
                                elif punishment == "ban":
                                    user: discord.User = self.bot.get_user(user_id) or await self.bot.fetch_user(user_id)
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

    @commands.command()
    @commands.bot_has_permissions(manage_messages=True)
    async def purge(self, ctx: bots.CustomContext, messages: int) -> None:
        """Deletes a set amount of messages from a channel."""
        await ctx.channel.purge(limit=messages)
        await ctx.send("Deleted.", ephemeral=True)

    @commands.command()
    @commands.bot_has_permissions(manage_roles=True)
    async def mute(self, ctx: bots.CustomContext, *, member: discord.Member) -> None:
        """
        Mutes a member of the server.
        You must first configure this with the config command.
        """
        await mute(member, guild_document=ctx["guild_document"])
        await ctx.send(f"<@{member.id}> has been muted.")

    @commands.command()
    @commands.bot_has_permissions(manage_roles=True)
    async def unmute(self, ctx: bots.CustomContext, *, member: discord.Member) -> None:
        """
        Unmutes a member of the server.
        You must first configure this with the config command, and you must also have muted this member previously.
        """
        await unmute(member, guild_document=ctx["guild_document"])
        await ctx.send(f"<@{member.id}> has been unmuted.")

    @commands.command()
    @commands.bot_has_permissions(manage_roles=True)
    async def timemute(
        self,
        ctx: bots.CustomContext,
        member: discord.Member,
        time: converters.TimedeltaShorthand,
    ) -> None:
        """Mutes a member, and then unmutes them later."""
        time: datetime.timedelta = cast(datetime.timedelta, time)
        await ctx.invoke(self.mute, member=member)
        await ctx["guild_document"].update_db(
            {
                "$set": {
                    f"punishments.{member.id}.mute": (
                            datetime.datetime.utcnow() + time
                    )
                }
            }
        )
        await ctx.send("This member has been muted, and their unpunishment has been scheduled.", ephemeral=True)

    @commands.command()
    @commands.bot_has_permissions(ban_members=True)
    async def timeban(
        self,
        ctx: bots.CustomContext,
        member: discord.Member,
        time: converters.TimedeltaShorthand,
        *,
        reason: str = None,
    ) -> None:
        """Bans a member, and then unbans them later."""
        member: member if not isinstance(member, int) else discord.Object(id=member)
        if get_permission(ctx, member) >= get_permission(ctx, ctx.author):
            raise RuntimeError("You cannot ban this member.")
        time: datetime.timedelta = cast(datetime.timedelta, time)
        unpunishdatetime: datetime.datetime = datetime.datetime.utcnow() + time
        localunpunishdatetime: datetime.datetime = datetime.datetime.now() + time  # Us "humans" have this "time" thing all wrong. ow.
        await member.send(
            (await ctx.channel.create_invite(reason=f'Unban for {reason}', max_uses=1, max_age=int((time + datetime.timedelta(days=1)).total_seconds()))).url,
            embed=discord.Embed(description=f"To rejoin <t:{math.floor(localunpunishdatetime.timestamp())}:R> ({unpunishdatetime.astimezone().tzinfo.tzname(unpunishdatetime).upper()}), "
                                            f"use this link. It will not work until then.")
        )
        await member.ban(reason=reason, delete_message_days=0)
        await ctx["guild_document"].update_db(
            {
                "$set": {
                    f"punishments.{member.id}.ban": (
                        unpunishdatetime
                    )
                }
            }
        )
        await ctx.send("This member has been bans, and their unpunishment has been scheduled.", ephemeral=True)


def setup(bot):
    bot.add_cog(Moderation(bot))
