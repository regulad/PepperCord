import math
import typing

import discord
import instances
import pymongo
from discord.ext import commands
from utils import checks, errors, managers


xp_to = 2.7
xp_multiplier = 1.5


def get_xp(level: int):
    xp = level ** xp_to * xp_multiplier
    return xp


def get_level(xp: typing.Union[int, float]):
    level = (xp / xp_multiplier) ** (1.0 / xp_to)
    return math.trunc(level)


class LevelConfigManager(managers.CommonConfigManager):
    def __init__(
        self,
        model: discord.Guild,
        collection: pymongo.collection.Collection,
    ):
        super().__init__(model, collection, "levels_disabled", False)


class LevelManager(managers.CommonConfigManager):
    def __init__(self, model: typing.Union[discord.Member, discord.User], collection: pymongo.collection.Collection):
        super().__init__(model, collection, "xp", 0)

    def increment(self, new_xp: int):
        new_key = self.active_key + new_xp
        super().write(new_key)


class Levels(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if not message.guild:
            return

    @commands.group(
        invoke_without_command=True,
        case_insensitive=True,
        name="xp",
        brief="XP tools.",
        description="XP/Levelling tools & configuration.",
    )
    @commands.guild_only()
    async def xp(self, ctx):
        raise errors.SubcommandNotFound()

    @xp.command(
        name="disable", brief="Disables levelling in a server.", description="Disables earning of XP and level-up alerts."
    )
    @commands.check(checks.is_admin)
    async def disable(self, ctx):
        LevelConfigManager(ctx.guild, instances.guild_collection).write(True)
        await ctx.message.add_reaction(emoji="✅")

    @xp.command(
        name="enable", brief="Enables levelling in a server.", description="Enables earning of XP and level-up alerts."
    )
    @commands.check(checks.is_admin)
    async def enable(self, ctx):
        LevelConfigManager(ctx.guild, instances.guild_collection).write(False)
        await ctx.message.add_reaction(emoji="✅")

    @xp.command(name="set", brief="Writes XP level.", description="Writes XP level, overriding any present XP.")
    @commands.is_owner()
    async def set(self, ctx, user: typing.Optional[typing.Union[discord.Member, discord.User]], *, xp: int):
        user = user or ctx.author
        LevelManager(user, instances.user_collection).write(xp)
        await ctx.message.add_reaction(emoji="✅")

    @xp.command(
        name="increment", aliases=["add"], brief="Adds to XP level.", description="Adds to XP level, keeping any present XP."
    )
    @commands.is_owner()
    async def set(self, ctx, user: typing.Optional[typing.Union[discord.Member, discord.User]], *, xp: int):
        user = user or ctx.author
        LevelManager(user, instances.user_collection).increment(xp)
        await ctx.message.add_reaction(emoji="✅")

    @commands.command(name="rank", aliases=["level"], brief="Displays current level & rank.")
    async def rank(self, ctx, *, user: typing.Optional[typing.Union[discord.Member, discord.User]]):
        user = user or ctx.author
        xp = LevelManager(user, instances.user_collection).read()
        level = get_level(xp)
        next_level = get_xp(level + 1) - xp
        embed = (
            discord.Embed(colour=user.colour, title=f"{user.name}'s Level")
            .add_field(name="XP:", value=f"```{xp}```")
            .add_field(name="Level:", value=f"```{level}```")
            .add_field(name="To next:", value=f"```{round(next_level)}```")
            .set_thumbnail(url=user.avatar_url)
        )
        await ctx.send(embed=embed)


def setup(bot):
    bot.add_cog(Levels(bot))
