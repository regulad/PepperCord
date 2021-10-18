from typing import Optional, cast, Any
from io import BytesIO
from os.path import basename
from urllib.parse import urlparse

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
        name="allnsfw",
        aliases=["ansfw"],
        brief="Shows all NSFW tags.",
    )
    @check_is_allowed_nsfw
    async def ansfwneko(self, ctx: CustomContext):
        thread: discord.Thread = await ctx.message.create_thread(name="Results")
        for tag in NSFWImageTags.__members__.values():
            image_response = await self.nekos_life_client.image(tag, True)  # ImageResponse class is not exposed.
            image_buffer: BytesIO = BytesIO(image_response.bytes)
            image_file: discord.File = discord.File(image_buffer, filename=image_response.full_name)
            try:
                await thread.send(f"**{tag.name.title().replace('_', ' ')}**", files=[image_file])
            except discord.HTTPException:
                await thread.send(f"Couldn't send **{tag.name.title().replace('_', ' ')}**: {image_response.url}")
        await thread.edit(archived=True)

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

    @nekosg.command(
        name="allsfw",
        aliases=["asfw"],
        brief="Shows all SFW tags.",
    )
    async def asfwneko(self, ctx: CustomContext):
        thread: discord.Thread = await ctx.message.create_thread(name="Results")
        for tag in SFWImageTags.__members__.values():
            image_response = await self.nekos_life_client.image(tag, True)  # ImageResponse class is not exposed.
            image_buffer: BytesIO = BytesIO(image_response.bytes)
            image_file: discord.File = discord.File(image_buffer, filename=image_response.full_name)
            try:
                await thread.send(f"**{tag.name.title().replace('_', ' ')}**", files=[image_file])
            except discord.HTTPException:
                await thread.send(f"Couldn't send **{tag.name.title().replace('_', ' ')}**: {image_response.url}")
        await thread.edit(archived=True)

    @nekosg.command(
        name="8ball",
        aliases=["eightball"],
        brief="Uses the 8Ball.",
    )
    async def eightball(self, ctx: CustomContext, *, question: Optional[str] = None) -> None:
        eightball_resposne = await self.nekos_life_client.random_8ball(question or "question", get_image_bytes=True)
        eightball_buffer: BytesIO = BytesIO(eightball_resposne.image_bytes)
        eightball_filename: str = basename(urlparse(eightball_resposne.image_url).path)
        eightball_file: discord.File = discord.File(eightball_buffer, filename=eightball_filename)
        eightball_embed: discord.Embed = (
            discord.Embed(title=eightball_resposne.text.title(), color=discord.Colour.blurple())
            .set_image(url=f"attachment://{eightball_filename}")
        )
        await ctx.send(files=[eightball_file], embed=eightball_embed)

    @nekosg.command(
        name="owoify",
        brief="OwO your text!",
    )
    async def owoify(self, ctx: CustomContext, *, text: Optional[str] = None):
        text: str = (ctx.message.reference.resolved.clean_content if ctx.message.reference is not None else text) \
                    or "You didn't supply any text..."
        await ctx.send((await self.nekos_life_client.owoify(text)).text)

    @nekosg.command(
        name="fact",
        brief="Get a fact!",
    )
    async def fact(self, ctx: CustomContext) -> None:
        await ctx.send(f"*\"{(await self.nekos_life_client.random_fact_text()).text}\"*")


def setup(bot: BOT_TYPES) -> None:
    bot.add_cog(Nekos(bot))
