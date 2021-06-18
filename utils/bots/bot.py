from typing import Union, Optional, List

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

        # This block of code is kinda stupid.
        self.service_account: Optional[ServiceAccount] = None
        self.gtts_client_session: Optional[ClientSession] = None
        self.async_gtts_session: Optional[AsyncGTTSSession] = None
        self.topggpy: Optional[DBLClient] = None
        self.topgg_webhook: Optional[WebhookManager] = None

        super().__init__(command_prefix, help_command=help_command, description=description, **options)

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

    async def get_guild_document(self, model: discord.Guild) -> Document:
        """Get's a guild's document from the database."""

        return await Document.get_document(self._database["guild"], {"_id": model.id})

    async def get_user_document(self, model: Union[discord.Member, discord.User]) -> Document:
        """Get's a user's document from the database."""

        return await Document.get_document(self._database["user"], {"_id": model.id})

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


class CustomAutoShardedBot(CustomBotBase, discord.AutoShardedClient):
    pass


class CustomBot(CustomBotBase, discord.Client):
    pass


BOT_TYPES = Union[CustomBot, CustomAutoShardedBot]


__all__ = ["CustomBot", "CustomAutoShardedBot", "BOT_TYPES"]
