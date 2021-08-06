from typing import Optional, Dict, Any

from discord.ext import commands

from utils.database import Document
from utils.audio import AudioPlayer
from utils.localization import Locale


class CustomContext(commands.Context):
    def __init__(self, **attrs):
        self._guild_document: Optional[Document] = None
        self._author_document: Optional[Document] = None
        self._command_document: Optional[Document] = None
        self._custom_state: Dict[Any, Any] = {}
        super().__init__(**attrs)

    def __getitem__(self, item: Any) -> Any:
        return self._custom_state[item]

    def __setitem__(self, key: Any, value: Any) -> None:
        self._custom_state[key] = value

    def __delitem__(self, key: Any) -> None:
        del self._custom_state[key]

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
        """Returns a AudioPlayer. If none exist, it will create one. Requires the voice_client to not be None."""

        if self.voice_client is None:
            return None
        else:
            return self.bot.get_audio_player(self.voice_client)

    @property
    def locale(self) -> Locale:
        """Returns the context's locale. This may be customized in guilds."""

        if self.guild_document is not None:
            return Locale[self.guild_document.get("locale", "en_US")]
        else:
            return Locale.en_US

    async def get_documents(self) -> None:
        """Gets documents from the database to be used later on."""

        if self.command is not None:
            self._command_document = await self.bot.get_command_document(self.command)

        if self.guild is not None:
            self._guild_document = await self.bot.get_guild_document(self.guild)

        if self.author is not None:
            self._author_document = await self.bot.get_user_document(self.author)
