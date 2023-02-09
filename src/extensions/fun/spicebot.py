from typing import Optional

import aiohttp
import discord
from discord.ext import commands

from utils import bots, webhook

SPICE_BOT_ID: int = 933457773365170256


class SpiceBot(commands.Cog):
    """
    A homage to the original PepperCord, SpiceBot.
    https://github.com/regulad/SpiceBot
    """

    def __init__(self, bot: bots.BOT_TYPES) -> None:
        self.bot: bots.BOT_TYPES = bot
        self.client: Optional[aiohttp.ClientSession] = None

    async def cog_load(self) -> None:
        self.client = aiohttp.ClientSession()

    async def cog_before_invoke(self, ctx: bots.CustomContext) -> None:
        if ctx.guild is None:
            spice_bot_user: discord.abc.User = ctx.guild.get_member(
                SPICE_BOT_ID
            ) or await ctx.bot.fetch_user(SPICE_BOT_ID)
            spice_bot_webhook: discord.Webhook = (
                await webhook.get_or_create_namespaced_webhook(
                    "spicebot",
                    ctx.bot,
                    ctx.channel,
                    avatar=await spice_bot_user.avatar.read(),
                    name=spice_bot_user.display_name,
                )
            )
            ctx.send_handler = webhook.ImpersonateSendHandler(
                spice_bot_webhook, spice_bot_user
            )

    async def cog_unload(self) -> None:
        if self.client is not None:
            await self.client.close()

    @commands.command(aliases=["inspire"])
    async def quote(self, ctx: bots.CustomContext) -> None:
        """Get Inspired!"""
        async with self.client.get("https://zenquotes.io/api/random") as random:
            json_object: list[dict] = await random.json()
            main_json_object: dict = json_object[-1]
            # We sucked at asyncio.
            await ctx.send(
                embed=discord.Embed(
                    title=main_json_object["a"],
                    description=main_json_object["q"],
                )
            )

    @commands.command()
    async def ez(self, ctx: bots.CustomContext) -> None:
        """gg no re"""
        await ctx.send("https://tenor.com/view/ez-yann-gauthier-gif-18979624")

    @commands.command()
    async def real(self, ctx: bots.CustomContext) -> None:
        """get real"""
        await ctx.send("https://tenor.com/view/get-real-sexy-among-us-gif-19307656")

    @commands.command(aliases=["gummy"])
    async def gummi(self, ctx: bots.CustomContext) -> None:
        """🐻🐻🐻🐻 🧟 👉😗👈 🌪"""
        await ctx.send("https://vm.tiktok.com/ZMJWJQCSH/")

    @commands.command(aliases=["dog"])
    async def derg(self, ctx: bots.CustomContext) -> None:
        """Nice doggy!"""
        await ctx.send(
            embed=discord.Embed(
                title="░▄▀▄▀▀▀▀▄▀▄░░░░░░░░░\n"
                "░█░░░░░░░░▀▄░░░░░░▄░\n"
                "█░░▀░░▀░░░░░▀▄▄░░█░█\n"
                "█░▄░█▀░▄░░░░░░░▀▀░░█\n"
                "█░░▀▀▀▀░░░░░░░░░░░░█\n"
                "█░░░░░░░░░░░░░░░░░░█\n"
                "█░░░░░░░░░░░░░░░░░░█\n"
                "░█░░▄▄░░▄▄▄▄░░▄▄░░█░\n"
                "░█░▄▀█░▄▀░░█░▄▀█░▄▀░\n"
                "░░▀░░░▀░░░░░▀░░░▀░░░"
            )
        )


async def setup(bot: bots.BOT_TYPES) -> None:
    await bot.add_cog(SpiceBot(bot))
