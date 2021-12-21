from typing import Optional, cast, Literal

import discord
from aiohttp import ClientSession
from anekos import *
from discord.ext import commands

from utils.bots import BOT_TYPES, CustomContext


class TagConverter(commands.Converter):
    async def convert(self, ctx: commands.Context, argument: str) -> SFWImageTags:
        try:
            tag = RealSFWImageTags[argument.upper().replace(" ", "_")]
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

    @commands.group()
    async def nekos(self, ctx: CustomContext) -> None:
        pass

    @nekos.command()
    @commands.cooldown(3, 120, commands.BucketType.channel)
    async def image(
        self,
        ctx: CustomContext,
        quantity: Literal[tuple(range(1, 11))] = commands.Option(
            1,
            description="Defines the number of images you want to see. Defaults to 1, max is 10.",
        ),
        *,
        tag: Optional[TagConverter] = commands.Option(
            None,
            description="The tag you want to search. You can see all options if you leave this blank.",
        ),
    ) -> None:
        """Pull an image from nekos.life."""
        if tag is not None:
            if quantity > 10:
                raise RuntimeError("Too many images!")
            await ctx.send(
                "\n".join(
                    [
                        (
                            await self.nekos_life_client.image(
                                cast(RealSFWImageTags, tag)
                            )
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
                            for tag in RealSFWImageTags.__members__.keys()
                        ]
                    ),
                ),
            )

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
    @commands.cooldown(3, 120, commands.BucketType.channel)
    async def images(
        self,
        ctx: CustomContext,
        add_author: bool = commands.Option(
            False,
            description="If the author should be added to the thread where all the tags will be displayed.",
        ),
    ) -> None:
        """Shows a sampler of all the images."""
        await ctx.defer(ephemeral=True)
        message: discord.Message = await ctx.channel.send(f"**Results**")
        thread: discord.Thread = await message.create_thread(name=f"Results")
        if add_author:
            await thread.add_user(ctx.author)
        for tag in RealSFWImageTags.__members__.values():
            image_response = await self.nekos_life_client.image(
                tag
            )  # ImageResponse class is not exposed.
            await thread.send(
                f"**{tag.name.title().replace('_', ' ')}**: {image_response.url}"
            )
        await thread.edit(archived=True)
        await ctx.send(f"Thread created: <#{thread.id}>", ephemeral=True)

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
