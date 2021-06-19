from typing import Optional

from discord.ext import commands

from utils.database import Document
from utils.audio import AudioPlayer


class CustomContext(commands.Context):
    def __init__(self, **attrs):
        self._guild_document: Optional[Document] = None
        self._author_document: Optional[Document] = None
        self._command_document: Optional[Document] = None
        super().__init__(**attrs)

    @property
    def guild_document(self) -> Optional[Document]:
        return self._guild_document

    @property
    def author_document(self) -> Optional[Document]:
        return self._author_document

    @property
    def command_document(self) -> Optional[Document]:
        return self._command_document

    @property
    def audio_player(self) -> Optional[AudioPlayer]:
        """Returns a AudioPlayer. If none exists, it will create one. Requires the voice_client to not be None."""

        if self.voice_client is None:
            return None
        else:
            return self.bot.get_audio_player(self.voice_client)

    async def get_documents(self) -> None:
        """Gets documents from the database to be used later on."""

        if self.command is not None:
            self._command_document: Document = await self.bot.get_command_document(self.command)

        if self.guild is not None:
            self._guild_document: Document = await self.bot.get_guild_document(self.guild)

        if self.author is not None:
            self._author_document: Document = await self.bot.get_user_document(self.author)
