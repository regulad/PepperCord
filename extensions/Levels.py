import copy
import math
import random
import typing

import discord
from discord.ext import commands, menus
from utils import checks, errors
from utils.database import Document

xp_to = 2.8
xp_multiplier = 1.7
xp_start = 1
xp_end = 5


class UserLevel:
    """An object that represents the level of a user via their user_doc."""

    def __init__(self, user: typing.Union[discord.User, discord.Member], document: Document) -> None:
        self.user = user
        self.document = document

    @classmethod
    async def get_user(cls, bot, user: typing.Union[discord.User, discord.Member]):
        """Returns the UserLevel object for a given user."""
        document = await Document.get_from_id(bot.database["user"], user.id)
        return cls(user, document)

    def _get_xp(self, level: int):
        """Gets the xp value for a given level."""
        xp = level ** xp_to * xp_multiplier
        return xp

    def _get_level(self, xp: typing.Union[int, float]):
        """Gets the level for a given amount of xp."""
        level = (xp / xp_multiplier) ** (1.0 / xp_to)
        return math.trunc(level)

    @property
    def xp(self):
        """Gets the amount of xp for a given user."""
        return self.document.setdefault("xp", 0)

    @property
    def level(self):
        """Gets the level of a given user using their xp."""
        return self._get_level(self.xp)

    async def increment(self, amount: int):
        """Increments a the user's xp by a given amount. Returns a tuple of the before xp and the new xp."""
        current = copy.deepcopy(self.xp)
        new_xp = current + amount
        self.document["xp"] = new_xp
        await self.document.update_db("$set")
        return (current, new_xp)


class Levels(
    commands.Cog, name="Levels", description='Each member can "level up" and raise their point on the server\'s leaderboard'
):
    def __init__(self, bot):
        self.bot = bot
        self.xp_cd = commands.CooldownMapping.from_cooldown(3, 10, commands.BucketType.user)

    async def cog_check(self, ctx):
        if ctx.guild is None:
            raise commands.NoPrivateMessage()
        return True

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        ctx = await self.bot.get_context(message)
        level = await UserLevel.get_user(self.bot, ctx.author)
        # Recursion prevention
        if (not ctx.guild) or (ctx.author.bot):
            return
        # Cooldown
        bucket = self.xp_cd.get_bucket(message)
        retry_after = bucket.update_rate_limit()
        if retry_after:
            return
        # Actual processing
        gen_xp = random(xp_start, xp_end)
        # Levelup message
        if new_level > current_level:
            if not ctx.guild_doc.setdefault("levels", {}).setdefault("disabled", True):
                next_xp = get_xp(new_level + 1) - get_xp(new_level)
                embed = (
                    discord.Embed(
                        colour=message.author.colour,
                        title="Level up!",
                        description=f"{message.author.display_name} just levelled up to `{new_level}`!",
                    )
                    .add_field(name="To next:", value=f"```{round(next_xp)}```")
                    .set_thumbnail(url=message.author.avatar_url)
                )
                try:
                    redirect = ctx.guild.get_channel(ctx.guild_doc.setdefault("levels", {})["redirect"])
                    await redirect.send(message.author.mention, embed=embed)
                except:
                    await ctx.reply(embed=embed)
                message_xp += 1
        # The actual action
        ctx.user_doc["xp"] = new_xp
        await ctx.user_doc.replace_db()

    @commands.command(
        name="redirect",
        brief="Sets channel to redirect level-up alerts to.",
        description="Sets channel to redirect level-up alerts to. Defaults to sending in the same channel.",
        usage="[Channel]",
    )
    @commands.check(checks.is_admin)
    async def redirect(self, ctx, *, channel: typing.Optional[discord.TextChannel]):
        channel = channel or ctx.channel
        ctx.guild_doc.setdefault("levels", {})["redirect"] = channel.id
        await ctx.guild_doc.replace_db()

    @commands.command(
        name="disablexp",
        aliases=["disablelevels"],
        brief="Disables level-up alerts.",
        description="Disables level-up alerts. You will still earn XP to use in other servers.",
    )
    @commands.check(checks.is_admin)
    async def disablexp(self, ctx):
        ctx.guild_doc.setdefault("levels", {})["disabled"] = True
        await ctx.guild_doc.replace_db()

    @commands.command(
        name="enablexp",
        aliases=["enablelevels"],
        brief="Enables level-up alerts.",
        description="Enables level-up alerts. You will still earn XP to use in other servers.",
    )
    @commands.check(checks.is_admin)
    async def enablexp(self, ctx):
        ctx.guild_doc.setdefault("levels", {})["disabled"] = False
        await ctx.guild_doc.replace_db()

    @commands.command(
        name="rank", aliases=["level"], brief="Displays current level & rank.", description="Displays current level & rank."
    )
    async def rank(self, ctx, *, user: typing.Optional[discord.Member]):
        user = user or ctx.author
        user_doc = await Document.get_from_id(self.bot.database["user"], user.id)
        xp = user_doc.setdefault("xp", 0)
        level = get_level(xp)
        next_level = get_xp(level + 1) - xp
        embed = (
            discord.Embed(colour=user.colour, title=f"{user.display_name}'s level")
            .add_field(name="XP:", value=f"```{round(xp)}```")
            .add_field(name="Level:", value=f"```{round(level)}```")
            .add_field(name="To next:", value=f"```{round(next_level)}```")
            .set_thumbnail(url=user.avatar_url)
        )
        await ctx.send(embed=embed)

    @commands.command(name="leaderboard", brief="Displays current level & rank.", description="Displays current level & rank.")
    @commands.cooldown(1, 30, commands.cooldowns.BucketType.guild)
    async def leaderboard(
        self,
        ctx,
    ):
        if ctx.guild.large:
            raise errors.TooManyMembers()
        embed: discord.Embed = discord.Embed(colour=discord.Colour.random(), title=f"{ctx.guild.name}").set_thumbnail(
            url=ctx.guild.icon_url
        )
        member_xp_dict = {}
        for member in ctx.guild.members:
            member_doc = await Document.get_from_id(self.bot.database["user"], member.id)
            member_xp_dict[member] = member_doc.setdefault("xp", 0)
        sorted_dict = misc.sort_dict(member_xp_dict)
        i = 0
        for member in list(sorted_dict.keys())[:10]:
            xp = sorted_dict[member]
            i += 1
            embed.add_field(
                name=f"{i}. {member.display_name}",
                value=f"Level {round(get_level(xp))} ({round(xp)} XP)",
                inline=False,
            )
        await ctx.send(embed=embed)


def setup(bot):
    bot.add_cog(Levels(bot))
