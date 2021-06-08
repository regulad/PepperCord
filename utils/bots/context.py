from typing import Optional

from discord.ext import commands

from utils.database import Document
from utils.audio import AudioPlayer


class CustomContext(commands.Context):
    def __init__(self, **attrs):
        self._guild_document: Optional[Document] = None
        self._author_document: Optional[Document] = None
        super().__init__(**attrs)

    @property
    def guild_document(self) -> Optional[Document]:
        return self._guild_document

    @property
    def author_document(self) -> Optional[Document]:
        return self._author_document

    @property
    def audio_player(self) -> Optional[AudioPlayer]:
        """Returns a AudioPlayer. If none exists, it will create one. Requires the voice_client to not be None."""

        if self.voice_client is None:
            return None
        else:
            return self.bot.get_audio_player(self.voice_client)

    async def get_documents(self):  # Eh. Does the job, but a rewrite wouldn't be a bad idea.
        """Gets documents from the database to be used later on. Must be called to use guild_doc or user_doc"""

        if self.guild:
            self._guild_document = await self.bot.get_document(self.guild)
        if self.author:
            self._author_document = await self.bot.get_document(self.author)
