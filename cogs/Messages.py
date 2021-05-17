import copy

import discord
import instances
import pymongo
from discord.ext import commands
from utils import checks, errors, managers


class GuildMessageManager(managers.CommonConfigManager):
    def __init__(self, guild: discord.Guild, collection: pymongo.collection.Collection):
        super().__init__(guild, collection, "messages", {})

    def read(self, message_type: str):
        return_dict = self.active_key[message_type]
        return return_dict

    def write(self, message_type: str, channel: discord.TextChannel, message: str):
        working_key = copy.deepcopy(self.active_key)
        working_key.update({message_type: {str(channel.id): message}})
        super().write(working_key)


class Messages(commands.Cog, name="Messages", description="Messages displayed when an event takes place."):
    def __init__(self, bot):
        self.bot = bot

    async def cog_check(self, ctx):
        return await checks.has_permission_level(ctx, 3)

    async def member_message_processor(self, member: discord.Member, event: str):
        guild = member.guild
        messages_dict = GuildMessageManager(guild, instances.guild_collection).read(event)
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

    @commands.group(
        invoke_without_command=True,
        case_insensitive=True,
        name="messages",
        aliases=["events"],
        brief="Configures events.",
        description="Configures what is displayed when a certain event occurs.",
    )
    async def events(self, ctx):
        raise errors.SubcommandNotFound()

    @events.command(
        name="add",
        aliases=["set"],
        brief="Sets message displayed when an action occurs.",
        description="Sets message displayed when an action occursm. Message types include on_member_join and on_member_remove.",
    )
    async def setmessage(self, ctx, message_type: str, channel: discord.TextChannel, *, message: str):
        GuildMessageManager(ctx.guild, instances.guild_collection).write(message_type, channel, message)
        await ctx.message.add_reaction(emoji="✅")


def setup(bot):
    bot.add_cog(Messages(bot))
