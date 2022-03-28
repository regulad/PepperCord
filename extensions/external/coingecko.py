from typing import Optional

import discord
from aiocoingecko import AsyncCoinGeckoAPISession
from aiohttp import ClientSession
from discord.ext import commands, menus

from utils.bots import CustomContext


class CoinMenuSource(menus.ListPageSource):
    async def format_page(self, menu, page_entries):
        offset = menu.current_page * self.per_page
        base_embed = discord.Embed(title="Coins")
        base_embed.set_footer(text=f"Page {menu.current_page + 1}/{self.get_max_pages()}")

        for iteration, value in enumerate(page_entries, start=offset):
            base_embed.add_field(
                name=f"{iteration + 1}: {value['symbol']}",
                value=f"{value['name']}: `{value['id']}`",
                inline=False,
            )

        return base_embed


class CurrencyMenuSource(menus.ListPageSource):
    async def format_page(self, menu, page_entries) -> discord.Embed:
        offset = menu.current_page * self.per_page

        lines: list = []

        for iteration, value in enumerate(page_entries, start=offset):
            lines.append(f"**{iteration + 1}: {value}**")

        description: str = "\n".join(lines)

        embed: discord.Embed = discord.Embed(
            title="Currencies", description=description
        )
        embed.set_footer(text=f"Page {menu.current_page + 1}/{self.get_max_pages()}")

        return embed


class CoinGecko(commands.Cog):
    """Interact with the CoinGecko API to pull data about all sorts of cryptocurrencies."""

    def __init__(self, bot):
        self.bot = bot

        self.client_session = ClientSession()
        self.coin_gecko_session = AsyncCoinGeckoAPISession(
            client_session=self.client_session
        )

        self.cooldown = commands.CooldownMapping.from_cooldown(
            100, 60, commands.BucketType.default
        )

    def cog_unload(self):
        self.bot.loop.create_task(self.client_session.close())

    async def cog_check(self, ctx):
        cooldown: commands.Cooldown = self.cooldown.get_bucket(ctx.message)
        retry_after: float = cooldown.update_rate_limit()

        if retry_after:
            raise commands.CommandOnCooldown(cooldown, retry_after, self.cooldown.type)
        else:
            return True

    @commands.group()
    async def coingecko(self, ctx) -> None:
        pass

    @coingecko.command()
    async def coins(self, ctx: CustomContext) -> None:
        """Sends you a list of all cryptocurrencies that can be searched."""

        await ctx.defer(ephemeral=True)

        get: list = await self.coin_gecko_session.get_coins_list()

        await menus.ViewMenuPages(source=CoinMenuSource(get, per_page=15)).start(
            ctx, ephemeral=True
        )

    @coingecko.command()
    async def currencies(self, ctx: CustomContext) -> None:
        """Lists all currencies that cryptocurrencies can be compared to."""

        await ctx.defer(ephemeral=True)

        get: list = await self.coin_gecko_session.get_supported_vs_currencies()

        await menus.ViewMenuPages(source=CurrencyMenuSource(get, per_page=20)).start(
            ctx, ephemeral=True
        )

    @coingecko.command()
    async def price(
            self,
            ctx: CustomContext,
            coin: str = commands.Option(
                description="The name of a currency to search. Example: ethereum."
            ),
            currency: Optional[str] = commands.Option(
                "usd",
                description="The currency that the coin's value will be represented in. Defaults to usd.",
            ),
    ) -> None:
        """Gets the price of a cryptocurrency."""

        await ctx.defer(ephemeral=True)

        get: dict = await self.coin_gecko_session.get_price(coin, currency)

        if not get:
            await ctx.send(
                f"Couldn't find anything on {coin} in {currency}.", ephemeral=True
            )
        else:
            await ctx.send(f"{get[coin][currency]} {currency.upper()}", ephemeral=True)


def setup(bot):
    bot.add_cog(CoinGecko(bot))
