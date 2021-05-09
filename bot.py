from tools.managers import ConfigManager
import discord
from discord.ext import commands
from pretty_help import PrettyHelp

activeConfigManager = ConfigManager()
bot = commands.Bot(command_prefix=commands.when_mentioned_or(activeConfigManager.readKey('discord.commands.prefix')), case_insensitive=True, intents=discord.Intents.all())
bot.help_command = PrettyHelp(color=discord.Colour.orange())
cooldown = commands.CooldownMapping.from_cooldown(4.0, 10.0, commands.BucketType.user)

@bot.check_once
async def bot_check_once(ctx):
  bucket = cooldown.get_bucket(ctx.message)
  retry_after = bucket.update_rate_limit()
  if retry_after:
    raise commands.CommandOnCooldown(bucket, retry_after)
  else:
    return True

@bot.event
async def on_command_error(ctx, e):
  if isinstance(e, commands.CommandOnCooldown):
    await ctx.send(f'Slow the brakes, speed racer! We don\'t want any rate limiting... Try executing your command again in `{round(e.retry_after, 1)}` seconds.')
  elif isinstance(e, commands.CommandNotFound):
    await ctx.send(f'{e}.')
  elif isinstance(e, commands.BadArgument) or isinstance(e, commands.BadUnionArgument):
    await ctx.send(f'Your arguments are invalid. Try `{ctx.prefix}help {ctx.command}`')
  else:
    await ctx.send('An error occured processing your command.')
