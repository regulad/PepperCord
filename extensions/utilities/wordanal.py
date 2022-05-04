from io import StringIO
from json import dump
from typing import Optional

from discord import Embed, File
from discord.app_commands import describe, default_permissions
from discord.app_commands import guild_only as ac_guild_only
from discord.ext.commands import (
    Cog,
    cooldown,
    has_permissions,
    BucketType,
    hybrid_command, guild_only, bot_has_permissions,
)
from discord.ext.menus import ListPageSource, ViewMenuPages

from utils.bots import BOT_TYPES, CustomContext


class LevelSource(ListPageSource):
    def __init__(self, data, guild):
        self.guild = guild
        super().__init__(data, per_page=10)

    async def format_page(self, menu, page_entries):
        offset = menu.current_page * self.per_page
        base_embed = Embed(title=f"{self.guild.name}'s Word Leaderboard")
        base_embed.set_footer(
            text=f"Page {menu.current_page + 1}/{self.get_max_pages()}"
        )
        if self.guild.icon is not None:
            base_embed.set_thumbnail(url=self.guild.icon.url)
        for iteration, value in enumerate(page_entries, start=offset):
            base_embed.add_field(
                name=f"{iteration + 1}. {value[0]}",
                value=f"{value[1]} occurrences",
                inline=False,
            )
        return base_embed


class WordAnalysis(Cog):
    """Find the most common words in your server's messages."""

    def __init__(self, bot: BOT_TYPES) -> None:
        self.bot: BOT_TYPES = bot

    @hybrid_command()
    @cooldown(1, 2400, type=BucketType.guild)
    @has_permissions(manage_messages=True)
    @bot_has_permissions(manage_messages=True)
    @default_permissions(manage_messages=True)
    @guild_only()
    @ac_guild_only()
    @describe(
        should_dump="Dump the word analysis to a file.",
        length="The length of the word to find. Leave empty for any length.",
    )
    async def wordanal(
            self,
            ctx: CustomContext,
            length: Optional[int] = None,
            should_dump: Optional[bool] = True,
    ) -> None:
        """Find the most common words in your server's messages."""

        await ctx.defer()

        quantity: dict[str, int] = {}

        for channel in ctx.guild.text_channels:
            async for message in channel.history(limit=None):
                if not message.author.bot and message.clean_content:
                    for word in message.clean_content.split():
                        word: str = word.lower()
                        if (length is None or (len(word) == length)) and word.isalpha():
                            if word in quantity:
                                quantity[word] += 1
                            else:
                                quantity[word] = 1

        quantity: dict[str, int] = {
            k: v
            for k, v in sorted(quantity.items(), key=lambda item: item[1], reverse=True)
        }

        source: LevelSource = LevelSource(
            sorted(quantity.items(), key=lambda x: x[1], reverse=True), ctx.guild
        )

        await ViewMenuPages(source).start(ctx)

        if should_dump:
            with StringIO() as fp:
                dump(quantity, fp, indent=4)
                fp.seek(0)
                await ctx.send(file=File(fp, "wordanal.json"))


async def setup(bot: BOT_TYPES) -> None:
    await bot.add_cog(WordAnalysis(bot))
