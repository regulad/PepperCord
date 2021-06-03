import asyncio

import discord
from discord.ext import commands, menus

from extensions.Starboard import AlreadyPinned
from utils import checks, bots

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

    commands.BotMissingPermissions: "The bot was unable to perform the action requested, "
                                    "since it is missing permissions required to do so. Try re-inviting the bot.",

    commands.CheckFailure: "A check failed.",
}


def find_error(error):
    try:
        return known_errors[error.__class__]
    except KeyError:
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
                name=f"Type: {self.error.__class__.__name__}", value=f"```{str(self.error)}```"
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


class ErrorHandling(commands.Cog):
    """Handles raised errors."""

    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        safe_reinvoke = isinstance(error, (commands.CommandOnCooldown, commands.CheckFailure))
        await ctx.message.add_reaction("‼️")
        if await ctx.bot.is_owner(ctx.author) and safe_reinvoke:
            await ctx.message.add_reaction("🔁")
            await ctx.reinvoke()
        else:
            await ErrorMenu(error).start(ctx)


def setup(bot):
    bot.add_cog(ErrorHandling(bot))
