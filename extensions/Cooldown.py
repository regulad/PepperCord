from discord.ext import commands


class Cooldown(commands.Cog):
    """The cooldown system prevents abuse of the bots."""

    def __init__(self, bot):
        self.bot = bot

        self.cooldown = commands.CooldownMapping.from_cooldown(
            self.bot.config["discord"]["commands"]["cooldown"]["rate"],
            self.bot.config["discord"]["commands"]["cooldown"]["per"],
            commands.BucketType.user,
        )

    async def bot_check_once(self, ctx):
        # Cooldown
        bucket = self.cooldown.get_bucket(ctx.message)
        retry_after = bucket.update_rate_limit()
        if retry_after:
            raise commands.CommandOnCooldown(bucket, retry_after)
        else:
            return True


def setup(bot):
    bot.add_cog(Cooldown(bot))
