import copy
import math
import operator
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

    def __init__(self, user: typing.Union[discord.Member, discord.User], document: Document) -> None:
        self.user = user
        self.document = document

    @classmethod
    async def get_user(cls, bot, user: typing.Union[discord.Member, discord.User]):
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

    @property
    def next(self):
        """Gets the xp required to reach the next level a user may obtain."""
        return self._get_xp(self.level + 1)

    async def increment(self, amount: int):
        """Increments a the user's xp by a given amount. Returns a dict with information on the old and new level/xp of the user."""
        current = copy.deepcopy(self.xp)
        new_xp = current + amount
        self.document["xp"] = new_xp
        next_level = self.level + 1
        next_xp = self._get_xp(next_level)
        return_dict = {
            "old": {
                "xp": current,
                "level": self._get_level(current),
            },
            "new": {"xp": self.xp, "level": self.level},
            "next": {"xp": next_xp, "level": next_level},
        }
        # To prevent rounding issues, kinda jank but not horrible
        if return_dict["old"]["level"] < return_dict["new"]["level"]:
            self.document["xp"] += 1
        await self.document.replace_db()
        return return_dict


class LevelSource(menus.ListPageSource):
    def __init__(self, data, guild):
        self.guild = guild
        return super().__init__(data, per_page=10)

    async def format_page(self, menu, page_entries):
        offset = menu.current_page * self.per_page
        base_embed = discord.Embed(title=f"{self.guild.name}'s Leaderboard").set_thumbnail(url=self.guild.icon_url)
        for iteration, value in enumerate(page_entries, start=offset):
            base_embed.add_field(
                name=f"{iteration + 1}.", value=f"{value.user.mention}: Level {value.level} (`{value.xp}` XP)", inline=False
            )
        return base_embed


class Levels(commands.Cog):
    """Each member can "level up" and raise their point on the server's leaderboard."""

    def __init__(self, bot):
        self.bot = bot
        self.xp_cd = commands.CooldownMapping.from_cooldown(3, 10, commands.BucketType.user)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """on_message grants xp to the user and sends level-up alerts to the guild if the guild privledged so desire."""
        ctx = await self.bot.get_context(message)
        level = await UserLevel.get_user(self.bot, ctx.author)
        # Prevents levels from being earned outside of a guild and the bot from responding to other bots
        if (not ctx.guild) or (ctx.author.bot):
            return
        # Cooldown: prevents spam/macros
        bucket = self.xp_cd.get_bucket(message)
        retry_after = bucket.update_rate_limit()
        if retry_after:
            return
        # Actual processing: chooses a random number, gets the user's document, then adds the xp value into the document
        gen_xp = random.randrange(xp_start, xp_end)
        user_level = UserLevel(ctx.author, ctx.user_doc)
        user_level_up = await user_level.increment(gen_xp)
        # Levelup message: Makes sure that the user's level actually increased and level-up alerts are not disabled in the guild before sending a level-up alert.
        if user_level_up["new"]["level"] > user_level_up["old"]["level"] and (
            not ctx.guild_doc.setdefault("levels", {}).setdefault("disabled", True)
        ):
            next_level = user_level_up["next"]["level"]
            next_xp = round(user_level_up["next"]["xp"] - user_level_up["new"]["xp"])
            embed = (
                discord.Embed(
                    colour=ctx.author.colour,
                    title="Level up!",
                    description=f"{ctx.author.display_name} just levelled up to `{next_level}`!",
                )
                .add_field(name="To next:", value=f"```{next_xp}```")
                .set_thumbnail(url=ctx.author.avatar_url)
            )
            try:
                await ctx.guild.get_channel(ctx.guild_doc.setdefault("levels", {})["redirect"]).send(
                    ctx.author.mention, embed=embed
                )
            except:
                await ctx.reply(embed=embed)

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
        user_doc = await UserLevel.get_user(self.bot, user)
        embed = (
            discord.Embed(colour=user.colour, title=f"{user.display_name}'s level")
            .add_field(name="XP:", value=f"```{user_doc.xp}```")
            .add_field(name="Level:", value=f"```{user_doc.level}```")
            .add_field(name="To next:", value=f"```{round(user_doc.next - user_doc.xp)}```")
            .set_thumbnail(url=user.avatar_url)
        )
        await ctx.send(embed=embed)

    @commands.command(name="leaderboard", brief="Displays current level & rank.", description="Displays current level & rank.")
    @commands.cooldown(1, 30, commands.cooldowns.BucketType.guild)
    async def leaderboard(self, ctx):
        if ctx.guild.large:
            raise errors.TooManyMembers()
        member_xps = []
        for member in ctx.guild.members:
            member_xps.append(await UserLevel.get_user(ctx.bot, member))
        sorted_xps = sorted(member_xps, key=operator.attrgetter("xp"), reverse=True)
        source = LevelSource(sorted_xps, ctx.guild)
        pages = menus.MenuPages(source=source)
        await pages.start(ctx)


def setup(bot):
    bot.add_cog(Levels(bot))
