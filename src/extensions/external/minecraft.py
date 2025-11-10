# from __future__ import annotations  # cant do this -- breaks discord
import re
from asyncio import TaskGroup
from base64 import b64decode
from enum import Enum, auto
from io import BytesIO
from json import dumps, loads
from logging import getLogger
from typing import Optional, List, TypedDict, cast

from discord import Colour, Embed, File, Forbidden, Member, TextChannel, DMChannel
from discord.app_commands import describe
from discord.ext.commands import hybrid_command, Cog
from discord.ext.tasks import loop
from mc_format import color as minecraft_legacy_to_ansi
from mcstatus import JavaServer, BedrockServer
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


class ComponentDict(TypedDict):
    """Represents a Minecraft component dict."""

    # https://minecraft.fandom.com/wiki/Raw_JSON_text_format#Java_Edition
    # this is only a plaintext component because server MOTDs cannot be localized

    # Content
    text: str

    # Children
    extra: List["ComponentDict"]

    # Formatting
    color: Optional[str]
    font: Optional[str]
    bold: Optional[bool]
    italic: Optional[bool]
    underlined: Optional[bool]
    strikethrough: Optional[bool]
    obfuscated: Optional[bool]

    # Interactivity
    # insertion # not used in MOTDs
    # clickEvent # not used in MOTDs
    # hoverEvent # not used in MOTDs


def minecraft_legacy_to_plain_text(legacy: str) -> str:
    return re.sub(r"§[0-9a-fklmnor]", "", legacy)


def minecraft_component_to_markdown(component: ComponentDict) -> str:
    strings: list[str] = []

    text: str = component["text"]

    if component.get("bold"):
        text = f"**{text}**"

    if component.get("italic"):
        text = f"*{text}*"

    if component.get("underlined"):
        text = f"__{text}__"

    if component.get("strikethrough"):
        text = f"~~{text}~~"

    if component.get("obfuscated"):
        text = f"||{text}||"

    if text:
        strings.append(text)

    if component.get("extra"):
        for child in component["extra"]:
            strings.append(minecraft_component_to_markdown(child))

    return "".join(strings)


def minecraft_component_to_ansi(component: ComponentDict) -> str:
    strings: list[str] = []

    text: str = component["text"]

    if color := component.get("color"):
        if color == "black":
            text = f"\033[30m{text}\033[0m"
        elif color == "dark_blue":
            text = f"\033[34m{text}\033[0m"
        elif color == "dark_green":
            text = f"\033[32m{text}\033[0m"
        elif color == "dark_aqua":
            text = f"\033[36m{text}\033[0m"
        elif color == "dark_red":
            text = f"\033[31m{text}\033[0m"
        elif color == "dark_purple":
            text = f"\033[35m{text}\033[0m"
        elif color == "gold":
            text = f"\033[33m{text}\033[0m"
        elif color == "gray":
            text = f"\033[37m{text}\033[0m"
        elif color == "dark_gray":
            text = f"\033[90m{text}\033[0m"
        elif color == "blue":
            text = f"\033[94m{text}\033[0m"
        elif color == "green":
            text = f"\033[92m{text}\033[0m"
        elif color == "aqua":
            text = f"\033[96m{text}\033[0m"
        elif color == "red":
            text = f"\033[91m{text}\033[0m"
        elif color == "light_purple":
            text = f"\033[95m{text}\033[0m"
        elif color == "yellow":
            text = f"\033[93m{text}\033[0m"
        elif color == "white":
            text = f"\033[97m{text}\033[0m"
        else:
            # hex color
            hex_color = color.lstrip("#")
            r, g, b = (
                int(hex_color[:2], 16),
                int(hex_color[2:4], 16),
                int(hex_color[4:], 16),
            )
            text = f"\033[38;2;{r};{g};{b}m{text}\033[0m"

    if component.get("bold"):
        text = f"\033[1m{text}\033[0m"

    if component.get("italic"):
        text = f"\033[3m{text}\033[0m"

    if component.get("underlined"):
        text = f"\033[4m{text}\033[0m"

    if component.get("strikethrough"):
        text = f"\033[9m{text}\033[0m"

    if component.get("obfuscated"):
        text = f"\033[8m{text}\033[0m"

    if text:
        strings.append(text)

    if component.get("extra"):
        for child in component["extra"]:
            strings.append(minecraft_component_to_ansi(child))

    return "".join(strings)


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

    motd: str | None = None
    if isinstance(status_response, JavaStatusResponse) and (
        description_raw := status_response.raw.get("description")
    ):
        if isinstance(description_raw, str):
            motd = minecraft_legacy_to_ansi(description_raw)
        elif isinstance(description_raw, dict):
            motd = minecraft_component_to_ansi(cast(ComponentDict, description_raw))
    elif isinstance(status_response, BedrockStatusResponse):
        motd = minecraft_legacy_to_ansi(status_response.description)
    elif isinstance(status_response, QueryResponse):
        motd = minecraft_legacy_to_ansi(str(status_response.motd.raw))
    if motd is not None:
        embed = embed.add_field(
            name="MOTD:",
            value=f"```ansi\n{motd}```",
            inline=False,
        )

    if isinstance(status_response, (JavaStatusResponse, BedrockStatusResponse)):
        embed = embed.add_field(name="Ping:", value=f"{status_response.latency:.1f}ms")

    if isinstance(status_response, QueryResponse):
        embed = embed.add_field(name="Map:", value=status_response.map)

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
                minecraft_legacy_to_plain_text(player_name)
                for player_name in player_list
            )
            player_field += "\n" + "\n".join(player_list_sorted)
        embed = embed.add_field(
            name="Players:",
            value=player_field,
            inline=False,
        )

    if isinstance(status_response, (BedrockStatusResponse, JavaStatusResponse)):
        version_name: str
        if isinstance(status_response.version, BedrockStatusVersion):
            version_name = (
                f"{status_response.version.brand} {status_response.version.version}"
            )
        else:
            version_name = status_response.version.name

        embed = embed.add_field(
            name="Version:",
            value=f"{version_name}, (ver. {status_response.version.protocol})",
            inline=False,
        )
    else:  # must be Query
        embed = embed.add_field(
            name="Software:",
            value=f"{status_response.software.brand} {status_response.software.version}",
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
        self.check_for_server_status_changes.start()

    async def cog_unload(self) -> None:
        self.check_for_server_status_changes.stop()

    async def _check_for_server_updates_single_server(
        self, document: PCDocument, server: SerializedServerType
    ) -> None:
        logger.debug(
            f"Checking for server status changes in {document._collection.name} {document['_id']} {server}..."
        )

        server_address = server["address"]
        server_type = MinecraftServerType(server["type"])
        channel_id = server["channel"]
        previous_status_json = server["previous_status"]
        previous_status_dict = (
            loads(previous_status_json) if previous_status_json is not None else None
        )
        channel = cast(TextChannel | None, self.bot.get_channel(channel_id))

        if channel is None:
            logger.warning(
                f"Could not find channel {channel_id} in {document._collection.name} {document['_id']}"
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
                    f"Could not send message to {channel_id} in {document._collection.name} {document['_id']}"
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

    async def _check_for_server_updates_document(self, document: PCDocument) -> None:
        logger.debug(
            f"Checking for server status changes in {document._collection.name} {document['_id']}..."
        )
        async with TaskGroup() as tg:
            for server in document.get("minecraft_servers", []):
                tg.create_task(
                    self._check_for_server_updates_single_server(document, server)
                )

    @loop(minutes=1)
    async def check_for_server_status_changes(self) -> None:
        logger.debug("Checking for server status changes...")

        # first step: get any documents in either the users or guild collection that have minecraft_servers set
        user_collection = self.bot.database.get_collection("user")
        user_query = {"minecraft_servers": {"$exists": True}}
        raw_user_documents = await user_collection.find(user_query).to_list(length=None)
        user_documents = [
            document.wrap(user_collection, user_query)
            for document in raw_user_documents
        ]

        guild_collection = self.bot.database.get_collection("guild")
        guild_query = {"minecraft_servers": {"$exists": True}}
        raw_guild_documents = await guild_collection.find(guild_query).to_list(
            length=None
        )
        guild_documents = [
            document.wrap(guild_collection, guild_query)
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
