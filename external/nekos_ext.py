from typing import Optional

import discord
from anekos import *
from aiohttp import ClientSession
from discord.ext import commands

from utils.bots import BOT_TYPES, CustomContext


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


def setup(bot: BOT_TYPES) -> None:
    bot.add_cog(Nekos(bot))
