import datetime
from enum import Enum
from typing import Any, Optional, List, Self, Sequence, cast

import discord
from discord.app_commands import describe
from discord.app_commands import guild_only as ac_guild_only
from discord.ext import commands, menus
from discord.ext.commands import hybrid_group, guild_only

from discord.ext.menus import ListPageSource, MenuPages
from utils.attachments import find_url_recurse
from utils.bots.bot import CustomBot
from utils.bots.context import CustomContext


class CustomCommand:
    """Represents a custom command."""

    def __init__(self, command: str, message: str):
        self._command = command
        self._message = message

    @property
    def command(self) -> str:
        return self._command

    @property
    def message(self) -> str:
        return self._message

    async def execute(self, ctx: CustomContext) -> None:
        await ctx.reply(self.message, mention_author=False)

    @classmethod
    def from_tuple(cls, input_tuple: tuple[str, str]) -> Self:
        command = input_tuple[0]
        message = input_tuple[1]
        return cls(command=command, message=message)

    @classmethod
    def from_dict(cls, input_dict: dict[str, str]) -> Sequence[Self]:
        custom_commands = []
        for custom_command_item in input_dict.items():
            custom_command = cls.from_tuple(custom_command_item)
            custom_commands.append(custom_command)
        return custom_commands


class CustomCommandSource(
    ListPageSource[
        CustomCommand, MenuPages[CustomBot, CustomContext, "CustomCommandSource"]
    ]
):
    def __init__(self, data: Sequence[CustomCommand], guild: discord.Guild) -> None:
        self.guild = guild
        super().__init__(data, per_page=10)

    async def format_page(
        self,
        menu: MenuPages[CustomBot, CustomContext, "CustomCommandSource"],
        page_entries: list[CustomCommand] | CustomCommand,
    ) -> discord.Embed:
        assert isinstance(
            page_entries, list
        )  # guaranteed at runtime by per_page being > 1

        offset = menu.current_page * self.per_page
        base_embed = discord.Embed(title=f"{self.guild.name}'s Custom Commands")
        base_embed.set_footer(
            text=f"Page {menu.current_page + 1}/{self.get_max_pages()}"
        )
        if self.guild.icon is not None:
            base_embed.set_thumbnail(url=self.guild.icon.url)
        for iteration, value in enumerate(page_entries, start=offset):
            base_embed.add_field(
                name=f"{iteration + 1}: {value.command}",
                value=f"```{value.message}```",
                inline=False,
            )
        return base_embed


def match_commands(
    possible_commands: Sequence[CustomCommand],
    query: str,
    *,
    case_insensitive: bool = True,
    first_word_only: bool = True,
    starts_with: bool = True,
    exact: bool = True,
) -> Optional[CustomCommand]:
    """Attempts to find a CustomCommand from a list of CustomCommands."""

    if first_word_only:
        query = query.strip().split()[0] if len(query.strip().split()) > 0 else ""

    for possible_command in possible_commands:
        if (
            case_insensitive
            and (
                (exact and query.lower() == possible_command.command.lower())
                or (
                    not exact
                    and (
                        (
                            starts_with
                            and query.lower().startswith(
                                possible_command.command.lower()
                            )
                        )
                        or (
                            not starts_with
                            and possible_command.command.lower() in query.lower()
                        )
                    )
                )
            )
            or (
                not case_insensitive
                and (
                    (exact and query == possible_command.command)
                    or (
                        not exact
                        and (
                            (starts_with and query.startswith(possible_command.command))
                            or (not starts_with and possible_command.command in query)
                        )
                    )
                )
            )
        ):
            return possible_command
        else:
            continue
    else:
        return None  # No CC found


def get_custom_command_from_guild(
    ctx: CustomContext, query: Optional[str] = None
) -> Optional[CustomCommand]:
    query = query or ctx.message.clean_content

    return match_commands(
        CustomCommand.from_dict(ctx["guild_document"].get("commands", [])),
        query,
        case_insensitive=ctx["guild_document"].get("cc_is_case_insensitive", True),
        first_word_only=ctx["guild_document"].get("cc_first_word_only", True),
        starts_with=ctx["guild_document"].get("cc_starts_with", True),
        exact=ctx["guild_document"].get("cc_exact", True),
    )


class CustomCommandDoesNotExist(commands.BadArgument):
    """Raised when a custom command should exist and it does not."""

    pass


class CustomCommandConverter(commands.Converter[CustomCommand]):
    """Converts an argument into a custom command."""

    async def convert(self, ctx: commands.Context[Any], argument: str) -> CustomCommand:
        custom_ctx = cast(CustomContext, ctx)  # known at runtime
        custom_command = get_custom_command_from_guild(custom_ctx, argument)
        if custom_command is None:
            raise CustomCommandDoesNotExist()
        else:
            return custom_command


class CustomCommands(commands.Cog):
    """Create commands unique to your server! You can configure keywords to send something when a user sends a certain keyword."""

    def __init__(self, bot: CustomBot) -> None:
        self.bot = bot

        self.cooldown = commands.CooldownMapping.from_cooldown(
            3, 10, commands.BucketType.channel
        )

    @commands.Cog.listener()
    async def on_custom_command_success(
        self, custom_command: CustomCommand, ctx: CustomContext
    ) -> None:
        await ctx.message.add_reaction("✅")

    @commands.Cog.listener()
    async def on_custom_command_error(
        self,
        custom_command: CustomCommand,
        ctx: CustomContext,
        reason: BaseException,
    ) -> None:
        if isinstance(reason, commands.CommandOnCooldown):
            await ctx.message.add_reaction("⏰")
        else:
            await ctx.message.add_reaction("❌")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        ctx = await self.bot.get_context(message, cls=CustomContext)

        if (
            not ctx.author.bot
            and ctx.guild is not None
            and ctx["guild_document"].get("commands") is not None
            and not ctx.valid
        ):
            # Lots of conditions to get here.
            # Oh well, that will happen if you have to make your own command invocation system.

            custom_command = get_custom_command_from_guild(ctx)

            if custom_command is None:
                return

            ctx.bot.dispatch("custom_command", custom_command, ctx)

            try:
                bucket = cast(
                    commands.Cooldown, self.cooldown.get_bucket(ctx.message)
                )  # guaranteed at runtime
                retry_after = bucket.update_rate_limit()

                if retry_after is not None and isinstance(
                    self.cooldown.type, commands.BucketType
                ):
                    raise commands.CommandOnCooldown(
                        bucket, retry_after, self.cooldown.type
                    )
                elif retry_after is not None:
                    # Not sure why we would get here.
                    raise commands.CommandOnCooldown(
                        bucket, retry_after, commands.BucketType.default
                    )

                await custom_command.execute(ctx)
            except Exception as exception:
                ctx.bot.dispatch("custom_command_error", custom_command, ctx, exception)
            else:
                ctx.bot.dispatch("custom_command_success", custom_command, ctx)

    @hybrid_group(aliases=["cc"], fallback="list")  # type: ignore[arg-type]  # valid at runtime; bad d.py type
    @ac_guild_only()
    @guild_only()
    async def customcommands(self, ctx: CustomContext) -> None:
        """Lists all custom commands currently on the server."""
        assert ctx.guild is not None  # guaranteed at runtime with checks
        commands_dict = ctx["guild_document"].get("commands", {})
        custom_commands = CustomCommand.from_dict(commands_dict)
        source = CustomCommandSource(custom_commands, ctx.guild)
        pages: menus.MenuPages[CustomBot, CustomContext, CustomCommandSource] = (
            menus.MenuPages(source=source)
        )
        await pages.start(ctx)

    @customcommands.command()  # type: ignore[arg-type]  # valid at runtime; bad d.py type
    @commands.has_permissions(administrator=True)
    @guild_only()
    async def find(self, ctx: CustomContext, *, query: CustomCommandConverter) -> None:
        """Fetch a custom command using the name of one."""
        cmd: CustomCommand = cast(CustomCommand, query)
        await ctx.send(
            f'The custom command "{cmd.command}" has the message "{cmd.message}".',
            ephemeral=True,
        )

    @customcommands.group(aliases=["m"], invoke_without_command=True)  # type: ignore[arg-type]  # valid at runtime; bad d.py type
    @commands.has_permissions(administrator=True)
    @guild_only()
    async def match(self, ctx: CustomContext) -> None:
        pass

    @match.command()  # type: ignore[arg-type]  # valid at runtime; bad d.py type
    @guild_only()
    async def case(
        self, ctx: CustomContext, *, is_case_sensitive: bool = False
    ) -> None:
        """Configures case sensitivity of the CustomCommand finder."""
        await ctx["guild_document"].update_db(
            {"$set": {"cc_is_case_insensitive": not is_case_sensitive}}
        )
        await ctx.send("Settings updated.", ephemeral=True)

    @match.command()  # type: ignore[arg-type]  # valid at runtime; bad d.py type
    @guild_only()
    async def firstword(
        self, ctx: CustomContext, *, first_word_only: bool = True
    ) -> None:
        """Configures if only the first word of a message should be checked for a custom command."""
        await ctx["guild_document"].update_db(
            {"$set": {"cc_first_word_only": first_word_only}}
        )
        await ctx.send("Settings updated.", ephemeral=True)

    @match.command()  # type: ignore[arg-type]  # valid at runtime; bad d.py type
    @guild_only()
    async def startswith(
        self, ctx: CustomContext, *, must_start_with: bool = True
    ) -> None:
        """Configures if only the start of a message should be checked for a custom command."""
        await ctx["guild_document"].update_db(
            {"$set": {"cc_starts_with": must_start_with}}
        )
        await ctx.send("Settings updated.", ephemeral=True)

    @match.command()  # type: ignore[arg-type]  # valid at runtime; bad d.py type
    async def exact(self, ctx: CustomContext, *, must_be_exact: bool = True) -> None:
        """Configures if only the start of a message should be checked for a custom command."""
        await ctx["guild_document"].update_db({"$set": {"cc_exact": must_be_exact}})
        await ctx.send("Settings updated.", ephemeral=True)

    @customcommands.command()  # type: ignore[arg-type]  # valid at runtime; bad d.py type
    @commands.has_permissions(administrator=True)
    @describe(
        command="The command that must be sent.",
        message="The message that the bot will respond with. Defaults to the most recently sent image.",
    )
    @guild_only()
    async def add(
        self,
        ctx: CustomContext,
        command: str,
        *,
        message: Optional[str] = None,
    ) -> None:
        """
        Adds a custom command to the guild.
        Custom commands are case-sensitive (by default) and both the invocation keyword and the message must be placed in quotes if they are multiple words.
        If a Message is not specified, the most recently sent media will be used.
        If a ⏰ is added to the message, it means you are being rate-limited.
        """
        message = (
            message
            if message is not None
            else (await find_url_recurse(ctx.message, ctx.bot))[0]
        )
        await ctx["guild_document"].update_db(
            {"$set": {f"commands.{command}": message}}
        )
        await ctx.send("Custom command added.", ephemeral=True)

    @customcommands.command()  # type: ignore[arg-type]  # valid at runtime; bad d.py type
    @commands.has_permissions(administrator=True)
    @describe(command="The command to be removed.")
    @guild_only()
    async def delete(
        self,
        ctx: CustomContext,
        *,
        command: str,
    ) -> None:
        """Deletes a custom command from the guild."""
        if (
            ctx["guild_document"].get("commands") is not None
            and ctx["guild_document"]["commands"].get(command) is not None
        ):
            await ctx["guild_document"].update_db(
                {"$unset": {f"commands.{command}": 1}}
            )
            await ctx.send("Custom command removed.", ephemeral=True)
        else:
            raise commands.CommandNotFound(f"{command} is not registered.")


async def setup(bot: CustomBot) -> None:
    await bot.add_cog(CustomCommands(bot))
