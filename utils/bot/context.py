from typing import Optional

from discord.ext import commands

from utils.database import Document
from utils.music import MusicPlayer


class MusicPlayerExists(Exception):
    pass


class NoVoiceClient(Exception):
    pass


class CustomContext(commands.Context):
    def __init__(self, **attrs):
        self._guild_doc = None
        self._user_doc = None
        super().__init__(**attrs)

    @property
    def guild_doc(self) -> Optional[Document]:
        return self._guild_doc

    @property
    def user_doc(self) -> Optional[Document]:
        return self._user_doc

    @property
    def music_player(self) -> Optional[MusicPlayer]:
        """Returns the active MusicPlayer, if one exists."""

        if self.voice_client is None:
            return self.voice_client

        for player in self.bot.music_players:
            if player.voice_client == self.voice_client:
                music_player = player
                break
        else:
            music_player = None

        return music_player

    def create_music_player(self):
        """Creates a MusicPlayer using the VoiceClient.
        If no VoiceClient exists, raise NoVoiceClient.
        If a MusicPlayer already exists, raise MusicPlayerExists."""

        if self.voice_client is None:
            raise NoVoiceClient()
        if self.music_player is not None:
            raise MusicPlayerExists()

        music_player = MusicPlayer(self.voice_client)
        self.bot.music_players.append(music_player)

    async def get_documents(self, database):
        """Gets documents from the database to be used later on. Must be called to use guild_doc or user_doc"""

        if self.guild:
            self._guild_doc = await Document.get_from_id(database["guild"], self.guild.id)
        if self.author:
            self._user_doc = await Document.get_from_id(database["user"], self.author.id)
