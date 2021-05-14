import typing

import discord
import instances
from discord.ext import commands
from utils import checks, errors, managers


class administration(
    commands.Cog,
    name="Administration",
    description="Tools for administration.",
):
    def __init__(self, bot):
        self.bot = bot

    async def cog_check(self, ctx):
        return checks.has_permission_level(ctx, 3)

    async def member_message_processor(self, member: discord.Member, event: str):
        guild = member.guild
        messages_dict = managers.GuildMessageManager(guild, instances.activeDatabase["servers"]).read(event)
        if messages_dict:
            for channel in messages_dict.keys():
                active_channel = self.bot.get_channel(int(channel))
                message = messages_dict[channel]
                embed = discord.Embed(colour=member.colour, description=message)
                await active_channel.send(member.mention, embed=embed)

    @commands.Cog.listener()
    async def on_member_join(self, member):
        await self.member_message_processor(member, "on_member_join")

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        await self.member_message_processor(member, "on_member_remove")

    async def reaction_processor(self, payload: discord.RawReactionActionEvent):
        if payload.guild_id == None or payload.user_id == self.bot.user.id:
            return
        guild: discord.Guild = self.bot.get_guild(payload.guild_id)
        channel: discord.TextChannel = guild.get_channel(payload.channel_id)
        message: discord.PartialMessage = channel.get_partial_message(payload.message_id)
        author: discord.Member = guild.get_member(payload.user_id)
        emoji: discord.PartialEmoji = payload.emoji
        reaction_dict = managers.GuildReactionManager(guild, instances.activeDatabase["servers"]).read()
        if reaction_dict:
            for key_channel in reaction_dict.keys():
                channel_dict = reaction_dict[key_channel]
                if int(key_channel) == channel.id:
                    for key_message in channel_dict.keys():
                        message_dict = channel_dict[key_message]
                        if int(key_message) == message.id:
                            for role_pair in message_dict.keys():
                                if role_pair == emoji.name:
                                    role = guild.get_role(message_dict[role_pair])
                                    if payload.event_type == "REACTION_ADD":
                                        await author.add_roles(role)
                                    elif payload.event_type == "REACTION_REMOVE":
                                        await author.remove_roles(role)

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        await self.reaction_processor(payload)

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent):
        await self.reaction_processor(payload)

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
        permission_level = managers.GuildPermissionManager(ctx.guild, instances.activeDatabase["servers"]).read(entity)
        await ctx.send(f"{entity.id} has permission level {permission_level}")

    @permissions.command(
        name="write",
        brief="Write permission level of a role.",
        description="Writes given permission level into a role.",
        usage="<Permission Level> <Role>",
    )
    async def write(self, ctx, value: int, *, entity: discord.Role):
        try:
            managers.GuildPermissionManager(ctx.guild, instances.activeDatabase["servers"]).write(entity, value)
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
                instances.activeDatabase["servers"],
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
                instances.activeDatabase["servers"],
                "mute_role",
                "",
            ).write(str(role.id))
        except:
            await ctx.message.add_reaction(emoji="\U0000274c")
        else:
            await ctx.message.add_reaction(emoji="\U00002705")

    @config.command(
        name="message",
        aliases=["setmessage"],
        brief="Sets message displayed when an action occurs.",
        description="Sets message displayed when an action occurs. Message types include on_member_join and on_member_remove.",
    )
    async def setmessage(self, ctx, message_type: str, channel: discord.TextChannel, *, message: str):
        try:
            managers.GuildMessageManager(ctx.guild, instances.activeDatabase["servers"]).write(message_type, channel, message)
        except:
            await ctx.message.add_reaction(emoji="\U0000274c")
        else:
            await ctx.message.add_reaction(emoji="\U00002705")

    @config.command(
        name="reactionrole",
        aliases=["reaction", "rr"],
        brief="Configures reaction role.",
        description="Configures reaction role. The bot must have permissions to add rections in the desired channel.",
        usage="<Channel> <Message> <Emoji> <Role>",
    )
    async def reactionrole(
        self,
        ctx,
        channel: discord.TextChannel,
        message: typing.Union[discord.Message, discord.PartialMessage],
        emoji: typing.Union[discord.Emoji, discord.PartialEmoji, str],
        role: discord.Role,
    ):
        try:
            managers.GuildReactionManager(ctx.guild, instances.activeDatabase["servers"]).write(channel, message, emoji, role)
            message_model = channel.get_partial_message(message.id)
            await message_model.add_reaction(emoji)
        except:
            await ctx.message.add_reaction(emoji="\U0000274c")
        else:
            await ctx.message.add_reaction(emoji="\U00002705")


def setup(bot):
    bot.add_cog(administration(bot))
