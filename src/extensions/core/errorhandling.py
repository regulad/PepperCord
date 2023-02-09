import asyncio
from logging import getLogger
from typing import Optional, cast, Type

import discord
from asyncgTTS import LibraryException as TtsException
from discord import Interaction, ButtonStyle, Embed, TextStyle
from discord.app_commands import CommandInvokeError as AppCommandInvokeError
from discord.ext import commands, menus
from discord.ext.commands import CommandNotFound
from discord.ext.menus import button
from discord.ui import Modal, TextInput
from evb import LibraryException as EvbException

from utils import checks, bots, attachments
from utils.bots import CustomContext


logger = getLogger(__name__)

known_errors: dict[Type, str] = {
    checks.CantCreateAudioClient: "The bot failed to find a way to make an audio player. Are you in a voice channel?",
    checks.NotSharded: "This bot is not sharded. This command can only run if the bot is sharded.",
    asyncio.QueueFull: "The queue is full. Please wait for this track to finish before you play the next song.",
    commands.UserInputError: "You entered a bad argument.",
    commands.NSFWChannelRequired: "This command displays explicit content. "
    "You can only use it in channels marked as NSFW.",
    commands.CommandOnCooldown: "You'll need to wait before you can execute this command again.",
    commands.NotOwner: "Only the bot's owner may execute this command.",
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
    intent = TextInput(
        label="What were you trying to do?",
        placeholder="Example: I was trying to play a song.",
        style=TextStyle.long,
    )
    steps = TextInput(
        label="What steps did you take to do this?",
        placeholder="Example: I typed ?play song and clicked send.",
        style=TextStyle.long,
    )
    result = TextInput(
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
                    "Please use [the support server (click here)](https://redirector.regulad.xyz/discord) "
                    "for any additional help or to self-diagnose your problem."
                )
            ),
            ephemeral=True,
        )
        # send error
        for owner in self.ctx.bot.effective_owners:
            await owner.send(
                embed=(
                    Embed(
                        title=f"**{self.ctx.author.display_name}** (`{self.ctx.author.id}`) encountered an error in "
                        f"**{self.ctx.guild.name}** (`{self.ctx.guild.id}`) "
                        f"with the command `{self.ctx.command}`.",
                        description=f"Type: **{self.error.__class__.__name__}**\n```{str(self.error)}```"
                        if len(str(self.error)) > 0
                        else f"Type: **{self.error.__class__.__name__}**",
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


class ErrorMenu(menus.ViewMenu):
    def __init__(self, error: Exception, **kwargs):
        if isinstance(error, commands.HybridCommandError):
            error = error.original

        if isinstance(error, (commands.CommandInvokeError, AppCommandInvokeError)):
            error = error.original

        self.error = error

        super().__init__(auto_defer=False, **kwargs)

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

        return await channel.send(embed=embed, **self._get_kwargs())

    @button(
        "ℹ",
        label="Support Server",
        style=ButtonStyle.url,
        url="https://redirector.regulad.xyz/discord",
    )
    async def support_server(self, button: discord.ui.Button, interaction: Interaction):
        pass

    @button("⚠", label="Report Error", style=ButtonStyle.red)
    async def on_info(self, payload: Interaction):
        await payload.response.send_modal(
            ErrorSupportModal(self.error, cast(CustomContext, self.ctx))
        )


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

    @commands.Cog.listener("on_command_completion")
    async def affirm_working(self, ctx: bots.CustomContext) -> None:
        if ctx.interaction is None:
            await ctx.message.add_reaction("✅")

    @commands.Cog.listener("on_command_error")
    async def soft_affirm_error(
        self, ctx: bots.CustomContext, error: Exception
    ) -> None:
        if ctx.interaction is None and not isinstance(error, CommandNotFound):
            await ctx.message.add_reaction("❌")

    @commands.Cog.listener("on_command_error")
    async def affirm_error(self, ctx: bots.CustomContext, error: Exception) -> None:
        if ctx.command is not None and not isinstance(error, commands.DisabledCommand):
            await ErrorMenu(error).start(ctx, ephemeral=ctx.interaction is not None)

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


async def setup(bot: bots.BOT_TYPES) -> None:
    await bot.add_cog(ErrorHandling(bot))
    await bot.add_cog(ErrorLogging(bot))
