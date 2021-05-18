import math
import random
import typing

import discord
import instances
import pymongo
from discord.ext import commands
from utils import checks, errors, managers

xp_to = 2.8
xp_multiplier = 1.7
xp_start = 1
xp_end = 5


def get_xp(level: int):
    xp = level ** xp_to * xp_multiplier
    return xp


def get_level(xp: typing.Union[int, float]):
    level = (xp / xp_multiplier) ** (1.0 / xp_to)
    return math.trunc(level)


class LevelConfigManager(managers.CommonConfigManager):
    def __init__(
        self,
        model: typing.Union[discord.Guild, discord.Member, discord.User],
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
        self.bot: commands.Bot = bot
        self.xp_cd = commands.CooldownMapping.from_cooldown(3, 10, commands.BucketType.user)

    async def cog_check(self, ctx):
        if ctx.guild is None:
            raise commands.NoPrivateMessage()
        return True

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # Recursion prevention
        if (not message.guild) or (message.author.bot):
            return
        # Cooldown
        bucket = self.xp_cd.get_bucket(message)
        retry_after = bucket.update_rate_limit()
        if retry_after:
            return
        # Actual processing
        user_instance = LevelManager(message.author, instances.user_collection)
        current_xp = user_instance.read()
        current_level = get_level(current_xp)
        message_xp = random.randrange(xp_start, xp_end)
        new_xp = current_xp + message_xp
        new_level = get_level(new_xp)
        # Levelup message
        if new_level > current_level:
            # Disabled
            guild_config = LevelConfigManager(message.guild, instances.guild_collection)
            user_config = LevelConfigManager(message.author, instances.user_collection)
            if not (guild_config.read() or user_config.read()):
                next_xp = get_xp(new_level + 1) - current_xp
                embed = (
                    discord.Embed(
                        colour=message.author.colour,
                        title="Level up!",
                        description=f"{message.author.display_name} just levelled up to `{new_level}`!",
                    )
                    .add_field(name="To next:", value=f"```{round(next_xp)}```")
                    .set_thumbnail(url=message.author.avatar_url)
                )
                channel = managers.CommonConfigManager(
                    message.guild,
                    instances.guild_collection,
                    "redirect",
                    0,
                ).read()
                if channel:
                    channel_model: discord.TextChannel = message.guild.get_channel(channel)
                    await channel_model.send(message.author.mention, embed=embed)
                else:
                    await message.reply(embed=embed)
        # The actual action
        user_instance.increment(message_xp)

    @commands.group(
        invoke_without_command=True,
        case_insensitive=True,
        name="disablexp",
        aliases=["disablelevels"],
        brief="Disables level-up alerts.",
        description="Disables level-up alerts. You will still earn XP to use in other servers.",
    )
    async def disablexp(self, ctx):
        raise errors.SubcommandNotFound()

    @disablexp.command(
        name="server",
        aliases=["guild"],
        brief="Disables level-up alerts for the entire server.",
        description="Disables level-up alerts for the entire server. Server members will still learn XP to use in other servers that the bot is in.",
    )
    @commands.check(checks.is_admin)
    async def dserver(self, ctx):
        LevelConfigManager(ctx.guild, instances.guild_collection).write(True)
        await ctx.message.add_reaction(emoji="✅")

    @disablexp.command(
        name="user",
        aliases=["self"],
        brief="Disables level-up alerts for just you.",
        description="Disables level-up alerts for just you. You will still earn XP to use in other servers.",
    )
    async def duser(self, ctx):
        LevelConfigManager(ctx.author, instances.guild_collection).write(True)
        await ctx.message.add_reaction(emoji="✅")

    @commands.group(
        invoke_without_command=True,
        case_insensitive=True,
        name="Enablesxp",
        aliases=["enablelevels"],
        brief="Enables level-up alerts.",
        description="Enables level-up alerts. You will still earn XP to use in other servers.",
    )
    async def enablexp(self, ctx):
        raise errors.SubcommandNotFound()

    @enablexp.command(
        name="server",
        aliases=["guild"],
        brief="Enables level-up alerts for the entire server.",
        description="Enables level-up alerts for the entire server. Server members who have individually disabled notofications will still be disabled.",
    )
    @commands.check(checks.is_admin)
    async def eserver(self, ctx):
        LevelConfigManager(ctx.guild, instances.guild_collection).write(False)
        await ctx.message.add_reaction(emoji="✅")

    @enablexp.command(
        name="user",
        aliases=["self"],
        brief="Enables level-up alerts for just you.",
        description="Enables level-up alerts for just you. You will still earn XP to use in other servers.",
    )
    async def euser(self, ctx):
        LevelConfigManager(ctx.author, instances.guild_collection).write(False)
        await ctx.message.add_reaction(emoji="✅")

    @commands.command(
        name="setxp", brief="Writes XP level.", description="Writes XP level, overriding any present XP. Only for the owner"
    )
    @commands.is_owner()
    async def set(self, ctx, user: typing.Optional[typing.Union[discord.Member, discord.User]], *, xp: int):
        user = user or ctx.author
        LevelManager(user, instances.user_collection).write(xp)
        await ctx.message.add_reaction(emoji="✅")

    @commands.command(
        name="rank", aliases=["level"], brief="Displays current level & rank.", description="Displays current level & rank."
    )
    async def rank(self, ctx: commands.Context, *, user: typing.Optional[discord.Member]):
        user = user or ctx.author
        xp = LevelManager(user, instances.user_collection).read()
        level = get_level(xp)
        next_level = get_xp(level + 1) - xp
        embed = (
            discord.Embed(colour=user.colour, title=f"{user.display_name}'s level")
            .add_field(name="XP:", value=f"```{xp}```")
            .add_field(name="Level:", value=f"```{level}```")
            .add_field(name="To next:", value=f"```{round(next_level)}```")
            .set_thumbnail(url=user.avatar_url)
        )
        await ctx.send(embed=embed)

    @commands.command(name="leaderboard", brief="Displays current level & rank.", description="Displays current level & rank.")
    @commands.cooldown(1, 30, commands.cooldowns.BucketType.guild)
    async def leaderboard(
        self,
        ctx: commands.Context,
    ):
        if ctx.guild.large:
            raise errors.TooManyMembers()
        async with ctx.typing():
            embed: discord.Embed = discord.Embed(colour=discord.Colour.random(), title=f"{ctx.guild.name}").set_thumbnail(
                url=ctx.guild.icon_url
            )
            member_xp_dict = {}
            for member in ctx.guild.members:  # Horribly inefficent. Like, really bad.
                member_xp_dict[member] = LevelManager(member, instances.user_collection).read()
            sorted_list = sorted(member_xp_dict.items(), key=lambda item: item[1], reverse=True)
            del sorted_list[15:]
            sorted_dict = dict(sorted_list)
            dict_index = 0
            for member in list(sorted_dict.keys()):
                dict_index += 1
                xp = sorted_dict[member]
                embed.add_field(
                    name=f"{dict_index}. {member.display_name}", value=f"Level {get_level(xp)} ({xp} XP)", inline=False
                )
            await ctx.send(embed=embed)

    @commands.command(
        name="xp-level",
        aliases=["xptolevel"],
        brief="Displays level for set amount of XP.",
        description="Displays the level that a set amount of XP would have.",
    )
    async def xp_level(self, ctx, *, xp: typing.Union[int, float]):
        await ctx.send(get_level(xp))

    @commands.command(
        name="level-xp", aliases=["leveltoxp"], brief="Displays XP for set level.", description="Displays XP for set level."
    )
    async def level_xp(self, ctx, *, level: int):
        await ctx.send(get_xp(level))


def setup(bot):
    bot.add_cog(Levels(bot))
