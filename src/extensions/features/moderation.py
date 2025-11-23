import discord
from discord.app_commands import describe, default_permissions
from discord.app_commands import guild_only as ac_guild_only
from discord.ext import commands
from discord.ext.commands import hybrid_command, guild_only

from utils.bots.bot import CustomBot
from utils.bots.context import CustomContext


class Moderation(commands.Cog):
    """Tools for moderation in guilds."""

    def __init__(self, bot: CustomBot) -> None:
        self.bot = bot

    @hybrid_command(aliases=["pu", "del"])  # type: ignore[arg-type]  # bad d.py export
    @commands.has_permissions(manage_messages=True)
    @commands.bot_has_permissions(manage_messages=True)
    @default_permissions(manage_messages=True)
    @ac_guild_only()
    @guild_only()
    @describe(messages="The amount of messages to be deleted.")
    async def purge(
        self,
        ctx: CustomContext,
        messages: int,
    ) -> None:
        """Deletes a set amount of messages from a channel."""
        if not isinstance(
            ctx.channel,
            (
                discord.TextChannel,
                discord.VoiceChannel,
                discord.StageChannel,
                discord.Thread,
            ),
        ):
            await ctx.send("Messages in this channel can't be purged.", ephemeral=True)
            return
        async with ctx.typing(ephemeral=True):
            if ctx.interaction is None:
                await ctx.message.delete()
            await ctx.channel.purge(
                limit=messages, reason=f"Requested by {ctx.author}."
            )
            await ctx.send("Deleted.", ephemeral=True, delete_after=5)


async def setup(bot: CustomBot) -> None:
    await bot.add_cog(Moderation(bot))
