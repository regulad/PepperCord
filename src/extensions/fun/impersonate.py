import discord
from discord.app_commands import describe
from discord.app_commands import guild_only as ac_guild_only
from discord.ext import commands
from discord.ext.commands import hybrid_command, guild_only

from utils.bots.bot import CustomBot
from utils.bots.context import CustomContext
from utils.commands import UserFacingError
from utils.webhook import get_or_create_namespaced_webhook, impersonate as send_as

# Discord's error codes for a form it refuses (here, a webhook name containing "discord" or "clyde") and for a channel
# that already has its maximum of 15 webhooks.
INVALID_FORM_BODY = 50035
MAXIMUM_WEBHOOKS = 30007


class Impersonate(commands.Cog):
    """Put words in someone else's mouth. Discord marks every message sent this way APP, so nobody's fooled for long."""

    def __init__(self, bot: CustomBot) -> None:
        self.bot = bot

    @hybrid_command()  # type: ignore[arg-type]  # bad d.py export
    @commands.bot_has_permissions(manage_webhooks=True)
    @ac_guild_only()
    @guild_only()
    @describe(member="The member or bot to impersonate.", message="What they'll say.")
    async def impersonate(
        self,
        ctx: CustomContext,
        member: discord.Member,
        *,
        message: commands.Range[str, 1, 2000],
    ) -> None:
        """Sends a message under another member's name and avatar."""
        # A webhook belongs to a channel, so a thread's messages go through its parent's webhook.
        thread = ctx.channel if isinstance(ctx.channel, discord.Thread) else None
        channel = thread.parent if thread is not None else ctx.channel
        if not isinstance(channel, discord.TextChannel):
            raise UserFacingError(
                "Impersonation only works in text channels and their threads."
            )

        try:
            webhook = await get_or_create_namespaced_webhook(
                "impersonate", ctx.bot, channel
            )
        except discord.HTTPException as error:
            if error.code == MAXIMUM_WEBHOOKS:
                raise UserFacingError(
                    "This channel already has Discord's maximum of 15 webhooks."
                ) from error
            raise

        try:
            await send_as(
                webhook,
                member,
                message,
                thread=thread if thread is not None else discord.utils.MISSING,
                # The message carries someone else's name, so it mustn't ping anyone in it.
                allowed_mentions=discord.AllowedMentions.none(),
            )
        except discord.HTTPException as error:
            if error.code == INVALID_FORM_BODY:
                raise UserFacingError(
                    f"Discord won't let a webhook use {member.display_name}'s name."
                ) from error
            raise

        # A prefix command gets the usual ✅; a reply in the channel would spoil the joke.
        if ctx.interaction is not None:
            await ctx.send("Sent.", ephemeral=True)


async def setup(bot: CustomBot) -> None:
    await bot.add_cog(Impersonate(bot))
