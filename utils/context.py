from discord.ext import commands

from .database import Document


class CustomContext(commands.Context):
    def __init__(self, *, database, **attrs):
        self._database = database
        super().__init__(**attrs)

    @property
    def guild_doc(self):
        """Returns a coroutine that when awaited will return a Document instance for the guild."""
        if self.guild:
            return Document.find_one_or_insert_document(self._database["guild"], {"_id": self.guild.id})

    @property
    def user_doc(self):
        """Returns a coroutine that when awaited will return a Document instance for the author."""
        if self.author:
            return Document.find_one_or_insert_document(self._database["user"], {"_id": self.author.id})
