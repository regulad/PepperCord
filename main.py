"""
Regulad's PepperCord
https://github.com/regulad/PepperCord
"""

import logging
import os
import pathlib

import discord
from art import text2art
from discord.ext import commands
from pretty_help import PrettyHelp

import instances
from utils import errors, managers

logger = logging.getLogger("discord")
logger.setLevel(logging.INFO)
if not pathlib.Path("logs/").exists():
    os.mkdir("logs/")
handler = logging.FileHandler(filename="logs/peppercord.log", encoding="utf-8", mode="a+")
handler.setFormatter(logging.Formatter("%(asctime)s:%(levelname)s:%(name)s: %(message)s"))
logger.addHandler(handler)


async def get_prefix(bot, message):
    if message.guild is None:
        return commands.when_mentioned_or(instances.config_instance["discord"]["commands"]["prefix"])(bot, message)
    else:
        guild_prefix = managers.GuildConfigManager(
            message.guild,
            instances.activeDatabase["servers"],
            "prefix",
            instances.config_instance["discord"]["commands"]["prefix"],
        ).read()
        return commands.when_mentioned_or(guild_prefix)(bot, message)


bot = commands.Bot(
    command_prefix=get_prefix,
    case_insensitive=True,
    intents=discord.Intents.all(),
    help_command=PrettyHelp(color=discord.Colour.orange()),
)
cooldown = commands.CooldownMapping.from_cooldown(
    instances.config_instance["discord"]["commands"]["cooldown"]["rate"],
    instances.config_instance["discord"]["commands"]["cooldown"]["per"],
    commands.BucketType.user,
)


def load_extensions(path: str):
    for file in os.listdir(path):
        if file.endswith(".py"):
            full_path = path + file
            try:
                bot.load_extension(full_path.strip(".py").replace("/", "."))
            except Exception as e:
                print(f"{e}\nContinuing recursively")


@bot.event
async def on_ready():
    print(
        f"{text2art(text=bot.user.name, font='rnd-large')}\nLogged in as {bot.user.name}#{bot.user.discriminator} ({bot.user.id})"
    )


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
        await ctx.reinvoke()
    elif isinstance(e, commands.BotMissingPermissions):
        await ctx.send(f"I'm missing permissions I need to function. To re-invite me, see `{ctx.prefix}invite`.")
    elif isinstance(e, commands.NSFWChannelRequired):
        await ctx.send("No horny! A NSFW channel is required to execute this command.")
    elif isinstance(e, commands.CommandOnCooldown):
        await ctx.send(
            f"Slow the brakes, speed racer! We don't want any rate limiting... Try executing your command again in `{round(e.retry_after, 1)}` seconds."
        )
    elif isinstance(e, commands.UserInputError):
        await ctx.send(f"Command is valid, but input is invalid. Try `{ctx.prefix}help {ctx.command}`.")
    elif isinstance(e, commands.CheckFailure):
        await ctx.send("You cannot run this command.")
    elif isinstance(e, errors.SubcommandNotFound):
        await ctx.send(f"You need to specify a subcommand. Try `{ctx.prefix}help`.")
    elif isinstance(e, errors.NotConfigured):
        await ctx.send("This command must be configured first. Ask an admin.")
    elif isinstance(e, commands.CommandNotFound):
        await ctx.send(f"{e}. Try `{ctx.prefix}help`.")
    elif isinstance(e, commands.CommandError):
        await ctx.send("An error occured processing your command. Try again.")
    else:
        await ctx.send(
            f"Something went very wrong while processing your command. This can be caused by bad arguments or something worse. Execption: ```{e}``` You can contact support with `{ctx.prefix}support`."
        )


if __name__ == "__main__":
    bot.load_extension("jishaku")
    load_extensions(instances.config_instance["extensions"]["dir"])
    bot.run(instances.config_instance["discord"]["api"]["token"])
