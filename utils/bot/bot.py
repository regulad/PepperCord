from typing import Union

import discord
import motor.motor_asyncio
from discord.ext import commands

from utils.music import MusicPlayer
from .context import CustomContext
from .documents import ModelDocument


class CustomBotBase(commands.bot.BotBase):
    def __init__(self, command_prefix, help_command, description=None, *, database, config, **options):
        self._database = database
        self._config = config

        self._music_players = []
        self._documents = []
        # TODO: Having these objects stored here prevents them from being garbage collected, causing a memory leak.

        super().__init__(command_prefix, help_command=help_command, description=description, **options)

    @property
    def database(self) -> motor.motor_asyncio.AsyncIOMotorDatabase:
        return self._database

    @property
    def config(self) -> dict:
        return self._config

    @property
    def music_players(self) -> list:
        return self._music_players

    @property
    def documents(self) -> list:
        return self._documents

    def get_music_player(self, voice_client: discord.VoiceClient):
        """Gets or creates music player from VoiceClient."""

        for player in self.music_players:
            if player.voice_client == voice_client:
                return player
        else:
            music_player = MusicPlayer(voice_client)
            self.music_players.append(music_player)
            return music_player

    async def get_document(self, model: Union[discord.Guild, discord.Member, discord.User]):
        """Returns a cached document, or a new one if necessary."""

        if isinstance(model, discord.Guild):
            collection = self.database["guild"]
        elif isinstance(model, (discord.Member, discord.User)):
            collection = self.database["user"]

        for document in self.documents:
            if document.model == model:
                return document
        else:
            document = await ModelDocument.get_from_model(collection, model)
            self.documents.append(document)
            return document

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
            await result.get_documents()
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
