from typing import Union, Optional, List
import datetime
from random import choice, randint

from discord.ext import commands, menus
import discord
from topgg import DBLClient, WebhookManager
from topgg.types import BotVoteData, BotData

from utils import bots, database


PESTERING_MESSAGES = [
    "Like the bot? Vote for it!",
]


def get_top_gg_link(bot_id: int) -> str:
    return f"https://top.gg/bot/{bot_id}"


class VotesMenu(menus.Menu):
    def __init__(
            self,
            document: database.Document,
            user: Union[discord.Member, discord.User],
            *,
            timeout=180.0,
            delete_message_after=False,
            clear_reactions_after=False,
            check_embeds=False,
            message=None
    ):
        self.document = document
        self.user = user

        super().__init__(
            timeout=timeout,
            delete_message_after=delete_message_after,
            clear_reactions_after=clear_reactions_after,
            check_embeds=check_embeds,
            message=message
        )

    async def send_initial_message(self, ctx, channel):
        votes: List[float] = self.document.get("votes", [])

        if len(votes) > 0:
            embed = discord.Embed(title=f"{self.user.display_name}'s Votes").set_thumbnail(url=self.user.avatar.url).add_field(
                name="Times voted:", value=len(votes)
            ).add_field(
                name="First voted:", value=f"{datetime.datetime.utcfromtimestamp(votes[0])} UTC"
            ).add_field(
                name="Last voted:", value=f"{datetime.datetime.utcfromtimestamp(votes[-1])} UTC"
            )

            return await channel.send(embed=embed)
        else:
            return await channel.send(f"{self.user.display_name} hasn't voted yet.")


class TopGGWebhook(commands.Cog, name="Voting"):
    """Vote for the bot on Top.gg for some sick rewards."""

    def __init__(self, bot: bots.BOT_TYPES) -> None:
        self.bot = bot

        self.topgg_webhook = WebhookManager(bot).dbl_webhook(
            bot.config.get("PEPPERCORD_TOPGG_WH_ROUTE", "/topgg"), bot.config["PEPPERCORD_TOPGG_WH_SECRET"]
        )
        self.topgg_webhook.run(int(bot.config.get("PEPPERCORD_TOPGG_WH", "5000")))

    def cog_unload(self) -> None:
        self.bot.loop.create_task(self.topgg_webhook.close())

    @commands.Cog.listener()
    async def on_dbl_vote(self, data: BotVoteData) -> None:
        if int(data["bot"]) == self.bot.user.id:
            user: Optional[discord.User] = self.bot.get_user(int(data["user"]))
            if user is not None:
                document: database.Document = await self.bot.get_user_document(user)
                await document.update_db({"$push": {"votes": datetime.datetime.utcnow().timestamp()}})

                if not document.get("nopester", False):
                    await user.send(f"Thanks for voting! You have voted {len(document['votes'])} time(s).")

    @commands.Cog.listener()
    async def on_command_completion(self, ctx: bots.CustomContext) -> None:
        if not (ctx.author_document.get("nopester", False) or await ctx.bot.is_owner(ctx.author)):
            if len(ctx.author_document.get("votes", [])) > 0:
                if datetime.datetime.utcfromtimestamp(ctx.author_document["votes"][-1]) \
                        + datetime.timedelta(days=1) > datetime.datetime.utcnow():
                    return  # We don't want to pester a user who just voted.

            if randint(0, 100) > 2:
                return  # We don't want to bother the user all the time asking to vote.

            # If a user has not voted in the past 24 hours, there is only a 2% chance we make it here.

            await ctx.send(
                f"Psst... {choice(PESTERING_MESSAGES)} "
                f"{get_top_gg_link(ctx.bot.user.id)} "
                f"{'Tried of these messages? Try nopester.' if ctx.author_document.get('pestered', 0) > 2 else ''}"
            )

            await ctx.author_document.update_db({"$inc": {"pestered": 1}})

    @commands.command(
        name="nopester",
        brief="Stops the bot from \"pestering\" you.",
        description="Stops the bot from \"pestering\" (reminding to vote) you.",
    )
    async def nopester(self, ctx: bots.CustomContext) -> None:
        await ctx.author_document.update_db({"$set": {"nopester": True}})

    @commands.command(
        name="yespester",
        brief="Disables nopester.",
        description="Disables nopester. Back so soon?",
    )
    async def yespester(self, ctx: bots.CustomContext) -> None:
        await ctx.author_document.update_db({"$set": {"nopester": False}})

    @commands.command(
        name="votes",
        brief="Gives some info about the user's voting status.",
        description="Gives you info about when the user first voted and when the most recently voted.",
    )
    async def votes(self, ctx: bots.CustomContext, *, user: Optional[Union[discord.Member, discord.User]]) -> None:
        async with ctx.typing():
            user: Union[discord.Member, discord.User] = user or ctx.author
            document: database.Document = await self.bot.get_user_document(user)
            await VotesMenu(document, user).start(ctx)


class TopGG(commands.Cog):
    """Utilities for interacting with Top.gg."""

    def __init__(self, bot: bots.BOT_TYPES) -> None:
        self.bot = bot

        if isinstance(bot, bots.CustomAutoShardedBot):
            self.topggpy = DBLClient(bot, bot.config["PEPPERCORD_TOPGG"], autopost=True, post_shard_count=True)
        else:
            self.topggpy = DBLClient(bot, bot.config["PEPPERCORD_TOPGG"], autopost=True)

    def cog_unload(self) -> None:
        self.bot.loop.create_task(self.topggpy.close())

    @commands.command(
        name="vote",
        aliases=["bump"],
        brief="Gets the link to vote for the bot on Top.gg.",
        description="Gets the link to vote for the bot on Top.gg.",
    )
    async def vote(self, ctx: bots.CustomContext) -> None:
        await ctx.send(get_top_gg_link(ctx.bot.user.id))

    @commands.command(
        name="totalvotes",
        brief="Shows the total amount of votes the bot has obtained.",
        description="Shows how many votes the bot has received.",
    )
    async def totalvotes(self, ctx: bots.CustomContext) -> None:
        async with ctx.typing():
            bot_info: BotData = await self.topggpy.get_bot_info()
            await ctx.send(f"{ctx.bot.user.name} has received {bot_info['points']} votes on Top.gg. Why don't you make it {int(bot_info['points']) + 1}?")


def setup(bot: bots.BOT_TYPES) -> None:
    if bot.config.get("PEPPERCORD_TOPGG") is not None:
        bot.add_cog(TopGG(bot))
    if bot.config.get("PEPPERCORD_TOPGG_WH_SECRET") is not None:
        bot.add_cog(TopGGWebhook(bot))


def teardown(bot: bots.BOT_TYPES) -> None:
    if bot.config.get("PEPPERCORD_TOPGG") is not None:
        bot.add_cog("TopGG")
    if bot.config.get("PEPPERCORD_TOPGG_WH_SECRET") is not None:
        bot.add_cog("Voting")

