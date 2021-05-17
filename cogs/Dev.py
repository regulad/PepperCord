import typing

import discord
import instances
from discord.ext import commands
from utils import managers


class Dev(
    commands.Cog,
    name="Developer",
    description="Commands for the bot's developer used to operate the bot.",
):
    def __init__(self, bot):
        self.bot = bot

    async def cog_check(self, ctx):
        return await self.bot.is_owner(ctx.author)

    @commands.command(
        name="blacklist",
        description="Tools to blacklist entity from using the bot.",
        brief="Blacklists declared entity.",
        usage="<Value> <Entity>",
    )
    async def blacklist(self, ctx, value: bool, *, entity: typing.Union[discord.Guild, discord.Member, discord.User]):
        if isinstance(entity, discord.Guild):
            collection = instances.guild_collection
        elif isinstance(entity, (discord.Member, discord.User)):
            collection = instances.user_collection
        managers.BlacklistManager(
            entity,
            collection,
        ).write(value)
        await ctx.message.add_reaction(emoji="\U00002705")

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
