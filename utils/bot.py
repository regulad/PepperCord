import discord
from discord.ext import commands

from utils.database import Document


class CustomContext(commands.Context):
    def __init__(self, **attrs):
        self.guild_doc = None
        self.user_doc = None
        super().__init__(**attrs)

    async def get_documents(self, database):
        """Gets documents from the database to be used later on. Must be called to use guild_doc or user_doc"""
        if self.guild:
            self.guild_doc = await Document.get_from_id(database["guild"], self.guild.id)
        if self.author:
            self.user_doc = await Document.get_from_id(database["user"], self.author.id)


class CustomBotBase(commands.bot.BotBase):
    def __init__(self, command_prefix, help_command, description, *, database, config, **options):
        self.database = database
        self.config = config
        super().__init__(command_prefix, help_command=help_command, description=description, **options)

    async def get_context(self, message, *, cls=CustomContext):
        r"""|coro|

        Returns the invocation context from the message.

        This is a more low-level counter-part for :meth:`.process_commands`
        to allow users more fine grained control over the processing.

        The returned context is not guaranteed to be a valid invocation
        context, :attr:`.Context.valid` must be checked to make sure it is.
        If the context is not valid then it is not a valid candidate to be
        invoked under :meth:`~.Bot.invoke`.

        Parameters
        -----------
        message: :class:`discord.Message`
            The message to get the invocation context from.
        cls
            The factory class that will be used to create the context.
            By default, this is :class:`.Context`. Should a custom
            class be provided, it must be similar enough to :class:`.Context`\'s
            interface.

        Returns
        --------
        :class:`.Context`
            The invocation context. The type of this can change via the
            ``cls`` parameter.
        """

        result = await super().get_context(message, cls=cls)
        if isinstance(result, CustomContext):
            await result.get_documents(self.database)
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
