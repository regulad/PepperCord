import datetime
from random import choice, randint
from typing import Union, Optional, List

import discord
from discord.app_commands import describe
from discord.ext import commands, menus
from discord.ext.commands import hybrid_group
from topgg import DBLClient, WebhookManager
from topgg.types import BotVoteData, BotData

from utils import bots, database
from utils.bots import CustomContext

PESTERING_MESSAGES: List[str] = [
    "Like the bot? Vote for it!",
    "Vote for the bot!",
    "Enjoy the bot? Vote for it!",
]


def get_top_gg_link(bot_id: int) -> str:
    return f"https://top.gg/bot/{bot_id}"


class VotesMenu(menus.ViewMenu):
    def __init__(
            self,
            document: database.Document,
            user: Union[discord.Member, discord.User],
            **kwargs,
    ):
        self.document = document
        self.user = user

        super().__init__(
            **kwargs,
        )

    async def send_initial_message(self, ctx, channel):
        votes: List[datetime.datetime] = self.document.get("votes", [])

        if len(votes) > 0:
            embed = (
                discord.Embed(title=f"{self.user.display_name}'s Votes")
                    .set_thumbnail(url=self.user.avatar.url)
                    .add_field(name="Times voted:", value=len(votes))
                    .add_field(name="First voted:", value=f"<t:{votes[0].timestamp():.0f}>")
                    .add_field(
                    name="Last voted:", value=f"<t:{votes[-1].timestamp():.0f}:R>"
                )
            )

            return await channel.send(embed=embed, **self._get_kwargs())
        else:
            return await channel.send(
                f"{self.user.display_name} hasn't voted yet.", **self._get_kwargs()
            )


class TopGGWebhook(commands.Cog, name="Voting"):
    """Vote for the bot on Top.gg for some sick rewards."""

    def __init__(self, bot: bots.BOT_TYPES) -> None:
        self.bot = bot

        self.webhook_manager: WebhookManager | None = None

    async def cog_load(self) -> None:
        self.webhook_manager = WebhookManager(self.bot)

        self.webhook_manager.dbl_webhook(
            self.bot.config.get("PEPPERCORD_TOPGG_WH_ROUTE", "/topgg"),
            self.bot.config["PEPPERCORD_TOPGG_WH_SECRET"],
        )

        self.webhook_manager.run(int(self.bot.config.get("PEPPERCORD_TOPGG_WH", "5000")))

    async def cog_unload(self) -> None:
        await self.webhook_manager.close()

    @commands.Cog.listener()
    async def on_dbl_vote(self, data: BotVoteData) -> None:
        if int(data["bot"]) == self.bot.user.id:
            user: Optional[discord.User] = self.bot.get_user(int(data["user"]))
            if user is not None:
                user_document: database.Document = await self.bot.get_user_document(
                    user
                )
                await user_document.update_db(
                    {"$push": {"votes": datetime.datetime.utcnow()}}
                )

                if not user_document.get("nopester", False):
                    await user.send(
                        f"Thanks for voting! You have voted {len(user_document['votes'])} time(s)."
                    )

    @commands.Cog.listener()
    async def on_command_completion(self, ctx: bots.CustomContext) -> None:
        if not (
                ctx["author_document"].get("nopester", False)
                or await ctx.bot.is_owner(ctx.author)
        ):
            if len(ctx["author_document"].get("votes", [])) > 0:
                if (
                        ctx["author_document"]["votes"][-1] + datetime.timedelta(days=1)
                        > datetime.datetime.utcnow()
                ):
                    return  # We don't want to pester a user who just voted.

            if randint(0, 20) > 1:
                return  # We don't want to bother the user all the time asking to vote.

            # If a user has not voted in the past 24 hours, there is only a 5% chance we make it here.

            if ctx["author_document"].get("pestered", 0) > 2:
                await ctx.author.send(
                    f"Psst... {choice(PESTERING_MESSAGES)} "
                    f"{get_top_gg_link(ctx.bot.user.id)}"
                )

            await ctx["author_document"].update_db({"$inc": {"pestered": 1}})

    @hybrid_group(fallback="status")
    async def voting(self, ctx: CustomContext) -> None:
        """Tells you if you have pestering enabled."""
        if ctx["author_document"].get("nopester", False):
            await ctx.send(
                f"{ctx.author.mention} You have pestering disabled. "
                f"{get_top_gg_link(ctx.bot.user.id)}"
            )
        else:
            await ctx.send(
                f"{ctx.author.mention} You have pestering enabled. "
                f"{get_top_gg_link(ctx.bot.user.id)}"
            )

    @voting.command()
    @describe(pester="If the bot should be allowed to pester you to vote.")
    async def pester(
            self,
            ctx: bots.CustomContext,
            *,
            pester: bool = False,
    ) -> None:
        """Adjust the pester status."""
        await ctx["author_document"].update_db({"$set": {"nopester": not pester}})
        await ctx.send("Settings updated.", ephemeral=True)

    @commands.command()
    @describe(user="The user who will have their stats displayed.")
    async def votes(
            self,
            ctx: bots.CustomContext,
            *,
            user: discord.Member,
    ) -> None:
        """Shows you your voting stats."""
        await ctx.defer(ephemeral=True)
        document: database.Document = await self.bot.get_user_document(user)

        await VotesMenu(document, user).start(ctx, ephemeral=True)


class TopGG(commands.Cog):
    """Utilities for interacting with Top.gg."""

    def __init__(self, bot: bots.BOT_TYPES) -> None:
        self.bot = bot
        self.topggpy: DBLClient | None = None

    async def cog_load(self) -> None:
        if isinstance(self.bot, bots.CustomAutoShardedBot):
            self.topggpy = DBLClient(
                self.bot,
                self.bot.config["PEPPERCORD_TOPGG"],
                autopost=True,
                post_shard_count=True,
            )
        else:
            self.topggpy = DBLClient(self.bot, self.bot.config["PEPPERCORD_TOPGG"], autopost=True)

    async def cog_unload(self) -> None:
        await self.topggpy.close()

    @hybrid_group(fallback="link")
    async def topgg(self, ctx: bots.CustomContext) -> None:
        """Shows you where to vote for the bot on top.gg"""
        await ctx.send(get_top_gg_link(ctx.bot.user.id), ephemeral=True)

    @topgg.command()
    async def totalvotes(self, ctx: bots.CustomContext) -> None:
        """Shows the total amount of votes the bot as accumulated."""
        await ctx.defer(ephemeral=True)
        bot_info: BotData = await self.topggpy.get_bot_info()
        await ctx.send(
            f"{ctx.bot.user.name} has received {bot_info['points']} votes on Top.gg. Why don't you make it {int(bot_info['points']) + 1}?",
            ephemeral=True,
        )


async def setup(bot: bots.BOT_TYPES) -> None:
    if bot.config.get("PEPPERCORD_TOPGG") is not None:
        await bot.add_cog(TopGG(bot))
    if bot.config.get("PEPPERCORD_TOPGG_WH_SECRET") is not None:
        await bot.add_cog(TopGGWebhook(bot))
