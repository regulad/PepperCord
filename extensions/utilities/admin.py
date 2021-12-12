import discord
from discord.ext import commands, menus

from utils.bots import CustomContext, BOT_TYPES
from utils.checks import has_permission_level, LowPrivilege
from utils.permissions import Permission, get_permission


class DeleteMenu(menus.ViewMenu):
    """Confirmation menu for deleting server information."""

    async def send_initial_message(
        self, ctx, channel: discord.TextChannel
    ) -> discord.Message:
        return await channel.send(
            "Would you like the bot to leave the server and delete all information? "
            "**Warning**: this process is not reversible.",
            **self._get_kwargs(),
        )

    @menus.button("✅")
    async def confirm(self, payload) -> None:
        await self.message.edit("Deleting...")
        await self.ctx["guild_document"].delete_db()
        await self.ctx.guild.leave()
        self.stop()

    @menus.button("❌")
    async def reject(self, payload) -> None:
        await self.message.edit("Action cancelled.")
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

    @commands.command()
    async def message(
        self,
        ctx: CustomContext,
        channel: discord.TextChannel = commands.Option(
            description="The channel that the message will be sent in.",
        ),
        *,
        text: str,
    ) -> None:
        """Send a message as the bot in a channel of your choosing."""
        channel = ctx.guild.get_channel_or_thread(channel.id)
        await channel.send(text)

    @commands.group()
    async def configuration(self, ctx: CustomContext) -> None:
        """Configure the bot for use in your server."""
        pass

    @configuration.command()
    async def mute(
        self,
        ctx: CustomContext,
        *,
        role: discord.Role = commands.Option(
            description="The role that people will get when they are muted."
        ),
    ) -> None:
        """Chooses a role to give to people when they are muted. This role must already have been created."""
        await ctx["guild_document"].update_db({"$set": {"mute_role": role.id}})
        await ctx.send("Done.", ephemeral=True)

    @configuration.group()
    async def customnsfw(self, ctx: CustomContext) -> None:
        pass

    @customnsfw.command()
    async def add(self, ctx: CustomContext, *, channel: discord.TextChannel) -> None:
        """Add a channel to the list of channels that can be used for NSFW content"""

        await ctx["guild_document"].update_db({"$push": {"customnsfw": channel.id}})
        await ctx.send("Added.", ephemeral=True)

    @customnsfw.command()
    async def remove(self, ctx: CustomContext, *, channel: discord.TextChannel) -> None:
        """Remove a channel to the list of channels that can be used for NSFW content"""

        await ctx["guild_document"].update_db({"$pull": {"customnsfw": channel.id}})
        await ctx.send("Removed.", ephemeral=True)

    @commands.command()
    async def delete(self, ctx: CustomContext) -> None:
        """Deletes all the info about the bot in this server. This cannot be undone."""
        await DeleteMenu().start(ctx, ephemeral=True)


def setup(bot: BOT_TYPES) -> None:
    bot.add_cog(Administration(bot))
