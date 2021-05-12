import typing

from discord import utils

import instances
import discord
from discord.ext import commands
from discord.guild import Guild
from utils.checks import has_permission_level
import utils.managers
from utils.errors import SubcommandNotFound


class administration(
    commands.Cog,
    name="Administration",
    description="Tools for administration.",
):
    def __init__(self, bot):
        self.bot = bot

    async def cog_check(self, ctx):
        return (has_permission_level(ctx, 3)) and (commands.guild_only())

    @commands.group(
        invoke_without_command=True,
        case_insensitive=True,
        name="permissions",
        aliases=["perms", "priv", "privileges"],
        brief="Change server permissions.",
        description="Read & write permissions of various entities on the server. Level 0 means that the entity has no permissions, level 1 means that they have manager permissions (think controlling music or reading audit logs), level 2 means that they have moderator privileges, and level 3 means that they have administrator privileges.",
    )
    async def permissions(self, ctx):
        raise SubcommandNotFound()

    @permissions.command(
        name="read",
        brief="Displays permission level of entity.",
        description="Gets current permission level from member or role.",
        usage="<Member|Role>",
    )
    async def read(self, ctx, *, entity: typing.Union[discord.Member, discord.Role]):
        permission_level = utils.managers.GuildPermissionManager(ctx.guild, instances.activeDatabase["servers"]).read(entity)
        await ctx.send(f"{entity.id} has permission level {permission_level}")

    @permissions.command(
        name="write",
        brief="Write permission level of a role.",
        description="Writes given permission level into a role.",
        usage="<Permission Level> <Role>",
    )
    async def write(self, ctx, value: int, *, entity: discord.Role):
        try:
            utils.managers.GuildPermissionManager(ctx.guild, instances.activeDatabase["servers"]).write(entity, value)
        except:
            await ctx.message.add_reaction(emoji="\U0000274c")
        else:
            await ctx.message.add_reaction(emoji="\U00002705")

    @commands.group(
        invoke_without_command=True,
        case_insensitive=True,
        name="configuration",
        aliases=["config"],
        brief="Configures bot.",
        description="Configures bot in the scope of this server.",
    )
    async def config(self, ctx):
        raise SubcommandNotFound()

    @config.command(name="prefix", brief="Sets the bot's prefix.", description="Sets the bot's prefix. It can be any string.")
    async def prefix(self, ctx, *, prefix: str):
        try:
            utils.managers.GuildConfigManager(
                ctx.guild,
                instances.activeDatabase["servers"],
                "prefix",
                instances.config_instance["discord"]["commands"]["prefix"],
            ).write(prefix)
        except:
            await ctx.message.add_reaction(emoji="\U0000274c")
        else:
            await ctx.message.add_reaction(emoji="\U00002705")


def setup(bot):
    bot.add_cog(administration(bot))
