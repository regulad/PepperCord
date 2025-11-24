from __future__ import annotations

from asyncio import sleep
from typing import TYPE_CHECKING, Optional, Union, cast

from discord import ClientUser, Embed, Guild, Message, TextChannel
from discord.abc import Messageable, GuildChannel
from discord.ext.commands import Cog, guild_only, CheckFailure, command
from discord.ext.menus import ListPageSource, MenuPages

from utils.bots.bot import CustomBot
from utils.bots.context import CustomContext


class MessageOfTheDay(Cog):
    """
    This cog provides a mechanism by which the bot's admin can disseminate information/announcements upon the bot's users.
    No user-facing commands.
    """

    def __init__(self, bot: CustomBot) -> None:
        self.bot = bot
        self._motd_channel_id = int(bot.config["PEPPERCORD_MOTD_CHANNEL"])
        self._motd_min_invocations = int(bot.config["PEPPERCORD_MOTD_MIN_INVOCATIONS"])

        self._motd_channel_cached: TextChannel | None = None
        self._motd_current_message: Message | None = None

    @Cog.listener()
    async def on_after_invocation_nonblocking(self, ctx: CustomContext) -> None:
        author_document = ctx["author_document"]
        await author_document.update_db({"$inc": {"loyalty": 1}})
        # I'd like to see someone manage to cause an integer overflow with this.
        total_invocations = int(await author_document.safe_subscript("loyalty"))

        already_seen_motds_raw = await author_document.safe_get("motds_seen", [])
        if not isinstance(already_seen_motds_raw, list):
            raise RuntimeError(
                f"A non-list somehow snuck into `motds_seen` on {author_document}"
            )
        already_seen_motds_ids = [int(message) for message in already_seen_motds_raw]
        del already_seen_motds_raw  # No idea if this actually helps the GC. Let's assume it does.

        if self._motd_channel_cached is None or self._motd_current_message is None:
            # can't do any processing
            return
        elif total_invocations < self._motd_min_invocations:
            # This user isn't yet "loyal" enough to see an MOTD.
            # (In reality, the user hasn't used the bot enough to not get pissed off if they get pestered)
            return

        if self._motd_current_message.id in already_seen_motds_ids:
            # The user has already seen this MOTD. Let's avoid pestering them further.
            return

        ordinal_suffix_of_invocation: str
        match (total_invocations % 10):
            case 1:
                ordinal_suffix_of_invocation = "st"
            case 2:
                ordinal_suffix_of_invocation = "nd"
            case 3:
                ordinal_suffix_of_invocation = "rd"
            case _:
                ordinal_suffix_of_invocation = "th"
        formal_invocations = f"{total_invocations}{ordinal_suffix_of_invocation}"

        # I'm currently using an embed to disseminate MOTDs, perhaps `impersonate` would also be a viable alternative?
        cu_me = cast(ClientUser, self.bot.user)
        await ctx.send(
            embed=(
                Embed(
                    title=f"{cu_me.display_name} PSA!",
                    type="rich",
                    description=self._motd_current_message.content,
                )
                .set_thumbnail(
                    url=cu_me.avatar.url if cu_me.avatar is not None else None
                )
                .set_footer(
                    text=(
                        f"Fun fact: this is your {formal_invocations} time using this copy of PepperCord since 2025!"
                    )
                )
            ),
            ephemeral=True,
        )

        # We're done here. Let's make sure the sender doesn't see it again.
        await author_document.update_db(
            {"$push": {"motds_seen": self._motd_current_message.id}}
        )

    @Cog.listener()
    async def on_ready(self) -> None:
        maybe_motd_channel = await self.bot.fetch_channel(self._motd_channel_id)
        if not isinstance(maybe_motd_channel, TextChannel):
            raise ValueError(
                f"Expected a text channel but got {maybe_motd_channel}! MOTD will not work."
            )
        my_permissions = maybe_motd_channel.permissions_for(maybe_motd_channel.guild.me)
        if not (my_permissions.read_message_history and my_permissions.read_messages):
            raise ValueError(
                f"I do not have the necessary permissions to use {maybe_motd_channel} as an MOTD channel!"
            )
        self._motd_channel_cached = maybe_motd_channel

        async for message in self._motd_channel_cached.history(limit=1):
            self._motd_current_message = message
            break

        # If history never iterated, it's fine. That would only happen if there's no history in the MOTD channel, leaving self._motd_current_message as None.
        # Since self._motd_current_message *should* be None if there isn't a current message, this works elegantly.
        # NOTE: since the MOTD channel SHOULD NOT be writable by the general public, we're treating it as privileged and not going to escape anything within it. Forkers beware.

    @Cog.listener()
    async def on_message(self, message: Message) -> None:
        # Using the ID here instead of an object accounts for the incredibly narrow edge-case
        # where a new message is received before the on_ready hook finishes executing.
        if message.channel.id == self._motd_channel_id and (
            self._motd_current_message is None
            or message.created_at > self._motd_current_message.created_at
        ):
            self._motd_current_message = message
        # I'm not even sure if its possible that a message received via the gateway is older than an already-received one,
        # but Discord has been known to be odd with its prioritization of gateway events.


async def setup(bot: CustomBot) -> None:
    await bot.add_cog(MessageOfTheDay(bot))
