import copy
from typing import List, Optional, Dict, Union

import discord
from discord.ext import commands

from extensions.features.moderation import get_any_id
from utils.bots import CustomContext, BOT_TYPES


class ShuffleNicks(commands.Cog):
    """A mini-game where you can shuffle the nicknames of people on a server."""

    def __init__(self, bot: BOT_TYPES) -> None:
        self.bot: BOT_TYPES = bot

    @commands.command(
        name="shufflenames",
        aliases=["shufflenicks"],
        brief="Shuffles usernames.",
        description="Shuffles usernames around between people. Do it again to reverse.",
    )
    @commands.cooldown(1, 3600, commands.BucketType.guild)
    @commands.bot_has_permissions(manage_nicknames=True)
    @commands.has_permissions(manage_nicknames=True)
    async def shufflenicks(self, ctx: CustomContext) -> None:
        """
        Shuffles nicknames between people on your server.
        """
        await ctx.defer(ephemeral=True)

        if ctx["guild_document"].get("shuffled") is None:
            if (
                    divmod(len(ctx.guild.members), 2)[-1] != 0
            ):  # If member count is not even
                temp_member_list: Optional[List[discord.Member]] = copy.copy(
                    ctx.guild.members
                )
                temp_member_list.pop()
                member_list: List[discord.Member] = temp_member_list
            else:
                member_list: List[discord.Member] = copy.copy(ctx.guild.members)

            middle_index: int = len(member_list) // 2
            pair_set_one: List[discord.Member] = member_list[middle_index:]
            pair_set_two: List[discord.Member] = member_list[:middle_index]

            pairing: Dict[discord.Member, discord.Member] = {}

            for one, two in zip(pair_set_one, pair_set_two):
                pairing[one] = two

            member_pairings: Dict[
                Union[discord.Member, discord.User],
                Union[discord.Member, discord.User],
            ] = copy.copy(pairing)

            db_pairings: Dict[str, int] = {}
            for one, two in pairing.items():
                db_pairings[str(one.id)] = two.id

            await ctx["guild_document"].update_db({"$set": {"shuffled": db_pairings}})
        else:  # Previous paring exists, roll with it
            db_pairings: Dict[str, int] = copy.copy(ctx["guild_document"]["shuffled"])
            await ctx["guild_document"].update_db({"$unset": {"shuffled": 1}})  # Reset
            member_pairings: Dict[
                Union[discord.Member, discord.User],
                Union[discord.Member, discord.User],
            ] = {}
            for one_id_as_str, two_id in db_pairings.items():
                one: Optional[Union[discord.Member, discord.User]] = await get_any_id(
                    ctx, int(one_id_as_str)
                )
                two: Optional[Union[discord.Member, discord.User]] = await get_any_id(
                    ctx, two_id
                )

                assert one is not None, two is not None

                member_pairings[one] = two
        # Time to actually shuffle nicks...

        for one, two in member_pairings.items():
            one_display_name: str = copy.copy(one.display_name)
            if isinstance(one, discord.Member):
                try:
                    await one.edit(
                        nick=two.display_name,
                        reason=f"Nickname shuffle requested by {ctx.author.display_name}",
                    )
                except discord.Forbidden:
                    pass
            if isinstance(two, discord.Member):
                try:
                    await two.edit(
                        nick=one_display_name,
                        reason=f"Nickname shuffle requested by {ctx.author.display_name}",
                    )
                except discord.Forbidden:
                    pass
        await ctx.send("Done shuffling nicknames.", ephemeral=True)

    @commands.command()
    @commands.cooldown(1, 3600, commands.BucketType.guild)
    @commands.bot_has_permissions(manage_nicknames=True)
    async def resetnicks(self, ctx: CustomContext) -> None:
        """Reset nicknames of all people who had their nicknames changed."""
        await ctx.defer(ephemeral=True)

        if ctx["guild_document"].get("shuffled") is not None:
            await ctx["guild_document"].update_db({"$unset": {"shuffled": 1}})
        for member in ctx.guild.members:
            try:
                await member.edit(nick=None)
            except discord.Forbidden:
                continue
        await ctx.send("Done resetting nicknames.", ephemeral=True)


def setup(bot: BOT_TYPES) -> None:
    bot.add_cog(ShuffleNicks(bot))
