import typing

import discord
from discord.ext import commands
from utils import errors
from utils.database import Document


class Blacklist(commands.Cog):
    """The blacklist system allows the bot owner to take abuse matters into their own hands and prevent a malicious user or guild from abusing the bot."""

    def __init__(self, bot):
        self.bot = bot

    async def bot_check(self, ctx):
        if ctx.guild is not None and ctx.guild_doc.setdefault("blacklisted", False):
            raise errors.Blacklisted()
        elif ctx.user_doc.setdefault("blacklisted", False):
            raise errors.Blacklisted()
        else:
            return True

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
        entity: typing.Optional[typing.Union[discord.User, discord.Member, discord.Guild]],
    ):
        value = value or True
        entity = entity or ctx.guild
        if isinstance(entity, discord.Guild):
            document = await Document.get_from_id(ctx.bot.database["guild"], entity.id)
        elif isinstance(entity, (discord.Member, discord.User)):
            document = await Document.get_from_id(ctx.bot.database["user"], entity.id)
        document["blacklisted"] = value
        await document.replace_db()


def setup(bot):
    bot.add_cog(Blacklist(bot))
