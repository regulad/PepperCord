from datetime import datetime
from typing import cast

from discord import (
    Member,
    Guild,
    HTTPException,
    Status,
    Interaction,
    AppCommandType,
    Embed,
)
from discord.app_commands import describe, context_menu
from discord.app_commands import guild_only as ac_guild_only
from discord.ext.commands import Cog, guild_only, hybrid_group, Greedy, Command
from discord.utils import escape_markdown, format_dt

from utils import checks
from utils.bots import BOT_TYPES, CustomContext
from utils.database import Document
from utils.misc import status_breakdown

WATCH_CM: str = "Watch Status"
UNWATCH_CM: str = "Stop Watching Status"


@context_menu(name=WATCH_CM)
@ac_guild_only()
async def watch_cm_pred(interaction: Interaction, member: Member) -> None:
    ctx: CustomContext = await CustomContext.from_interaction(interaction)
    await ctx.invoke(
        cast(
            Command,
            cast(StatusWatch, ctx.bot.get_cog(StatusWatch.__name__)).statuswatch,
        ),
        member,
    )


@context_menu(name=UNWATCH_CM)
@ac_guild_only()
async def unwatch_cm_pred(interaction: Interaction, member: Member) -> None:
    ctx: CustomContext = await CustomContext.from_interaction(interaction)
    await ctx.invoke(
        cast(
            Command,
            cast(StatusWatch, ctx.bot.get_cog(StatusWatch.__name__)).statuswatch_stop,
        ),
        member,
    )


class StatusWatch(Cog):
    """A set of tools that allows you to watch the status of another user and get notified when it changes."""

    def __init__(self, bot: BOT_TYPES) -> None:
        self.bot: BOT_TYPES = bot

    def cog_load(self) -> None:
        self.bot.tree.add_command(watch_cm_pred)
        self.bot.tree.add_command(unwatch_cm_pred)

    def cog_unload(self) -> None:
        self.bot.tree.remove_command(WATCH_CM, type=AppCommandType.user)
        self.bot.tree.remove_command(UNWATCH_CM, type=AppCommandType.user)

    @Cog.listener("on_presence_update")
    async def notify(self, before: Member, after: Member) -> None:
        document: Document = await self.bot.get_user_document(after)
        if (
            before.status != after.status and after.status is not Status.offline
        ):  # We don't care about presences here.
            before_breakdown: str | None = status_breakdown(
                before.desktop_status, before.mobile_status, before.web_status
            )
            after_breakdown: str | None = status_breakdown(
                after.desktop_status, after.mobile_status, after.web_status
            )
            from_text: str = f"\nfrom `{str(before.status).title()}`{f' ({before_breakdown})' if before_breakdown else ''}"
            for guild_id, user_id in [
                (int(scope.split("-")[0]), int(scope.split("-")[-1]))
                for scope in document.get("watchers", [])
            ]:
                try:
                    if guild_id == after.guild.id:
                        guild: Guild = self.bot.get_guild(
                            guild_id
                        ) or await self.bot.fetch_guild(guild_id)

                        await (
                            self.bot.get_user(user_id)
                            or await self.bot.fetch_user(user_id)
                        ).send(
                            f"Update from {escape_markdown(guild.name)}: "
                            f"{after.mention}'s ({escape_markdown(after.display_name)}) status has changed to "
                            f"`{str(after.status).title()}`{f' ({after_breakdown})' if after_breakdown else ''}"
                            f"{from_text if before.status is not Status.offline else ''}"
                        )
                except HTTPException:
                    continue

    @Cog.listener("on_presence_update")
    async def update_last_online(self, before: Member, after: Member) -> None:
        document: Document = await self.bot.get_user_document(after)
        if (
            before.status is not Status.offline and after.status is Status.offline
        ) or after.status is not Status.offline:
            await document.update_db(
                {"$set": {"last_online": datetime.utcnow()}}
            )  # probably some mongo managed solution

    @hybrid_group(name="watch", aliases=("w", "sw"), fallback="start")
    @guild_only()
    @ac_guild_only()
    @describe(
        member="The member to watch. This will be in the context of server this command is executed in."
    )
    @checks.check_presences_enabled
    @checks.check_members_enabled
    async def statuswatch(self, ctx: CustomContext, member: Member) -> None:
        """Watch a member's status. You'll receive updates in a DM."""
        document: Document = await ctx.bot.get_user_document(member)
        await document.update_db(
            {"$push": {"watchers": f"{ctx.guild.id}-{ctx.author.id}"}}
        )
        await ctx.send(f"{member.mention} is now being watched.", ephemeral=True)

    @statuswatch.command(name="bulk")
    @guild_only()
    @describe(
        members="The members to watch. This will be in the context of server this command is executed in.\n"
        "This can be in any format, comma seperated."
    )
    @checks.check_presences_enabled
    async def statuswatch_bulk(
        self, ctx: CustomContext, members: Greedy[Member]
    ) -> None:
        """Watch a list of members' status. You'll receive updates in a DM."""
        await ctx.send(f"Registering {len(members)}...", ephemeral=True)
        for member in members:
            await ctx.invoke(self.statuswatch, member=member)

    @statuswatch.command(name="stop")
    @guild_only()
    @describe(
        member="The member to stop watching. This will be in the context of server this command is executed in."
    )
    @checks.check_presences_enabled
    async def statuswatch_stop(self, ctx: CustomContext, member: Member) -> None:
        """Stop watching a member's status."""
        document: Document = await ctx.bot.get_user_document(member)
        await document.update_db(
            {"$pull": {"watchers": f"{ctx.guild.id}-{ctx.author.id}"}}
        )
        await ctx.send(f"{member.mention} is no longer being watched.", ephemeral=True)

    @statuswatch.command(name="last_online", aliases=["last", "online"])
    @guild_only()
    @describe(member="The member to get the last online time of.")
    @checks.check_presences_enabled
    async def statuswatch_last_online(self, ctx: CustomContext, member: Member) -> None:
        """Get the last time a member was online."""
        async with ctx.typing(ephemeral=True):
            document: Document = await ctx.bot.get_user_document(member)
            last_online: datetime | None = document.get(
                "last_online",
                datetime.utcnow() if member.status is not Status.offline else None,
            )
            if member.status is not Status.offline:
                await ctx.send(
                    embed=Embed(
                        description=f"{member.mention} is currently online.",
                        color=0x389D58,
                    ),
                    ephemeral=True,
                )
            elif last_online is not None:
                await ctx.send(
                    embed=Embed(
                        description=f"{member.mention} was last online {format_dt(last_online)}.",
                        color=0x747F8D,
                    ),
                    ephemeral=True,
                )
            else:
                await ctx.send(
                    embed=Embed(
                        description=f"No data exists for {member.mention}. Please try again later.",
                        color=0x747F8D,
                    ),
                    ephemeral=True,
                )


async def setup(bot: BOT_TYPES) -> None:
    await bot.add_cog(StatusWatch(bot))
