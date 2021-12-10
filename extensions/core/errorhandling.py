import asyncio
from typing import Optional, cast

import discord
from asyncgTTS import LibraryException as TtsException
from discord.ext import commands, menus
from evb import LibraryException as EvbException

from utils import checks, bots, attachments
from utils.bots import CustomContext

known_errors = {
    checks.NotSharded: "This bot is not sharded. This command can only run if the bot is sharded.",
    asyncio.QueueFull: "The queue is full. Please wait for this track to finish before you play the next song.",
    checks.NotInVoiceChannel: "You must be in a voice channel to execute this command.",
    commands.UserInputError: "You entered a bad argument.",
    commands.NSFWChannelRequired: "This command displays explicit content. "
    "You can only use it in channels marked as NSFW.",
    commands.CommandOnCooldown: "You'll need to wait before you can execute this command again.",
    commands.NotOwner: "Only the bot's owner may execute this command.",
    checks.LowPrivilege: "You are not authorized to run this command. Ask a server administrator if you believe "
    "this is an error.",
    bots.NotConfigured: "This feature must be configured before use. Ask a server administrator.",
    commands.BotMissingPermissions: "The bot was unable to perform the action requested, "
    "since it is missing permissions required to do so. Try re-inviting the bot.",
    commands.CheckFailure: "A check failed.",
    attachments.WrongMedia: "The media that was found could not be used for the desired action.",
    attachments.NoMedia: "Could not find media to use.",
    EvbException: "Something went wrong while trying to use EditVideoBot.",
    TtsException: "Something went wrong while trying to use text_to_speech.",
    checks.Blacklisted: "You have been blacklisted from using this bot.",
    attachments.MediaTooLong: "You can't download media this long.",
    attachments.MediaTooLarge: "This media is too large to be uploaded to discord.",
}

try:
    from extensions.features.starboard import AlreadyPinned
except ImportError:
    AlreadyPinned = object
else:
    known_errors[AlreadyPinned] = "This message is already pinned to the starboard."

try:
    from external.text_to_speech import VoiceDoesNotExist
except ImportError:  # it might not exist if it's not configured
    VoiceDoesNotExist = object
else:
    known_errors[VoiceDoesNotExist] = "This voice doesn't exist. Check voices."


def find_error(error) -> Optional[str]:
    for known_error, response in known_errors.items():
        if isinstance(error, known_error):
            return response
    else:
        return None


class ErrorMenu(menus.ViewMenu):
    def __init__(self, error: Exception, **kwargs):
        if isinstance(error, commands.CommandInvokeError):
            error = error.original

        self.error = error

        super().__init__(**kwargs)

    async def send_initial_message(self, ctx, channel):
        error_response = find_error(self.error)

        embed = discord.Embed(
            colour=discord.Colour.red(), title="An error has occurred."
        )

        if len(str(self.error)) > 0:
            embed.add_field(
                name=f"Type: {self.error.__class__.__name__}",
                value=f"```{str(self.error)}```",
            )
        else:
            embed.description = f"**Type: {self.error.__class__.__name__}**"

        if error_response is not None:
            embed.set_footer(text=f"Tip: {error_response}")

        return await ctx.send(embed=embed, ephemeral=True)


class ErrorLogging(commands.Cog):
    """Logs errors (and successes) to the database."""

    def __init__(self, bot: bots.BOT_TYPES):
        self.bot = bot

    @commands.Cog.listener("on_context_creation")
    async def append_command_document(self, ctx: commands.Context):
        ctx: CustomContext = cast(CustomContext, ctx)
        ctx["command_document"] = (
            await ctx.bot.get_command_document(ctx.command)
            if ctx.command is not None
            else None
        )

    @commands.Cog.listener("on_command")
    async def log_command_uses(self, ctx: bots.CustomContext) -> None:
        if ctx.command is not None:
            await ctx["command_document"].update_db({"$inc": {"stats.uses": 1}})

    @commands.Cog.listener("on_command_completion")
    async def log_command_completion(self, ctx: bots.CustomContext) -> None:
        if ctx.command is not None:
            await ctx["command_document"].update_db({"$inc": {"stats.successes": 1}})

    @commands.Cog.listener("on_command_error")
    async def log_command_error(
        self, ctx: bots.CustomContext, error: Exception
    ) -> None:
        if ctx.command is not None:
            await ctx["command_document"].update_db({"$inc": {"stats.errors": 1}})


class ErrorHandling(commands.Cog):
    """Handles raised errors."""

    def __init__(self, bot: bots.BOT_TYPES):
        self.bot = bot

    @commands.Cog.listener("on_command_error")
    async def affirm_error(self, ctx: bots.CustomContext, error: Exception) -> None:
        if ctx.command is not None and ctx.interaction is not None:
            await ErrorMenu(error).start(ctx)

    @commands.Cog.listener("on_command_error")
    async def attempt_to_reinvoke(
        self, ctx: bots.CustomContext, error: Exception
    ) -> None:
        if ctx.command is not None:
            if await ctx.bot.is_owner(ctx.author):
                if ctx.valid and isinstance(
                    error, (commands.CommandOnCooldown, commands.CheckFailure)
                ):
                    await ctx.reinvoke()

    @commands.Cog.listener("on_command_error")
    async def determine_if_critical(
        self, ctx: bots.CustomContext, error: Exception
    ) -> None:
        critical: bool = not isinstance(
            error,
            (
                commands.UserInputError,
                commands.CommandOnCooldown,
                commands.CheckFailure,
                commands.CommandInvokeError,
                commands.CommandNotFound,
            ),
        )

        if critical:
            ctx.bot.dispatch(
                "critical_error", ctx, error
            )  # I'll do something with this later, maybe a support system?


def setup(bot: bots.BOT_TYPES):
    bot.add_cog(ErrorHandling(bot))
    bot.add_cog(ErrorLogging(bot))
