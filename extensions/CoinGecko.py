from typing import Optional

from aiocoingecko import AsyncCoinGeckoAPISession
from aiohttp import ClientSession
from discord.ext import commands, menus
import discord


class CoinMenuSource(menus.ListPageSource):
    async def format_page(self, menu, page_entries):
        offset = menu.current_page * self.per_page
        base_embed = discord.Embed(title="Coins")

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

        embed: discord.Embed = discord.Embed(title="Currencies", description=description)

        return embed


class CoinGecko(commands.Cog):
    """Interact with the CoinGecko API to pull data about all sorts of cryptocurrencies."""

    def __init__(self, bot):
        self.bot = bot

        self.client_session = ClientSession()
        self.coin_gecko_session = AsyncCoinGeckoAPISession(client_session=self.client_session)

        self.cooldown = commands.CooldownMapping.from_cooldown(100, 60, commands.BucketType.default)

    async def cog_check(self, ctx):
        cooldown: commands.Cooldown = self.cooldown.get_bucket(ctx.message)
        retry_after: float = cooldown.update_rate_limit()

        if retry_after:
            raise commands.CommandOnCooldown(cooldown, retry_after)
        else:
            return True

    @commands.group(
        invoke_without_command=True,
        case_insensitive=True,
        name="coingecko",
        aliases=["cg"],
        brief="Gets information from CoinGecko.",
        description="Get information from many CoinGecko API Routes.",
    )
    async def coingecko(self, ctx) -> None:
        get: dict = await self.coin_gecko_session.ping()
        await ctx.send(get["gecko_says"])

    @coingecko.command(
        name="coins",
        brief="List all coins.",
        description="List all coins that CoinGecko has info on.",
    )
    async def coins(self, ctx) -> None:
        get: list = await self.coin_gecko_session.get_coins_list()

        menu: menus.MenuPages = menus.MenuPages(source=CoinMenuSource(get, per_page=15))

        await menu.start(ctx)

    @coingecko.command(
        name="currencies",
        brief="List all currencies.",
        description="List all currencies CoinGecko has info on.",
    )
    async def currencies(self, ctx) -> None:
        get: list = await self.coin_gecko_session.get_supported_vs_currencies()

        menu: menus.MenuPages = menus.MenuPages(source=CurrencyMenuSource(get, per_page=20))

        await menu.start(ctx)

    @coingecko.command(
        name="price",
        brief="Get the price of a coin.",
        description="Get the price of a supported coin in a supported currency.",
        usage="<Coin (see cg coins)> [Currency (see cg currencies) (default USD)]",
    )
    async def price(self, ctx, coin: str, currency: Optional[str] = "usd") -> None:
        get: dict = await self.coin_gecko_session.get_price(coin, currency)

        if not get:
            await ctx.send(f"Couldn't find anything on {coin} in {currency}.")
            return

        await ctx.send(f"{get[coin][currency]} {currency.upper()}")


def setup(bot):
    bot.add_cog(CoinGecko(bot))
