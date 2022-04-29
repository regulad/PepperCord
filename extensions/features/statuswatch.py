from discord import Member, Guild, User, HTTPException, Status
from discord.app_commands import describe
from discord.ext.commands import Cog, guild_only, hybrid_group
from discord.utils import escape_markdown

from utils.bots import BOT_TYPES, CustomContext
from utils.database import Document


def status_breakdown(desktop_status: Status, mobile_status: Status, web_status: Status) -> str | None:
    strings: list[str] = []

    if desktop_status is not Status.offline:
        strings.append(f"Desktop: `{str(desktop_status).title()}`")

    if mobile_status is not Status.offline:
        strings.append(f"Mobile: `{str(mobile_status).title()}`")

    if desktop_status is not Status.offline:
        strings.append(f"Web: `{str(web_status).title()}`")

    return ", ".join(strings) if strings else None


class StatusWatch(Cog):
    """A set of tools that allows you to watch the status of another user and get notified when it changes."""

    def __init__(self, bot: BOT_TYPES) -> None:
        self.bot: BOT_TYPES = bot

    @Cog.listener()
    async def on_presence_update(self, before: Member, after: Member) -> None:
        document: Document = await self.bot.get_user_document(after)
        if before.status != after.status:  # We don't care about presences here.
            before_breakdown: str | None = status_breakdown(before.desktop_status, before.mobile_status,
                                                            before.web_status)
            after_breakdown: str | None = status_breakdown(after.desktop_status, after.mobile_status,
                                                           after.web_status)
            for guild_id, user_id \
                    in [(int(scope.split("-")[0]), int(scope.split("-")[-1])) for scope in
                        document.get("watchers", [])]:
                try:
                    guild: Guild = self.bot.get_guild(guild_id) or await self.bot.fetch_guild(guild_id)
                    user: User = self.bot.get_user(user_id) or await self.bot.fetch_user(user_id)

                    await user.send(
                        f"{after.mention}'s ({escape_markdown(after.display_name)}) status has changed to "
                        f"`{str(after.status).title()}`{f' ({after_breakdown}' if after_breakdown else ''}\n"
                        f"(from `{str(before.status).title()}`{f' ({before_breakdown})' if before_breakdown else ''})"
                    )
                except HTTPException:
                    continue


    @hybrid_group(name="watch", aliases=("w", "sw"), fallback="start")
    @guild_only()
    @describe(member="The member to watch. This will be in the context of server this command is executed in.")
    async def statuswatch(self, ctx: CustomContext, member: Member) -> None:
        """Watch a member's status. You'll receive updates in a DM."""
        document: Document = await ctx.bot.get_user_document(member)
        await document.update_db({"$push": {"watchers": f"{ctx.guild.id}-{member.id}"}})
        await ctx.send(f"{member.mention} is now being watched.", ephemeral=True)

    @statuswatch.command(name="stop")
    @guild_only()
    @describe(member="The member to stop watching. This will be in the context of server this command is executed in.")
    async def statuswatch_stop(self, ctx: CustomContext, member: Member) -> None:
        """Stop watching a member's status."""
        document: Document = await ctx.bot.get_user_document(member)
        await document.update_db({"$pull": {"watchers": f"{ctx.guild.id}-{member.id}"}})
        await ctx.send(f"{member.mention} is no longer being watched.", ephemeral=True)


async def setup(bot: BOT_TYPES) -> None:
    await bot.add_cog(StatusWatch(bot))
