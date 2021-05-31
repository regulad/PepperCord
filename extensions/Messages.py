import discord
from discord.ext import commands
from utils import checks, database, errors


async def member_message_processor(bot, member: discord.Member, event: str):
    guild_doc = await bot.get_document(member)
    messages_dict = guild_doc["messages"][event]
    if messages_dict:
        for channel in messages_dict.keys():
            active_channel = self.bot.get_channel(int(channel))
            message = messages_dict[channel]
            embed = discord.Embed(colour=member.colour, description=message)
            await active_channel.send(member.mention, embed=embed)


class Messages(commands.Cog):
    """Messages sent when an event occurs in a guild."""

    def __init__(self, bot):
        self.bot = bot

    async def cog_check(self, ctx):
        return await checks.is_admin(ctx)


    @commands.Cog.listener()
    async def on_member_join(self, member):
        await member_message_processor(self.bot, member, "on_member_join")

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        await member_message_processor(self.bot, member, "on_member_remove")

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
        name="disable",
        aliases=["off", "delete"],
        brief="Deletes messages.",
        description="Deletes all messages.",
    )
    async def sdisable(self, ctx):
        try:
            del ctx.guild_document["reactions"]
        except KeyError:
            raise errors.NotConfigured()
        await ctx.guild_document.replace_db()

    @events.command(
        name="add",
        aliases=["set"],
        brief="Sets message displayed when an action occurs.",
        description="Sets message displayed when an action occursm. Message types include on_member_join and on_member_remove.",
    )
    async def setmessage(self, ctx, message_type: str, channel: discord.TextChannel, *, message: str):
        ctx.guild_document.setdefault("messages", {}).setdefault(message_type, {})[str(channel.id)] = message
        await ctx.guild_document.replace_db()


def setup(bot):
    bot.add_cog(Messages(bot))
