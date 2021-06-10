from typing import Optional, Union

from discord.ext import commands
import discord

from utils import checks, permissions, bots


class Privileges(commands.Cog):
    """System for controlling privileges for executing commands in a guild."""

    def __init__(self, bot):
        self.bot = bot

    async def cog_check(self, ctx):
        return await checks.is_admin(ctx)

    @commands.group(
        invoke_without_command=True,
        case_insensitive=True,
        name="permissions",
        aliases=["perms", "priv", "privileges"],
        brief="Change server permissions.",
        description="Read & write permissions of various entities on the server. "
                    "Level 0 means that the entity has no permissions, "
                    "level 1 means that they have manager permissions (think controlling music or reading audit logs), "
                    "level 2 means that they have moderator privileges, "
                    "and level 3 means that they have administrator privileges.",
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
        if ctx.guild_document is None:
            raise bots.NotConfigured
        else:
            await ctx.guild_document.update_db({"$unset": {"permissions": 1}})

    @permissions.command(
        name="read",
        brief="Displays permission level of entity.",
        description="Gets raw permission level from member or role.",
        usage="[Member|Role]",
    )
    async def read(self, ctx, *, entity: Optional[Union[discord.Member, discord.Role]]):
        entity = entity or ctx.author
        perms = permissions.GuildPermissionManager(ctx)
        await ctx.send(f"{entity.name} has permission level `{await perms.read(entity)}`")

    @permissions.command(
        name="write",
        brief="Write permission level of a role.",
        description="Writes given permission level into a role. "
                    "Valid options include: Manager, Moderator, and Administrator.",
        usage="[Permission Level (Admin)] <Role>",
    )
    async def write(self, ctx, value: Optional[str], *, entity: discord.Role):
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


def setup(bot):
    bot.add_cog(Privileges(bot))
