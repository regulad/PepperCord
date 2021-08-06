from typing import Union, Optional, List

import discord
from discord.ext import commands
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
        # There doesn't seem to be an event dispatched when a VoiceClient is destroyed. Perhaps implement that?

        super().__init__(
            command_prefix,
            help_command=help_command,
            description=description,
            **options,
        )

    @property
    def config(self) -> dict:
        return self._config

    def get_audio_player(self, voice_client: discord.VoiceClient) -> AudioPlayer:
        """Gets or creates audio player from VoiceClient."""

        for player in self._audio_players:
            if player.voice_client == voice_client:
                return player
        else:
            music_player = AudioPlayer(voice_client)
            self._audio_players.append(music_player)
            return music_player

    async def get_command_document(self, command: commands.Command):
        """Gets a command's document from the database."""

        return await Document.get_document(
            self._database["commands"],
            {
                "name": command.name,
                "cog": command.cog_name,
                "parent": command.parent.name if command.parent is not None else None,
            },
        )

    async def get_guild_document(self, model: discord.Guild) -> Document:
        """Gets a guild's document from the database."""

        return await Document.get_document(self._database["guild"], {"_id": model.id})

    async def get_user_document(
        self, model: Union[discord.Member, discord.User]
    ) -> Document:
        """Gets a user's document from the database."""

        return await Document.get_document(self._database["user"], {"_id": model.id})

    async def get_context(self, message, *, cls=CustomContext):
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
