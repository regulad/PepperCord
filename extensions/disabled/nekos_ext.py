import asyncio
from typing import Optional, cast, Union, Type, List
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
    iteration: int = 1,
    add_author: bool = False,
) -> discord.Thread:
    tag_type: Type[Union[SFWImageTags, NSFWImageTags]] = (
        NSFWImageTags if nsfw_type is NSFWType.NSFW else SFWImageTags
    )
    if iteration == 1:
        thread: discord.Thread = await ctx.message.create_thread(name="Results")
    else:
        result_name: str = f"Results {iteration}"
        message: discord.Message = await ctx.send(f"**{result_name}**")
        thread: discord.Thread = await message.create_thread(name=result_name)
        if add_author:
            await thread.add_user(ctx.author)
    for tag in tag_type.__members__.values():
        image_response = await nekos_life_client.image(
            tag, True
        )  # ImageResponse class is not exposed.
        image_buffer: BytesIO = BytesIO(image_response.bytes)
        image_file: discord.File = discord.File(
            image_buffer, filename=image_response.full_name
        )
        try:
            await thread.send(
                f"**{tag.name.title().replace('_', ' ')}**", files=[image_file]
            )
        except discord.HTTPException:
            await thread.send(
                f"Couldn't send **{tag.name.title().replace('_', ' ')}**: {image_response.url}"
            )
    await thread.edit(archived=True)
    return thread


async def send_samplers(
    ctx: CustomContext,
    nekos_life_client: NekosLifeClient,
    nsfw_type: NSFWType,
    iterations: int = 1,
    add_author: bool = False,
) -> None:
    tasks: List[asyncio.Task] = []
    for iteration in range(1, iterations + 1):
        tasks.append(
            ctx.bot.loop.create_task(
                send_sampler(ctx, nekos_life_client, nsfw_type, iteration, add_author)
            )
        )
    await asyncio.wait(tasks)


async def send_images(
    ctx: CustomContext,
    nekos_life_client: NekosLifeClient,
    tag: Union[NSFWImageTags, SFWImageTags],
    iterations: int = 1,
) -> None:
    if iterations == 1:
        await send_image(ctx, nekos_life_client, tag)
    else:
        thread: discord.Thread = await ctx.message.create_thread(name="Results")
        tasks: List[asyncio.Task] = []
        for iterations in range(1, iterations + 1):
            tasks.append(
                ctx.bot.loop.create_task(send_image(thread, nekos_life_client, tag))
            )
        await asyncio.wait(tasks)
        await thread.edit(archived=True)


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
        pass

    @nekosg.command(
        name="nsfw",
        brief="Grabs a NSFW picture from nekos.life",
    )
    @commands.cooldown(3, 120, commands.BucketType.channel)
    @check_is_allowed_nsfw
    async def nsfwneko(
        self,
        ctx: CustomContext,
        quantity: Optional[int] = 1,
        *,
        tag: Optional[NSFWNekosTagConverter] = None,
    ) -> None:
        if tag is not None:
            if quantity > 7 and not await ctx.bot.is_owner(ctx.author):
                raise RuntimeError("Too many iterations! Maximum is 7.")
            await send_images(
                ctx, self.nekos_life_client, cast(NSFWImageTags, tag), quantity
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
                )
            )

    @nekosg.command(
        name="allnsfw",
        aliases=["ansfw"],
        brief="Shows all NSFW tags.",
    )
    @commands.cooldown(3, 120, commands.BucketType.channel)
    @check_is_allowed_nsfw
    async def ansfwneko(
        self, ctx: CustomContext, quantity: int = 1, add_author: bool = False
    ) -> None:
        if quantity > 3 and not await ctx.bot.is_owner(ctx.author):
            raise RuntimeError("Too many iterations! Maximum is 3.")
        await send_samplers(
            ctx, self.nekos_life_client, NSFWType.NSFW, quantity, add_author
        )

    @nekosg.command(
        name="sfw",
        brief="Grabs a SFW picture from nekos.life",
    )
    @commands.cooldown(3, 120, commands.BucketType.channel)
    async def sfwneko(
        self,
        ctx: CustomContext,
        quantity: Optional[int] = 1,
        *,
        tag: Optional[SFWNekosTagConverter] = None,
    ) -> None:
        if tag is not None:
            if quantity > 7 and not await ctx.bot.is_owner(ctx.author):
                raise RuntimeError("Too many iterations! Maximum is 7.")
            await send_images(
                ctx, self.nekos_life_client, cast(SFWImageTags, tag), quantity
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
                )
            )

    @nekosg.command(
        name="allsfw",
        aliases=["asfw"],
        brief="Shows all SFW tags.",
    )
    @commands.cooldown(3, 120, commands.BucketType.channel)
    async def asfwneko(
        self, ctx: CustomContext, quantity: int = 1, add_author: bool = False
    ) -> None:
        if quantity > 3 and not await ctx.bot.is_owner(ctx.author):
            raise RuntimeError("Too many iterations! Maximum is 3.")
        await send_samplers(
            ctx, self.nekos_life_client, NSFWType.SFW, quantity, add_author
        )

    @nekosg.command(
        name="8ball",
        aliases=["eightball"],
        brief="Uses the 8Ball.",
    )
    async def eightball(
        self, ctx: CustomContext, *, question: Optional[str] = None
    ) -> None:
        eightball_resposne = await self.nekos_life_client.random_8ball(
            question or "question"
        )
        eightball_embed: discord.Embed = discord.Embed(
            title=eightball_resposne.text.title(), color=discord.Colour.blurple()
        ).set_image(url=eightball_resposne.image_url)
        await ctx.send(embed=eightball_embed)

    @nekosg.command(
        name="owoify",
        brief="OwO your text!",
    )
    async def owoify(self, ctx: CustomContext, *, text: Optional[str] = None):
        text: str = (
            (
                ctx.message.reference.resolved.clean_content
                if ctx.message.reference is not None
                else text
            )
            or (
                (
                    await ctx.channel.history(
                        limit=1, before=ctx.message.created_at
                    ).flatten()
                )[0].clean_content
            )
            or "You didn't supply any text... Reply to a message you like or pass it as an argument!"
        )
        await ctx.send((await self.nekos_life_client.owoify(text)).text)

    @nekosg.command(
        name="fact",
        brief="Get a fact!",
    )
    async def fact(self, ctx: CustomContext) -> None:
        await ctx.send(f'*"{(await self.nekos_life_client.random_fact_text()).text}"*')


def setup(bot: BOT_TYPES) -> None:
    bot.add_cog(Nekos(bot))
