import datetime
import math
from typing import Optional, Union, cast

import discord
from discord.ext import commands, tasks

from utils import bots, database, converters


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
                                second=unpunish_time,
                                day=0,
                                month=0,
                                year=0,
                                tzinfo=datetime.timezone.utc,
                            )
                        ) < datetime.datetime.utcnow():
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

    @commands.command()
    @commands.has_permissions(moderate_members=True)
    @commands.bot_has_permissions(manage_messages=True)
    async def purge(
        self,
        ctx: bots.CustomContext,
        messages: int = commands.Option(
            description="The amount of messages to be deleted."
        ),
    ) -> None:
        """Deletes a set amount of messages from a channel."""
        await ctx.channel.purge(limit=messages)
        await ctx.send("Deleted.", ephemeral=True)

    @commands.command()
    @commands.has_permissions(moderate_members=True)
    @commands.bot_has_permissions(ban_members=True)
    async def timeban(
        self,
        ctx: bots.CustomContext,
        member: discord.Member = commands.Option(
            description="The member to be banned."
        ),
        time: converters.TimedeltaShorthand = commands.Option(
            description="The amount of time to keep the member punished for. Example: 10d."
        ),
        *,
        reason: str = commands.Option(
            None, description="The reason why this user was banned."
        ),
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
                description=f"To rejoin <t:{math.floor(localunpunishdatetime.timestamp())}:R> ({unpunishdatetime.astimezone().tzinfo.tzname(unpunishdatetime).upper()}), "
                f"use this link. It will not work until then."
            ),
        )
        await member.ban(reason=reason, delete_message_days=0)
        await ctx["guild_document"].update_db(
            {"$set": {f"punishments.{member.id}.ban": (unpunishdatetime)}}
        )
        await ctx.send(
            "This member has been bans, and their unpunishment has been scheduled.",
            ephemeral=True,
        )


def setup(bot):
    bot.add_cog(Moderation(bot))
