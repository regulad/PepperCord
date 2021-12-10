import datetime
from random import choice, randint
from typing import Union, Optional, List

import discord
from discord.ext import commands, menus
from topgg import DBLClient, WebhookManager
from topgg.types import BotVoteData, BotData

from utils import bots, database

PESTERING_MESSAGES: List[str] = [
    "Like the bot? Vote for it!",
]


def get_top_gg_link(bot_id: int) -> str:
    return f"https://top.gg/bot/{bot_id}"


class VotesMenu(menus.ViewMenu):
    def __init__(
        self,
        document: database.Document,
        user: Union[discord.Member, discord.User],
        *,
        timeout=180.0,
        delete_message_after=False,
        clear_reactions_after=False,
        check_embeds=False,
        message=None,
    ):
        self.document = document
        self.user = user

        super().__init__(
            timeout=timeout,
            delete_message_after=delete_message_after,
            clear_reactions_after=clear_reactions_after,
            check_embeds=check_embeds,
            message=message,
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

            return await ctx.send(embed=embed, ephemeral=True)
        else:
            return await ctx.send(f"{self.user.display_name} hasn't voted yet.")


class TopGGWebhook(commands.Cog, name="Voting"):
    """Vote for the bot on Top.gg for some sick rewards."""

    def __init__(self, bot: bots.BOT_TYPES) -> None:
        self.bot = bot

        self.webhook_manager = WebhookManager(bot)

        self.webhook_manager.dbl_webhook(
            bot.config.get("PEPPERCORD_TOPGG_WH_ROUTE", "/topgg"),
            bot.config["PEPPERCORD_TOPGG_WH_SECRET"],
        )

        self.webhook_manager.run(int(bot.config.get("PEPPERCORD_TOPGG_WH", "5000")))

    def cog_unload(self) -> None:
        self.bot.loop.create_task(self.webhook_manager.close())

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

            await ctx.send(
                f"Psst... {choice(PESTERING_MESSAGES)} "
                f"{get_top_gg_link(ctx.bot.user.id)}"
                f" Tried of these messages? Try nopester."
                if ctx["author_document"].get("pestered", 0) > 2
                else ""
            )

            await ctx["author_document"].update_db({"$inc": {"pestered": 1}})

    @commands.group()
    async def votesettings(self):
        pass

    @votesettings.command()
    async def pester(self, ctx: bots.CustomContext, *, nopester: bool = False) -> None:
        """Adjust the pester status."""
        await ctx["author_document"].update_db({"$set": {"nopester": nopester}})
        await ctx.send("Settings updated.", ephemeral=True)

    @commands.command()
    async def votes(
        self,
        ctx: bots.CustomContext,
        *,
        user: Optional[Union[discord.Member, discord.User]],
    ) -> None:
        """Shows you your voting stats."""
        await ctx.defer(ephemeral=True)
        user: Union[discord.Member, discord.User] = user or ctx.author
        document: database.Document = await self.bot.get_user_document(user)

        await VotesMenu(document, user).start(ctx)


class TopGG(commands.Cog):
    """Utilities for interacting with Top.gg."""

    def __init__(self, bot: bots.BOT_TYPES) -> None:
        self.bot = bot

        if isinstance(bot, bots.CustomAutoShardedBot):
            self.topggpy = DBLClient(
                bot,
                bot.config["PEPPERCORD_TOPGG"],
                autopost=True,
                post_shard_count=True,
            )
        else:
            self.topggpy = DBLClient(bot, bot.config["PEPPERCORD_TOPGG"], autopost=True)

    def cog_unload(self) -> None:
        self.bot.loop.create_task(self.topggpy.close())

    @commands.group()
    async def topgg(self, ctx: bots.CustomContext) -> None:
        pass

    @topgg.command()
    async def vote(self, ctx: bots.CustomContext) -> None:
        """Shows you where to vote for the bot on top.gg"""
        await ctx.send(get_top_gg_link(ctx.bot.user.id), ephemeral=True)

    @topgg.command()
    async def totalvotes(self, ctx: bots.CustomContext) -> None:
        """Shows the total amount of votes the bot as accumulated."""
        await ctx.defer(ephemeral=True)
        bot_info: BotData = await self.topggpy.get_bot_info()
        await ctx.send(
            f"{ctx.bot.user.name} has received {bot_info['points']} votes on Top.gg. Why don't you make it {int(bot_info['points']) + 1}?",
            ephemeral=True
        )


def setup(bot: bots.BOT_TYPES) -> None:
    if bot.config.get("PEPPERCORD_TOPGG") is not None:
        bot.add_cog(TopGG(bot))
    if bot.config.get("PEPPERCORD_TOPGG_WH_SECRET") is not None:
        bot.add_cog(TopGGWebhook(bot))
