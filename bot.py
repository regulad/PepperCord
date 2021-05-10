from tools.managers import ConfigManager
from tools.errors import SubcommandNotFound
import discord
from discord.ext import commands
from pretty_help import PrettyHelp

activeConfigManager = ConfigManager()
bot = commands.Bot(command_prefix=commands.when_mentioned_or(activeConfigManager.readKey('discord.commands.prefix')), case_insensitive=True, intents=discord.Intents.all())
bot.help_command = PrettyHelp(color=discord.Colour.orange())
cooldown = commands.CooldownMapping.from_cooldown(6.0, 10.0, commands.BucketType.user)

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
  if isinstance(e, (commands.CheckFailure, commands.CommandOnCooldown)) and await bot.is_owner(ctx.author):
    await ctx.send('You shouldn\'t be able to execute this command, but since you are the owner you get a free pass.')
    await ctx.reinvoke()
  elif isinstance(e, commands.BotMissingPermissions):
    await ctx.send(f'I\'m missing permissions I need to function. To re-invite me, see `{ctx.prefix}invite`.')
  elif isinstance(e, commands.NSFWChannelRequired):
    await ctx.send('No horny! A NSFW channel is required to execute this command.')
  elif isinstance(e, commands.CommandOnCooldown):
    await ctx.send(f'Slow the brakes, speed racer! We don\'t want any rate limiting... Try executing your command again in `{round(e.retry_after, 1)}` seconds.')
  elif isinstance(e, commands.UserInputError):
    await ctx.send(f'Command is valid, but input is invalid. Try `{ctx.prefix}help {ctx.command}`.')
  elif isinstance(e, commands.CheckFailure):
    await ctx.send('You cannot run this command.')
  elif isinstance(e, SubcommandNotFound):
    await ctx.send(f'You need to specify a subcommand. Try `{ctx.prefix}help`.')
  elif isinstance(e, commands.CommandNotFound):
    await ctx.send(f'Couldn\'t find {ctx.command}. Try `{ctx.prefix}help`.')
  elif isinstance(e, commands.CommandError):
    await ctx.send('An error occured processing your command. Try again.')
  else:
    await ctx.send(f'Something went very wrong while processing your command. This can be caused by bad arguments or something worse. Execption: ```{e}``` You can contact support with `{ctx.prefix}support`.')
