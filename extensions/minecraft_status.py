from base64 import b64decode
from io import BytesIO
from typing import Optional, List

import discord
import mcstatus
from aiohttp import ClientSession
from discord.ext import commands

from utils.bots import BOT_TYPES, CustomContext


class MinecraftError(Exception):
    """Base class for all minecraft-related errors."""

    pass


class MinecraftServerError(MinecraftError):
    """Raised when an issue is encountered with a Minecraft server."""

    pass


class MinecraftPlayerError(MinecraftError):
    """Raised when an issue is encountered with a Minecraft player."""

    pass


class Minecraft(commands.Cog):
    """Commands to do with minecraft."""

    def __init__(self, bot: BOT_TYPES) -> None:
        self.bot: BOT_TYPES = bot
        self.aiohttp_cs: ClientSession = ClientSession()

    def cog_unload(self) -> None:
        self.bot.loop.create_task(self.aiohttp_cs.close())

    @commands.command(
        name="javaserver",
        aliases=["mcstatus", "jestatus", "java"],
        description="Gets Minecraft: Java Edition server status.",
        usage="[Server:Port]",
    )
    async def java(
            self, ctx: CustomContext, *, server: Optional[str] = "smp.play.regulad.xyz"
    ) -> None:
        async with ctx.typing():
            try:
                server_lookup = await ctx.bot.loop.run_in_executor(
                    None, mcstatus.MinecraftServer.lookup, server
                )
                status = await server_lookup.async_status()
            except OSError as e:
                raise MinecraftServerError(f"{server}: {e}")
            except Exception:
                raise

            decoded = BytesIO(
                b64decode(status.favicon.replace("data:image/png;base64,", ""))
            )

            file = discord.File(decoded, filename="favicon.png")

            if (
                    isinstance(status.description, dict)
                    and status.description.get("extra") is not None
            ):
                strings: List[str] = []

                for string in status.description["extra"]:
                    text: str = string["text"]

                    if text:
                        if string.get("clickEvent") is not None:
                            if string["clickEvent"]["action"] == "open_url":
                                text: str = f"[{text}]({string['clickEvent']['value']})"

                        if string["bold"]:
                            text: str = f"**{text}**"

                        if string["italic"]:
                            text: str = f"*{text}*"

                        if string["underlined"]:
                            text: str = f"__{text}__"

                        if string["strikethrough"]:
                            text: str = f"~~{text}~~"

                        if string["obfuscated"]:
                            text: str = f"||{text}||"

                    strings.append(text)

                motd: Optional[str] = "".join(strings)
            elif (
                    isinstance(status.description, dict)
                    and status.description.get("text") is not None
            ):
                motd: Optional[str] = status.description["text"]
            elif isinstance(status.description, str):
                motd: Optional[str] = status.description
            else:
                motd: Optional[str] = None

            embed: discord.Embed = (
                discord.Embed(colour=discord.Colour.dark_gold(), title=server)
                    .add_field(
                    name="MOTD:",
                    value=motd
                    if motd is not None and len(motd) > 0
                    else "Couldn't read the MOTD. Likely a server issue.",
                    inline=False,
                )
                    .add_field(name="Ping:", value=f"{round(status.latency, 2)}ms")
                    .add_field(
                    name="Players:",
                    value=f"{status.players.online}/{status.players.max}",
                )
                    .add_field(
                    name="Version:",
                    value=f"{status.version.name}, (ver. {status.version.protocol})",
                    inline=False,
                )
                    .set_thumbnail(url="attachment://favicon.png")
            )

            await ctx.send(embed=embed, file=file)

    @commands.command(
        name="bedrockserver",
        aliases=["bestatus", "bedrock"],
        description="Gets Minecraft: Bedrock Edition server status.",
        usage="[Server:Port]",
    )
    async def bedrock(
            self, ctx: CustomContext, *, server: Optional[str] = "play.regulad.xyz"
    ) -> None:
        async with ctx.typing():
            try:
                server_lookup = await ctx.bot.loop.run_in_executor(
                    None, mcstatus.MinecraftBedrockServer.lookup, server
                )
                status = await server_lookup.async_status()
            except OSError as e:
                raise MinecraftServerError(f"{server}: {e}")
            except Exception:
                raise

            embed: discord.Embed = (
                discord.Embed(colour=discord.Colour.dark_gold(), title=server)
                    .add_field(name="MOTD:", value=f"```{status.motd}```", inline=False)
                    .add_field(name="Ping:", value=f"{round(status.latency, 2)}ms")
                    .add_field(
                    name="Players:",
                    value=f"{status.players_online}/{status.players_max}",
                )
                    .add_field(name="Map:", value=f'"{status.map}"')
                    .add_field(name="Brand:", value=status.version.brand)
                    .add_field(name="Protocol:", value=status.version.protocol)
            )

            await ctx.send(embed=embed)

    # @commands.command(
    #     name="player",
    #     aliases=["mcuser", "mcplayer"],
    #     description="Get data on a Minecraft: Java Edition user.",
    #     usage="[Player]",
    # )
    # async def player(
    #     self,
    #     ctx: CustomContext,
    #     *,
    #     player: Optional[Union[discord.Member, discord.User, str]],
    # ) -> None:
    #     player = player or ctx.author
    #     # Maybe add ability to link Minecraft account? Nah... not until Microsoft finishes migrating accounts.
    #
    #     if isinstance(player, discord.Member):
    #         player = player.display_name
    #     elif isinstance(player, discord.User):
    #         player = player.name
    #
    #     try:
    #         async with self.aiohttp_cs.get(
    #             f"https://api.mojang.com/users/profiles/minecraft/{player}"
    #         ) as request:
    #             result = await request.json()
    #             uuid: str = result["id"]
    #             name: str = result["name"]
    #     except KeyError or json.JSONDecodeError:
    #         raise MinecraftPlayerError(player)
    #
    #     embed: discord.Embed = (
    #         discord.Embed(title=name)
    #         .set_image(url=f"https://crafatar.com/renders/body/{uuid}?overlay")
    #         .add_field(name="UUID:", value=f"```{uuid}```")
    #     )
    #
    #     await ctx.send(embed=embed)


def setup(bot: BOT_TYPES):
    bot.add_cog(Minecraft(bot))
