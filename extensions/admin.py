import discord
from discord.ext import commands, menus
from discord.ext.menus import views

from utils.checks import has_permission_level, LowPrivilege
from utils.permissions import Permission, get_permission
from utils.bots import CustomContext, BOT_TYPES
from utils.converters import LocaleConverter
from utils.localization import Message


class DeleteMenu(views.ViewMenu):
    """Confirmation menu for deleting server information."""

    async def send_initial_message(self, ctx, channel) -> discord.Message:
        return await self.send_with_view(
            channel,
            "**Warning:** This action is destructive. *Please* only continue if you know what you are doing."
        )

    @menus.button("✅")
    async def confirm(self, interaction: discord.Interaction) -> None:
        await self.message.edit(content="Deleting guild information...")
        await self.ctx.guild_document.delete_db()
        await self.ctx.guild.leave()
        self.stop()

    @menus.button("❌")
    async def reject(self, interaction: discord.Interaction) -> None:
        await self.message.edit(content="Operation cancelled.")
        self.stop()

    async def prompt(self, ctx):
        await self.start(ctx)


class Administration(commands.Cog):
    """Tools for administrating and configuring guilds."""

    def __init__(self, bot: BOT_TYPES) -> None:
        self.bot = bot

    async def cog_check(self, ctx: CustomContext) -> bool:
        if not await has_permission_level(ctx, Permission.ADMINISTRATOR):
            raise LowPrivilege(Permission.ADMINISTRATOR, get_permission(ctx))
        else:
            return True

    @commands.command(
        name="message",
        brief="Send a message as the bot.",
        description="Send a message as the bots in any channel that you want.",
        usage="<Channel> <Message>",
    )
    async def do_message(self, ctx: CustomContext, channel: discord.TextChannel, *, text: str) -> None:
        channel = ctx.bot.get_channel(channel.id)
        await channel.send(text)

    @commands.group(
        invoke_without_command=True,
        case_insensitive=True,
        name="configuration",
        aliases=["config"],
        brief="Configures bots.",
        description="Configures bots in the scope of this server.",
    )
    async def config(self, ctx: CustomContext) -> None:
        pass

    @config.command(
        name="mute",
        brief="Sets role used to mute people.",
        description="Sets the role that is given to people who are muted. It must already be configured.",
    )
    async def mute(self, ctx: CustomContext, *, role: discord.Role) -> None:
        await ctx.guild_document.update_db({"$set": {"mute_role": role.id}})

    @config.command(
        name="locale",
        brief="Sets the server's locale.",
        description="Sets the server's locale. Supported locales:\n\n"
                    "* en_US\n"
                    "* catspeak",
    )
    async def locale(self, ctx: CustomContext, *, locale: LocaleConverter) -> None:
        await ctx.guild_document.update_db({"$set": {"locale": locale.name}})
        await ctx.send(ctx.locale.get_message(Message.SELECT_LANG))
        # TODO: Implement localization system wherever possible.

    @commands.command(
        name="delete",
        aliases=["leave"],
        brief="Deletes all data on the server, then leaves.",
        description="Deletes all the data the bots has collected and stored on this server, then leaves. Be careful!",
    )
    async def delete(self, ctx: CustomContext) -> None:
        await DeleteMenu().start(ctx)


def setup(bot: BOT_TYPES) -> None:
    bot.add_cog(Administration(bot))
