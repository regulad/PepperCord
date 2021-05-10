import nekos
from pycoingecko import CoinGeckoAPI
from discord.ext import commands
from discord.ext.commands.cooldowns import BucketType
from tools.errors import SubcommandNotFound

class explorer(commands.Cog, name='Internet Data', description='Gets random information from the internet. Some are productive, most arent.'):
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
  
  @commands.group(invoke_without_command=True, case_insensitive=True, name='nekosdev', aliases=['neko'], description='Get data from https//nekos.life/api/v2/', brief='Get data from nekos.life')
  async def nekosdev(self, ctx):
    raise SubcommandNotFound()
  
  @nekosdev.command(name='eightball')
  async def eightball(self, ctx):
    await ctx.send(nekos.eightball())
  
  @nekosdev.command(name='img', usage='[https://github.com/Nekos-life/nekos.py/blob/master/nekos/nekos.py#L17#L27]')
  @commands.is_nsfw()
  async def img(self, ctx, *, target: str = 'random_hentai_gif'):
    await ctx.send(nekos.img(target))

  @nekosdev.command(name='owoify')
  async def owoify(self, ctx, *, text: str = 'OwO'):
    await ctx.send(nekos.owoify(text))

  @nekosdev.command(name='cat')
  async def cat(self, ctx):
    await ctx.send(nekos.cat())

  @nekosdev.command(name='textcat')
  async def textcat(self, ctx):
    await ctx.send(nekos.textcat())

  @nekosdev.command(name='why')
  async def why(self, ctx):
    await ctx.send(nekos.why())

  @nekosdev.command(name='fact')
  async def fact(self, ctx):
    await ctx.send(nekos.fact())

def setup(bot):
  bot.add_cog(explorer(bot))
