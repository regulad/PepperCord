import typing

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
        description="Tools to blacklist entity from using the bots.",
        brief="Blacklists declared entity.",
        usage="<Value> <Entity>",
    )
    async def blacklist(
        self,
        ctx,
        value: typing.Optional[bool],
        *,
        entity: typing.Optional[typing.Union[discord.User, discord.Member, discord.Guild]],
    ):
        value = value or True
        entity = entity or ctx.guild
        document = await ctx.bot.get_document(entity)
        document["blacklisted"] = value
        await document.update_db({"$set": {"blacklisted": True}})


def setup(bot):
    bot.add_cog(Blacklist(bot))
