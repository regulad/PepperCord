from typing import List, Optional

import discord
from discord.ext import commands

from utils import bots
from utils.bots import CustomContext, BOT_TYPES


async def member_message_processor(
    bot: BOT_TYPES, member: discord.Member, event: str
) -> Optional[List[discord.Message]]:
    guild_doc = await bot.get_guild_document(member.guild)
    messages_dict = guild_doc.get("messages", {}).get(event, {})
    if messages_dict:
        messages: List[discord.Message] = []
        for channel, message in messages_dict.items():
            active_channel = member.guild.get_channel(int(channel))
            embed = discord.Embed(colour=member.colour, description=message)
            messages.append(await active_channel.send(member.mention, embed=embed))
        return messages


class Alerts(commands.Cog):
    """Messages sent when an event occurs in a guild."""

    def __init__(self, bot: BOT_TYPES) -> None:
        self.bot: BOT_TYPES = bot

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        await member_message_processor(self.bot, member, "on_member_join")

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member) -> None:
        await member_message_processor(self.bot, member, "on_member_remove")

    @commands.group()
    @commands.has_permissions(admin=True)
    async def events(self, ctx: CustomContext) -> None:
        pass

    @events.command()
    async def disable(self, ctx: CustomContext) -> None:
        """Removes all event data from the bot."""
        if ctx["guild_document"].get("reactions") is None:
            raise bots.NotConfigured
        await ctx["guild_document"].update_db({"$unset": {"reactions": 1}})
        await ctx.send("Done.", ephemeral=True)

    @events.command()
    async def add(
        self,
        ctx: CustomContext,
        messagetype: str = commands.Option(
            description="The event that must happen to dispatch this message. on_member_join or on_member_leave."
        ),
        channel: discord.TextChannel = commands.Option(
            description="The channel the message will be sent in."
        ),
        *,
        message: str = commands.Option(description="The contents of the message."),
    ) -> None:
        """Registers a message."""
        await ctx["guild_document"].update_db(
            {"$set": {f"messages.{messagetype}.{channel.id}": message}}
        )
        await ctx.send("Done.", ephemeral=True)


def setup(bot: BOT_TYPES):
    bot.add_cog(Alerts(bot))
