from typing import Optional, Union
from json import dump
from io import StringIO

import discord
from discord.ext import commands, menus

from utils import checks, bots


class ShardNotFound(Exception):
    pass


class GuildsMenuList(menus.ListPageSource):
    async def format_page(self, menu, page_entries):
        offset = menu.current_page * self.per_page
        base_embed = discord.Embed(title="Guilds")
        for iteration, value in enumerate(page_entries, start=offset):
            value: discord.Guild

            base_embed.add_field(
                name=f"{iteration + 1}: {value.name} ({value.id})",
                value=f"{value.member_count} members",
                inline=False,
            )
        return base_embed


class ShardMenu(menus.Menu):
    def __init__(
        self,
        shard_info,
        *,
        timeout=180.0,
        delete_message_after=False,
        clear_reactions_after=False,
        check_embeds=False,
        message=None,
    ):
        self.shard_info = shard_info

        super().__init__(
            timeout=timeout,
            delete_message_after=delete_message_after,
            clear_reactions_after=clear_reactions_after,
            check_embeds=check_embeds,
            message=message,
        )

    async def send_initial_message(self, ctx, channel):
        embed = (
            discord.Embed(
                title=f"Info for shard {self.shard_info.id + 1}/{self.shard_info.shard_count}",
            )
            .add_field(name="Online:", value=str(not self.shard_info.is_closed()))
            .add_field(name="Latency:", value=f"{round(self.shard_info.latency * 1000)} ms")
        )
        return await ctx.send(embed=embed)

    @menus.button("🔄")
    async def reconnect(self, payload):
        return await self.shard_info.reconnect()


class Dev(commands.Cog):
    """Tools to be used by the bots developer to operate the bots."""

    def __init__(self, bot: bots.BOT_TYPES) -> None:
        self.bot = bot

    async def cog_check(self, ctx: bots.CustomContext) -> bool:
        if not await ctx.bot.is_owner(ctx.author):
            raise commands.NotOwner('You do not own this bot.')
        return True

    @commands.command(
        name="nick",
        aliases=["nickname"],
        brief="Change nickname.",
        description="Change the bots's nickname, for situations where you do not have privileges to.",
    )
    @commands.guild_only()
    async def nick(self, ctx: bots.CustomContext, *, name: Optional[str]) -> None:
        await ctx.guild.me.edit(nick=name)

    @commands.command(
        name="guildraw",
        aliases=["document", "raw", "guilddocument"],
        brief="Get raw document for a guild.",
        description="Prints an guild's raw document. Be careful! It can contain sensitive information.",
    )
    async def guildraw(
            self,
            ctx:
            bots.CustomContext, entity: Optional[Union[discord.Guild, discord.Member, discord.User]],
    ) -> None:
        entity = entity or ctx.guild
        document = await ctx.bot.get_guild_document(entity)

        buffer = StringIO()
        dump(document, buffer)

        buffer.seek(0)
        file = discord.File(buffer, f"{entity.id}.json")
        await ctx.send(file=file)

    @commands.command(
        name="userraw",
        aliases=["userdocument"],
        brief="Get raw document for a user.",
        description="Prints an user's raw document. Be careful! It can contain sensitive information.",
    )
    async def userraw(
            self,
            ctx: bots.CustomContext,
            entity: Optional[Union[discord.Guild, discord.Member, discord.User]],
    ) -> None:
        entity = entity or ctx.author
        document = await ctx.bot.get_user_document(entity)

        buffer = StringIO()
        dump(document, buffer)

        buffer.seek(0)
        file = discord.File(buffer, f"{entity.id}.json")
        await ctx.send(file=file)

    @commands.command(
        name="shardinfo",
        aliases=["si"],
        brief="Gets info on a shard.",
        description="Gets info on a shard and presents a menu which can be used to manage the shard.",
    )
    @commands.check(checks.bot_is_sharded)
    async def shard_info(self, ctx: bots.CustomContext, *, shard_id: Optional[Union[discord.Guild, int]]) -> None:
        shard_id = shard_id or ctx.guild

        if isinstance(shard_id, discord.Guild):
            shard_id = shard_id.shard_id  # If the argument is a guild, replace shard_id with the shard_id of the guild

        shard_info = ctx.bot.get_shard(shard_id)

        if shard_info is None:
            raise ShardNotFound

        await ShardMenu(shard_info=shard_info).start(ctx)

    @commands.command(
        name="guilds",
        brief="Lists all guilds the bot is in.",
        description="Lists all guilds that the bot is in. May contain sensitive information!"
    )
    async def guilds(self, ctx: bots.CustomContext) -> None:
        await menus.MenuPages(GuildsMenuList(ctx.bot.guilds, per_page=10)).start(ctx)


def setup(bot: bots.BOT_TYPES):
    bot.add_cog(Dev(bot))
