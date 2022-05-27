import copy
import math
import operator
import random
from typing import Union, Optional

import discord
from discord import Interaction, Member, AppCommandType
from discord.app_commands import describe, context_menu, default_permissions
from discord.app_commands import guild_only as ac_guild_only
from discord.ext import commands, menus
from discord.ext.commands import hybrid_group, hybrid_command, guild_only

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
        base_embed = discord.Embed(title=f"{self.guild.name}'s Leaderboard")
        if self.guild.icon is not None:
            base_embed.set_thumbnail(url=self.guild.icon.url)
        base_embed.set_footer(
            text=f"Page {menu.current_page + 1}/{self.get_max_pages()}"
        )
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
                f"Level up! {self.source.user.mention}",
                embed=embed,
                **self._get_kwargs(),
            )
        else:
            return await channel.send(embed=embed, **self._get_kwargs())


RANK_CM_NAME: str = "Get Rank"


@context_menu(name=RANK_CM_NAME)
async def rank_cm(interaction: Interaction, user: Member) -> None:
    """Displays a user's current rank."""

    ctx: CustomContext = await CustomContext.from_interaction(interaction)
    user_level: Optional[UserLevel] = await UserLevel.get_user(interaction.client, user)
    if user_level is None:
        await ctx.send(f"{user.display_name} doesn't have a level.", ephemeral=True)
    else:
        await UserLevelMenu(user_level).start(ctx, ephemeral=True)


class Levels(commands.Cog):
    """Each member can "level up" and raise their point on the server's leaderboard."""

    def __init__(self, bot: BOT_TYPES):
        self.bot: BOT_TYPES = bot
        self.cooldown: commands.CooldownMapping = (
            commands.CooldownMapping.from_cooldown(3, 10, commands.BucketType.user)
        )

    async def cog_load(self) -> None:
        self.bot.tree.add_command(rank_cm)

    async def cog_unload(self) -> None:
        self.bot.tree.remove_command(RANK_CM_NAME, type=AppCommandType.user)

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

    @hybrid_group()
    @default_permissions(administrator=True)
    async def levelsettings(self, ctx: CustomContext) -> None:
        pass

    @levelsettings.command(
        name="redirect",
        usage="[Channel]",
    )
    @commands.has_permissions(administrator=True)
    @describe(channel="The channel all level-up notofications will be redirected to.")
    async def redirect(
            self,
            ctx: CustomContext,
            *,
            channel: discord.TextChannel,
    ) -> None:
        """
        Sets the channel level-up alerts will go to.
        By default, it's the current channel.
        This feature is currently broken.
        """
        channel = channel or ctx.channel
        await ctx["guild_document"].update_db({"$set": {"levels.redirect": channel.id}})
        await ctx.send("Settings updated.", ephemeral=True)

    @levelsettings.command()
    @commands.has_permissions(administrator=True)
    async def disablexp(
            self, ctx: CustomContext, *, enabled: Optional[bool] = False
    ) -> None:
        """Sets if levels are enabled or not."""
        await ctx["guild_document"].update_db(
            {"$set": {"levels.disabled": not enabled}}
        )
        await ctx.send("Settings updated.", ephemeral=True)

    @hybrid_command()
    async def rank(self, ctx: CustomContext, *, user: Optional[discord.Member]) -> None:
        """Displays your current rank."""
        async with ctx.typing(ephemeral=True):
            user: discord.Member = user or ctx.author
            user_level: Optional[UserLevel] = await UserLevel.get_user(self.bot, user)
            if user_level is None:
                await ctx.send(f"{user.display_name} doesn't have a level.", ephemeral=True)
            else:
                await UserLevelMenu(user_level).start(ctx, ephemeral=True)

    @hybrid_command()
    @guild_only()
    @ac_guild_only()
    async def leaderboard(self, ctx: CustomContext) -> None:
        """Displays the level of all members of the server relative to each other."""
        async with ctx.typing():
            member_xps = []

            for member in ctx.guild.members:
                xp = await UserLevel.get_user(ctx.bot, member)
                if xp is not None:
                    member_xps.append(xp)

            source = LevelSource(
                sorted(member_xps, key=operator.attrgetter("xp"), reverse=True),
                ctx.guild,
            )

            await menus.ViewMenuPages(source=source).start(ctx)


async def setup(bot: BOT_TYPES) -> None:
    await bot.add_cog(Levels(bot))
