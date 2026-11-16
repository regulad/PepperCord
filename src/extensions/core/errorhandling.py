import asyncio
import inspect
from copy import copy
from logging import getLogger
from typing import TYPE_CHECKING, Any, Optional, Type

import discord
from discord import Message
from discord.app_commands import CommandInvokeError as AppCommandInvokeError
from discord.ext import commands, menus
from discord.ext.commands import CommandNotFound

from utils import attachments
from utils.bots.bot import CustomBot
from utils.bots.context import CustomContext
from utils.commands import NotConfigured
from utils.checks.audio import CantCreateAudioClient
from utils.checks.blacklisted import EBlacklisted

# What is about to happen is nothing short of disgusting.
try:
    from yt_dlp import DownloadError  # type: ignore
except ImportError:
    from youtube_dl import DownloadError  # type: ignore
YoutubeDLError = inspect.getmro(DownloadError)[1]
del DownloadError

logger = getLogger(__name__)

known_errors: dict[Type[Any], str] = {
    CantCreateAudioClient: "The bot failed to find a way to make an audio player. Are you in a voice channel?",
    asyncio.QueueFull: "The queue is full. Please wait for this track to finish before you play the next song.",
    commands.UserInputError: "You entered a bad argument.",
    commands.NSFWChannelRequired: "This command displays explicit content. "
    "You can only use it in channels marked as NSFW.",
    commands.CommandOnCooldown: "You'll need to wait before you can execute this command again.",
    commands.NotOwner: "Only the bot's owner may execute this command.",
    NotConfigured: "This feature must be configured before use. Ask a server administrator.",
    commands.BotMissingPermissions: "The bot was unable to perform the action requested, "
    "since it is missing permissions required to do so. Try re-inviting the bot.",
    commands.CheckFailure: "A check failed.",
    attachments.WrongMedia: "The media that was found could not be used for the desired action.",
    attachments.NoMedia: "Could not find media to use.",
    EBlacklisted: "You have been blacklisted from using this bot.",
    attachments.MediaTooLong: "You can't download media this long.",
    attachments.MediaTooLarge: "This media is too large to be uploaded to discord.",
}


def find_error(error: Exception) -> Optional[str]:
    for known_error, response in known_errors.items():
        if isinstance(error, known_error):
            return response
    else:
        if error.__doc__ is not None:
            return error.__doc__
        else:
            return None


# Because ListPageSource comes from legacy untyped code and is being patched over with a stub, we need to do this to make sure it never gets subscripted at runtime.
if TYPE_CHECKING:
    _ErrorMenu_Base = menus.Menu[CustomBot, CustomContext]
else:
    _ErrorMenu_Base = menus.Menu


class ErrorMenu(_ErrorMenu_Base):
    def __init__(
        self, error: Exception, **kwargs: Any
    ) -> None:  # TODO: better kwarg passthrough
        if isinstance(error, commands.HybridCommandError):
            error = error.original

        if isinstance(error, (commands.CommandInvokeError, AppCommandInvokeError)):
            error = error.original

        self.error = error

        super().__init__(**kwargs)

    async def send_initial_message(
        self, ctx: CustomContext, channel: discord.abc.Messageable
    ) -> Message:
        error_response = find_error(self.error)

        embed = discord.Embed(
            colour=discord.Colour.red(), title="An error has occurred."
        )

        error_string = str(self.error)
        if isinstance(self.error, YoutubeDLError):
            error_string = self.error.msg  # type: ignore

        if len(str(error_string)) > 0:
            embed.add_field(
                name=f"Type: {self.error.__class__.__name__}",
                value=f"```{error_string}```",
            )
        else:
            embed.description = f"**Type: {self.error.__class__.__name__}**"

        if error_response is not None:
            embed.set_footer(text=f"Tip: {error_response}")

        return await channel.send(embed=embed)


class ErrorHandling(commands.Cog):
    """Handles raised errors."""

    def __init__(self, bot: CustomBot):
        self.bot = bot

    @commands.Cog.listener("on_command_completion")
    async def affirm_working(self, ctx: CustomContext) -> None:
        if ctx.interaction is None:
            await ctx.message.add_reaction("✅")

    @commands.Cog.listener("on_command_error")
    async def soft_affirm_error(self, ctx: CustomContext, error: Exception) -> None:
        if ctx.interaction is None and not isinstance(error, CommandNotFound):
            await ctx.message.add_reaction("❌")

    @commands.Cog.listener("on_command_error")
    async def affirm_error(self, ctx: CustomContext, error: Exception) -> None:
        if ctx.command is not None and not isinstance(error, commands.DisabledCommand):
            await ErrorMenu(error).start(ctx)

    @commands.Cog.listener("on_command_error")
    async def attempt_to_reinvoke(self, ctx: CustomContext, error: Exception) -> None:
        if ctx.command is not None:
            if await ctx.bot.is_owner(ctx.author):
                if ctx.valid and isinstance(
                    error, (commands.CommandOnCooldown, commands.CheckFailure)
                ):
                    if ctx.interaction is None:
                        await ctx.reinvoke()
                    else:
                        # We have to make this interaction into a regular message command.
                        # At this point in time, the interaction is already responded to.
                        # We will need to make sure our context is aware.
                        bodged_ctx = copy(ctx)  # Avoid mutating the original context.
                        await bodged_ctx.send(
                            f"You're the boss! Original error: {type(error)} Reinvoking...",
                            ephemeral=True,
                        )
                        # The reinvoke command is broken with interactions, so we have to do this.
                        # The reason why it is broken is weird: the context is never prepared!
                        # We can wait a couple seconds.
                        # Special case: abort the cooldown for this command.
                        if isinstance(error, commands.CommandOnCooldown):
                            bodged_ctx.command.reset_cooldown(bodged_ctx)  # type: ignore
                        await bodged_ctx.command.prepare(bodged_ctx)  # type: ignore  # Mutates context
                        # Additonally, reinvoking is broken for interactions.
                        bodged_ctx.interaction = None
                        await bodged_ctx.reinvoke(restart=False)

    @commands.Cog.listener("on_command_error")
    async def determine_if_critical(self, ctx: CustomContext, error: Exception) -> None:
        if isinstance(error, commands.CommandInvokeError):
            error = error.original

        critical: bool = not isinstance(
            error,
            (
                commands.UserInputError,
                commands.CommandOnCooldown,
                commands.CheckFailure,
                commands.CommandInvokeError,
                commands.CommandNotFound,
                commands.DisabledCommand,
                commands.CommandError,
            ),
        )

        if critical:
            await self.bot.on_error("command", ctx, error)


async def setup(bot: CustomBot) -> None:
    await bot.add_cog(ErrorHandling(bot))
