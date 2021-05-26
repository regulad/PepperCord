from discord.ext import commands

from .database import Document


class CustomContext(commands.Context):
    async def get_documents(self, database):
        """Gets documents from the database to be used later on. Must be called to use guild_doc or user_doc"""
        if self.guild:
            self.guild_doc = await Document.get_from_id(database["guild"], self.guild.id)
        if self.author:
            self.user_doc = await Document.get_from_id(database["user"], self.author.id)
