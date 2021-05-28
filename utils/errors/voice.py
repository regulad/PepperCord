from discord.ext import commands


class NotInVoiceChannel(commands.CheckFailure):
    pass


class NotAlone(commands.CheckFailure):
    pass
