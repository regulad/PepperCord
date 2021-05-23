import typing

import discord
import instances
from discord.ext import commands
from utils import checks, errors, managers, permissions


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
        permission_level_manager = permissions.GuildPermissionManager(ctx.guild, instances.active_collection)
        await permission_level_manager.fetch_document()
        permission_level = await permission_level_manager.read(entity)
        await ctx.send(f"{entity.name} has permission level `{permission_level}`")

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
        permission_manager = permissions.GuildPermissionManager(ctx.guild, instances.active_collection)
        await permission_manager.fetch_document()
        await permission_manager.write(entity, attribute)
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
        config_manager = managers.CommonConfigManager(
            ctx.guild,
            instances.active_collection,
            "prefix",
            instances.config_instance["discord"]["commands"]["prefix"],
        )
        await config_manager.fetch_document()
        await config_manager.write(prefix)
        await ctx.message.add_reaction(emoji="✅")

    @config.command(
        name="mute",
        brief="Sets role used to mute people.",
        description="Sets the role that is given to people who are muted. It must already be configured.",
    )
    async def mute(self, ctx, *, role: discord.Role):
        config_manager = managers.CommonConfigManager(
            ctx.guild,
            instances.active_collection,
            "mute_role",
            0,
        )
        await config_manager.fetch_document()
        await config_manager.write(role.id)
        await ctx.message.add_reaction(emoji="✅")

    @config.command(
        name="redirect",
        brief="Redirects level-up alerts to a certain channel.",
        description="Redirects level-up alerts to a certain channel. Pass 0 to disable.",
    )
    async def redirect(self, ctx, *, channel: discord.TextChannel):
        config_manager = managers.CommonConfigManager(
            ctx.guild,
            instances.active_collection,
            "redirect",
            0,
        )
        await config_manager.fetch_document()
        await config_manager.write(channel.id)
        await ctx.message.add_reaction(emoji="✅")

    @commands.command(
        name="color",
        aliases=["colour", "colourrole", "colorrole"],
        brief="Swiftly creates role with given color.",
        description="Swiftly creates a role with the given color. If specified, you can give it to a user.",
        usage="<R> <G> <B> [Name] [Member]",
    )
    async def colorrole(
        self,
        ctx: commands.Context,
        r: int,
        g: int,
        b: int,
        name: typing.Optional[str],
        member: typing.Optional[discord.Member],
    ):
        colourinstance = discord.Colour.from_rgb(r, g, b)
        name = name or "#" + str(str(hex(r)).strip("0x") + str(hex(g)).strip("0x") + str(hex(b)).strip("0x")).upper()
        role = await ctx.guild.create_role(name=name, colour=colourinstance)
        if member:
            await member.add_roles(role)
        await ctx.message.add_reaction(emoji="✅")


def setup(bot):
    bot.add_cog(Administration(bot))
