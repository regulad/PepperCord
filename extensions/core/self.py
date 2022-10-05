from discord import Relationship, RelationshipType, Invite
from discord.ext.commands import Cog, is_owner, command

from utils.bots import CustomContext, BOT_TYPES


class SelfUtils(Cog):
    """
    Utilities for the self part of the self-bot.
    """

    def __init__(self, bot: BOT_TYPES) -> None:
        self.bot: BOT_TYPES = bot

    @is_owner()
    @command()
    async def join(self, ctx: CustomContext, *, invite: str):
        """
        Joins a guild using an invitation.
        """

        invite: Invite = await ctx.bot.accept_invite(invite)
        await ctx.send(f"Joined {invite.guild}.")

    @Cog.listener()
    async def on_relationship_add(self, relationship: Relationship) -> None:
        if relationship.type == RelationshipType.incoming_request:
            await relationship.accept()

    # TODO: Add a command to join a group chat call/ accept a friend request/ accept a group chat invite/ etc.


async def setup(bot: BOT_TYPES) -> None:
    await bot.add_cog(SelfUtils(bot))
