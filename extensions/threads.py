from typing import Optional

from discord.ext import commands
import discord

from utils.checks import has_permission_level, LowPrivilege
from utils.permissions import Permission, get_permission
from utils.bots import CustomContext, BOT_TYPES
from utils.localization import Message


class Threads(commands.Cog):
    """A set of utilities to assist in working with threads."""

    def __init__(self, bot: BOT_TYPES) -> None:
        self.bot: BOT_TYPES = bot

    async def cog_check(self, ctx: CustomContext) -> bool:
        if not await has_permission_level(ctx, Permission.MANAGER):
            raise LowPrivilege(Permission.MANAGER, get_permission(ctx))
        else:
            return True

    @commands.Cog.listener("on_thread_update")
    async def thread_unarchiver(self, before: discord.Thread, after: discord.Thread) -> None:
        ctx: CustomContext = await self.bot.get_context(after.last_message if after.last_message is not None else await after.fetch_message(after.last_message_id))
        if ((not before.archived) and after.archived) and after.id in ctx.guild_document.get("unarchived_threads", []):
            await after.edit(archived=False)
            await after.send(ctx.locale.get_message(Message.THREAD_UNARCHIVED).format(thread=after))

    @commands.group(
        invoke_without_command=True,
        case_insensitive=True,
        name="thread",
        aliases=["threads"],
        description="A set of utilities to assist in working with threads",
    )
    async def thread(self, ctx: CustomContext) -> None:
        pass

    @thread.group(
        invoke_without_command=True,
        case_insensitive=True,
        name="archive",
        aliases=["unarchive"],
        description="A set of utilities to help with the archival of threads.",
    )
    async def archive(self, ctx: CustomContext) -> None:
        pass

    @archive.command(
        name="shield",
        aliases=["set"],
        description="Shields a Thread from being archived.",
    )
    async def shield(self, ctx: CustomContext, *, thread: Optional[discord.Thread] = None) -> None:
        thread = thread or ctx.channel if isinstance(ctx.channel, discord.Thread) else None
        if thread is None:
            raise commands.BadArgument("thread is required when not in a thread")

        await ctx.guild_document.update_db({"$push": {"unarchived_threads": thread.id}})

    @archive.command(
        name="unshield",
        aliases=["unset"],
        description="Unshields a Thread from being archived.",
    )
    async def unshield(self, ctx: CustomContext, *, thread: Optional[discord.Thread] = None) -> None:
        thread = thread or ctx.channel if isinstance(ctx.channel, discord.Thread) else None
        if thread is None:
            raise commands.BadArgument("thread is required when not in a thread")

        await ctx.guild_document.update_db({"$pull": {"unarchived_threads": thread.id}})


def setup(bot: BOT_TYPES) -> None:
    bot.add_cog(Threads(bot))
