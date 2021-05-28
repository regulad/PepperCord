from discord.ext import commands


class SubcommandNotFound(commands.CommandNotFound):
    pass


class NotConfigured(commands.CommandNotFound):
    pass


class TooManyMembers(commands.CommandError):
    pass
