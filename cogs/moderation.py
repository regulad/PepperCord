from discord.ext import commands


class moderation(
    commands.Cog,
    name="Moderation & Administration",
    description="Tools for moderators and administrators.",
):
    def __init__(self, bot):
        self.bot = bot


def setup(bot):
    bot.add_cog(moderation(bot))
