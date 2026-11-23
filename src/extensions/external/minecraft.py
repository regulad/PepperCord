# from __future__ import annotations  # cant do this -- breaks discord
from asyncio import TaskGroup
from base64 import b64decode
from bisect import bisect
from colorsys import rgb_to_hsv
from enum import Enum, auto
from io import BytesIO
from json import dumps, loads
from logging import getLogger
from typing import Optional, TypedDict, cast

from discord import (
    Colour,
    Embed,
    File,
    Forbidden,
    Member,
    NotFound,
    TextChannel,
    DMChannel,
)
from discord.app_commands import describe
from discord.ext.commands import hybrid_command, Cog
from discord.ext.tasks import loop
from discord.utils import escape_markdown
from mcstatus import JavaServer, BedrockServer
from mcstatus.motd import Motd
from mcstatus.motd.components import (
    BedrockFormatting,
    BedrockMinecraftColor,
    JavaFormatting,
    JavaMinecraftColor,
    WebColor,
)
from mcstatus.responses import (
    BedrockStatusResponse,
    JavaStatusResponse,
    QueryResponse,
    JavaStatusPlayers,
    BedrockStatusPlayers,
    QueryPlayers,
    BedrockStatusVersion,
)

from utils.bots.bot import CustomBot
from utils.bots.context import CustomContext
from utils.database import PCDocument

logger = getLogger(__name__)


class MinecraftServerType(Enum):
    JAVA = auto()
    BEDROCK = auto()


# Discord's ansi code blocks draw eight colours on every client, shaded to suit each reader's theme. Newer clients also
# draw bright and RGB colours, but older ones leave that text plain, so each Minecraft colour maps to one of the eight.
# White and quartz keep the theme's own text colour.
_DISCORD_ANSI_COLOURS: dict[int, tuple[str, ...]] = {
    30: ("BLACK",),
    31: ("DARK_RED", "RED", "MATERIAL_REDSTONE"),
    32: ("DARK_GREEN", "GREEN", "MATERIAL_EMERALD"),
    33: (
        "GOLD",
        "YELLOW",
        "MINECOIN_GOLD",
        "MATERIAL_GOLD",
        "MATERIAL_COPPER",
        "MATERIAL_RESIN",
    ),
    34: ("DARK_BLUE", "BLUE", "MATERIAL_LAPIS"),
    35: ("DARK_PURPLE", "LIGHT_PURPLE", "MATERIAL_AMETHYST"),
    36: ("DARK_AQUA", "AQUA", "MATERIAL_DIAMOND"),
    37: ("GRAY", "DARK_GRAY", "MATERIAL_IRON", "MATERIAL_NETHERITE"),
}
_DISCORD_ANSI_COLOUR_BY_NAME: frozendict[str, int] = frozendict(
    {name: code for code, names in _DISCORD_ANSI_COLOURS.items() for name in names}
)


def _discord_ansi_colour(rgb: tuple[int, int, int]) -> int | None:
    """Pick the Discord ansi colour nearest in hue to an RGB colour, or None for white."""
    red, green, blue = rgb
    hue, saturation, value = rgb_to_hsv(red / 255, green / 255, blue / 255)
    if value < 0.2:
        return 30
    if saturation < 0.25:
        return None if value > 0.85 else 37
    # Red, yellow (orange and gold too), green, cyan, blue, magenta, then red again, split at these hues in degrees.
    return (31, 33, 32, 36, 34, 35, 31)[bisect((15, 70, 160, 200, 260, 330), hue * 360)]


def motd_to_discord_ansi(motd: Motd) -> str:
    """Render a MOTD for an ansi code block, in the colours and styles that every Discord client draws."""
    colour: int | None = None
    bold = underlined = False
    drawn: tuple[int | None, bool, bool] = (None, False, False)
    rendered: list[str] = []
    for component in motd.parsed:
        match component:
            case JavaMinecraftColor() | BedrockMinecraftColor():
                # As in Minecraft, a colour code also ends bold and underline.
                colour = _DISCORD_ANSI_COLOUR_BY_NAME.get(component.name)
                bold = underlined = False
            case WebColor():
                colour = _discord_ansi_colour(component.rgb)
            case JavaFormatting.RESET | BedrockFormatting.RESET:
                colour = None
                bold = underlined = False
            case JavaFormatting.BOLD | BedrockFormatting.BOLD:
                bold = True
            case JavaFormatting.UNDERLINED:
                underlined = True
            case str() if component:
                if (colour, bold, underlined) != drawn:
                    # Resetting before each new style is how Discord reliably switches from one style to the next.
                    codes = ["0"]
                    if bold:
                        codes.append("1")
                    if underlined:
                        codes.append("4")
                    if colour is not None:
                        codes.append(str(colour))
                    rendered.append(f"\033[{';'.join(codes)}m")
                    drawn = (colour, bold, underlined)
                rendered.append(component)
            # Discord draws no italic, strikethrough or obfuscated text, and translation keys have no text to show.
    if drawn != (None, False, False):
        rendered.append("\033[0m")
    return "".join(rendered)


async def generate_minecraft_embed(
    server_address: str,
    server_type: MinecraftServerType,
    *,
    include_latency: bool = True,
    timeout: int = 30,  # this is ludicrously high, but aternos servers take FOREVER to respond
) -> tuple[Embed, File | None]:
    server_lookup: JavaServer | BedrockServer
    status_response: JavaStatusResponse | BedrockStatusResponse | QueryResponse
    match server_type:
        case MinecraftServerType.JAVA:
            server_lookup = await JavaServer.async_lookup(
                server_address, timeout=timeout
            )
        case MinecraftServerType.BEDROCK:
            server_lookup = BedrockServer.lookup(server_address, timeout=timeout)
    try:
        status_response = await server_lookup.async_status()
    except OSError:
        # maybe a timeout, maybe a connection error
        # mcstatus already implements retries, so this is a last ditch effort
        if isinstance(server_lookup, JavaServer):
            status_response = await server_lookup.async_query()
        else:
            raise  # oh well

    embed = Embed(colour=Colour.dark_gold(), title=server_address)

    file: File | None = None
    if (
        isinstance(status_response, JavaStatusResponse)
        and status_response.icon is not None
    ):
        file_header, favicon_bytes = status_response.icon.split(";base64,")
        mime = file_header.split(":")[1]

        if mime == "image/png":
            decoded = BytesIO(b64decode(favicon_bytes))
            file = File(decoded, filename="favicon.png")
    if file:
        embed = embed.set_thumbnail(url=f"attachment://{file.filename}")

    # mcstatus parses every kind of MOTD: Java's legacy text or JSON components, Bedrock's and Query's legacy text.
    if status_response.motd.to_plain().strip():
        embed = embed.add_field(
            name="MOTD:",
            # A field holds at most 1,024 characters, and a colourful MOTD spends most of them on escape codes.
            value=f"```ansi\n{motd_to_discord_ansi(status_response.motd)[:1000]}```",
            inline=False,
        )

    if include_latency and isinstance(
        status_response, (JavaStatusResponse, BedrockStatusResponse)
    ):
        embed = embed.add_field(name="Ping:", value=f"{status_response.latency:.1f}ms")

    if isinstance(status_response, QueryResponse):
        embed = embed.add_field(
            name="Map:", value=escape_markdown(status_response.map_name)
        )

    players_max: int | None = None
    players_online: int | None = None
    player_list: list[str] | None = None
    if hasattr(status_response, "players"):
        players_max = status_response.players.max
        players_online = status_response.players.online

        if isinstance(players := status_response.players, QueryPlayers):
            player_list = players.list.copy()
        elif isinstance(players := status_response.players, JavaStatusPlayers):
            player_list = [player.name for player in players.sample or []]
    elif isinstance(players := status_response.players, BedrockStatusPlayers):
        players_max = players.max
        players_online = players.online

    if players_max is not None and players_online is not None:
        player_field = f"**{players_online}**/**{players_max}**"
        if player_list is not None and len(player_list) > 0:
            player_list_sorted = sorted(
                Motd.parse(player_name).to_plain() for player_name in player_list
            )
            # Servers fill the sample with any text they like, which would otherwise render as Markdown.
            lines = [escape_markdown(name) for name in player_list_sorted]
            # A field holds at most 1,024 characters, and a query lists every player online.
            shown = 0
            for line in lines:
                if len(player_field) + len(line) + 1 > 990:
                    break
                player_field += f"\n{line}"
                shown += 1
            if shown < len(lines):
                player_field += f"\n…and {len(lines) - shown} more"
        embed = embed.add_field(
            name="Players:",
            value=player_field,
            inline=False,
        )

    if isinstance(status_response, (BedrockStatusResponse, JavaStatusResponse)):
        version_name: str
        if isinstance(status_response.version, BedrockStatusVersion):
            version_name = (
                f"{status_response.version.brand} {status_response.version.name}"
            )
        else:
            version_name = status_response.version.name
        # Servers colour their version names with the same codes as their MOTDs.
        version_name = Motd.parse(
            version_name, bedrock=isinstance(status_response, BedrockStatusResponse)
        ).to_plain()

        embed = embed.add_field(
            name="Version:",
            value=f"{escape_markdown(version_name)}, (ver. {status_response.version.protocol})",
            inline=False,
        )
    else:  # must be Query
        embed = embed.add_field(
            name="Software:",
            value=escape_markdown(
                f"{status_response.software.brand} {status_response.software.version}"
            ),
            inline=False,
        )

    return embed, file


class SerializedServerType(TypedDict):
    address: str
    channel: int
    previous_status: str | None
    type: int


class Minecraft(Cog):
    """Commands to do with minecraft."""

    def __init__(self, bot: CustomBot) -> None:
        self.bot = bot

    @Cog.listener()
    async def on_ready(self) -> None:
        # on_ready fires again after every new gateway session, and starting a running loop raises.
        if not self.check_for_server_status_changes.is_running():
            self.check_for_server_status_changes.start()

    async def cog_unload(self) -> None:
        self.check_for_server_status_changes.stop()

    async def _check_for_server_updates_single_server(
        self, document: PCDocument, server: SerializedServerType
    ) -> None:
        logger.debug(
            f"Checking for server status changes in {document._collection.name} "
            f"{await document.safe_subscript('_id')} {server}..."
        )

        server_address = server["address"]
        server_type = MinecraftServerType(server["type"])
        channel_id = server["channel"]
        previous_status_json = server["previous_status"]
        previous_status_dict = (
            loads(previous_status_json) if previous_status_json is not None else None
        )
        channel = cast(TextChannel | DMChannel | None, self.bot.get_channel(channel_id))
        if channel is None:
            # DM channels aren't cached after a restart until someone messages the bot there.
            try:
                channel = cast(
                    TextChannel | DMChannel, await self.bot.fetch_channel(channel_id)
                )
            except (NotFound, Forbidden):
                pass

        if channel is None:
            logger.warning(
                f"Could not find channel {channel_id} in {document._collection.name} "
                f"{await document.safe_subscript('_id')}"
            )
            return

        embed: Embed | None = None
        file: File | None = None
        try:
            embed, file = await generate_minecraft_embed(
                server_address, server_type, include_latency=False
            )
        except Exception:
            pass

        embed_serialized = embed.to_dict() if embed is not None else None

        if embed_serialized != previous_status_dict:
            try:
                if embed is not None and previous_status_dict is None:
                    message = "Server came online!"
                elif embed is not None and previous_status_dict is not None:
                    message = "Server status changed."
                else:
                    message = (
                        "Server could not be reached, it's likely offline. "
                        "Updates will resume when it comes back online."
                    )

                # Previously, this line was used:
                # await channel.send(content=message, embed=embed, file=file)
                # However, this now triggers my type checker. I'm not sure why, as it should work.
                # Probably an error in d.py

                if embed is not None and file is not None:
                    await channel.send(content=message, embed=embed, file=file)
                elif embed is not None and file is None:
                    await channel.send(content=message, embed=embed)
                else:
                    await channel.send(content=message)
            except Forbidden:
                logger.warning(
                    f"Could not send message to {channel_id} in {document._collection.name} "
                    f"{await document.safe_subscript('_id')}"
                )
            await document.update_db(
                {
                    "$set": {
                        "minecraft_servers.$[server].previous_status": (
                            dumps(embed_serialized)
                            if embed_serialized is not None
                            else None
                        )
                    }
                },
                array_filters=[{"server.address": server_address}],
            )

    async def _check_server_safely(
        self, document: PCDocument, server: SerializedServerType
    ) -> None:
        # One failing server would otherwise cancel the checks of every other server in the same pass.
        try:
            await self._check_for_server_updates_single_server(document, server)
        except Exception:
            logger.exception(f"Couldn't check {server['address']} for status changes.")

    async def _check_for_server_updates_document(self, document: PCDocument) -> None:
        logger.debug(
            f"Checking for server status changes in {document._collection.name} "
            f"{await document.safe_subscript("_id")}..."
        )
        async with TaskGroup() as tg:
            for server in await document.safe_get("minecraft_servers", []):
                tg.create_task(self._check_server_safely(document, server))

    @loop(minutes=1)
    async def check_for_server_status_changes(self) -> None:
        # discord.py ends a loop on any error it doesn't treat as a dropped connection, such as a database error.
        try:
            await self._check_all_servers()
        except Exception:
            logger.exception("Couldn't check Minecraft servers for status changes.")

    async def _check_all_servers(self) -> None:
        logger.debug("Checking for server status changes...")

        # first step: get any documents in either the users or guild collection that have minecraft_servers set
        user_collection = self.bot.ddb.get_collection("user")
        user_query = {"minecraft_servers": {"$exists": True}}
        raw_user_documents = await user_collection.find(user_query).to_list(length=None)
        user_documents = [
            document.wrap(user_collection, {"_id": document["_id"]})
            for document in raw_user_documents
        ]

        guild_collection = self.bot.ddb.get_collection("guild")
        guild_query = {"minecraft_servers": {"$exists": True}}
        raw_guild_documents = await guild_collection.find(guild_query).to_list(
            length=None
        )
        guild_documents = [
            document.wrap(guild_collection, {"_id": document["_id"]})
            for document in raw_guild_documents
        ]

        all_documents = user_documents + guild_documents

        async with TaskGroup() as tg:
            for document in all_documents:
                tg.create_task(self._check_for_server_updates_document(document))

    @hybrid_command()  # type: ignore[arg-type]  # bad d.py export
    @describe(
        server_address="The address of the Minecraft server",
        server_type="The type of the Minecraft server",
    )
    async def lookup_minecraft_server(
        self,
        ctx: CustomContext,
        *,
        server_address: str,
        server_type: MinecraftServerType = MinecraftServerType.JAVA,
    ) -> None:
        """Get the status of a Minecraft server"""
        async with ctx.typing(ephemeral=True):
            embed, file = await generate_minecraft_embed(server_address, server_type)
            await ctx.send(embed=embed, file=file, ephemeral=True)

    @hybrid_command()  # type: ignore[arg-type]  # bad d.py export
    @describe(
        server_address="The address of the Minecraft server",
        server_type="The type of the Minecraft server",
        dms="Whether to send the updates in your DMs",
        channel="The channel to send the updates to, if not in DMs",
    )
    async def watch_minecaft_server(
        self,
        ctx: CustomContext,
        *,
        server_address: str,
        server_type: MinecraftServerType = MinecraftServerType.JAVA,
        dms: bool = False,
        channel: Optional[TextChannel] = None,
    ) -> None:
        """Get sent updates on the status of a Minecraft server every time it changes."""
        async with ctx.typing(ephemeral=True):
            final_channel: TextChannel | DMChannel
            if not dms and channel:
                if ctx.guild is None or not isinstance(ctx.author, Member):
                    raise Exception(
                        "You must use this command in DMs mode to use it outside of a server."
                    )
                if channel not in ctx.guild.text_channels:
                    raise Exception("This channel does not belong to this server.")
                elif channel.permissions_for(ctx.author).send_messages is False:
                    raise Exception(
                        "You do not have permission to send messages in this channel."
                    )
                elif channel.permissions_for(ctx.guild.me).send_messages is False:
                    raise Exception(
                        "I do not have permission to send messages in this channel."
                    )
                final_channel = channel
            elif dms:
                final_channel = ctx.author.dm_channel or await ctx.author.create_dm()
            else:
                final_channel = cast(
                    TextChannel | DMChannel, ctx.channel
                )  # this command can't be called in group channels

            message = await ctx.send("Testing connection to the server...")
            embed, file = await generate_minecraft_embed(
                server_address, server_type, include_latency=False
            )
            await message.edit(
                content="Connected to the server. Registering server to watch...",
                embed=embed,
                attachments=(file,) if file is not None else tuple(),
            )

            if isinstance(final_channel, DMChannel):
                await ctx["author_document"].update_db(
                    {
                        "$push": {
                            "minecraft_servers": {
                                "address": server_address,
                                "type": server_type.value,
                                "channel": final_channel.id,
                                "previous_status": dumps(embed.to_dict()),
                            }
                        }
                    }
                )
            else:
                await ctx["guild_document"].update_db(
                    {
                        "$push": {
                            "minecraft_servers": {
                                "address": server_address,
                                "type": server_type.value,
                                "channel": final_channel.id,
                                "previous_status": dumps(embed.to_dict()),
                            }
                        }
                    }
                )

            await message.edit(
                content="Server registered. You will now receive updates on the server status."
            )

    @hybrid_command()  # type: ignore[arg-type]  # bad d.py export
    @describe(
        server_address="The address of the Minecraft server",
        server_type="The type of the Minecraft server",
        channel="The channel to stop sending updates to",
    )
    async def unwatch_minecaft_server(
        self,
        ctx: CustomContext,
        *,
        server_address: str,
        server_type: MinecraftServerType = MinecraftServerType.JAVA,
        channel: Optional[TextChannel] = None,
    ) -> None:
        """Stop receiving updates on the status of a Minecraft server."""
        async with ctx.typing(ephemeral=True):
            final_channel: TextChannel | DMChannel
            if channel:
                if ctx.guild is None or not isinstance(ctx.author, Member):
                    raise Exception(
                        "You must use this command in DMs mode to use it outside of a server."
                    )
                if channel not in ctx.guild.text_channels:
                    raise Exception("This channel does not belong to this server.")
                elif channel.permissions_for(ctx.author).send_messages is False:
                    raise Exception(
                        "You do not have permission to send messages in this channel."
                    )
                elif channel.permissions_for(ctx.guild.me).send_messages is False:
                    raise Exception(
                        "I do not have permission to send messages in this channel."
                    )
                final_channel = channel
            else:
                final_channel = cast(
                    TextChannel | DMChannel, ctx.channel
                )  # this command can't be called in group channels

            if isinstance(final_channel, DMChannel):
                await ctx["author_document"].update_db(
                    {
                        "$pull": {
                            "minecraft_servers": {
                                "address": server_address,
                                "type": server_type.value,
                                "channel": final_channel.id,
                            }
                        }
                    }
                )
            else:
                await ctx["guild_document"].update_db(
                    {
                        "$pull": {
                            "minecraft_servers": {
                                "address": server_address,
                                "type": server_type.value,
                                "channel": final_channel.id,
                            }
                        }
                    }
                )

            await ctx.send(
                "Server unregistered. You will no longer receive updates on the server status."
            )


async def setup(bot: CustomBot) -> None:
    await bot.add_cog(Minecraft(bot))
