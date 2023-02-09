from discord.ext import commands

from utils.bots import BOT_TYPES


class Cooldown(commands.Cog):
    """The cooldown system prevents abuse of the bots."""

    def __init__(self, bot):
        self.bot = bot

        self.cooldown: commands.CooldownMapping = (
            commands.CooldownMapping.from_cooldown(10, 6, commands.BucketType.user)
        )

    async def bot_check_once(self, ctx):
        # Cooldown
        bucket: commands.Cooldown = self.cooldown.get_bucket(ctx.message)
        retry_after: float = bucket.update_rate_limit()
        if retry_after:
            raise commands.CommandOnCooldown(bucket, retry_after, self.cooldown.type)
        else:
            return True


async def setup(bot: BOT_TYPES) -> None:
    await bot.add_cog(Cooldown(bot))
