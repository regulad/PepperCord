from enum import Enum, auto
from typing import Optional, cast, Literal

import discord
from aiohttp import ClientSession
from anekos import *
from discord.ext import commands

from utils import bots, webhook
from utils.bots import BOT_TYPES, CustomContext
from utils.misc import split_string_chunks


class NSFWType(Enum):
    NSFW = auto()
    SFW = auto()
    REAL_SFW = auto()


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


async def send_sampler(
        ctx: CustomContext,
        nekos_life_client: NekosLifeClient,
        nsfw_type: NSFWType,
        add_author: bool = False,
) -> discord.Thread:
    match nsfw_type:
        case NSFWType.NSFW:
            tag_type = NSFWImageTags
        case NSFWType.SFW:
            tag_type = SFWImageTags
        case _:
            tag_type = RealSFWImageTags

    message: discord.Message = await ctx.channel.send(
        f"**{nsfw_type.name.replace('_', ' ').title()} Results**"
    )
    thread: discord.Thread = await message.create_thread(
        name=f"{nsfw_type.name.replace('_', ' ').title()} Results"
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

    async def secure_session(self) -> None:
        if self.nekos_http_client is None:
            self.nekos_http_client = ClientSession()
        if self.nekos_life_client is None:
            self.nekos_life_client = NekosLifeClient(session=self.nekos_http_client)

    async def cog_before_invoke(self, ctx: CustomContext) -> None:
        await self.secure_session()

    async def owo_filter(self, owoify: str) -> str:
        await self.secure_session()
        return "".join(
            [
                (await self.nekos_life_client.owoify(fragment)).text
                for fragment
                in split_string_chunks(owoify, chunk_size=199)
            ]
        )

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        ctx: bots.CustomContext = cast(bots.CustomContext, await self.bot.get_context(message))
        if (message.channel.id in ctx["guild_document"].get("owo_channels", [])
            or message.author.id in ctx["guild_document"].get("owo_members", [])) \
                and ctx.command is None \
                and not ctx.author.bot \
                and ctx.message.webhook_id is None:
            owo_webhook: discord.Webhook = await webhook.get_or_create_namespaced_webhook(
                "owo",
                ctx.bot,
                message.channel,
                name="Catboy Translator",
                avatar=await self.bot.user.avatar.read(),
            )
            await webhook.filter_message(message, self.owo_filter, owo_webhook)

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        await self.secure_session()

    def cog_unload(self) -> None:
        if self.nekos_http_client is not None:
            self.bot.loop.create_task(self.nekos_http_client.close())

    @commands.group(aliases=["n"])
    async def nekos(self, ctx: CustomContext) -> None:
        pass

    @nekos.command()
    @commands.has_permissions(administrator=True)
    async def canowo(
            self,
            ctx: bots.CustomContext,
            *,
            channel: Optional[discord.TextChannel] = commands.Option(description="The channel to set to OwO mode.")
    ) -> None:
        """Turns on OwO mode for this channel."""
        channel: discord.TextChannel = channel or ctx.channel
        await ctx["guild_document"].update_db({"$push": {"owo_channels": channel.id}})
        await ctx.send("This channel is now in OwO mode.", ephemeral=True)

    @nekos.command()
    @commands.has_permissions(administrator=True)
    async def cannotowo(
            self,
            ctx: bots.CustomContext,
            *,
            channel: Optional[discord.TextChannel] = commands.Option(description="The channel to unset from OwO mode.")
    ) -> None:
        """Turns off OwO mode for this channel."""
        channel: discord.TextChannel = channel or ctx.channel
        await ctx["guild_document"].update_db({"$pull": {"owo_channels": channel.id}})
        await ctx.send("This channel is no longer in OwO mode.", ephemeral=True)

    @nekos.command()
    @commands.has_permissions(administrator=True)
    async def canowomember(
            self,
            ctx: bots.CustomContext,
            *,
            member: Optional[discord.Member] = commands.Option(description="The user to be put in OwO mode.")
    ) -> None:
        """Turns on OwO mode for this user."""
        member: discord.Member = member or ctx.author
        await ctx["guild_document"].update_db({"$push": {"owo_members": member.id}})
        await ctx.send("This user is now in OwO mode.", ephemeral=True)

    @nekos.command()
    @commands.has_permissions(administrator=True)
    async def cannotowomember(
            self,
            ctx: bots.CustomContext,
            *,
            member: Optional[discord.Member] = commands.Option(description="The user to be taken out of OwO mode.")
    ) -> None:
        """Turns off OwO mode for this user."""
        member: discord.Member = member or ctx.author
        await ctx["guild_document"].update_db({"$pull": {"owo_members": member.id}})
        await ctx.send("This user is no longer in OwO mode.", ephemeral=True)

    @nekos.command()
    @commands.cooldown(3, 120, commands.BucketType.channel)
    @commands.is_nsfw()
    async def nsfw(
            self,
            ctx: CustomContext,
            quantity: Literal[tuple(range(1, 11))] = commands.Option(
                1,
                description="Defines the number of images you want to see. Defaults to 1, max is 10.",
            ),
            *,
            tag: Optional[NSFWNekosTagConverter] = commands.Option(
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
    @commands.is_nsfw()
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
        thread: discord.Thread = await send_sampler(
            ctx, self.nekos_life_client, NSFWType.REAL_SFW, add_author
        )
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
