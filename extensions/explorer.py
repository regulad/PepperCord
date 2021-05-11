import nekos, discord
from mcstatus import MinecraftServer
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
  
  @commands.group(invoke_without_command=True, case_insensitive=True, name='neko', aliases=['nekos'], description='Get data from https//nekos.life/api/v2/', brief='Get data from nekos.life')
  async def neko(self, ctx):
    raise SubcommandNotFound()
  
  @neko.command(name='eightball', aliases=['8ball'])
  async def eightball(self, ctx):
    eightball = nekos.eightball()
    embed = discord.Embed(colour=discord.Colour.blurple(), title=eightball.text).set_image(url=eightball.image)
    await ctx.send(embed=embed)
  
  @neko.command(name='img', usage='[https://github.com/Nekos-life/nekos.py/blob/master/nekos/nekos.py#L17#L27]')
  @commands.is_nsfw()
  async def img(self, ctx, *, target: str = 'random_hentai_gif'):
    await ctx.send(nekos.img(target))

  @neko.command(name='owoify')
  async def owoify(self, ctx, *, text: str = 'OwO'):
    await ctx.send(nekos.owoify(text))

  @neko.command(name='cat')
  async def cat(self, ctx):
    await ctx.send(nekos.cat())

  @neko.command(name='textcat')
  async def textcat(self, ctx):
    await ctx.send(nekos.textcat())

  @neko.command(name='why')
  async def why(self, ctx):
    await ctx.send(nekos.why())

  @neko.command(name='fact')
  async def fact(self, ctx):
    await ctx.send(nekos.fact())
  
  @commands.command(name='minecraft', aliases=['mcstatus'], description='Gets Minecraft Server status using mcstatus.', brief='Gets Minecraft Server.')
  async def minecraft(self, ctx, *, server: str = 'play.regulad.xyz'):
    serverLookup = MinecraftServer.lookup(server)
    try:
      status = serverLookup.status()
    except:
      await ctx.send('Couldn\'t get information from the server. Is it online?')
    else:
      embed = discord.Embed(colour=discord.Colour.dark_gold(), title=server).add_field(name='Ping:', value=f'{status.latency}ms').add_field(name='Players:', value=f'{status.players.online} players')
      await ctx.send(embed=embed)

def setup(bot):
  bot.add_cog(explorer(bot))
