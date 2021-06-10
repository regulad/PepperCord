from typing import Optional, Union

import discord
from discord.ext import commands

from utils import checks


class Blacklist(commands.Cog):
    """The blacklist system allows the bots owner to take abuse matters into their own hands and prevent a malicious
    user or guild from abusing the bots."""

    def __init__(self, bot):
        self.bot = bot

    async def bot_check(self, ctx):
        return await checks.is_blacklisted(ctx)

    async def cog_check(self, ctx):
        return await ctx.bot.is_owner(ctx.author)

    @commands.command(
        name="blacklist",
        description="Tool to blacklist entity from using the bot.",
        brief="Blacklists declared entity.",
    )
    async def blacklist(
        self,
        ctx,
        *,
        entity: Optional[Union[discord.User, discord.Member, discord.Guild]],
    ):
        entity = entity or ctx.guild
        document = await ctx.bot.get_document(entity)
        await document.update_db({"$set": {"blacklisted": True}})

    @commands.command(
        name="unblacklist",
        description="Tool to unblacklist entity from using the bot.",
        brief="Unlacklists declared entity.",
    )
    async def unblacklist(
        self,
        ctx,
        *,
        entity: Optional[Union[discord.User, discord.Member, discord.Guild]],
    ):
        entity = entity or ctx.guild
        document = await ctx.bot.get_document(entity)
        await document.update_db({"$set": {"blacklisted": False}})


def setup(bot):
    bot.add_cog(Blacklist(bot))
