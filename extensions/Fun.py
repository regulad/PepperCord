# TODO: Remove this in favor of per-guild commands.

from discord.ext import commands


class Fun(commands.Cog):
    """Fun commands to try."""

    def __init__(self, bot):
        self.bot = bot

    @commands.group(
        invoke_without_command=True,
        case_insensitive=True,
        name="wavedash",
        aliases=["wave", "dash"],
        brief="Bounce, bounce, bounce...",
        description="Bounce, bounce, bounce...",
    )
    async def wavedash(self, ctx):
        await ctx.send(
            "<a:bad:839565043859193876><a:bounce1:839557305321259078><a:bad2:839565044249657414><a:bounce3:839557305074188318><a:bad4:839565044127760455><a:bounce5:839557305062391828>"
            * 2
        )

    @wavedash.command(name="Badeline", aliases=["bad", "b"])
    async def badeline(self, ctx):
        await ctx.send(
            "<a:bad:839565043859193876><a:bad1:839565043866796053><a:bad2:839565044249657414><a:bad3:839565043913064468><a:bad4:839565044127760455><a:bad5:839565043599278111>"
            * 2
        )

    @wavedash.command(name="Madeline", aliases=["mad", "m"])
    async def both(self, ctx):
        await ctx.send(
            "<a:bounce0:839557305120063508><a:bounce1:839557305321259078><a:bounce2:839557305053741056><a:bounce3:839557305074188318><a:bounce4:839557305058197546><a:bounce5:839557305062391828>"
            * 2
        )


def setup(bot):
    bot.add_cog(Fun(bot))
