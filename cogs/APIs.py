import base64
from io import BytesIO

import aiohttp
import discord
import nekos
from discord.ext import commands
from mcstatus import MinecraftServer
from utils import errors


class APIs(
    commands.Cog,
    name="APIs",
    description="Gets random information from all over the internet and beyond.",
):
    def __init__(self, bot):
        self.bot = bot

    @commands.group(
        invoke_without_command=True,
        case_insensitive=True,
        name="neko",
        aliases=["nekos"],
        description="Get data from https//nekos.life/api/v2/",
        brief="Get data from nekos.life",
    )
    async def neko(self, ctx):
        raise errors.SubcommandNotFound()

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

    @commands.group(
        invoke_without_command=True,
        case_insensitive=True,
        name="minecraft",
        aliases=["mc"],
        description="Gets all sorts of data for Minecraft.",
        brief="Get Minecraft Data.",
    )
    async def minecraft(self, ctx):
        raise errors.SubcommandNotFound()

    @minecraft.command(
        name="server",
        aliases=["status"],
        description="Gets Minecraft Server status using mcstatus.",
        brief="Gets Minecraft Server.",
        usage="[Server]",
    )
    async def server(self, ctx, *, server: str = "play.regulad.xyz"):
        serverLookup = MinecraftServer.lookup(server)
        try:
            status = await serverLookup.async_status()
            decoded = BytesIO(base64.b64decode(status.favicon.replace("data:image/png;base64,", "")))
        except:
            await ctx.send("Couldn't get information from the server. Is it online?")
        else:
            embed = (
                discord.Embed(colour=discord.Colour.dark_gold(), title=server)
                .add_field(name="Ping:", value=f"{status.latency}ms")
                .add_field(name="Players:", value=f"{status.players.online}/{status.players.max}")
                .add_field(name="Version:", value=f"{status.version.name}, (ver. {status.version.protocol})", inline=False)
                .set_thumbnail(url="attachment://favicon.png")
            )
            file = discord.File(decoded, filename="favicon.png")
            await ctx.send(embed=embed, file=file)

    @minecraft.command(
        name="player",
        aliases=["user"],
        description="Get data on a Minecraft user.",
        brief="Gets Minecraft player.",
        usage="<Player Username>",
    )
    async def player(self, ctx, *, player: str):
        async with aiohttp.ClientSession() as client:
            async with client.get(f"https://api.mojang.com/users/profiles/minecraft/{player}") as request:
                result = await request.json()
                uuid = result["id"]
                name = result["name"]
        embed = discord.Embed(title=name).set_image(url=f"https://crafatar.com/renders/body/{uuid}?overlay")
        await ctx.send(embed=embed)

    @commands.command(name="bored", description="Do something, stop being bored!", brief="Anti-boredom.")
    async def bored(self, ctx):
        async with aiohttp.ClientSession() as client:
            async with client.get("https://www.boredapi.com/api/activity/") as request:
                result = await request.json()
        embed = discord.Embed(title=result["type"], description=result["activity"])
        await ctx.send(embed=embed)

    @commands.command(name="quote", description="Get inspired from a random quote.", brief="Get inspired!")
    async def quote(self, ctx):
        async with aiohttp.ClientSession() as client:
            async with client.get("https://api.forismatic.com/api/1.0/?method=getQuote&format=json&lang=en") as request:
                result = await request.json()
        embed = discord.Embed(title=result["quoteText"]).set_author(name=result["quoteAuthor"])
        await ctx.send(embed=embed)


def setup(bot):
    bot.add_cog(APIs(bot))
