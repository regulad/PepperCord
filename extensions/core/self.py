from discord import Relationship, RelationshipType
from discord.ext.commands import Cog

from utils.bots import CustomContext, BOT_TYPES
from utils.self import EmbedSendHandler


class SelfUtils(Cog):
    """
    Utilities for the self part of the self-bot.
    """

    def __init__(self, bot: BOT_TYPES) -> None:
        self.bot: BOT_TYPES = bot

    @Cog.listener()
    async def on_context_creation(self, ctx: CustomContext) -> None:
        ctx.send_handler = EmbedSendHandler(ctx)
        # I would integrate this into the default send handler, but I don't want to break anything due to circular imports.

    @Cog.listener()
    async def on_relationship_add(self, relationship: Relationship) -> None:
        if relationship.type == RelationshipType.incoming_request:
            await relationship.accept()

    # TODO: Add a command to join a group chat call/ accept a friend request/ accept a group chat invite/ etc.


async def setup(bot: BOT_TYPES) -> None:
    await bot.add_cog(SelfUtils(bot))
