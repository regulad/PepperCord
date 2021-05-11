from art import text2art
from discord.ext import commands


class textDecoration(commands.Cog, name="Art", description="Convert text into art using art from PyPI"):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(
        name="asciiArt",
        aliases=["ascii", "art"],
        brief="Turn any text into ascii art!",
        description="Turn text into ascii art using art from PyPI.",
        usage="<Text>",
    )
    async def asciiArt(self, ctx, *, text):
        art = text2art(text, font="rnd-medium")
        if (len(art) + 6) > 2000:
            await ctx.send(f"Art was {len(art) - 2000} characters over the limit. Try with a shorter word.")
        else:
            await ctx.send(f"```{art}```")


def setup(bot):
    bot.add_cog(textDecoration(bot))
