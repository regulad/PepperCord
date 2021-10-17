from typing import Optional, cast, Any
from io import BytesIO

import discord
from anekos import *
from aiohttp import ClientSession
from discord.ext import commands

from utils.bots import BOT_TYPES, CustomContext
from utils.checks import check_is_allowed_nsfw


class NSFWNekosTagConverter(commands.Converter):
    async def convert(self, ctx: CustomContext, argument: str) -> NSFWImageTags:
        try:
            tag = NSFWImageTags[argument.upper().replace(" ", "_")]
        except KeyError:
            tag = None

        if tag is not None:
            return tag
        else:
            raise commands.BadArgument("Could not find tag.")


class SFWNekosTagConverter(commands.Converter):
    async def convert(self, ctx: CustomContext, argument: str) -> SFWImageTags:
        try:
            tag = SFWImageTags[argument.upper().replace(" ", "_")]
        except KeyError:
            tag = None

        if tag is not None:
            return tag
        else:
            raise commands.BadArgument("Could not find tag.")


class Nekos(commands.Cog):
    """An extension for interacting with the website nekos.life."""

    def __init__(self, bot: BOT_TYPES) -> None:
        self.bot: BOT_TYPES = bot
        self.nekos_http_client: Optional[ClientSession] = None
        self.nekos_life_client: Optional[NekosLifeClient] = None

    async def cog_before_invoke(self, ctx: CustomContext) -> None:
        if self.nekos_http_client is None:
            self.nekos_http_client = ClientSession()
        if self.nekos_life_client is None:
            self.nekos_life_client = NekosLifeClient(session=self.nekos_http_client)

    def cog_unload(self) -> None:
        if self.nekos_http_client is not None:
            self.bot.loop.create_task(self.nekos_http_client.close())

    @commands.group(
        invoke_without_command=True,
        case_insensitive=True,
        name="nekos",
        aliases=["n"],
        brief="Utilizes nekos.life.",
        description="Utilizes nekos.life. Displays all endpoints.",
    )
    async def nekosg(self, ctx: CustomContext) -> None:
        await ctx.send(
            embed=discord.Embed(
                title="Endpoints",
                description="\n".join([f"* {item.url if not 'hentai' in str(item.url) else '<redacted>'}" for item in await self.nekos_life_client.endpoints()])
            )
        )

    @nekosg.command(
        name="nsfw",
        brief="Grabs a NSFW picture from nekos.life",
    )
    @check_is_allowed_nsfw
    async def nsfwneko(self, ctx: CustomContext, *, tag: Optional[NSFWNekosTagConverter] = None):
        if tag is not None:
            tag: NSFWImageTags = cast(NSFWImageTags, tag)
            image_response = await self.nekos_life_client.image(tag, True)  # ImageResponse class is not exposed.
            image_buffer: BytesIO = BytesIO(image_response.bytes)
            image_file: discord.File = discord.File(image_buffer, filename=image_response.full_name)
            await ctx.send(files=[image_file])
        else:
            await ctx.send(
                embed=discord.Embed(
                    title="Tags",
                    description="\n".join([f"* {tag.title().replace('_', ' ')}" for tag in NSFWImageTags.__members__.keys()]),
                )
            )


    @nekosg.command(
        name="sfw",
        brief="Grabs a SFW picture from nekos.life",
    )
    async def sfwneko(self, ctx: CustomContext, *, tag: Optional[SFWNekosTagConverter] = None):
        if tag is not None:
            tag: SFWImageTags = cast(SFWImageTags, tag)
            image_response = await self.nekos_life_client.image(tag, True)  # ImageResponse class is not exposed.
            image_buffer: BytesIO = BytesIO(image_response.bytes)
            image_file: discord.File = discord.File(image_buffer, filename=image_response.full_name)
            await ctx.send(files=[image_file])
        else:
            await ctx.send(
                embed=discord.Embed(
                    title="Tags",
                    description="\n".join([f"* {tag.title().replace('_', ' ')}" for tag in SFWImageTags.__members__.keys()]),
                )
            )


def setup(bot: BOT_TYPES) -> None:
    bot.add_cog(Nekos(bot))
