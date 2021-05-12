import discord
import instances
from utils import checks, errors, managers
from discord.ext import commands


class moderation(
    commands.Cog,
    name="Moderation",
    description="Tools for moderation.",
):
    def __init__(self, bot):
        self.bot = bot

    async def cog_check(self, ctx):
        return checks.has_permission_level(ctx, 2)

    @commands.command(
        name="purge",
        aliases=["purgemessages", "deletemessages"],
        brief="Delete a set amount of messages.",
        description="Delete a specified amount of messages in the current channel.",
    )
    async def purge(self, ctx, messages: int):
        await ctx.channel.purge(limit=messages + 1)

    @commands.command(name="kick", brief="Kicks user from the server.", description="Kicks user from the server.")
    async def kick(self, ctx, member: discord.Member, *, reason: str):
        try:
            await member.kick(reason=reason)
        except:
            await ctx.message.add_reaction(emoji="\U0000274c")
        else:
            await ctx.message.add_reaction(emoji="\U00002705")

    @commands.command(name="ban", brief="Bans user from the server.", description="Banss user from the server.")
    async def ban(self, ctx, member: discord.Member, *, reason: str):
        try:
            await member.ban(reason=reason)
        except:
            await ctx.message.add_reaction(emoji="\U0000274c")
        else:
            await ctx.message.add_reaction(emoji="\U00002705")

    @commands.command(
        name="mute",
        brief="Mutes user from typing in text channels.",
        description="Mutes user from typing in text channels. Must be configured first.",
    )
    async def mute(self, ctx, *, member: discord.Member):
        try:
            mute_role_id = managers.GuildConfigManager(
                ctx.guild,
                instances.activeDatabase["servers"],
                "mute_role",
                "",
            ).read()
            mute_role = ctx.guild.get_role(int(mute_role_id))
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
        brief="Unmutes user from typing in text channels.",
        description="Unmutes user from typing in text channels. Must be configured first.",
    )
    async def unmute(self, ctx, *, member: discord.Member):
        try:
            mute_role_id = managers.GuildConfigManager(
                ctx.guild,
                instances.activeDatabase["servers"],
                "mute_role",
                "",
            ).read()
            mute_role = ctx.guild.get_role(int(mute_role_id))
        except:
            raise errors.NotConfigured()
        try:
            await member.remove_roles(mute_role)
        except:
            await ctx.message.add_reaction(emoji="\U0000274c")
        else:
            await ctx.message.add_reaction(emoji="\U00002705")


def setup(bot):
    bot.add_cog(moderation(bot))
