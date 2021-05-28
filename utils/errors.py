from discord.ext import commands


class SubcommandNotFound(commands.CommandNotFound):
    pass


class NotConfigured(commands.CommandNotFound):
    pass


class Blacklisted(commands.CheckFailure):
    pass


class TooManyMembers(commands.CommandError):
    pass


class LowPrivilege(commands.CheckFailure):
    pass


class AlreadyPinned(Exception):
    pass


class NotSharded(Exception):
    pass


class NotInVoiceChannel(commands.CheckFailure):
    pass


class NotAlone(commands.CheckFailure):
    pass
