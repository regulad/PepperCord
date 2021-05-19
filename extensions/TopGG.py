import dbl
import instances
from discord.ext import commands


class TopGG(commands.Cog, name="Top.gg", description="Get perks for upvoting the bot on Top.gg, like reduced cooldowns."):
    def __init__(self, bot):
        self.bot = bot
        self.token = instances.config_instance["topgg"]["token"]
        self.dblpy = dbl.DBLClient(bot=self.bot, token=self.token, autopost=True)


def setup(bot):
    bot.add_cog(TopGG(bot))
