from typing import List, Optional

import discord
from discord.app_commands import describe, default_permissions
from discord.app_commands import guild_only as ac_guild_only
from discord.ext import commands
from discord.ext.commands import hybrid_group, guild_only

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

    @hybrid_group()
    @ac_guild_only()
    @guild_only()
    @default_permissions(administrator=True)
    @commands.has_permissions(administrator=True)
    async def events(self, ctx: CustomContext) -> None:
        pass

    @events.command()
    @guild_only()
    async def disable(self, ctx: CustomContext) -> None:
        """Removes all event data from the bot."""
        if ctx["guild_document"].get("reactions") is None:
            raise bots.NotConfigured
        await ctx["guild_document"].update_db({"$unset": {"reactions": 1}})
        await ctx.send("Done.", ephemeral=True)

    @events.command()
    @describe(
        messagetype="The event that must be recieved to dispatch the message. on_member_join or on_member_remove, for members joining and leaving respectively.",
        channel="The channel to send the message to.",
        message="The message to send, not including the member mention.",
    )
    @guild_only()
    async def add(
            self,
            ctx: CustomContext,
            messagetype: str,
            channel: discord.TextChannel,
            *,
            message: str,
    ) -> None:
        """Registers a message."""
        await ctx["guild_document"].update_db(
            {"$set": {f"messages.{messagetype}.{channel.id}": message}}
        )
        await ctx.send("Done.", ephemeral=True)


async def setup(bot: BOT_TYPES) -> None:
    await bot.add_cog(Alerts(bot))
