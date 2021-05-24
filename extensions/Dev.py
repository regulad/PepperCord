import typing

import discord
from discord.ext import commands
from utils.database import Document


class Dev(
    commands.Cog,
    name="Developer",
    description="Commands for the bot's developer used to operate the bot.",
):
    def __init__(self, bot):
        self.bot = bot

    async def cog_check(self, ctx):
        return await self.bot.is_owner(ctx.author)

    @commands.command(
        name="blacklist",
        description="Tools to blacklist entity from using the bot.",
        brief="Blacklists declared entity.",
        usage="<Value> <Entity>",
    )
    async def blacklist(
        self,
        ctx,
        value: typing.Optional[bool],
        *,
        entity: typing.Optional[typing.Union[discord.User, discord.Member, discord.Guild]]
    ):
        value = value or True
        entity = entity or ctx.guild
        if isinstance(entity, discord.Guild):
            document = await Document.get_document(self.bot.database["guild"], {"_id": entity.id})
        elif isinstance(entity, (discord.Member, discord.User)):
            document = await Document.get_document(self.bot.database["guild"], {"_id": entity.id})
        document["blacklisted"] = True
        await document.replace_db()

    @commands.command(
        name="nick",
        aliases=["nickname"],
        brief="Change nickname.",
        description="Change the bot's nickname, for situations where you do not have privleges to.",
    )
    @commands.guild_only()
    async def nick(self, ctx, *, name: str):
        await ctx.guild.me.edit(nick=name)


def setup(bot):
    bot.add_cog(Dev(bot))
