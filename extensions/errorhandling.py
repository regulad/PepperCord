import asyncio
from typing import Optional

import discord
from discord.ext import commands, menus
from evb import LibraryException as EvbException
from asyncgTTS import LibraryException as TtsException

from extensions.starboard import AlreadyPinned
from extensions.text_to_speech import VoiceDoesNotExist
from utils import checks, bots, attachments

known_errors = {
    checks.NotSharded: "This bot is not sharded. This command can only run if the bot is sharded.",
    asyncio.QueueFull: "The queue is full. Please wait for this track to finish before you play the next song.",
    checks.NotInVoiceChannel: "You must be in a voice channel to execute this command.",
    commands.UserInputError: "You entered a bad argument.",
    AlreadyPinned: "This message is already pinned to the starboard.",
    commands.NSFWChannelRequired: "This command displays explicit content. "
    "You can only use it in channels marked as NSFW.",
    commands.CommandOnCooldown: "You'll need to wait before you can execute this command again.",
    commands.NotOwner: "Only the bot's owner may execute this command.",
    checks.LowPrivilege: "You are not authorized to run this command. Ask a server administrator if you believe "
    "this is an error.",
    bots.NotConfigured: "This feature must be configured before use. Ask a server administrator.",
    VoiceDoesNotExist: "This voice doesn't exist. Check voices.",
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


def find_error(error) -> Optional[str]:
    for known_error, response in known_errors.items():
        if isinstance(error, known_error):
            return response
    else:
        return None


class ErrorMenu(menus.Menu):
    def __init__(self, error: Exception):
        if isinstance(error, commands.CommandInvokeError):
            error = error.original

        self.error = error

        super().__init__()

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

        return await ctx.send(embed=embed)

    @menus.button("🛑")
    async def on_stop(self, payload):
        await self.message.delete()
        self.stop()


class ErrorLogging(commands.Cog):
    """Logs errors (and successes) to the database."""

    def __init__(self, bot: bots.BOT_TYPES):
        self.bot = bot

    @commands.Cog.listener("on_command")
    async def log_command_uses(self, ctx: bots.CustomContext) -> None:
        if ctx.command is not None:
            await ctx.command_document.update_db({"$inc": {"stats.uses": 1}})

    @commands.Cog.listener("on_command_completion")
    async def log_command_completion(self, ctx: bots.CustomContext) -> None:
        if ctx.command is not None:
            await ctx.command_document.update_db({"$inc": {"stats.successes": 1}})

    @commands.Cog.listener("on_command_error")
    async def log_command_error(
        self, ctx: bots.CustomContext, error: Exception
    ) -> None:
        if ctx.command is not None:
            await ctx.command_document.update_db({"$inc": {"stats.errors": 1}})


class ErrorHandling(commands.Cog):
    """Handles raised errors."""

    def __init__(self, bot: bots.BOT_TYPES):
        self.bot = bot

    @commands.Cog.listener("on_command_completion")
    async def affirm_success(self, ctx: bots.CustomContext) -> None:
        await ctx.message.add_reaction("✅")

    @commands.Cog.listener("on_command_error")
    async def affirm_error(self, ctx: bots.CustomContext, error: Exception) -> None:
        await ctx.message.add_reaction("‼️")
        if ctx.command is not None:
            await ErrorMenu(error).start(ctx)

    @commands.Cog.listener("on_command_error")
    async def attempt_to_reinvoke(
        self, ctx: bots.CustomContext, error: Exception
    ) -> None:
        if ctx.command is not None:
            if await ctx.bot.is_owner(ctx.author):
                await ctx.message.add_reaction("🔁")

                if ctx.valid and isinstance(
                    error, (commands.CommandOnCooldown, commands.CheckFailure)
                ):
                    await ctx.reinvoke()
                else:
                    await ctx.message.add_reaction("❌")

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