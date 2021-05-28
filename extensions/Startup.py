from discord.ext import commands


class Startup(commands.Cog):
    """Things to do on startup."""

    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        print(f"Logged in as {self.bot.user.name}#{self.bot.user.discriminator} ({self.bot.user.id})")


def setup(bot):
    bot.add_cog(Startup(bot))
