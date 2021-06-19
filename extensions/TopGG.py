from typing import Union, Optional, List
import datetime
from random import randint

from discord.ext import commands, menus
import discord
from topgg import DBLClient, WebhookManager
from topgg.types import BotVoteData

from utils import bots, database


PESTERING_MESSAGES = [
    "Psst... Like the bot? Vote for it!",
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
            embed = discord.Embed(title=f"{self.user.display_name}'s Votes").set_thumbnail(url=self.user.avatar_url).add_field(
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

            random_index: int = randint(0, len(PESTERING_MESSAGES) - 1)

            await ctx.send(f"{PESTERING_MESSAGES[random_index]} {get_top_gg_link(ctx.bot.user.id)}")

    @commands.command(
        name="vote",
        aliases=["bump"],
        brief="Gets the link to vote.",
        description="Gets the link to vote for the bot on Top.gg.",
    )
    async def vote(self, ctx: bots.CustomContext) -> None:
        await ctx.send(get_top_gg_link(ctx.bot.user.id))

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
        user: Union[discord.Member, discord.User] = user or ctx.author
        document: database.Document = await self.bot.get_user_document(user)
        await VotesMenu(document, user).start(ctx)


class TopGG(commands.Cog):
    """Utilities for interacting with Top.gg."""

    def __init__(self, bot: bots.BOT_TYPES) -> None:
        self.bot = bot


def setup(bot: bots.BOT_TYPES) -> None:
    if bot.config.get("PEPPERCORD_TOPGG") is not None:
        if isinstance(bot, bots.CustomAutoShardedBot):
            bot.topggpy = DBLClient(bot, bot.config["PEPPERCORD_TOPGG"], autopost=True, post_shard_count=True)
        else:
            bot.topggpy = DBLClient(bot, bot.config["PEPPERCORD_TOPGG"], autopost=True)

        bot.add_cog(TopGG(bot))
    if bot.config.get("PEPPERCORD_TOPGG_WH") is not None \
            and bot.config.get("PEPPERCORD_TOPGG_WH_ROUTE") is not None \
            and bot.config.get("PEPPERCORD_TOPGG_WH_SECRET") is not None:
        bot.topgg_webhook = WebhookManager(bot).dbl_webhook(
            bot.config["PEPPERCORD_TOPGG_WH_ROUTE"], bot.config["PEPPERCORD_TOPGG_WH_SECRET"]
        )
        bot.topgg_webhook.run(int(bot.config["PEPPERCORD_TOPGG_WH"]))

        bot.add_cog(TopGGWebhook(bot))


def teardown(bot: bots.BOT_TYPES) -> None:
    if bot.topggpy is not None:
        bot.remove_cog("TopGG")

        bot.loop.create_task(bot.topggpy.close())
        # Not perfect, but it shouldn't be that big of an issue.
        # It isn't normally mission critical to close the connection.
    if bot.topgg_webhook is not None:
        bot.remove_cog("Voting")

        bot.loop.create_task(bot.topgg_webhook.close())
        # Above also applies here, to a greater extent.
