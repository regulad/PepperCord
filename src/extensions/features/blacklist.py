from typing import Union

import discord
from discord.ext import commands

from utils.checks.blacklisted import is_blacklisted, EBlacklisted
from utils.commands import UserFacingError
from utils.bots.bot import CustomBot
from utils.bots.context import CustomContext


def _this_guild(ctx: CustomContext) -> discord.Guild:
    if ctx.guild is None:
        raise UserFacingError(
            "Name a user or server: there's no server here to default to."
        )
    return ctx.guild


# Without None in the Union, a name that matches nothing fails to convert instead of falling back to this server.
_ENTITY_DEFAULT = commands.parameter(
    default=_this_guild, displayed_default="this server"
)


class Blacklist(commands.Cog):
    """The blacklist system allows the bots owner to take abuse matters into their own hands and prevent a malicious
    user or guild from abusing the bots."""

    def __init__(self, bot: CustomBot) -> None:
        self.bot = bot

    async def bot_check(self, ctx: CustomContext) -> bool:  # type: ignore[override]  # bad types exported
        if await is_blacklisted(ctx) or (
            ctx.bot.config.get("PEPPERCORD_TESTGUILDS") is not None
            and ctx.guild is not None
            and ctx.guild.id
            not in [
                int(guild)
                for guild in ctx.bot.config["PEPPERCORD_TESTGUILDS"].split(",")
            ]
        ):
            raise EBlacklisted()
        else:
            return True

    async def cog_check(self, ctx: CustomContext) -> bool:  # type: ignore[override]  # bad types exported
        return await ctx.bot.is_owner(ctx.author)

    @commands.command()
    async def blacklist(
        self,
        ctx: CustomContext,
        *,
        entity: Union[discord.User, discord.Member, discord.Guild] = _ENTITY_DEFAULT,
    ) -> None:
        """Disallows a user, member, or a guild from using the bot."""
        if isinstance(entity, discord.Guild):
            document = await ctx.bot.get_guild_document(entity)
        else:
            document = await ctx.bot.get_user_document(entity)
        await document.update_db({"$set": {"blacklisted": True}})
        await ctx.send(f"Blacklisted {entity.name}.", ephemeral=True)

    @commands.command()
    async def unblacklist(
        self,
        ctx: CustomContext,
        *,
        entity: Union[discord.User, discord.Member, discord.Guild] = _ENTITY_DEFAULT,
    ) -> None:
        """Allows a user, member, or a guild to use the bot"""
        if isinstance(entity, discord.Guild):
            document = await ctx.bot.get_guild_document(entity)
        else:
            document = await ctx.bot.get_user_document(entity)
        await document.update_db({"$set": {"blacklisted": False}})
        await ctx.send(f"Unblacklisted {entity.name}.", ephemeral=True)


async def setup(bot: CustomBot) -> None:
    await bot.add_cog(Blacklist(bot))
