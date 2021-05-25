import discord
from discord.ext import commands

from .context import CustomContext


class CustomBotBase(commands.bot.BotBase):
    def __init__(self, command_prefix, help_command, description, *, database, config, **options):
        self._database = database
        self._config = config
        super().__init__(command_prefix, help_command=help_command, description=description, **options)

    @property
    def database(self):
        return self._database

    @property
    def config(self):
        return self._config

    async def get_context(self, message, *, cls=CustomContext):
        result = await super().get_context(message, cls=cls)
        if isinstance(result, CustomContext):
            await result.get_document(self._database)
        return result

    async def invoke(self, ctx):
        """|coro|

        Invokes the command given under the invocation context and
        handles all the internal event dispatch mechanisms.

        Parameters
        -----------
        ctx: :class:`.Context`
            The invocation context to invoke.
        """
        if ctx.command is not None:
            self.dispatch("command", ctx)
            try:
                if await self.can_run(ctx, call_once=True):
                    async with ctx.typing():
                        await ctx.command.invoke(ctx)
                        await ctx.message.add_reaction(emoji="✅")
                else:
                    raise commands.errors.CheckFailure("The global check once functions failed.")
            except commands.errors.CommandError as exc:
                await ctx.command.dispatch_error(ctx, exc)
            else:
                self.dispatch("command_completion", ctx)
        elif ctx.invoked_with:
            exc = commands.errors.CommandNotFound('Command "{}" is not found'.format(ctx.invoked_with))
            self.dispatch("command_error", ctx, exc)


class CustomAutoShardedBot(CustomBotBase, discord.AutoShardedClient):
    pass


class CustomBot(CustomBotBase, discord.Client):
    pass
