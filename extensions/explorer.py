from pycoingecko import CoinGeckoAPI
from discord.ext import commands
from discord.ext.commands.cooldowns import BucketType
from tools.errors import SubcommandNotFound

class explorer(commands.Cog, name='Internet Data', description='Gets information from the internet.'):
  def __init__(self, bot):
    self.bot = bot
  
  @commands.group(invoke_without_command=True, case_insensitive=True, name='crypto', aliases=['blockchain'], brief='Looks up data on the crypto blockchain.', description='Finds cryptocurrency blockchain information using CoinGecko.')
  @commands.cooldown(100, 55, BucketType.default)
  async def crypto(self, ctx):
    raise SubcommandNotFound()
  
  @crypto.command(name='status', aliases=['ping'], brief='Gets status from API.', description='Gets status from the CoinGeckoAPI.')
  async def ping(self, ctx):
    await ctx.send(CoinGeckoAPI().ping()['gecko_says'])
  
  @crypto.command(name='price', aliases=['value'], brief='Finds price of coin.', description='Finds price of coin using CoinGecko.', usage='[Coin] [Currency]')
  async def price(self, ctx, coin: str = 'ethereum', currency: str = 'usd'):
    await ctx.send(f'{CoinGeckoAPI().get_price(ids=coin, vs_currencies=currency.lower())[coin.lower()][currency.lower()]} {currency.upper()}')

def setup(bot):
  bot.add_cog(explorer(bot))
