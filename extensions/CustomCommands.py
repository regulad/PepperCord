from typing import Optional, List

import discord
from discord.ext import commands, menus

from utils import checks, bots
from utils.attachments import find_url_recurse
from extensions.Moderation import mute


async def process_custom_keywords(ctx: bots.CustomContext, message_string: str) -> bool:
    output: bool = False

    if "$del" in message_string:
        await ctx.message.delete()
        output: bool = True

    if "$mute" in message_string:
        await mute(ctx.author, guild_document=ctx.guild_document)
        output: bool = True

    if "$kick" in message_string:
        await ctx.author.kick()
        output: bool = True

    if "$ban" in message_string:
        await ctx.author.ban()
        output: bool = True

    return output


class CustomCommand:
    """Represents a custom command."""

    def __init__(self, command: str, message: str):
        self.command = command
        self.message = message

    @classmethod
    def from_tuple(cls, input_tuple: tuple):
        command = input_tuple[0]
        message = input_tuple[1]
        return cls(command=command, message=message)

    @classmethod
    def from_dict(cls, input_dict: dict):
        custom_commands = []
        for custom_command_item in input_dict.items():
            custom_command = cls.from_tuple(custom_command_item)
            custom_commands.append(custom_command)
        return custom_commands


class CustomCommandSource(menus.ListPageSource):
    def __init__(self, data: list[CustomCommand], guild):
        self.guild = guild
        super().__init__(data, per_page=10)

    async def format_page(self, menu, page_entries):
        offset = menu.current_page * self.per_page
        base_embed = discord.Embed(title=f"{self.guild.name}'s Custom Commands").set_thumbnail(url=self.guild.icon_url)
        for iteration, value in enumerate(page_entries, start=offset):
            base_embed.add_field(
                name=f"{iteration + 1}: {value.command}",
                value=f"```{value.message}```",
                inline=False,
            )
        return base_embed


class CustomCommands(commands.Cog):
    """Custom commands for just one guild."""

    def __init__(self, bot: bots.BOT_TYPES) -> None:
        self.bot = bot

        self.cooldown = commands.CooldownMapping.from_cooldown(3, 10, commands.BucketType.channel)

    async def cog_check(self, ctx: bots.CustomContext) -> None:
        return await checks.is_admin(ctx)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        ctx: bots.CustomContext = await self.bot.get_context(message)

        if len(ctx.message.clean_content.strip()) > 0 \
                and not ctx.author.bot \
                and ctx.guild is not None \
                and ctx.guild_document.get("commands") is not None \
                and not ctx.valid:
            # Lots of conditions to get here.
            # Oh well, that will happen if you have to make your own command invocation system.

            custom_commands: List[CustomCommand] = CustomCommand.from_dict(ctx.guild_document["commands"])

            for custom_command in custom_commands:
                if custom_command.command in ctx.message.clean_content.strip() \
                        if ctx.guild_document.get("ccmatch", False) \
                        else ctx.message.clean_content.split()[0].lower() == custom_command.command.lower():
                    command: CustomCommand = custom_command
                    break  # We found our command!
            else:
                return  # No command.

            bucket: commands.Cooldown = self.cooldown.get_bucket(ctx.message)
            retry_after: float = bucket.update_rate_limit()

            try:
                processed: bool = await process_custom_keywords(ctx, command.message)
            except discord.DiscordException:
                await ctx.message.add_reaction("❌")
                return  # Something nasty happened.

            if retry_after:
                await ctx.message.add_reaction("⏰")  # User is being rate-limited!
            elif not processed:
                await ctx.send(command.message)
            else:
                try:
                    await ctx.message.add_reaction("✅")
                except discord.NotFound:
                    return  # Message likely got deleted during keyword processing.

    @commands.group(
        invoke_without_command=True,
        case_insensitive=True,
        name="customcommands",
        aliases=["commands", "cc"],
        brief="Tools for configuration of custom commands.",
        description="Tools for configuration of custom commands.",
    )
    async def customcommands(self, ctx: bots.CustomContext) -> None:
        commands_dict = ctx.guild_document.get("commands", {})
        custom_commands = CustomCommand.from_dict(commands_dict)
        source = CustomCommandSource(custom_commands, ctx.guild)
        pages = menus.MenuPages(source=source)
        await pages.start(ctx)

    @customcommands.command(
        name="match",
        aliases=["m"],
        brief="Sets options for matching invocation keywords in messages.",
        description="Sets options for matching invocation keywords in messages.\n\n"
                    "* True: A command will be invoked if the command is found anywhere in the message."
                    "Commands are case-sensitive.\n"
                    "* False: "
                    "A command will only be invoked if the command is found in the first word of a message. "
                    "Commands are not case-sensitive.\n\n"
                    "The default is False."
    )
    @commands.check(checks.is_admin)
    async def match(self, ctx: bots.CustomContext, match: bool) -> None:
        await ctx.guild_document.update_db({"$set": {"ccmatch": match}})

    @customcommands.command(
        name="add",
        aliases=["set"],
        brief="Adds a custom command.",
        description="Adds a custom command to the guild.\n"
                    "Custom commands are case-sensitive (by default), "
                    "and both the invocation keyword and the message must be placed in quotes if they are multiple "
                    "words.\n"
                    "If a Message is not specified, the most recently sent media will be used.\n\n"
                    "If a ⏰ is added to the message, it means you are being rate-limited.\n\n"
                    "Commands can contain special keywords that perform certain actions:\n\n"
                    "* $del: Deletes the message that invoked the command.\n"
                    "* $mute: Mutes the sender.\n"
                    "* $kick: Kicks the sender.\n"
                    "* $ban: Bans the sender.",
        usage="<Keyword> [Message]",
    )
    @commands.check(checks.is_admin)
    async def ccadd(self, ctx: bots.CustomContext, command: str, *, message: Optional[str] = None) -> None:
        message: str = message if message is not None else (await find_url_recurse(ctx.message))[0]
        await ctx.guild_document.update_db({"$set": {f"commands.{command}": message}})

    @customcommands.command(
        name="delete",
        aliases=["del", "remove"],
        brief="Deletes a custom command.",
        description="Deletes a custom command from the guild.",
    )
    @commands.check(checks.is_admin)
    async def ccdel(self, ctx: bots.CustomContext, *, command: str) -> None:
        if ctx.guild_document.get("commands") is not None \
                and ctx.guild_document["commands"].get(command) is not None:
            await ctx.guild_document.update_db({"$unset": {f"commands.{command}": 1}})
        else:
            raise commands.CommandNotFound(f"{command} is not registered.")


def setup(bot: bots.BOT_TYPES):
    bot.add_cog(CustomCommands(bot))
