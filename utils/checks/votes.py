from discord.ext.commands import CheckFailure

from utils.bots import CustomContext


class NotVoted(CheckFailure):
    """Raised when the bot is capable of receiving votes and a user has executed a command that requires voting,
    but the user has not voted."""

    pass


async def is_a_voter(ctx: CustomContext):
    if ctx.bot.topgg_webhook is not None and len(ctx.author_document.get("votes", [])) == 0:
        raise NotVoted
    return True


__all__ = ["NotVoted", "is_a_voter"]
