import typing

import discord
from discord.ext import commands, menus

from utils import checks, permissions, bots


class DeleteMenu(menus.Menu):
    """Confirmation menu for deleting server information."""

    def __init__(
        self,
        *,
        timeout=180.0,
        delete_message_after=False,
        clear_reactions_after=False,
        check_embeds=False,
        message=None,
    ):
        self.result = None

        super().__init__(
            timeout=timeout,
            delete_message_after=delete_message_after,
            clear_reactions_after=clear_reactions_after,
            check_embeds=check_embeds,
            message=message,
        )

    async def send_initial_message(self, ctx, channel):
        return await ctx.send(
            "**Warning:** This action is destructive. *Please* only continue if you know what you are doing."
        )

    @menus.button("✅")
    async def confirm(self, payload):
        await self.message.edit(content="Deleting guild information...")
        self.result = True
        self.stop()

    @menus.button("❌")
    async def reject(self, payload):
        await self.message.edit(content="Operation cancelled.")
        self.result = False
        self.stop()

    async def prompt(self, ctx):
        await self.start(ctx, wait=True)
        return self.result


class Administration(commands.Cog):
    """Tools for administrating and configuring guilds."""

    def __init__(self, bot):
        self.bot = bot

    async def cog_check(self, ctx):
        return await checks.is_admin(ctx)

    @commands.command(
        name="message",
        brief="Send a message as the bots.",
        description="Send a message as the bots in any channel that you want.",
        usage="<Channel> <Message>",
    )
    async def do_message(self, ctx, channel: discord.TextChannel, *, text: str):
        channel = ctx.bot.get_channel(channel.id)
        await channel.send(text)

    @commands.group(
        invoke_without_command=True,
        case_insensitive=True,
        name="permissions",
        aliases=["perms", "priv", "privileges"],
        brief="Change server permissions.",
        description="Read & write permissions of various entities on the server. Level 0 means that the entity has no permissions, level 1 means that they have manager permissions (think controlling music or reading audit logs), level 2 means that they have moderator privileges, and level 3 means that they have administrator privileges.",
    )
    async def permissions(self, ctx):
        pass

    @permissions.command(
        name="disable",
        aliases=["off", "delete"],
        brief="Deletes permission data.",
        description="Deletes all permission data. This reverts permissions to their initial state.",
    )
    async def sdisable(self, ctx):
        try:
            ctx.guild_document["permissions"]
        except KeyError:
            raise bots.NotConfigured
        await ctx.guild_document.update_db({"$unset": {"permissions": 1}})

    @permissions.command(
        name="read",
        brief="Displays permission level of entity.",
        description="Gets raw permission level from member or role.",
        usage="[Member|Role]",
    )
    async def read(self, ctx, *, entity: typing.Optional[typing.Union[discord.Member, discord.Role]]):
        entity = entity or ctx.author
        perms = permissions.GuildPermissionManager(ctx)
        await ctx.send(f"{entity.name} has permission level `{await perms.read(entity)}`")

    @permissions.command(
        name="write",
        brief="Write permission level of a role.",
        description="Writes given permission level into a role. Valid options include: Manager, Moderator, and Administrator.",
        usage="[Permission Level (Admin)] <Role>",
    )
    async def write(self, ctx, value: typing.Optional[str], *, entity: discord.Role):
        value = value or "Admin"
        if value == "Admin" or value == "Administrator" or value == "admin" or value == "administrator":
            attribute = permissions.Permissions.ADMINISTRATOR
        elif value == "Mod" or value == "Moderator" or value == "mod" or value == "moderator":
            attribute = permissions.Permissions.MODERATOR
        elif value == "Man" or value == "Manager" or value == "man" or value == "manager":
            attribute = permissions.Permissions.MANAGER
        else:
            raise commands.BadArgument
        perms = permissions.GuildPermissionManager(ctx)
        await perms.write(entity, attribute)

    @commands.group(
        invoke_without_command=True,
        case_insensitive=True,
        name="configuration",
        aliases=["config"],
        brief="Configures bots.",
        description="Configures bots in the scope of this server.",
    )
    async def config(self, ctx):
        pass

    @config.command(
        name="mute",
        brief="Sets role used to mute people.",
        description="Sets the role that is given to people who are muted. It must already be configured.",
    )
    async def mute(self, ctx, *, role: discord.Role):
        await ctx.guild_document.update_db({"$set": {"mute_role": role.id}})

    @commands.command(
        name="delete",
        aliases=["leave"],
        brief="Deletes all data on the server, then leaves.",
        description="Deletes all the data the bots has collected and stored on this server, then leaves. Be careful!",
    )
    async def delete(self, ctx):
        if await DeleteMenu().prompt(ctx):
            await ctx.guild_document.delete_db()
            await ctx.guild.leave()


def setup(bot):
    bot.add_cog(Administration(bot))
