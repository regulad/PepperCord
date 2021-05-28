from discord.ext import commands


class LowPrivilege(commands.CheckFailure):
    pass


class Blacklisted(commands.CheckFailure):
    pass
