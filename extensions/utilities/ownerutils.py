from typing import Optional, Union

import discord
from discord.ext import commands, menus

from utils import checks, bots


class ShardNotFound(Exception):
    pass


class GuildsMenuList(menus.ListPageSource):
    async def format_page(self, menu, page_entries):
        offset = menu.current_page * self.per_page
        base_embed = discord.Embed(title="Guilds")
        base_embed.set_footer(
            text=f"Page {menu.current_page + 1}/{self.get_max_pages()}"
        )
        for iteration, value in enumerate(page_entries, start=offset):
            value: discord.Guild

            base_embed.add_field(
                name=f"{iteration + 1}: {value.name} ({value.id})",
                value=f"{value.member_count} members",
                inline=False,
            )
        return base_embed


class ShardMenu(menus.ViewMenu):
    def __init__(
            self,
            shard_info,
            **kwargs,
    ):
        self.shard_info = shard_info

        super().__init__(**kwargs)

    async def send_initial_message(self, ctx, channel):
        embed = (
            discord.Embed(
                title=f"Info for shard {self.shard_info.id + 1}/{self.shard_info.shard_count}",
            )
                .add_field(name="Online:", value=str(not self.shard_info.is_closed()))
                .add_field(
                name="Latency:", value=f"{round(self.shard_info.latency * 1000)} ms"
            )
        )
        return await channel.send(embed=embed, **self._get_kwargs())

    @menus.button("🔄")
    async def reconnect(self, payload):
        return await self.shard_info.reconnect()


class OwnerUtils(commands.Cog):
    """Tools to be used by the bots developer to operate the bots."""

    def __init__(self, bot: bots.BOT_TYPES) -> None:
        self.bot = bot

    async def cog_check(self, ctx: bots.CustomContext) -> bool:
        if not await ctx.bot.is_owner(ctx.author):
            raise commands.NotOwner("You do not own this bot.")
        return True

    @commands.command()
    @commands.guild_only()
    async def nick(
            self,
            ctx: bots.CustomContext,
            *,
            nickname: Optional[str],
    ) -> None:
        """Sets the bots nickname in this guild to a desired string."""
        await ctx.guild.me.edit(nick=nickname)
        await ctx.send("Changed nickname", ephemeral=True)

    @commands.command()
    @checks.check_bot_is_sharded
    async def shardinfo(
            self,
            ctx: bots.CustomContext,
            *,
            shard_id: Optional[Union[discord.Guild, int]],
    ) -> None:
        """Get info on the bots current shard, if the bot is sharded."""

        shard_id = shard_id or ctx.guild

        if isinstance(shard_id, discord.Guild):
            shard_id = (
                shard_id.shard_id
            )  # If the argument is a guild, replace shard_id with the shard_id of the guild

        shard_info = ctx.bot.get_shard(shard_id)

        if shard_info is None:
            raise ShardNotFound

        await ShardMenu(shard_info=shard_info).start(ctx, ephemeral=True)

    @commands.command()
    async def guilds(self, ctx: bots.CustomContext) -> None:
        """List all the guilds the bot is in."""
        await menus.ViewMenuPages(
            GuildsMenuList(sorted(ctx.bot.guilds, key=lambda g: g.me.joined_at), per_page=10)
        ).start(
            ctx, ephemeral=True
        )


async def setup(bot: bots.BOT_TYPES) -> None:
    await bot.add_cog(OwnerUtils(bot))
