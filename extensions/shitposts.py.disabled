from discord.ext import commands

class shitposts(commands.Cog, name='Shitposts', description='Eat shit and die'):
  def __init__(self, bot):
    self.bot = bot

  @commands.group(invoke_without_command=True, case_insensitive= True, name='wavedash', aliases=['wave', 'dash'], description='Bounce, bounce, bounce...')
  async def wavedash(self, ctx):
    await ctx.send('<a:bad:839565043859193876><a:bounce1:839557305321259078><a:bad2:839565044249657414><a:bounce3:839557305074188318><a:bad4:839565044127760455><a:bounce5:839557305062391828>' * 2)

  @wavedash.command(name='Badeline', aliases=['bad', 'b'])
  async def badeline(self, ctx):
    await ctx.send('<a:bad:839565043859193876><a:bad1:839565043866796053><a:bad2:839565044249657414><a:bad3:839565043913064468><a:bad4:839565044127760455><a:bad5:839565043599278111>' * 2)

  @wavedash.command(name='Madeline', aliases=['mad', 'm'])
  async def both(self, ctx):
    await ctx.send('<a:bounce0:839557305120063508><a:bounce1:839557305321259078><a:bounce2:839557305053741056><a:bounce3:839557305074188318><a:bounce4:839557305058197546><a:bounce5:839557305062391828>' * 2)

  @commands.command(name='pissed', aliases=['imfuckingpissed'], description='I\'m fucking pissed')
  async def pissed(self, ctx):
    await ctx.send('https://cdn.discordapp.com/attachments/824789288574779393/839563746073903135/pissed.gif')
  
  @commands.command(name='flashbang', description='MY EYES')
  async def flashbang(self, ctx):
    await ctx.send('https://tenor.com/view/flashbang-gif-20496920')
  
  @commands.command(name='chucklenuts', aliases=['meetTheScout'], description='next time eat a salad')
  async def salad(self, ctx):
    await ctx.send('https://cdn.discordapp.com/attachments/331316693941092362/835129887592546355/image0-143.gif')
  
  @commands.command(name='realHelp', aliases=['?help', 'helpUsers'], )
  async def realHelp(self, ctx):
    await ctx.send('https://media.discordapp.net/attachments/471139142353551389/807792787273154601/image0.gif')
  
  @commands.command(name='cocopops', description='Funny fish.')
  async def cocopops(self, ctx):
    await ctx.send('https://media.discordapp.net/attachments/791054037624553482/828391631392604160/redditsave.com_nyy3tnzz67r61.gif')
    
  @commands.command(name='nocopops', description='Sad fish.')
  async def nocopops(self, ctx):
    await ctx.send('https://tenor.com/view/coco-pops-no-coco-pops-goldfish-gif-20372473')
  
  @commands.command(name='woman', description='woman is talking')
  async def woman(self, ctx):
    await ctx.send('https://media.discordapp.net/attachments/710281705235283988/761392520424849408/image0.gif')
  
  @commands.command(name='juan', aliases=['juan.'], description='juan.')
  async def juan(self, ctx):
    await ctx.send('https://cdn.discordapp.com/attachments/824789288574779393/840031880400207872/iu.png')

def setup(bot):
  bot.add_cog(shitposts(bot))
