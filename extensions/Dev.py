import typing

import discord
import instances
from discord.ext import commands
from utils import permissions


class Dev(
    commands.Cog,
    name="Developer",
    description="Commands for the bot's developer used to operate the bot.",
):
    def __init__(self, bot):
        self.bot = bot

    async def cog_check(self, ctx):
        return await self.bot.is_owner(ctx.author)

    # If the bot joins a blacklisted guild, leave.
    @commands.Cog.listener()
    async def on_guild_join(guild: discord.Guild):
        if permissions.BlacklistManager(guild, instances.active_collection).read():
            await guild.leave()

    @commands.command(
        name="blacklist",
        description="Tools to blacklist entity from using the bot.",
        brief="Blacklists declared entity.",
        usage="<Value> <Entity>",
    )
    async def blacklist(self, ctx, value: typing.Optional[bool], *, entity: typing.Optional[discord.Guild]):
        value = value or True
        entity = entity or ctx.guild
        blacklist_manager = permissions.BlacklistManager(
            entity,
            instances.active_collection,
        )
        await blacklist_manager.fetch_document()
        await blacklist_manager.write(value)
        await ctx.message.add_reaction(emoji="✅")

    @commands.command(
        name="nick",
        aliases=["nickname"],
        brief="Change nickname.",
        description="Change the bot's nickname, for situations where you do not have privleges to.",
    )
    @commands.guild_only()
    async def nick(self, ctx, *, name: str):
        await ctx.guild.me.edit(nick=name)


def setup(bot):
    bot.add_cog(Dev(bot))
