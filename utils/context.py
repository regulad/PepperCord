from discord.ext import commands

from .database import Document


class CustomContext(commands.Context):
    def __init__(self, *, collection, **attrs):
        self._collection = collection
        super().__init__(**attrs)

        # If the context is from a guild, fetch the guild's document from the database.
        if self.guild:
            self._document = Document.find_one_or_insert_document(self._collection, {"_id": self.guild.id})

    @property
    def document(self):
        """Returns a coroutine that """
        return self._document or None
