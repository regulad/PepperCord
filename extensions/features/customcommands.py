from enum import Enum
from typing import Optional, List, cast

import discord
from discord.ext import commands, menus

from extensions.features.moderation import mute
from utils import checks, bots
from utils.attachments import find_url_recurse
from utils.localization import Message

KEYWORD_PREFIX: str = "$"


class Keyword(Enum):
    """Represents a keyword that may be executed from a CustomCommand."""

    DELETE_MESSAGE = "del"
    MUTE_MEMBER = "mute"
    KICK_MEMBER = "kick"
    BAN_MEMBER = "ban"

    @classmethod
    def parse(cls, message: str):
        for keyword in cls.__members__.values():
            if KEYWORD_PREFIX + keyword.value in message:
                return keyword

    async def execute(self, ctx: bots.CustomContext) -> None:
        if self is self.__class__.DELETE_MESSAGE:
            await ctx.message.delete()
        elif self is self.__class__.MUTE_MEMBER:
            await mute(ctx.author, guild_document=ctx["guild_document"])
        elif self is self.__class__.KICK_MEMBER:
            await ctx.author.kick()
        elif self is self.__class__.BAN_MEMBER:
            await ctx.author.ban()


class CustomCommand:
    """Represents a custom command."""

    def __init__(self, command: str, message: str):
        self._command: str = command
        self._message: str = message

    @property
    def command(self) -> str:
        return self._command

    @property
    def message(self) -> str:
        return self._message

    @property
    def keyword(self) -> Optional[Keyword]:
        return Keyword.parse(self.message)

    async def execute(self, ctx: bots.CustomContext) -> None:
        if self.keyword is not None:
            await self.keyword.execute(ctx)
        else:
            await ctx.send(self.message)

    @classmethod
    def from_tuple(cls, input_tuple: tuple):
        command = input_tuple[0]
        message = input_tuple[1]
        return cls(command=command, message=message)

    @staticmethod
    def from_dict(input_dict: dict):
        custom_commands = []
        for custom_command_item in input_dict.items():
            custom_command = CustomCommand.from_tuple(custom_command_item)
            custom_commands.append(custom_command)
        return custom_commands


class CustomCommandSource(menus.ListPageSource):
    def __init__(self, data: list[CustomCommand], guild):
        self.guild = guild
        super().__init__(data, per_page=10)

    async def format_page(self, menu, page_entries):
        offset = menu.current_page * self.per_page
        base_embed = discord.Embed(
            title=f"{self.guild.name}'s Custom Commands"
        ).set_thumbnail(url=self.guild.icon.url)
        for iteration, value in enumerate(page_entries, start=offset):
            base_embed.add_field(
                name=f"{iteration + 1}: {value.command}",
                value=f"```{value.message}```",
                inline=False,
            )
        return base_embed


def match_commands(
    possible_commands: List[CustomCommand],
    query: str,
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
    ctx: bots.CustomContext, query: Optional[str] = None
) -> Optional[CustomCommand]:
    query = query or ctx.message.clean_content

    return match_commands(
        CustomCommand.from_dict(ctx["guild_document"].get("commands", [])),
        query,
        ctx["guild_document"].get("cc_is_case_insensitive", True),
        ctx["guild_document"].get("cc_first_word_only", True),
        ctx["guild_document"].get("cc_starts_with", True),
        ctx["guild_document"].get("cc_exact", True),
    )


class CustomCommandDoesNotExist(commands.BadArgument):
    """Raised when a custom command should exist and it does not."""

    pass


class CustomCommandConverter(commands.Converter):
    """Converts an argument into a custom command."""

    async def convert(self, ctx: commands.Context, argument: str) -> CustomCommand:
        custom_ctx: bots.CustomContext = cast(bots.CustomContext, ctx)
        custom_command: Optional[CustomCommand] = get_custom_command_from_guild(
            custom_ctx, argument
        )
        if custom_command is None:
            raise CustomCommandDoesNotExist()
        else:
            return custom_command


class CustomCommands(commands.Cog):
    """Custom commands for just one guild."""

    def __init__(self, bot: bots.BOT_TYPES) -> None:
        self.bot = bot

        self.cooldown = commands.CooldownMapping.from_cooldown(
            3, 10, commands.BucketType.channel
        )

    @commands.Cog.listener()
    async def on_custom_command_success(
        self, custom_command: CustomCommand, ctx: bots.CustomContext
    ) -> None:
        if custom_command.keyword is None:
            await ctx.message.add_reaction("✅")

    @commands.Cog.listener()
    async def on_custom_command_error(
        self,
        custom_command: CustomCommand,
        ctx: bots.CustomContext,
        reason: BaseException,
    ):
        if isinstance(reason, commands.CommandOnCooldown):
            await ctx.message.add_reaction("⏰")
        else:
            await ctx.message.add_reaction("❌")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        ctx: bots.CustomContext = await self.bot.get_context(message)

        if (
            not ctx.author.bot
            and ctx.guild is not None
            and ctx["guild_document"].get("commands") is not None
            and not ctx.valid
        ):
            # Lots of conditions to get here.
            # Oh well, that will happen if you have to make your own command invocation system.

            custom_command: Optional[CustomCommand] = get_custom_command_from_guild(ctx)

            if custom_command is not None:
                ctx.bot.dispatch("custom_command", custom_command, ctx)

                try:
                    bucket: commands.Cooldown = self.cooldown.get_bucket(ctx.message)
                    retry_after: Optional[float] = bucket.update_rate_limit()
                    if retry_after is not None:
                        raise commands.CommandOnCooldown(
                            bucket, retry_after, self.cooldown.type
                        )

                    await custom_command.execute(ctx)
                except Exception as exception:
                    ctx.bot.dispatch(
                        "custom_command_error", custom_command, ctx, exception
                    )
                else:
                    ctx.bot.dispatch("custom_command_success", custom_command, ctx)

    @commands.group(
        invoke_without_command=True,
        case_insensitive=True,
        name="customcommands",
        aliases=["commands", "cc"],
        description="Tools for configuration of custom commands.",
    )
    async def customcommands(self, ctx: bots.CustomContext) -> None:
        commands_dict = ctx["guild_document"].get("commands", {})
        custom_commands = CustomCommand.from_dict(commands_dict)
        source = CustomCommandSource(custom_commands, ctx.guild)
        pages = menus.MenuPages(source=source)
        await pages.start(ctx)

    @customcommands.command(
        name="invoke",
        aliases=["run", "info"],
        brief="Runs a custom command.",
        description="Runs a custom command.",
    )
    @checks.check_is_admin
    async def invoke(
        self, ctx: bots.CustomContext, *, query: CustomCommandConverter
    ) -> None:
        custom_command: CustomCommand = cast(CustomCommand, query)
        await ctx.send(
            ctx["locale"]
            .get_message(Message.CUSTOM_COMMAND_GET)
            .format(cmd=custom_command)
        )

    @customcommands.group(
        invoke_without_command=True,
        case_insensitive=True,
        name="match",
        aliases=["m"],
        description="Sets options for matching invocation keywords in messages.",
    )
    @checks.check_is_admin
    async def match(self, ctx: bots.CustomContext) -> None:
        pass

    @match.command(
        name="case",
        description="Sets case sensitivity.",
    )
    async def case(
        self, ctx: bots.CustomContext, *, is_case_sensitive: bool = False
    ) -> None:
        await ctx["guild_document"].update_db(
            {"$set": {"cc_is_case_insensitive": not is_case_sensitive}}
        )

    @match.command(
        name="firstword",
        aliases=["word"],
        description="Sets if only the first word will be scanned for custom commands.",
    )
    async def word(self, ctx: bots.CustomContext, *, first_word_only: bool = True):
        await ctx["guild_document"].update_db(
            {"$set": {"cc_first_word_only": first_word_only}}
        )

    @match.command(
        name="startswith",
        aliases=["start"],
        description="Sets if the message must start with the custom command for it to register.",
    )
    async def startswith(
        self, ctx: bots.CustomContext, *, must_start_with: bool = True
    ):
        await ctx["guild_document"].update_db(
            {"$set": {"cc_starts_with": must_start_with}}
        )

    @match.command(
        name="exact",
        description="Sets if the message must be exactly the custom command.",
    )
    async def exact(self, ctx: bots.CustomContext, *, must_be_exact: bool = True):
        await ctx["guild_document"].update_db({"$set": {"cc_exact": must_be_exact}})

    @customcommands.command(
        name="add",
        aliases=["set"],
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
    @checks.check_is_admin
    async def ccadd(
        self, ctx: bots.CustomContext, command: str, *, message: Optional[str] = None
    ) -> None:
        message: str = (
            message if message is not None else (await find_url_recurse(ctx.message))[0]
        )
        await ctx["guild_document"].update_db(
            {"$set": {f"commands.{command}": message}}
        )

    @customcommands.command(
        name="delete",
        aliases=["del", "remove"],
        description="Deletes a custom command from the guild.",
    )
    @checks.check_is_admin
    async def ccdel(self, ctx: bots.CustomContext, *, command: str) -> None:
        if (
            ctx["guild_document"].get("commands") is not None
            and ctx["guild_document"]["commands"].get(command) is not None
        ):
            await ctx["guild_document"].update_db(
                {"$unset": {f"commands.{command}": 1}}
            )
        else:
            raise commands.CommandNotFound(f"{command} is not registered.")


def setup(bot: bots.BOT_TYPES):
    bot.add_cog(CustomCommands(bot))
