# from __future__ import annotations  # cant do this -- breaks discord
from asyncio import TaskGroup
from base64 import b64decode
from enum import Enum, auto
from functools import partial
from io import BytesIO
from json import dumps, loads
from logging import getLogger
from typing import Optional, List, TypedDict, Iterable

import discord
from discord import Embed, File, TextChannel, DMChannel
from discord.app_commands import describe
from discord.ext import commands, tasks
from discord.ext.commands import hybrid_command, Cog
from mc_format import color as minecraft_legacy_to_ansi
from mcstatus import JavaServer, BedrockServer
from mcstatus.bedrock_status import BedrockStatusResponse
from mcstatus.pinger import PingResponse
from mcstatus.querier import QueryResponse

from utils.bots import BOT_TYPES, CustomContext
from utils.database import Document

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
            r, g, b = int(hex_color[:2], 16), int(hex_color[2:4], 16), int(hex_color[4:], 16)
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
    timeout: int = 30  # this is ludicrously high, but aternos servers take FOREVER to respond
) -> tuple[Embed, File | None]:
    server_lookup: JavaServer | BedrockServer
    status: PingResponse | BedrockStatusResponse | QueryResponse
    match server_type:
        case MinecraftServerType.JAVA:
            server_lookup = await JavaServer.async_lookup(server_address, timeout=timeout)
        case MinecraftServerType.BEDROCK:
            server_lookup = BedrockServer.lookup(server_address, timeout=timeout)
    try:
        status = await server_lookup.async_status()
    except OSError:
        # maybe a timeout, maybe a connection error
        # mcstatus already implements retries, so this is a last ditch effort
        if isinstance(server_lookup, JavaServer):
            status = await server_lookup.async_query()
        else:
            raise  # oh well

    embed = Embed(colour=discord.Colour.dark_gold(), title=server_lookup.address.host)

    file: File | None = None
    if hasattr(status, "favicon"):
        file_header, favicon_bytes = status.favicon.split(";base64,")
        mime = file_header.split(":")[1]

        if mime == "image/png":
            decoded = BytesIO(b64decode(favicon_bytes))
            file = File(decoded, filename="favicon.png")
    if file:
        embed = embed.set_thumbnail(url=f"attachment://{file.filename}")

    motd: str | None = None
    motd_formatted: bool = False
    if hasattr(status, "raw") and (description_raw := status.raw.get("description")):
        if isinstance(description_raw, str):
            motd = description_raw
        elif isinstance(description_raw, dict):
            motd = minecraft_component_to_markdown(description_raw)
            motd_formatted = True
    elif hasattr(status, "description"):
        motd = status.description
    elif hasattr(status, "motd"):
        motd = status.motd
    if motd:
        if not motd_formatted:
            # we need to convert the minecraft formatting (§) to ansi
            motd = minecraft_legacy_to_ansi(motd)
            motd_formatted = True

        embed = embed.add_field(
            name="MOTD:",
            value=f"```ansi\n{motd}```",
            inline=False,
        )

    if hasattr(status, "latency") and include_latency:
        embed = embed.add_field(name="Ping:", value=f"{status.latency:.1f}ms")

    if hasattr(status, "map"):
        embed = embed.add_field(name="Map:", value=status.map)

    players_max: int | None = None
    players_online: int | None = None
    player_list: list[str] | None = None
    if hasattr(status, "players"):
        players_max = status.players.max
        players_online = status.players.online
        if hasattr(status.players, "sample") and isinstance(status.players.sample, Iterable):
            player_list = [player.name for player in status.players.sample]
        elif hasattr(status.players, "names") and isinstance(status.players.names, list):
            player_list = status.players.names.copy()
    elif hasattr(status, "players_max") and hasattr(status, "players_online"):
        players_max = status.players_max
        players_online = status.players_online

    if players_max is not None and players_online is not None:
        player_field = f"**{players_online}**/**{players_max}**"
        if player_list is not None and len(player_list) > 0:
            player_field += "\n" + ", ".join(player_list)
        embed = embed.add_field(
            name="Players:",
            value=player_field,
            inline=False,
        )

    if hasattr(status, "version"):
        version_name: str
        if isinstance(status.version, BedrockStatusResponse.Version):
            version_name = f"{status.version.brand} {status.version.version}"
        else:
            version_name = status.version.name

        embed = embed.add_field(
            name="Version:",
            value=f"{version_name}, (ver. {status.version.protocol})",
            inline=False,
        )
    elif hasattr(status, "software"):
        embed = embed.add_field(
            name="Software:",
            value=f"{status.software.brand} {status.software.version}",
            inline=False,
        )

    return embed, file


class Minecraft(commands.Cog):
    """Commands to do with minecraft."""

    def __init__(self, bot: BOT_TYPES) -> None:
        self.bot: BOT_TYPES = bot

    @Cog.listener()
    async def on_ready(self) -> None:
        self.check_for_server_status_changes.start()

    def cog_unload(self) -> None:
        self.check_for_server_status_changes.stop()

    async def _check_for_server_updates_single_server(self, document: Document, server: dict) -> None:
        logger.debug(f"Checking for server status changes in {document._collection.name} {document['_id']} {server}...")

        server_address = server["address"]
        server_type = MinecraftServerType(server["type"])
        channel_id = server["channel"]
        previous_status_json = server["previous_status"]
        previous_status_dict = loads(previous_status_json) if previous_status_json is not None else None
        channel = self.bot.get_channel(channel_id)

        if channel is None:
            logger.warning(f"Could not find channel {channel_id} in {document._collection.name} {document['_id']}")
            return

        embed: Embed | None = None
        file: File | None = None
        try:
            embed, file = await generate_minecraft_embed(server_address, server_type, include_latency=False)
        except Exception as e:
            pass

        embed_serialized = embed.to_dict() if embed is not None else None

        if embed_serialized != previous_status_dict:
            try:
                if embed is not None and previous_status_dict is None:
                    message = "Server came online!"
                elif embed is not None and previous_status_dict is not None:
                    message = "Server status changed."
                else:
                    message = ("Server could not be reached, it's likely offline. "
                               "Updates will resume when it comes back online.")
                await channel.send(content=message, embed=embed, file=file)
            except discord.Forbidden:
                logger.warning(f"Could not send message to {channel_id} in {document._collection.name} {document['_id']}")
                pass
            await document.update_db(
                {
                    "$set": {
                        "minecraft_servers.$[server].previous_status": dumps(embed_serialized) if embed_serialized is not None else None
                    }
                },
                array_filters=[{"server.address": server_address}]
            )

    async def _check_for_server_updates_document(self, document: Document) -> None:
        logger.debug(f"Checking for server status changes in {document._collection.name} {document['_id']}...")
        async with TaskGroup() as tg:
            for server in document.get("minecraft_servers", []):
                tg.create_task(self._check_for_server_updates_single_server(document, server))

    @tasks.loop(minutes=1)
    async def check_for_server_status_changes(self) -> None:
        logger.debug("Checking for server status changes...")

        # first step: get any documents in either the users or guild collection that have minecraft_servers set
        user_collection = self.bot.database.get_collection("user")
        user_query = {
            "minecraft_servers": {"$exists": True}
        }
        raw_user_documents = await user_collection.find(user_query).to_list(length=None)
        user_documents = [Document(document, collection=user_collection, query=user_query | {"_id": document["_id"]})
                          for document in raw_user_documents]

        guild_collection = self.bot.database.get_collection("guild")
        guild_query = {
            "minecraft_servers": {"$exists": True}
        }
        raw_guild_documents = await guild_collection.find(guild_query).to_list(length=None)
        guild_documents = [Document(document, collection=guild_collection, query=guild_query | {"_id": document["_id"]})
                           for document in raw_guild_documents]

        all_documents = user_documents + guild_documents

        async with TaskGroup() as tg:
            for document in all_documents:
                tg.create_task(self._check_for_server_updates_document(document))

    @hybrid_command()
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

    @hybrid_command()
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
                if channel not in ctx.guild.text_channels:
                    raise Exception("This channel does not belong to this server.")
                elif channel.permissions_for(ctx.author).send_messages is False:
                    raise Exception("You do not have permission to send messages in this channel.")
                elif channel.permissions_for(ctx.guild.me).send_messages is False:
                    raise Exception("I do not have permission to send messages in this channel.")
                final_channel = channel
            elif dms:
                final_channel = ctx.author.dm_channel or await ctx.author.create_dm()
            else:
                final_channel = ctx.channel

            message = await ctx.send("Testing connection to the server...")
            embed, file = await generate_minecraft_embed(server_address, server_type, include_latency=False)
            await message.edit(content="Connected to the server. Registering server to watch...", embed=embed,
                               attachments=(file,))

            if isinstance(final_channel, DMChannel):
                await ctx["author_document"].update_db(
                    {
                        "$push": {
                            "minecraft_servers": {
                                "address": server_address,
                                "type": server_type.value,
                                "channel": final_channel.id,
                                "previous_status": dumps(embed.to_dict())
                            }
                        }
                    }
                )
            elif isinstance(final_channel, TextChannel):
                await ctx["guild_document"].update_db(
                    {
                        "$push": {
                            "minecraft_servers": {
                                "address": server_address,
                                "type": server_type.value,
                                "channel": final_channel.id,
                                "previous_status": dumps(embed.to_dict())
                            }
                        }
                    }
                )

            await message.edit(content="Server registered. You will now receive updates on the server status.")

    @hybrid_command()
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
                if channel not in ctx.guild.text_channels:
                    raise Exception("This channel does not belong to this server.")
                elif channel.permissions_for(ctx.author).send_messages is False:
                    raise Exception("You do not have permission to send messages in this channel.")
                elif channel.permissions_for(ctx.guild.me).send_messages is False:
                    raise Exception("I do not have permission to send messages in this channel.")
                final_channel = channel
            else:
                final_channel = ctx.channel

            if isinstance(final_channel, DMChannel):
                await ctx["author_document"].update_db(
                    {
                        "$pull": {
                            "minecraft_servers": {
                                "address": server_address,
                                "type": server_type.value,
                                "channel": final_channel.id
                            }
                        }
                    }
                )
            elif isinstance(final_channel, TextChannel):
                await ctx["guild_document"].update_db(
                    {
                        "$pull": {
                            "minecraft_servers": {
                                "address": server_address,
                                "type": server_type.value,
                                "channel": final_channel.id
                            }
                        }
                    }
                )

            await ctx.send("Server unregistered. You will no longer receive updates on the server status.")


async def setup(bot: BOT_TYPES) -> None:
    await bot.add_cog(Minecraft(bot))
