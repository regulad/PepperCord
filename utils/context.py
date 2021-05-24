from discord.ext import commands


class CustomContext(commands.Context):
    def __init__(self, *, guild_doc, user_doc, **attrs):
        self._guild_doc = guild_doc
        self._user_doc = user_doc
        super().__init__(**attrs)

    @property
    def guild_doc(self):
        """Returns a coroutine that when awaited will return a Document instance for the guild."""
        return self._guild_doc

    @property
    def user_doc(self):
        """Returns a coroutine that when awaited will return a Document instance for the author."""
        return self._user_doc
