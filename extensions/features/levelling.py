import copy
import math
import operator
import random
from typing import Union, Optional

import discord
from discord.ext import commands, menus

from utils import checks, database
from utils.bots import CustomContext, BOT_TYPES

xp_to = 2.3
xp_multiplier = 1.6
xp_start = 2
xp_end = 5


def _get_xp(level: float):
    """Gets the xp value for a given level."""
    xp = level ** xp_to * xp_multiplier
    return xp


def _get_level(xp: float):
    """Gets the level for a given amount of xp."""
    level = (xp / xp_multiplier) ** (1.0 / xp_to)
    return math.trunc(level)


class UserLevel:
    """An object that represents the level of a user via their user_doc."""

    def __init__(
        self, user: Union[discord.Member, discord.User], document: database.Document
    ):
        self.user = user
        self.document = document

    @classmethod
    async def get_user(cls, bot, user: Union[discord.Member, discord.User]):
        """Returns the UserLevel object for a given user."""

        if user.bot:
            return None
        else:
            document = await bot.get_user_document(user)
            return cls(user, document)

    @property
    def xp(self) -> float:
        """Gets the amount of xp for a given user."""
        return self.document.get("xp", 0)

    @property
    def level(self) -> float:
        """Gets the level of a given user using their xp."""

        return _get_level(self.xp)

    @property
    def next(self) -> float:
        """Gets the xp required to reach the next level a user may obtain."""

        return _get_xp(self.level + 1)

    async def increment(self, amount: int):
        """Increments a the user's xp by a given amount. Returns a dict with information on the old and new level/xp
        of the user."""

        current = copy.deepcopy(self.xp)
        await self.document.update_db({"$inc": {"xp": amount}})
        next_level = self.level + 1
        next_xp = _get_xp(next_level)
        return_dict = {
            "old": {"xp": current, "level": _get_level(current)},
            "new": {"xp": self.xp, "level": self.level},
            "next": {"xp": next_xp, "level": next_level},
        }
        return return_dict


class LevelSource(menus.ListPageSource):
    def __init__(self, data, guild):
        self.guild = guild
        super().__init__(data, per_page=10)

    async def format_page(self, menu, page_entries):
        offset = menu.current_page * self.per_page
        base_embed = discord.Embed(
            title=f"{self.guild.name}'s Leaderboard"
        ).set_thumbnail(url=self.guild.icon.url)
        for iteration, value in enumerate(page_entries, start=offset):
            base_embed.add_field(
                name=f"{iteration + 1}: {value.user.display_name}",
                value=f"Level {value.level} (`{value.xp}` XP)",
                inline=False,
            )
        return base_embed


class UserLevelMenu(menus.Menu):
    def __init__(self, source: UserLevel, level_up: bool = False, **kwargs):
        self.source = source
        self.level_up = level_up

        super().__init__(**kwargs)

    async def send_initial_message(self, ctx, channel):
        embed = (
            discord.Embed(
                colour=self.source.user.colour,
                title=f"{self.source.user.display_name}'s level",
            )
            .add_field(name="XP:", value=f"```{self.source.xp}```")
            .add_field(name="Level:", value=f"```{self.source.level}```")
            .add_field(
                name="To next:",
                value=f"```{round(self.source.next - self.source.xp)}```",
            )
            .set_thumbnail(url=self.source.user.avatar.url)
        )
        if self.level_up:
            return await channel.send(
                f"Level up! {self.source.user.mention}", embed=embed
            )
        else:
            return await channel.send(embed=embed)


class Levels(commands.Cog):
    """Each member can "level up" and raise their point on the server's leaderboard."""

    def __init__(self, bot: BOT_TYPES):
        self.bot: BOT_TYPES = bot
        self.cooldown: commands.CooldownMapping = (
            commands.CooldownMapping.from_cooldown(3, 10, commands.BucketType.user)
        )

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        """on_message grants xp to the user and sends level-up alerts to the guild if the guild privileged so desire."""
        ctx: CustomContext = await self.bot.get_context(message)

        if await checks.is_blacklisted(ctx):
            return

        bucket: commands.Cooldown = self.cooldown.get_bucket(message)
        retry_after: float = bucket.update_rate_limit()

        if not ctx.guild:
            return  # raise commands.NoPrivateMessage
        elif ctx.author.bot:
            return  # User must a a bot
        elif retry_after:
            return  # raise commands.CommandOnCooldown(cooldown=bucket, retry_after=retry_after), Not the same as of v2

        gen_xp = random.randrange(xp_start, xp_end)
        user_level = UserLevel(ctx.author, ctx["author_document"])
        user_level_up = await user_level.increment(gen_xp)

        if user_level_up["new"]["level"] > user_level_up["old"]["level"] and (
            not ctx["guild_document"].get("levels", {}).get("disabled", True)
        ):
            redirect_channel_id: int = (
                ctx["guild_document"].get("levels", {}).get("redirect")
            )

            if redirect_channel_id is None:
                channel = None
            else:
                channel = ctx.guild.get_channel(redirect_channel_id)

            await UserLevelMenu(user_level, True).start(ctx, channel=channel)

    @commands.command(
        name="setxp",
        description="Sets a user's xp count to a certain number.",
        usage="<Xp> [User]",
    )
    @commands.is_owner()
    async def set_xp(
        self,
        ctx: CustomContext,
        xp: int,
        *,
        user: Optional[Union[discord.User, discord.Member]],
    ) -> None:
        user: Union[discord.User, discord.Member] = user or ctx.author
        document: database.Document = await ctx.bot.get_user_document(user)
        await document.update_db({"$set": {"xp": xp}})

    @commands.command(
        name="setlevel",
        description="Sets a user's level count to a certain number.",
        usage="<Level> [User]",
    )
    @commands.is_owner()
    async def set_level(
        self,
        ctx: CustomContext,
        level: int,
        *,
        user: Optional[Union[discord.User, discord.Member]],
    ) -> None:
        user: Union[discord.User, discord.Member] = user or ctx.author
        document: database.Document = await ctx.bot.get_user_document(user)
        await document.update_db({"$set": {"xp": _get_xp(level)}})

    @commands.command(
        name="redirect",
        description="Sets channel to redirect level-up alerts to.\n"
        "Defaults to sending in the same channel.",
        usage="[Channel]",
    )
    @checks.check_is_admin
    async def redirect(
        self, ctx: CustomContext, *, channel: Optional[discord.TextChannel]
    ) -> None:
        channel = channel or ctx.channel
        await ctx["guild_document"].update_db({"$set": {"levels.redirect": channel.id}})

    @commands.command(
        name="disablexp",
        aliases=["disablelevels"],
        description="Disables level-up alerts. You will still earn XP to use in other servers.",
    )
    @checks.check_is_admin
    async def disablexp(self, ctx: CustomContext) -> None:
        await ctx["guild_document"].update_db({"$set": {"levels.disabled": True}})

    @commands.command(
        name="enablexp",
        aliases=["enablelevels"],
        description="Enables level-up alerts. You will still earn XP to use in other servers.",
    )
    @checks.check_is_admin
    async def enablexp(self, ctx: CustomContext) -> None:
        await ctx["guild_document"].update_db({"$set": {"levels.disabled": False}})

    @commands.command(
        name="rank",
        aliases=["level"],
        description="Displays current level & rank.",
    )
    async def rank(self, ctx: CustomContext, *, user: Optional[discord.Member]) -> None:
        async with ctx.typing():
            user: discord.Member = user or ctx.author
            user_level: Optional[UserLevel] = await UserLevel.get_user(self.bot, user)
            if user_level is None:
                await ctx.send(f"{user.display_name} doesn't have a level.")
            else:
                await UserLevelMenu(user_level).start(ctx)

    @commands.command(
        name="leaderboard",
        aliases=["top"],
        description="Displays current level & rank.",
    )
    async def leaderboard(self, ctx: CustomContext) -> None:
        async with ctx.typing():
            member_xps = []

            for member in ctx.guild.members[:500]:  # To prevent DB from exploding
                xp = await UserLevel.get_user(ctx.bot, member)
                if xp is not None:
                    member_xps.append(xp)

            source = LevelSource(
                sorted(member_xps, key=operator.attrgetter("xp"), reverse=True),
                ctx.guild,
            )

            if len(ctx.guild.members) > 500:
                await ctx.send(
                    "Please note that in large guilds (Larger than 500 members), "
                    "the leaderboard may be inaccurate."
                )

            await menus.MenuPages(source=source).start(ctx)


def setup(bot: BOT_TYPES):
    bot.add_cog(Levels(bot))
