import time

from discord.ext import commands
from utils.checks import has_permission_level


class moderation(
    commands.Cog,
    name="Moderation",
    description="Tools for moderators.",
):
    def __init__(self, bot):
        self.bot = bot

    async def cog_check(self, ctx):
        return (has_permission_level(ctx, 2)) and (commands.guild_only())

    @commands.command(
        name="purge",
        aliases=["purgemessages", "deletemessages"],
        brief="Delete a set amount of messages.",
        description="Delete a specified amount of messages in the current channel.",
    )
    async def purge(self, ctx, messages: int):
        await ctx.channel.purge(limit=messages + 1)


def setup(bot):
    bot.add_cog(moderation(bot))
