import discord
from discord.ext import commands, menus

from utils import checks


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

    @property
    def as_dict(self):
        return {self.command: self.message}


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

    def __init__(self, bot):
        self.bot = bot

    async def cog_check(self, ctx):
        return await checks.is_admin(ctx)

    @commands.Cog.listener()
    async def on_message(self, message):
        ctx = await self.bot.get_context(message)

        if ctx.author == self.bot.user or ctx.author == ctx.guild.me:
            return
        if ctx.guild is None:
            return

        try:
            commands_dict = ctx.guild_document["commands"]
        except KeyError:
            return

        if len(ctx.message.content) == 0:
            return
        else:
            command_no_whitespace = ctx.message.content.strip()
            command_words = command_no_whitespace.split()
            effective_command = command_words[0]

        custom_commands = CustomCommand.from_dict(commands_dict)

        for custom_command in custom_commands:
            if custom_command.command == effective_command:
                await ctx.send(custom_command.message)
                break

    @commands.group(
        invoke_without_command=True,
        case_insensitive=True,
        name="customcommands",
        aliases=["commands", "cc"],
        brief="Tools for configuration of custom commands.",
        description="Tools for configuration of custom commands.",
    )
    async def customcommands(self, ctx):
        commands_dict = ctx.guild_document.setdefault("commands", {})
        custom_commands = CustomCommand.from_dict(commands_dict)
        source = CustomCommandSource(custom_commands, ctx.guild)
        pages = menus.MenuPages(source=source)
        await pages.start(ctx)

    @customcommands.command(
        name="add", aliases=["set"], brief="Adds a custom command.", description="Adds a custom command to the guild."
    )
    async def ccadd(self, ctx, command: str, message: str):
        custom_command = CustomCommand(command=command, message=message)
        ctx.guild_document.setdefault("commands", {}).update(custom_command.as_dict)
        await ctx.guild_document.replace_db()

    @customcommands.command(
        name="delete",
        aliases=["del", "remove"],
        brief="Deletes a custom command.",
        description="Deletes a custom command from the guild.",
    )
    async def ccdel(self, ctx, command: str):
        try:
            del ctx.guild_document.setdefault("commands", {})[command]
        except KeyError:
            raise commands.CommandNotFound(f"""Command "{command}" is not found""")
        else:
            await ctx.guild_document.replace_db()


def setup(bot):
    bot.add_cog(CustomCommands(bot))
