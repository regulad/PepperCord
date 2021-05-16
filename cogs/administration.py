import typing

import discord
import instances
from discord.ext import commands
from utils import checks, errors, managers


class Administration(
    commands.Cog,
    name="Administration",
    description="Tools for administration.",
):
    def __init__(self, bot):
        self.bot = bot

    async def cog_check(self, ctx):
        return await checks.has_permission_level(ctx, 3)

    @commands.command(
        name="message",
        brief="Send a message as the bot.",
        description="Send a message as the bot in any channel that you want.",
        usage="<Channel> <Message>",
    )
    async def doMessage(self, ctx, channel: discord.TextChannel, *, text: str):
        channel = self.bot.get_channel(channel.id)
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
        raise errors.SubcommandNotFound()

    @permissions.command(
        name="read",
        brief="Displays permission level of entity.",
        description="Gets current permission level from member or role.",
        usage="<Member|Role>",
    )
    async def read(self, ctx, *, entity: typing.Union[discord.Member, discord.Role]):
        permission_level = managers.GuildPermissionManager(ctx.guild, instances.guild_collection).read(entity)
        await ctx.send(f"{entity.id} has permission level {permission_level}")

    @permissions.command(
        name="write",
        brief="Write permission level of a role.",
        description="Writes given permission level into a role.",
        usage="<Permission Level> <Role>",
    )
    async def write(self, ctx, value: int, *, entity: discord.Role):
        try:
            managers.GuildPermissionManager(ctx.guild, instances.guild_collection).write(entity, value)
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
        raise errors.SubcommandNotFound()

    @config.command(name="prefix", brief="Sets the bot's prefix.", description="Sets the bot's prefix. It can be any string.")
    async def prefix(self, ctx, *, prefix: str):
        try:
            managers.CommonConfigManager(
                ctx.guild,
                instances.guild_collection,
                "prefix",
                instances.config_instance["discord"]["commands"]["prefix"],
            ).write(prefix)
        except:
            await ctx.message.add_reaction(emoji="\U0000274c")
        else:
            await ctx.message.add_reaction(emoji="\U00002705")

    @config.command(
        name="mute",
        brief="Sets role used to mute people.",
        description="Sets the role that is given to people who are muted. It must already be configured.",
    )
    async def mute(self, ctx, *, role: discord.Role):
        try:
            managers.CommonConfigManager(
                ctx.guild,
                instances.guild_collection,
                "mute_role",
                0,
            ).write(role.id)
        except:
            await ctx.message.add_reaction(emoji="\U0000274c")
        else:
            await ctx.message.add_reaction(emoji="\U00002705")


def setup(bot):
    bot.add_cog(Administration(bot))
