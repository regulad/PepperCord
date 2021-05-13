import base64
import time

import discord
import nekos
from art import text2art
from discord.ext import commands
from discord.ext.commands.cooldowns import BucketType
from mcstatus import MinecraftServer
from pycoingecko import CoinGeckoAPI
from utils.errors import SubcommandNotFound


class explorer(
    commands.Cog,
    name="Fun",
    description="Gets random information from all over the internet and beyond.",
):
    def __init__(self, bot):
        self.bot = bot

    @commands.group(
        invoke_without_command=True,
        case_insensitive=True,
        name="wavedash",
        aliases=["wave", "dash"],
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

    @commands.group(
        invoke_without_command=True,
        case_insensitive=True,
        name="crypto",
        aliases=["blockchain"],
        brief="Looks up data on the crypto blockchain.",
        description="Finds cryptocurrency blockchain information using CoinGecko.",
    )
    @commands.cooldown(100, 55, BucketType.default)
    async def crypto(self, ctx):
        raise SubcommandNotFound()

    @crypto.command(
        name="status",
        aliases=["ping"],
        brief="Gets status from API.",
        description="Gets status from the CoinGeckoAPI.",
    )
    async def ping(self, ctx):
        await ctx.send(CoinGeckoAPI().ping()["gecko_says"])

    @crypto.command(
        name="price",
        aliases=["value"],
        brief="Finds price of coin.",
        description="Finds price of coin using CoinGecko.",
        usage="[Coin] [Currency]",
    )
    async def price(self, ctx, coin: str = "ethereum", currency: str = "usd"):
        await ctx.send(
            f"{CoinGeckoAPI().get_price(ids=coin, vs_currencies=currency.lower())[coin.lower()][currency.lower()]} {currency.upper()}"
        )

    @commands.group(
        invoke_without_command=True,
        case_insensitive=True,
        name="neko",
        aliases=["nekos"],
        description="Get data from https//nekos.life/api/v2/",
        brief="Get data from nekos.life",
    )
    async def neko(self, ctx):
        raise SubcommandNotFound()

    @neko.command(name="eightball", aliases=["8ball"])
    async def eightball(self, ctx):
        eightball = nekos.eightball()
        embed = discord.Embed(colour=discord.Colour.blurple(), title=eightball.text).set_image(url=eightball.image)
        await ctx.send(embed=embed)

    @neko.command(
        name="img",
        usage="[https://github.com/Nekos-life/nekos.py/blob/master/nekos/nekos.py#L17#L27]",
    )
    @commands.is_nsfw()
    async def img(self, ctx, *, target: str = "hentai"):
        try:
            await ctx.send(nekos.img(target))
        except nekos.errors.InvalidArgument:
            await ctx.send("Couldn't find that type of image.")

    @neko.command(name="owoify")
    async def owoify(self, ctx, *, text: str = "OwO"):
        await ctx.send(nekos.owoify(text))

    @neko.command(name="cat")
    async def cat(self, ctx):
        await ctx.send(nekos.cat())

    @neko.command(name="textcat")
    async def textcat(self, ctx):
        await ctx.send(nekos.textcat())

    @neko.command(name="why")
    async def why(self, ctx):
        await ctx.send(nekos.why())

    @neko.command(name="fact")
    async def fact(self, ctx):
        await ctx.send(nekos.fact())

    @commands.command(
        name="minecraft",
        aliases=["mcstatus"],
        description="Gets Minecraft Server status using mcstatus.",
        brief="Gets Minecraft Server.",
    )
    async def minecraft(self, ctx, *, server: str = "play.regulad.xyz"):
        serverLookup = MinecraftServer.lookup(server)
        try:
            status = await serverLookup.async_status()
        except:
            await ctx.send("Couldn't get information from the server. Is it online?")
        else:
            embed = (
                discord.Embed(colour=discord.Colour.dark_gold(), title=server)
                .add_field(name="Ping:", value=f"{status.latency}ms")
                .add_field(name="Players:", value=f"{status.players.online}/{status.players.max}")
                .add_field(name="Version:", value=f"{status.version.name}, (ver. {status.version.protocol})", inline=False)
            )
            await ctx.send(embed=embed)


def setup(bot):
    bot.add_cog(explorer(bot))
