from discord.ext import commands

from .database import Document


class CustomContext(commands.Context):
    def __init__(self, *, collection, **attrs):
        self._collection = collection
        super().__init__(**attrs)

    @property
    def document(self):
        """Returns a coroutine that when awaited will return a Document instance."""
        if self.guild:
            return Document.find_one_or_insert_document(self._collection, {"_id": self.guild.id})
