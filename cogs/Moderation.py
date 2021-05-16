import copy
import time
import typing

import discord
import instances
import pymongo
from discord.ext import commands, tasks
from utils import checks, errors, managers


class GuildPunishmentManager(managers.CommonConfigManager):
    def __init__(self, guild: discord.Guild, collection: pymongo.collection.Collection):
        super().__init__(guild, collection, "punishments", {})

    def write(self, punishment_type: str, member: discord.Member, punishment_time: typing.Union[int, float]):
        unpunishtime = time.time() + punishment_time
        working_key = copy.deepcopy(self.active_key)
        working_key.update({str(member.id): {punishment_type: unpunishtime}})
        super().write(working_key)

    def delete(self, member: discord.Member):
        working_key = copy.deepcopy(self.active_key)
        working_key.update({str(member.id): 1})
        super().delete(working_key)


class Moderation(
    commands.Cog,
    name="Moderation",
    description="Tools for moderation.",
):
    def __init__(self, bot):
        self.bot = bot

        self.unpunish.start()

    def cog_unload(self):
        self.unpunish.stop()

    @tasks.loop(seconds=30)
    async def unpunish(self):
        for guild in self.bot.guilds:
            guild_punishments = GuildPunishmentManager(guild, instances.guild_collection)
            punishment_dict = guild_punishments.read()
            if punishment_dict:
                for user in punishment_dict.keys():
                    user_dict = punishment_dict[user]
                    user_model = self.bot.get_user(int(user))
                    for punishment in user_dict.keys():
                        unpunish_time = user_dict[punishment]
                        if unpunish_time <= time.time():
                            try:
                                if punishment == "mute":
                                    mute_role_id = managers.CommonConfigManager(
                                        guild,
                                        instances.guild_collection,
                                        "mute_role",
                                        "",
                                    ).read()
                                    mute_role = guild.get_role(mute_role_id)
                                    member = await guild.fetch_member(user_model.id)
                                    try:
                                        await member.remove_roles(mute_role)
                                    except:
                                        pass
                                elif punishment == "ban":
                                    try:
                                        await guild.unban(user=user_model, reason="Timeban expired.")
                                    except:
                                        pass
                            finally:
                                guild_punishments.delete(user_model)

    async def cog_check(self, ctx):
        return await checks.has_permission_level(ctx, 2)

    @commands.command(
        name="purge",
        aliases=["purgemessages", "deletemessages"],
        brief="Delete a set amount of messages.",
        description="Delete a specified amount of messages in the current channel.",
    )
    async def purge(self, ctx, messages: int):
        await ctx.channel.purge(limit=messages + 1)

    @commands.command(name="kick", brief="Kicks user from the server.", description="Kicks user from the server.")
    async def kick(self, ctx, member: discord.Member, *, reason: str = ""):
        try:
            await member.kick(reason=reason)
        except:
            await ctx.message.add_reaction(emoji="\U0000274c")
        else:
            await ctx.message.add_reaction(emoji="\U00002705")

    @commands.command(name="ban", brief="Bans user from the server.", description="Bans user from the server.")
    async def ban(self, ctx, member: typing.Union[discord.Member, discord.User], *, reason: str = ""):
        try:
            await ctx.guild.ban(user=member, reason=reason)
        except:
            await ctx.message.add_reaction(emoji="\U0000274c")
        else:
            await ctx.message.add_reaction(emoji="\U00002705")

    @commands.command(name="unban", brief="Unbans user from the server.", description="Unbans user from the server.")
    async def unban(self, ctx, member: typing.Union[discord.Member, discord.User], *, reason: str = ""):
        try:
            await ctx.guild.unban(user=member, reason=reason)
        except:
            await ctx.message.add_reaction(emoji="\U0000274c")
        else:
            await ctx.message.add_reaction(emoji="\U00002705")

    @commands.command(
        name="mute",
        aliases=["gulag"],
        brief="Mutes user from typing in text channels.",
        description="Mutes user from typing in text channels. Must be configured first.",
    )
    async def mute(self, ctx, *, member: discord.Member):
        try:
            mute_role_id = managers.CommonConfigManager(
                ctx.guild,
                instances.guild_collection,
                "mute_role",
                0,
            ).read()
            mute_role = ctx.guild.get_role(mute_role_id)
        except:
            raise errors.NotConfigured()
        try:
            await member.add_roles(mute_role)
        except:
            await ctx.message.add_reaction(emoji="\U0000274c")
        else:
            await ctx.message.add_reaction(emoji="\U00002705")

    @commands.command(
        name="unmute",
        aliases=["ungulag"],
        brief="Unmutes user from typing in text channels.",
        description="Unmutes user from typing in text channels. Must be configured first.",
    )
    async def unmute(self, ctx, *, member: discord.Member):
        try:
            mute_role_id = managers.CommonConfigManager(
                ctx.guild,
                instances.guild_collection,
                "mute_role",
                0,
            ).read()
            mute_role = ctx.guild.get_role(mute_role_id)
        except:
            raise errors.NotConfigured()
        try:
            await member.remove_roles(mute_role)
        except:
            await ctx.message.add_reaction(emoji="\U0000274c")
        else:
            await ctx.message.add_reaction(emoji="\U00002705")

    @commands.command(
        name="timemute",
        aliases=["timegulag"],
        brief="Mutes a user and unmutes them later",
        description="Mutes a user then schedueles their unmuting",
        usage="<Member> [Time (Minutes)]",
    )
    async def timemute(self, ctx, member: discord.Member, time: int = 10):
        try:
            await ctx.invoke(self.mute, member=member)
            GuildPunishmentManager(
                ctx.guild,
                instances.guild_collection,
            ).write("mute", member, time * 60)
        except:
            await ctx.message.add_reaction(emoji="\U0000274c")
        else:
            await ctx.message.add_reaction(emoji="\U000023ed")

    @commands.command(
        name="timeban",
        brief="Mutes a user and unmutes them later",
        description="Mutes a user then schedueles their unmuting",
        usage="<Member> [Time (Minutes)]",
    )
    async def timeban(self, ctx, member: discord.Member, time: int = 10):
        try:
            await ctx.invoke(self.ban, member=member)
            GuildPunishmentManager(
                ctx.guild,
                instances.guild_collection,
            ).write("ban", member, time * 60)
        except:
            await ctx.message.add_reaction(emoji="\U0000274c")
        else:
            await ctx.message.add_reaction(emoji="\U000023ed")


def setup(bot):
    bot.add_cog(Moderation(bot))
