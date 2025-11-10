import asyncio
import inspect
from copy import copy
from logging import getLogger
from tkinter import N
from typing import TYPE_CHECKING, Any, Optional, cast, Type

import discord
from discord import (
    Interaction,
    ButtonStyle,
    Embed,
    Message,
    RawReactionActionEvent,
    TextStyle,
)
from discord.app_commands import CommandInvokeError as AppCommandInvokeError
from discord.ext import commands, menus
from discord.ext.commands import CommandNotFound
from discord.ext.menus import button
from discord.ui import Modal, TextInput

from utils import attachments
from utils.bots.bot import CustomBot
from utils.bots.context import CustomContext
from utils.bots.commands import NotConfigured
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


class ErrorSupportModal(Modal, title="Support Form"):
    intent: TextInput[ErrorSupportModal] = TextInput(
        label="What were you trying to do?",
        placeholder="Example: I was trying to play a song.",
        style=TextStyle.long,
    )
    steps: TextInput[ErrorSupportModal] = TextInput(
        label="What steps did you take to do this?",
        placeholder="Example: I typed ?play song and clicked send.",
        style=TextStyle.long,
    )
    result: TextInput[ErrorSupportModal] = TextInput(
        label="What happened?",
        placeholder="Example: The bot didn't play the song.",
        style=TextStyle.long,
    )

    def __init__(self, error: Exception, ctx: CustomContext):
        super().__init__()
        self.error = error
        self.ctx = ctx

    async def on_submit(self, interaction: Interaction, /) -> None:
        await interaction.response.send_message(
            embed=(
                Embed(
                    description="The error has been submitted for review. "
                    "Please use [the support server (click here)](https://discord.gg/xwH2Bw7P5b) "
                    "for any additional help or to self-diagnose your problem."
                )
            ),
            ephemeral=True,
        )
        # send error
        for owner in await self.ctx.bot.fetch_effective_owners():
            await owner.send(
                embed=(
                    Embed(
                        title=f"**{self.ctx.author.display_name}** (`{self.ctx.author.id}`) encountered an error in "
                        + (
                            f"**{self.ctx.guild.name}** (`{self.ctx.guild.id}`) "
                            if self.ctx.guild is not None
                            else f"a non-server environment "
                        )
                        + f"with the command `{self.ctx.command}`.",
                        description=(
                            f"Type: **{self.error.__class__.__name__}**\n```{str(self.error)}```"
                            if len(str(self.error)) > 0
                            else f"Type: **{self.error.__class__.__name__}**"
                        ),
                    )
                    .add_field(
                        name="Intended Action",
                        value=self.intent.value,
                        inline=False,
                    )
                    .add_field(
                        name="Steps Taken",
                        value=self.steps.value,
                        inline=False,
                    )
                    .add_field(
                        name="Result",
                        value=self.result.value,
                        inline=False,
                    )
                )
            )


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

    # @button("ℹ")
    # async def support_server(
    #     self, menu: ErrorMenu, raw_reaction_event: RawReactionActionEvent
    # ) -> None:
    #     pass

    # @button("⚠")
    # async def on_info(self, menu: ErrorMenu, raw_reaction_event: RawReactionActionEvent) -> None:
    #     await payload.response.send_modal(
    #         ErrorSupportModal(self.error, cast(CustomContext, self.ctx))
    #     )


class ErrorLogging(commands.Cog):
    """Logs errors (and successes) to the database."""

    def __init__(self, bot: CustomBot):
        self.bot = bot

    @commands.Cog.listener("on_context_creation")
    async def append_command_document(self, ctx: commands.Context[Any]) -> None:
        custom_ctx: CustomContext = cast(CustomContext, ctx)
        custom_ctx["command_document"] = (
            await custom_ctx.bot.get_command_document(custom_ctx.command)
            if custom_ctx.command is not None
            else None
        )

    @commands.Cog.listener("on_command")
    async def log_command_uses(self, ctx: CustomContext) -> None:
        if ctx.command is not None:
            await ctx["command_document"].update_db({"$inc": {"stats.uses": 1}})

    @commands.Cog.listener("on_command_completion")
    async def log_command_completion(self, ctx: CustomContext) -> None:
        if ctx.command is not None:
            await ctx["command_document"].update_db({"$inc": {"stats.successes": 1}})

    @commands.Cog.listener("on_command_error")
    async def log_command_error(self, ctx: CustomContext, error: Exception) -> None:
        if ctx.command is not None:
            await ctx["command_document"].update_db({"$inc": {"stats.errors": 1}})


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
    await bot.add_cog(ErrorLogging(bot))
