from discord.ext import commands

from .database import Document


class CustomContext(commands.Context):
    async def get_document(self, database):
        """Gets documents from the database to be used later on. Must be called to use guild_doc or user_doc"""
        if self.guild:
            self._guild_doc = await Document.get_document(database["guild"], {"_id": self.guild.id})
        if self.author:
            self._user_doc = await Document.get_document(database["user"], {"_id": self.author.id})

    @property
    def guild_doc(self):
        """Returns a coroutine that when awaited will return a Document instance for the guild."""
        return self._guild_doc

    @property
    def user_doc(self):
        """Returns a coroutine that when awaited will return a Document instance for the author."""
        return self._user_doc
