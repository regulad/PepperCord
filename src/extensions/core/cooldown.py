from typing import Any, cast
from discord.ext import commands

from utils.bots.bot import CustomBot


class Cooldown(commands.Cog):
    """The cooldown system prevents abuse of the bots."""

    def __init__(self, bot: CustomBot) -> None:
        self.bot = bot

        self.cooldown: commands.CooldownMapping[Any] = (
            commands.CooldownMapping.from_cooldown(10, 6, commands.BucketType.user)
        )

    async def bot_check_once(self, ctx: commands.Context[Any]) -> bool:  # type: ignore[override]  # it is compatible
        # Cooldown
        bucket = cast(
            commands.Cooldown, self.cooldown.get_bucket(ctx.message)
        )  # it should always be there
        retry_after = bucket.update_rate_limit()
        if isinstance(retry_after, float):
            raise commands.CommandOnCooldown(bucket, retry_after, self.cooldown.type)  # type: ignore[arg-type]  # it does work
        else:
            return True


async def setup(bot: CustomBot) -> None:
    await bot.add_cog(Cooldown(bot))
