import discord
from discord.ext import commands

from utils import bots
from utils.bots import CustomContext, BOT_TYPES
from utils.checks import LowPrivilege, has_permission_level
from utils.permissions import Permission, get_permission


async def member_message_processor(bot: BOT_TYPES, member: discord.Member, event: str):
    guild_doc = await bot.get_guild_document(member.guild)
    messages_dict = guild_doc.get("messages", {}).get(event, {})
    if messages_dict:
        for channel, message in messages_dict.items():
            active_channel = member.guild.get_channel(int(channel))
            embed = discord.Embed(colour=member.colour, description=message)
            await active_channel.send(member.mention, embed=embed)


class Alerts(commands.Cog):
    """Messages sent when an event occurs in a guild."""

    def __init__(self, bot: BOT_TYPES) -> None:
        self.bot: BOT_TYPES = bot

    async def cog_check(self, ctx: CustomContext) -> bool:
        if not await has_permission_level(ctx, Permission.ADMINISTRATOR):
            raise LowPrivilege(Permission.ADMINISTRATOR, get_permission(ctx))
        else:
            return True

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        await member_message_processor(self.bot, member, "on_member_join")

    @commands.Cog.listener()
    async def on_member_remove(self, member) -> None:
        await member_message_processor(self.bot, member, "on_member_remove")

    @commands.group(
        invoke_without_command=True,
        case_insensitive=True,
        name="messages",
        aliases=["events", "alerts"],
        description="Commands that allow you to configure what is displayed when a certain event occurs.",
    )
    async def events(self, ctx: CustomContext) -> None:
        pass

    @events.command(
        name="disable",
        aliases=["off", "delete"],
        brief="Deletes messages.",
        description="Deletes all messages.",
    )
    async def sdisable(self, ctx: CustomContext) -> None:
        if ctx["guild_document"].get("reactions") is None:
            raise bots.NotConfigured
        await ctx["guild_document"].update_db({"$unset": {"reactions": 1}})

    @events.command(
        name="add",
        aliases=["set"],
        brief="Sets message displayed when an action occurs.",
        description="Sets message displayed when an action occursm. Message types include on_member_join and on_member_remove.",
    )
    async def setmessage(
            self,
            ctx: CustomContext,
            message_type: str,
            channel: discord.TextChannel,
            *,
            message: str,
    ) -> None:
        await ctx["guild_document"].update_db(
            {"$set": {f"messages.{message_type}.{channel.id}": message}}
        )


def setup(bot: BOT_TYPES):
    bot.add_cog(Alerts(bot))
