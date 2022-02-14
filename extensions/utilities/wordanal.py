from io import StringIO
from json import dump
from typing import Optional

from discord import Embed, File
from discord.ext.commands import Cog, command, cooldown, has_permissions, BucketType, Option
from discord.ext.menus import ListPageSource, ViewMenuPages

from utils.bots import BOT_TYPES, CustomContext


class LevelSource(ListPageSource):
    def __init__(self, data, guild):
        self.guild = guild
        super().__init__(data, per_page=10)

    async def format_page(self, menu, page_entries):
        offset = menu.current_page * self.per_page
        base_embed = Embed(
            title=f"{self.guild.name}'s Word Leaderboard"
        )
        if self.guild.icon is not None:
            base_embed.set_thumbnail(url=self.guild.icon.url)
        for iteration, value in enumerate(page_entries, start=offset):
            base_embed.add_field(
                name=f"{iteration + 1}. {value[0]}",
                value=f"{value[1]} occurrences",
                inline=False
            )
        return base_embed


class WordAnalysis(Cog):
    """Find the most common words in your server's messages."""

    def __init__(self, bot: BOT_TYPES) -> None:
        self.bot: BOT_TYPES = bot

    @command()
    @cooldown(1, 2400, type=BucketType.guild)
    @has_permissions(manage_messages=True)
    async def wordanal(
            self,
            ctx: CustomContext,
            length: Optional[int] = Option(
                None,
                description="The length of the word to find. Leave empty for any length."
            ),
            should_dump: Optional[bool] = Option(False, description="Dump the word analysis to a file."),
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

        quantity: dict[str, int] = {k: v for k, v in sorted(quantity.items(), key=lambda item: item[1], reverse=True)}

        source: LevelSource = LevelSource(sorted(quantity.items(), key=lambda x: x[1], reverse=True), ctx.guild)

        await ViewMenuPages(source).start(ctx)

        if should_dump:
            with StringIO() as f:
                dump(quantity, f, indent=4)
                f.seek(0)
                await ctx.send(file=File(f, "wordanal.json"))


def setup(bot: BOT_TYPES) -> None:
    bot.add_cog(WordAnalysis(bot))
