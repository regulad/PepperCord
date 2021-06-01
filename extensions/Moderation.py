import time
import typing

import discord
from discord.ext import commands, tasks

from utils import checks, bots


class Moderation(commands.Cog):
    """Tools for moderation in guilds."""

    def __init__(self, bot):
        self.bot = bot

        self.unpunish.start()

    def cog_unload(self):
        self.unpunish.stop()

    @tasks.loop(seconds=60)
    async def unpunish(self):  # Ehhhhhh.....
        for guild in self.bot.guilds:
            # Get the document for the guild
            guild_doc = await self.bot.get_document(guild)
            punishment_dict = guild_doc.setdefault("punishments", {})
            # If the punishment dict is present
            if punishment_dict:
                for user_id in punishment_dict.keys():
                    user_dict = punishment_dict[user_id]
                    for punishment in user_dict.keys():
                        unpunish_time = user_dict[punishment]
                        if unpunish_time <= time.time():
                            try:
                                if punishment == "mute":
                                    mute_role = guild.get_role(guild_doc["mute_role"])
                                    member = guild.get_member(user_id)
                                    await member.remove_roles(mute_role)
                                elif punishment == "ban":
                                    user = self.bot.get_user(user_id)
                                    await guild.unban(user=user, reason="Timeban expired.")
                            finally:
                                del punishment_dict[user_id]
                                await guild_doc.replace_db()

    async def cog_check(self, ctx):
        return await checks.is_mod(ctx)

    @commands.command(
        name="purge",
        aliases=["purgemessages", "deletemessages"],
        brief="Delete a set amount of messages.",
        description="Delete a specified amount of messages in the current channel.",
    )
    @commands.bot_has_permissions(manage_messages=True)
    async def purge(self, ctx, messages: int):
        await ctx.channel.purge(limit=messages + 1)

    @commands.command(name="kick", brief="Kicks user from the server.", description="Kicks user from the server.")
    @commands.bot_has_permissions(kick_members=True)
    async def kick(self, ctx, member: discord.Member, *, reason: str = ""):
        await member.kick(reason=reason)

    @commands.command(name="ban", brief="Bans user from the server.", description="Bans user from the server.")
    @commands.bot_has_permissions(ban_members=True)
    async def ban(self, ctx, member: typing.Union[discord.Member, discord.User], *, reason: str = ""):
        await ctx.guild.ban(user=member, reason=reason)

    @commands.command(name="unban", brief="Unbans user from the server.", description="Unbans user from the server.")
    @commands.bot_has_permissions(ban_members=True)
    async def unban(self, ctx, member: typing.Union[discord.Member, discord.User], *, reason: str = ""):
        await ctx.guild.unban(user=member, reason=reason)

    @commands.command(
        name="mute",
        aliases=["gulag"],
        brief="Mutes user from typing in text channels.",
        description="Mutes user from typing in text channels. Must be configured first.",
    )
    @commands.bot_has_permissions(manage_roles=True)
    async def mute(self, ctx, *, member: discord.Member):
        try:
            mute_role = ctx.guild.get_role(ctx.guild_document["mute_role"])
        except KeyError:
            raise bots.NotConfigured
        await member.add_roles(mute_role)

    @commands.command(
        name="unmute",
        aliases=["ungulag"],
        brief="Unmutes user from typing in text channels.",
        description="Unmutes user from typing in text channels. Must be configured first.",
    )
    @commands.bot_has_permissions(manage_roles=True)
    async def unmute(self, ctx, *, member: discord.Member):
        try:
            mute_role = ctx.guild.get_role(ctx.guild_document["mute_role"])
        except KeyError:
            raise bots.NotConfigured
        await member.remove_roles(mute_role)

    @commands.command(
        name="timemute",
        aliases=["timegulag"],
        brief="Mutes a user and unmutes them later",
        description="Mutes a user then schedueles their unmuting",
        usage="<Member> [Time (Minutes)]",
    )
    @commands.bot_has_permissions(manage_roles=True)
    async def timemute(self, ctx, member: discord.Member, unpunishtime: int = 10):
        await ctx.invoke(self.mute, member=member)
        ctx.guild_document.setdefault("punishments", {})[str(member.id)] = {"mute": time.time() + (unpunishtime * 60)}
        await ctx.guild_document.replace_db()
        await ctx.message.add_reaction(emoji="⏰")

    @commands.command(
        name="timeban",
        brief="Mutes a user and unmutes them later",
        description="Mutes a user then schedueles their unmuting",
        usage="<Member> [Time (Minutes)]",
    )
    @commands.bot_has_permissions(ban_members=True)
    async def timeban(self, ctx, member: discord.Member, unpunishtime: int = 10):
        await ctx.invoke(self.mute, member=member)
        ctx.guild_document.setdefault("punishments", {})[str(member.id)] = {"ban": time.time() + (unpunishtime * 60)}
        await ctx.guild_document.replace_db()
        await ctx.message.add_reaction(emoji="⏰")


def setup(bot):
    bot.add_cog(Moderation(bot))
