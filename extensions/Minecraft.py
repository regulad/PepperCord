import base64
import typing
from io import BytesIO

import aiohttp
import discord
import mcstatus
from discord.ext import commands


class Minecraft(commands.Cog):
    """Commands to do with minecraft."""

    def __init__(self, bot):
        self.bot = bot

    @commands.command(
        name="bedrockserver",
        aliases=["bestatus", "bedrock"],
        description="Gets Minecraft: Bedrock Edition server status.",
        brief="Gets Minecraft: BE server.",
        usage="[Server:Port]",
    )
    async def bedrock(self, ctx, *, server: str = "play.regulad.xyz"):
        server_lookup = mcstatus.MinecraftBedrockServer.lookup(server)
        try:
            status = await server_lookup.async_status()
            embed = (
                discord.Embed(colour=discord.Colour.dark_gold(), title=server)
                .add_field(name="MOTD:", value=f"```{status.motd}```", inline=False)
                .add_field(name="Ping:", value=f"{round(status.latency, 2)}ms")
                .add_field(name="Players:", value=f"{status.players_online}/{status.players_max}")
                .add_field(name="Map:", value=f'"{status.map}"')
                .add_field(name="Brand:", value=status.version.brand)
                .add_field(name="Protocol:", value=status.version.protocol)
            )
        except Exception:
            await ctx.send("Couldn't get information from the server. Is it online?")
        else:
            await ctx.send(embed=embed)

    @commands.command(
        name="javaserver",
        aliases=["mcstatus", "jestatus", "java"],
        description="Gets Minecraft: Java Edition server status.",
        brief="Gets Minecraft: JE server.",
        usage="[Server:Port]",
    )
    async def java(self, ctx, *, server: str = "play.regulad.xyz"):
        server_lookup = mcstatus.MinecraftServer.lookup(server)
        try:
            status = await server_lookup.async_status()
            decoded = BytesIO(base64.b64decode(status.favicon.replace("data:image/png;base64,", "")))
            embed = (
                discord.Embed(colour=discord.Colour.dark_gold(), title=server)
                .add_field(name="Ping:", value=f"{round(status.latency, 2)}ms")
                .add_field(name="Players:", value=f"{status.players.online}/{status.players.max}")
                .add_field(
                    name="Version:", value=f"{status.version.name}, (ver. {status.version.protocol})", inline=False
                )
                .set_thumbnail(url="attachment://favicon.png")
            )
            file = discord.File(decoded, filename="favicon.png")
        except Exception:
            await ctx.send("Couldn't get information from the server. Is it online?")
        else:
            await ctx.send(embed=embed, file=file)

    @commands.command(
        name="player",
        aliases=["mcuser", "mcplayer"],
        description="Get data on a Minecraft: Java Edition user.",
        brief="Gets Minecraft: JE player.",
        usage="[Player]",
    )
    async def player(self, ctx, *, player: typing.Optional[str]):
        player = player or ctx.author.display_name
        try:
            async with aiohttp.ClientSession() as client:
                async with client.get(f"https://api.mojang.com/users/profiles/minecraft/{player}") as request:
                    result = await request.json()
                    uuid = result["id"]
                    name = result["name"]
            embed = (
                discord.Embed(title=name)
                .set_image(url=f"https://crafatar.com/renders/body/{uuid}?overlay")
                .add_field(name="UUID:", value=f"```{uuid}```")
            )
        except KeyError:
            await ctx.send("Couldn't get information on the player. Is it a valid name?")
        else:
            await ctx.send(embed=embed)


def setup(bot):
    bot.add_cog(Minecraft(bot))
