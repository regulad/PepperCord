from discord.ext import commands
from utils import errors


class BotCheck(commands.Cog, name="Bot Checks", description="Global bot checks."):
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
        # Blacklist
        if ctx.guild != None and ctx.guild_doc.setdefault("blacklisted", False):
            raise errors.Blacklisted()
        elif ctx.user_doc.setdefault("blacklisted", False):
            raise errors.Blacklisted()
        else:
            return True


def setup(bot):
    bot.add_cog(BotCheck(bot))