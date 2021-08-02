from discord.ext import commands


class NotConfigured(commands.CommandNotFound):
    """Raised when a feature has not been configured in a guild."""

    pass


__all__ = ["NotConfigured"]
