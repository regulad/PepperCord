import discord
from discord.ext import commands, menus

from utils import checks, bots


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

    def __init__(self, bot):
        self.bot = bot

        self.cooldown = commands.CooldownMapping.from_cooldown(3, 10, commands.BucketType.channel)

    async def cog_check(self, ctx):
        return await checks.is_admin(ctx)

    @commands.Cog.listener()
    async def on_message(self, message):
        ctx = await self.bot.get_context(message)

        try:
            await checks.is_blacklisted(ctx)
        except checks.Blacklisted:
            return

        if ctx.guild is None:
            return  # raise commands.NoPrivateMessage
        elif ctx.guild_document.get("commands") is None:
            return  # raise bots.NotConfigured
        elif ctx.author == self.bot.user or ctx.author == ctx.guild.me:
            return
        elif len(ctx.message.content) == 0:
            return
        else:
            custom_commands = CustomCommand.from_dict(ctx.guild_document.get("commands"))

            command_no_whitespace = ctx.message.content.strip()
            command_words = command_no_whitespace.split()
            effective_command = command_words[0].lower()

            for custom_command in custom_commands:
                if custom_command.command == effective_command:
                    bucket: commands.Cooldown = self.cooldown.get_bucket(ctx.message)
                    retry_after: float = bucket.update_rate_limit()
                    
                    if retry_after:
                        return  # raise commands.CommandOnCooldown(cooldown=bucket, retry_after=retry_after)
                    else:
                        await ctx.send(custom_command.message)
                        break
            else:
                return  # Just for neatness. Not really required since when this loop breaks or fails the task ends.

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
    async def ccadd(self, ctx, command: str, *, message: str):
        await ctx.guild_document.update_db({"$set": {f"commands.{command.lower()}": message}})

    @customcommands.command(
        name="delete",
        aliases=["del", "remove"],
        brief="Deletes a custom command.",
        description="Deletes a custom command from the guild.",
    )
    async def ccdel(self, ctx, *, command: str):
        try:
            ctx.guild_document.get("commands", {})[command.lower()]
        except KeyError:
            raise commands.CommandNotFound(f"""Command "{command}" is not found""")
        else:
            await ctx.guild_document.update_db({"$unset": {f"commands.{command.lower()}": 1}})


def setup(bot):
    bot.add_cog(CustomCommands(bot))
