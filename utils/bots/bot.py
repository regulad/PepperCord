from typing import Union, Optional, List, Deque
from collections import deque

import discord
from discord.ext import commands
from topgg import DBLClient, WebhookManager
from aiohttp import ClientSession
from asyncgTTS import ServiceAccount, AsyncGTTSSession

from utils.database import Document
from utils.audio import AudioPlayer
from .context import CustomContext


class CustomBotBase(commands.bot.BotBase):
    def __init__(
            self,
            command_prefix,
            help_command=commands.HelpCommand(),
            description=None,
            *,
            database,
            config,
            **options,
    ):
        self._database = database
        self._config = config

        self._audio_players: List[AudioPlayer] = []
        # TODO: Having audio players stored here prevents them from being garbage collected, causing a memory leak.
        # Ideally, they should be deleted once the VoiceClient ceases to exist.
        # A subclass of VoiceClient may be a good idea, but that isn't very well documented.

        self._guild_documents: Deque[Document] = deque(maxlen=350)
        self._user_documents: Deque[Document] = deque(maxlen=350)
        # I'm not sure if it's an issue to have too many documents in the cache. It likely is.

        # This block of code is kinda stupid.
        self.service_account: Optional[ServiceAccount] = None
        self.gtts_client_session: Optional[ClientSession] = None
        self.async_gtts_session: Optional[AsyncGTTSSession] = None
        self.topggpy: Optional[DBLClient] = None
        self.topgg_webhook: Optional[WebhookManager] = None

        super().__init__(command_prefix, help_command=help_command, description=description, **options)

    @property
    def database(self):
        return self._database

    @property
    def config(self) -> dict:
        return self._config

    @property
    def music_players(self) -> list:
        return self._audio_players

    def get_audio_player(self, voice_client: discord.VoiceClient):
        """Gets or creates audio player from VoiceClient."""

        for player in self.music_players:
            if player.voice_client == voice_client:
                return player
        else:
            music_player = AudioPlayer(voice_client)
            self.music_players.append(music_player)
            return music_player

    async def get_guild_document(self, model: discord.Guild) -> Document:  # This gets called 3 times each message.
        """Returns a cached document, or a new one if necessary."""

        for document in self._guild_documents:
            if document["_id"] == model.id:
                to_return: Document = document
                self._guild_documents.remove(to_return)
                self._guild_documents.append(to_return)
                break
        else:
            to_return: Document = await Document.get_document(self.database["guild"], {"_id": model.id})
            self._guild_documents.append(to_return)

        return to_return

    async def get_user_document(self, model: Union[discord.Member, discord.User]) -> Document:  # This gets called 2 times.
        """Returns a cached document, or a new one if necessary."""

        for document in self._user_documents:
            if document["_id"] == model.id:
                to_return: Document = document
                self._user_documents.remove(to_return)
                self._user_documents.append(to_return)
                break
        else:
            to_return: Document = await Document.get_document(self.database["user"], {"_id": model.id})
            self._user_documents.append(to_return)

        return to_return

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
