from discord.ext import commands


class NotConfigured(commands.CommandNotFound):
    """Raised when a feature has not been configured in a guild."""

    pass


# Raise this, not RuntimeError, when a command can't do what was asked and the message is for the user:
# it's shown to them, but not reported to Sentry as a bug.
# It has no docstring on purpose. ErrorMenu shows an exception's docstring as a tip, and the message says it all.
class UserFacingError(commands.CommandError):
    pass


__all__ = ["NotConfigured", "UserFacingError"]
