import datetime
import math
from typing import Optional, Union, cast

import discord
from discord.app_commands import describe, default_permissions
from discord.app_commands import guild_only as ac_guild_only
from discord.ext import commands, tasks
from discord.ext.commands import hybrid_command, guild_only

from utils import bots, database, converters
from utils.bots import BOT_TYPES


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
                        if unpunish_time < datetime.datetime.utcnow():
                            try:  # Messy.
                                if punishment == "ban":
                                    user: discord.User = self.bot.get_user(
                                        user_id
                                    ) or await self.bot.fetch_user(user_id)
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

    @hybrid_command()
    @commands.is_owner()
    async def nopunish(self, ctx: bots.CustomContext):
        """Clears all previous punishments."""
        async with ctx.typing():
            for guild in ctx.bot.guilds:
                await (await ctx.bot.get_guild_document(guild)).update_db(
                    {"$unset": {"punishments": 1}}
                )
            await ctx.send("Done.")

    @hybrid_command(aliases=["pu", "del"])
    @commands.has_permissions(manage_messages=True)
    @commands.bot_has_permissions(manage_messages=True)
    @default_permissions(manage_messages=True)
    @ac_guild_only()
    @guild_only()
    @describe(messages="The amount of messages to be deleted.")
    async def purge(
            self,
            ctx: bots.CustomContext,
            messages: int,
    ) -> None:
        """Deletes a set amount of messages from a channel."""
        async with ctx.typing(ephemeral=True):
            if ctx.interaction is None:
                await ctx.message.delete()
            await ctx.channel.purge(limit=messages, reason=f"Requested by {ctx.author}.")
            await ctx.send("Deleted.", ephemeral=True, delete_after=5)

    @hybrid_command(aliases=["tb"])
    @commands.has_permissions(ban_members=True)
    @commands.bot_has_permissions(ban_members=True)
    @default_permissions(manage_messages=True)
    @describe(
        member="The member to be banned.",
        reason="The reason for the ban.",
        time="The amount of time for the user to be banned for",
    )
    @ac_guild_only()
    @guild_only()
    async def timeban(
            self,
            ctx: bots.CustomContext,
            member: discord.Member,
            time: converters.TimedeltaShorthand,
            *,
            reason: str | None = None,
    ) -> None:
        """Bans a member, and then unbans them later."""
        member: member if not isinstance(member, int) else discord.Object(id=member)
        if ctx.guild.roles.index(ctx.author.roles[-1]) <= ctx.guild.roles.index(
                member.roles[-1]
        ):
            raise RuntimeError("You cannot ban this member.")
        time: datetime.timedelta = cast(datetime.timedelta, time)
        unpunishdatetime: datetime.datetime = datetime.datetime.utcnow() + time
        localunpunishdatetime: datetime.datetime = (
                datetime.datetime.now() + time
        )  # Us "humans" have this "time" thing all wrong. ow.
        await member.send(
            (
                await ctx.channel.create_invite(
                    reason=f"Unban for {reason}",
                    max_uses=1,
                    max_age=int((time + datetime.timedelta(days=1)).total_seconds()),
                )
            ).url,
            embed=discord.Embed(
                description=f"To rejoin <t:{math.floor(localunpunishdatetime.timestamp())}:R> "
                            f"({unpunishdatetime.astimezone().tzinfo.tzname(unpunishdatetime).upper()}), "
                            f"use this link. It will not work until then."
            ),
        )
        await member.ban(reason=reason, delete_message_days=0)
        await ctx["guild_document"].update_db(
            {"$set": {f"punishments.{member.id}.ban": unpunishdatetime}}
        )
        await ctx.send(
            "This member has been bans, and their unpunishment has been scheduled.",
            ephemeral=True,
        )


async def setup(bot: BOT_TYPES) -> None:
    await bot.add_cog(Moderation(bot))
