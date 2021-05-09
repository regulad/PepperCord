from tools.managers.configManager import configManager
import discord
from discord.ext import commands
from pretty_help import PrettyHelp

activeConfigManager = configManager()
bot = commands.Bot(command_prefix=activeConfigManager.readKey('discord.prefix'), case_insensitive=True, intents=discord.Intents.all())
bot.help_command = PrettyHelp(color=discord.Colour.orange())
cooldown = commands.CooldownMapping.from_cooldown(1.0, 3.0, commands.BucketType.user)

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
    await ctx.send(e)
