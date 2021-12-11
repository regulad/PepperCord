import asyncio
import io
from typing import Optional, cast, Union, Type, List, Literal
from io import BytesIO
from os.path import basename
from urllib.parse import urlparse
from enum import Enum, auto

import discord
from anekos import *
from aiohttp import ClientSession
from discord.ext import commands

from utils.bots import BOT_TYPES, CustomContext
from utils.checks import check_is_allowed_nsfw


class NSFWType(Enum):
    NSFW = auto()
    SFW = auto()


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


async def send_sampler(
    ctx: CustomContext,
    nekos_life_client: NekosLifeClient,
    nsfw_type: NSFWType,
    add_author: bool = False,
) -> discord.Thread:
    tag_type: Type[Union[SFWImageTags, NSFWImageTags]] = (
        NSFWImageTags if nsfw_type is NSFWType.NSFW else SFWImageTags
    )
    message: discord.Message = await ctx.channel.send(
        f"**{'NSFW' if nsfw_type is NSFWType.NSFW else 'SFW'} Results**"
    )
    thread: discord.Thread = await message.create_thread(
        name=f"{'NSFW' if nsfw_type is NSFWType.NSFW else 'SFW'} Results"
    )
    if add_author:
        await thread.add_user(ctx.author)
    for tag in tag_type.__members__.values():
        image_response = await nekos_life_client.image(
            tag
        )  # ImageResponse class is not exposed.
        await thread.send(
            f"**{tag.name.title().replace('_', ' ')}**: {image_response.url}"
        )
    await thread.edit(archived=True)
    return thread


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

    @commands.group()
    async def nekos(self, ctx: CustomContext) -> None:
        pass

    @nekos.command()
    @commands.cooldown(3, 120, commands.BucketType.channel)
    @check_is_allowed_nsfw
    async def nsfw(
        self,
        ctx: CustomContext,
        quantity: Literal[tuple(range(1, 11))] = commands.Option(
            1,
            description="Defines the number of images you want to see. Defaults to 1, max is 10.",
        ),
        *,
        tag: Optional[SFWNekosTagConverter] = commands.Option(
            None,
            description="The tag you want to search. You can see all options if you leave this blank.",
        ),
    ) -> None:
        """Pull an NSFW image from nekos.life."""
        if tag is not None:
            if quantity > 10:
                raise RuntimeError("Too many images!")
            await ctx.send(
                "\n".join(
                    [
                        (
                            await self.nekos_life_client.image(cast(NSFWImageTags, tag))
                        ).url
                        for _ in range(1, quantity + 1)
                    ]
                ),
            )
        else:
            await ctx.send(
                embed=discord.Embed(
                    title="Tags",
                    description="\n".join(
                        [
                            f"* {tag.title().replace('_', ' ')}"
                            for tag in NSFWImageTags.__members__.keys()
                        ]
                    ),
                ),
            )

    @nekos.command()
    @commands.cooldown(3, 120, commands.BucketType.channel)
    async def sfw(
        self,
        ctx: CustomContext,
        quantity: Literal[tuple(range(1, 11))] = commands.Option(
            1,
            description="Defines the number of images you want to see. Defaults to 1, max is 10.",
        ),
        *,
        tag: Optional[SFWNekosTagConverter] = commands.Option(
            None,
            description="The tag you want to search. You can see all options if you leave this blank.",
        ),
    ) -> None:
        """Pull an SFW image from nekos.life."""
        if tag is not None:
            if quantity > 10:
                raise RuntimeError("Too many images!")
            await ctx.send(
                "\n".join(
                    [
                        (
                            await self.nekos_life_client.image(cast(SFWImageTags, tag))
                        ).url
                        for _ in range(1, quantity + 1)
                    ]
                ),
            )
        else:
            await ctx.send(
                embed=discord.Embed(
                    title="Tags",
                    description="\n".join(
                        [
                            f"* {tag.title().replace('_', ' ')}"
                            for tag in SFWImageTags.__members__.keys()
                        ]
                    ),
                ),
            )

    @nekos.command()
    @commands.cooldown(3, 120, commands.BucketType.channel)
    @check_is_allowed_nsfw
    async def allnsfw(
        self,
        ctx: CustomContext,
        add_author: bool = commands.Option(
            False,
            description="If the author should be added to the thread where all the tags will be displayed.",
        ),
    ) -> None:
        """Shows a sampler of all the NSFW image tags."""
        await ctx.defer(ephemeral=True)
        thread: discord.Thread = await send_sampler(
            ctx, self.nekos_life_client, NSFWType.NSFW, add_author
        )
        await ctx.send(f"Thread created: <#{thread.id}>", ephemeral=True)

    @nekos.command()
    @commands.cooldown(3, 120, commands.BucketType.channel)
    async def allsfw(
        self,
        ctx: CustomContext,
        add_author: bool = commands.Option(
            False,
            description="If the author should be added to the thread where all the tags will be displayed.",
        ),
    ) -> None:
        """Shows a sampler of all the SFW image tags."""
        await ctx.defer(ephemeral=True)
        thread: discord.Thread = await send_sampler(
            ctx, self.nekos_life_client, NSFWType.SFW, add_author
        )
        await ctx.send(f"Thread created: <#{thread.id}>", ephemeral=True)

    @nekos.command()
    async def eightball(
        self,
        ctx: CustomContext,
        *,
        question: Optional[str] = commands.Option(
            "question", description="The question that will be asked."
        ),
    ) -> None:
        """Use the magic 8 ball!"""
        await ctx.defer()
        eightball_resposne = await self.nekos_life_client.random_8ball(question)
        eightball_embed: discord.Embed = discord.Embed(
            title=eightball_resposne.text.title(), color=discord.Colour.blurple()
        ).set_image(url=eightball_resposne.image_url)
        await ctx.send(embed=eightball_embed)

    @nekos.command()
    async def owoify(
        self,
        ctx: CustomContext,
        *,
        text: str = commands.Option(description="The text to be owoifyed."),
    ) -> None:
        """Owoify your text!"""
        await ctx.defer()
        await ctx.send((await self.nekos_life_client.owoify(text)).text)

    @nekos.command()
    async def fact(self, ctx: CustomContext) -> None:
        """Get a neat fact!"""
        await ctx.defer()
        await ctx.send(f'*"{(await self.nekos_life_client.random_fact_text()).text}"*')


def setup(bot: BOT_TYPES) -> None:
    bot.add_cog(Nekos(bot))
