import typing

import discord
from discord.ext import commands
from utils import checks, errors, permissions


class Administration(
    commands.Cog,
    name="Administration",
    description="Tools for administration.",
):
    def __init__(self, bot):
        self.bot = bot

    async def cog_check(self, ctx):
        return await checks.is_admin(ctx)

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
            raise commands.BadArgument()
        perms = permissions.GuildPermissionManager(ctx)
        await perms.write(entity, attribute)
        await ctx.message.add_reaction(emoji="✅")

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
        ctx.guild_doc["prefix"] = prefix
        await ctx.guild_doc.update_db()
        await ctx.message.add_reaction(emoji="✅")

    @config.command(
        name="mute",
        brief="Sets role used to mute people.",
        description="Sets the role that is given to people who are muted. It must already be configured.",
    )
    async def mute(self, ctx, *, role: discord.Role):
        ctx.guild_doc["mute_role"] = role.id
        await ctx.guild_doc.update_db()
        await ctx.message.add_reaction(emoji="✅")


def setup(bot):
    bot.add_cog(Administration(bot))
