import copy
import datetime
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


async def get_any_id(ctx: commands.Context, uid: int) -> Optional[Union[discord.Member, discord.User]]:
    possible_object: Optional[Union[discord.Member, discord.User]] = ctx.guild.get_member(uid) or ctx.bot.get_user(uid)
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

    @tasks.loop(seconds=120)
    async def unpunish(self) -> None:
        for guild in self.bot.guilds:
            guild_doc: database.Document = await self.bot.get_guild_document(guild)
            if guild_doc.get("punishments") is not None:
                for user_id, user_dict in guild_doc["punishments"].items():
                    for punishment, unpunish_time in user_dict.items():
                        if (unpunish_time if isinstance(unpunish_time, datetime.datetime) else datetime.datetime(
                                second=unpunish_time, tzinfo=datetime.timezone.utc)) < datetime.datetime.utcnow():
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
        name="shufflenames",
        aliases=["shufflenicks"],
        brief="Shuffles usernames.",
        description="Shuffles usernames around between people. Do it again to reverse."
    )
    @commands.cooldown(1, 3600, commands.BucketType.guild)
    @commands.bot_has_permissions(manage_nicknames=True)
    async def shufflenicks(self, ctx: bots.CustomContext) -> None:
        async with ctx.typing():
            if ctx["guild_document"].get("shuffled") is None:
                if divmod(len(ctx.guild.members), 2)[-1] != 0:  # If member count is not even
                    temp_member_list: Optional[List[discord.Member]] = copy.copy(ctx.guild.members)
                    temp_member_list.pop()
                    member_list: List[discord.Member] = temp_member_list
                else:
                    member_list: List[discord.Member] = copy.copy(ctx.guild.members)

                middle_index: int = len(member_list) // 2
                pair_set_one: List[discord.Member] = member_list[middle_index:]
                pair_set_two: List[discord.Member] = member_list[:middle_index]

                pairing: Dict[discord.Member, discord.Member] = {}

                for one, two in zip(pair_set_one, pair_set_two):
                    pairing[one] = two

                member_pairings: Dict[Union[discord.Member, discord.User], Union[discord.Member, discord.User]] \
                    = copy.copy(pairing)

                db_pairings: Dict[str, int] = {}
                for one, two in pairing.items():
                    db_pairings[str(one.id)] = two.id

                await ctx["guild_document"].update_db({"$set": {"shuffled": db_pairings}})
            else:  # Previous paring exists, roll with it
                db_pairings: Dict[str, int] = copy.copy(ctx["guild_document"]["shuffled"])
                await ctx["guild_document"].update_db({"$unset": {"shuffled": 1}})  # Reset
                member_pairings: Dict[Union[discord.Member, discord.User], Union[discord.Member, discord.User]] = {}
                for one_id_as_str, two_id in db_pairings.items():
                    one: Optional[Union[discord.Member, discord.User]] = await get_any_id(ctx, int(one_id_as_str))
                    two: Optional[Union[discord.Member, discord.User]] = await get_any_id(ctx, two_id)

                    assert one is not None, two is not None

                    member_pairings[one] = two
            # Time to actually shuffle nicks...

            for one, two in member_pairings.items():
                one_display_name: str = copy.copy(one.display_name)
                if isinstance(one, discord.Member):
                    try:
                        await one.edit(nick=two.display_name,
                                       reason=f"Nickname shuffle requested by {ctx.author.display_name}")
                    except discord.Forbidden:
                        pass
                if isinstance(two, discord.Member):
                    try:
                        await two.edit(nick=one_display_name,
                                       reason=f"Nickname shuffle requested by {ctx.author.display_name}")
                    except discord.Forbidden:
                        pass

    @commands.command(
        name="resetnames",
        aliases=["resetnicks"],
        brief="Resets all user's nicknames."
    )
    @commands.cooldown(1, 3600, commands.BucketType.guild)
    @commands.bot_has_permissions(manage_nicknames=True)
    async def resetnicks(self, ctx: bots.CustomContext) -> None:
        async with ctx.typing():
            if ctx["guild_document"].get("shuffled") is not None:
                await ctx["guild_document"].update_db({"$unset": {"shuffled": 1}})
            for member in ctx.guild.members:
                try:
                    await member.edit(nick=None)
                except discord.Forbidden:
                    continue

    @commands.command(
        name="mute",
        aliases=["gulag"],
        brief="Mutes user from typing in text channels.",
        description="Mutes user from typing in text channels. Must be configured first.",
    )
    @commands.bot_has_permissions(manage_roles=True)
    async def mute(self, ctx: bots.CustomContext, *, member: discord.Member) -> None:
        await mute(member, guild_document=ctx["guild_document"])

    @commands.command(
        name="unmute",
        aliases=["ungulag"],
        brief="Unmutes user from typing in text channels.",
        description="Unmutes user from typing in text channels. Must be configured first.",
    )
    @commands.bot_has_permissions(manage_roles=True)
    async def unmute(self, ctx: bots.CustomContext, *, member: discord.Member) -> None:
        await unmute(member, guild_document=ctx["guild_document"])

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
        await ctx["guild_document"].update_db(
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
        await ctx["guild_document"].update_db(
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
