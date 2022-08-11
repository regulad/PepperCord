from datetime import datetime
from logging import Logger, getLogger
from math import floor
from typing import Optional, Any

from aiohttp import ClientSession
from discord import Embed, User, HTTPException
from discord.ext.commands import Cog, group
from discord.ext.menus import ListPageSource, ReactionMenuPages
from discord.ext.tasks import loop
from motor.motor_asyncio import AsyncIOMotorCollection

from utils.bots import BOT_TYPES, CustomContext
from utils.database import Document
from utils.misc import random_string, UTC_OFFSET

API_URL: str = "https://redirector.regulad.xyz/"
SHORT_URL: str = "https://crud.space/"

logger: Logger = getLogger(__name__)


class LoggedEvent:
    """A logged redirector event."""

    def __init__(
            self,
            link_id: str,
            redirected_to: str,
            redirected_at: datetime,
            remote: str,
            user_agent: Optional[str],
            *,
            document: Document,
    ):
        self.link_id: str = link_id
        self.redirected_to: str = redirected_to
        self.redirected_at: datetime = redirected_at
        self.remote: str = remote
        self.document: Document = document
        self.user_agent: Optional[str] = user_agent

    __slots__ = (
        "link_id",
        "redirected_to",
        "redirected_at",
        "remote",
        "document",
        "user_agent",
    )


class CampaignSource(ListPageSource):
    def __init__(
            self, campaigns: list[tuple[str, datetime]], *, per_page: int = 10
    ) -> None:
        super().__init__(
            sorted(campaigns, key=lambda x: x[1], reverse=True), per_page=per_page
        )

    async def format_page(self, menu, entries):
        offset = menu.current_page * self.per_page

        embed: Embed = Embed(title=f"All campaigns", color=0x00FF00)
        embed.set_footer(text=f"Page {menu.current_page + 1}/{self.get_max_pages()}")

        for iteration, entry in enumerate(entries, start=offset):
            embed.add_field(
                name=f"{iteration + 1}. {entry[0]}",
                value=f"<t:{floor((entry[1] - UTC_OFFSET).timestamp())}>",
                inline=False,
            )

        return embed


class HitSource(ListPageSource):
    def __init__(
            self, hits: list[LoggedEvent], campaign_id: str, *, per_page: int = 4
    ) -> None:
        self.campaign_id: str = campaign_id
        super().__init__(
            sorted(hits, key=lambda x: x.redirected_at, reverse=True), per_page=per_page
        )

    async def format_page(self, menu, entries):
        offset = menu.current_page * self.per_page

        embed: Embed = Embed(
            title=f"Campaign {self.campaign_id} summary",
            color=0x00FF00,
            description=f"{len(self.entries)} total hits",
        )
        embed.set_footer(text=f"Page {menu.current_page + 1}/{self.get_max_pages()}")

        for iteration, entry in enumerate(entries, start=offset):
            entry: LoggedEvent
            iteration: int
            embed.add_field(
                name=f"{iteration + 1}. ",
                value=f"Occurred at <t:{floor((entry.redirected_at - UTC_OFFSET).timestamp())}>\n"
                      f"Redirected to [{entry.redirected_to}]({entry.redirected_to})\n"
                      f"IP Address: `{entry.remote}`"
                      + (
                          f"\nUser Agent: `{entry.user_agent}`"
                          if entry.user_agent is not None
                          else ""
                      ),
                inline=False,
            )

        return embed


async def get_listen_doc(collection: AsyncIOMotorCollection, link_id: str) -> Document:
    return await Document.get_document(collection, {"_id": link_id})


def get_collection(bot: BOT_TYPES) -> AsyncIOMotorCollection:
    """Returns the database for the Redirector cog."""
    return bot.database["redirector"]


class Redirector(Cog):
    """A cog that allows you to use Redirector, an IP logging and analytics service."""

    def __init__(self, bot: BOT_TYPES) -> None:
        self.bot: BOT_TYPES = bot
        self.client_session: Optional[ClientSession] = None

    @Cog.listener()
    async def on_ready(self) -> None:
        # TODO: Webhook implementation

        self.check_for_redirections.start()

    @loop(seconds=60)
    async def check_for_redirections(self) -> None:
        async for raw_document in get_collection(self.bot).find({}):
            document: Document = Document(
                raw_document,
                collection=get_collection(self.bot),
                query={"_id": raw_document["_id"]},
            )

            if document.get("listening_user") is None:
                continue
            else:
                async with self.client_session.get(
                        f"{API_URL}hits/{document['_id']}"
                ) as response:
                    if response.status == 200:
                        data: list[dict[str, Any]] = await response.json()
                        for entry in data:
                            timestamp: datetime = datetime.fromisoformat(
                                entry["timestamp"]
                            )
                            if timestamp > document["last_checked"]:
                                self.bot.dispatch(
                                    "redirection",
                                    LoggedEvent(
                                        entry["link_id"],
                                        entry["redirected_to"],
                                        timestamp,
                                        entry["remote"],
                                        entry.get("user_agent"),
                                        document=document,
                                    ),
                                )

                        await document.update_db(
                            {"$currentDate": {"last_checked": True}}
                        )
                    else:
                        logger.warning(
                            f"Failed to get redirections for {document['_id']}"
                        )

    async def cog_load(self) -> None:
        if self.client_session is None:
            self.client_session = ClientSession()

    async def cog_unload(self) -> None:
        if self.client_session is not None:
            await self.client_session.close()
        if self.check_for_redirections.is_running():
            self.check_for_redirections.stop()

    @Cog.listener()
    async def on_redirection(self, logged_event: LoggedEvent) -> None:
        """A listener that is called when a redirection is logged."""

        listening_document: Document = logged_event.document

        if listening_document.get("listening_user") is not None:
            listening_user: User = self.bot.get_user(
                listening_document["listening_user"]
            ) or await self.bot.fetch_user(listening_document["listening_user"])

            embed: Embed = (
                Embed(
                    title="Result",
                    description=f"Regarding campaign ID `{logged_event.link_id}`",
                )
                .add_field(
                    name="Redirected to:",
                    value=f"[{logged_event.redirected_to}]({logged_event.redirected_to})",
                )
                .add_field(
                    name="Redirected at:",
                    value=f"<t:{floor((logged_event.redirected_at - UTC_OFFSET).timestamp())}>",
                )
                .add_field(name="IP Address:", value=f"`{logged_event.remote}`")
            )

            if logged_event.user_agent is not None:
                embed: Embed = embed.add_field(
                    name="User Agent:", value=f"`{logged_event.user_agent}`"
                )

            await listening_user.send("An IP address has been grabbed!", embed=embed)

    @group(aliases=["register_listener", "make_campaign", "r"], fallback="grab")
    async def ipgrab(
            self,
            ctx: CustomContext,
            destination: str,
            link_id: Optional[str],
    ) -> None:
        """
        Registers a redirector campaign.
        This can be used for IP grabbing, analytics, link shortening, or anything else that needs to be redirected.
        """

        async with ctx.typing(ephemeral=True):
            link_id: str = link_id or random_string(length=6)

            # Start listening
            listening_document: Document = await get_listen_doc(
                get_collection(self.bot), link_id
            )
            await listening_document.update_db(
                {
                    "$set": {"listening_user": ctx.author.id},
                    "$currentDate": {"last_checked": True, "created_at": True},
                }
            )

            async with self.client_session.post(
                    f"{API_URL}{link_id}", data=destination
            ) as response:
                if response.status != 201:
                    raise HTTPException(
                        response, response.reason
                    )  # Possibly jank. It should be fine.

            # TODO: Webhook implementation

            await ctx.send(
                f"Campaign link created: <{SHORT_URL}{link_id}>\n"
                f"Your campaign ID is: `{link_id}`\n"
                f"Make sure your DMs are open. You will receive notifications there.",
                ephemeral=True,
            )

    @ipgrab.command()
    async def all_campaigns(self, ctx: CustomContext) -> None:
        """Lists all the redirector campaigns you are listening to."""

        async with ctx.typing(ephemeral=True):
            all_campaigns: list[tuple[str, datetime]] = []

            async for document in get_collection(self.bot).find(
                    {"listening_user": ctx.author.id}
            ):
                all_campaigns.append((document["_id"], document["created_at"]))

            source: CampaignSource = CampaignSource(all_campaigns)

        await ReactionMenuPages(source).start(ctx, ephemeral=True)

    @ipgrab.command()
    async def summarize_campaign(
            self,
            ctx: CustomContext,
            link_id: str,
    ) -> None:
        """Summarizes a redirector campaign."""

        async with ctx.typing(ephemeral=True):
            all_hits: list[LoggedEvent] = []

            document: Document = await get_listen_doc(get_collection(self.bot), link_id)

            async with self.client_session.get(
                    f"{API_URL}hits/{document['_id']}"
            ) as response:
                data: list[dict[str, Any]] = await response.json()
                for entry in data:
                    timestamp: datetime = datetime.fromisoformat(entry["timestamp"])
                    all_hits.append(
                        LoggedEvent(
                            entry["link_id"],
                            entry["redirected_to"],
                            timestamp,
                            entry["remote"],
                            entry.get("user_agent"),
                            document=document,
                        )
                    )

            source: HitSource = HitSource(all_hits, link_id)

        await ReactionMenuPages(source).start(ctx, ephemeral=True)

    @ipgrab.command()
    async def stopgrabbing(
            self,
            ctx: CustomContext,
            link_id: str,
    ) -> None:
        """Stops listening to a campaign ID."""

        async with ctx.typing(ephemeral=True):
            listening_document: Document = await get_listen_doc(
                get_collection(self.bot), link_id
            )

            if listening_document.get("listening_user") is None:
                await ctx.send("That campaign ID is not being listened to.", ephemeral=True)
                return

            if listening_document["listening_user"] != ctx.author.id:
                await ctx.send("You are not listening to that campaign ID.", ephemeral=True)
                return

            await listening_document.delete_db()
            await ctx.send(
                "You are no longer listening to that campaign ID.", ephemeral=True
            )


async def setup(bot: BOT_TYPES) -> None:
    """Loads the Redirector cog."""
    await bot.add_cog(Redirector(bot))
