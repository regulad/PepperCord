from discord.ext import commands
from utils import errors


class ErrorHandling(commands.Cog, name="Error Handling", description="Listeners & commands for error handling."):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_command_error(self, ctx, e):
        await ctx.message.add_reaction(emoji="❌")
        if isinstance(e, (commands.CheckFailure, commands.CommandOnCooldown)) and await bot.is_owner(ctx.author):
            try:
                await ctx.reinvoke()
            except Exception as e:
                await ctx.send(f"During the attempt to reinvoke your command, another exception occured. See: ```{e}```")
        elif isinstance(e, errors.TooManyMembers):
            await ctx.send("This command doesn't work very well in large servers and has been disabled there. Sorry!")
        elif isinstance(e, errors.Blacklisted):
            await ctx.send("You have been blacklisted from utilizing this instance of the bot.")
        elif isinstance(e, commands.BotMissingPermissions):
            await ctx.send(f"I'm missing permissions I need to function. To re-invite me, see `{ctx.prefix}invite`.")
        elif isinstance(e, commands.NoPrivateMessage):
            await ctx.send(f"This commands can only be executed in a server.")
        elif isinstance(e, commands.NSFWChannelRequired):
            await ctx.send("No horny! A NSFW channel is required to execute this command.")
        elif isinstance(e, commands.CommandOnCooldown):
            await ctx.send(
                f"Slow the brakes, speed racer! We don't want any rate limiting... Try executing your command again in `{round(e.retry_after, 1)}` seconds."
            )
        elif isinstance(e, commands.UserInputError):
            await ctx.send(f"Command is valid, but input is invalid. Try `{ctx.prefix}help {ctx.command}`.")
        elif isinstance(e, (commands.MissingPermissions, errors.LowPrivilege)):
            await ctx.send("You are missing required permissions.")
        elif isinstance(e, commands.CheckFailure):
            await ctx.send("You cannot run this command.")
        elif isinstance(e, errors.SubcommandNotFound):
            await ctx.send(f"You need to specify a subcommand. Try `{ctx.prefix}help`.")
        elif isinstance(e, errors.NotConfigured):
            await ctx.send("This command must be configured first. Ask an admin.")
        elif isinstance(e, commands.CommandNotFound):
            await ctx.send(f"{e}. Try `{ctx.prefix}help`.")
        else:
            await ctx.send(
                f"Something went very wrong while processing your command. This can be caused by bad arguments or something worse. Execption: ```{e}``` You can contact support with `{ctx.prefix}support`."
            )


def setup(bot):
    bot.add_cog(ErrorHandling(bot))
