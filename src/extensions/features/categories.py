from typing import Sequence
from discord import CategoryChannel, Embed, Message, Thread
from discord.app_commands import (
    default_permissions,
    guild_only as ac_guild_only,
    describe,
)
from discord.ext.commands import (
    Cog,
    hybrid_group,
    bot_has_permissions,
    has_permissions,
    guild_only,
)
from discord.ext.menus import ListPageSource, MenuPages

from utils.bots.bot import CustomBot
from utils.bots.context import CustomContext


class CategoryList(
    ListPageSource[CategoryChannel, MenuPages[CustomBot, CustomContext, "CategoryList"]]
):
    def __init__(
        self, entries: Sequence[CategoryChannel], *, per_page: int = 15
    ) -> None:
        if not (per_page > 1):
            raise RuntimeError("This source must be initialized with per_page > 1")
        super().__init__(entries, per_page=per_page)

    async def format_page(
        self,
        menu: MenuPages[CustomBot, CustomContext, "CategoryList"],
        entries: list[CategoryChannel] | CategoryChannel,
    ) -> Embed:
        offset = menu.current_page * self.per_page
        assert isinstance(
            entries, list
        )  # guranteed at runtime by runtimeerror being raised in init

        embed = Embed(title=f"All tracked categories", color=0xBBFAFA)
        embed.set_footer(text=f"Page {menu.current_page + 1}/{self.get_max_pages()}")

        for iteration, entry in enumerate(entries, start=offset):
            embed.add_field(
                name=f"{iteration + 1}. {entry.name}",
                value=entry.mention,
                inline=False,
            )

        return embed


class Categories(Cog):
    """A set of tools for managing categories in a Discord server."""

    def __init__(self, bot: CustomBot) -> None:
        self.bot: CustomBot = bot

    @Cog.listener()
    async def on_message(self, message: Message) -> None:
        ctx: CustomContext = await self.bot.get_context(message)
        if (
            ctx.guild is not None
            and ctx.channel.category is not None  # type: ignore[union-attr]  # guaranteed by ctx.guild is not None
            and not isinstance(ctx.channel, Thread)
            and hasattr(ctx.channel, "position")
            and (
                ctx.channel.category.id  # type: ignore[union-attr]  # guaranteed by ctx.guild is not None
                in ctx["guild_document"].get("autosort_categories", [])
            )
        ):
            await ctx.channel.edit(position=ctx.channel.category.position)  # type: ignore[union-attr]  # guaranteed by ctx.guild is not None

    @hybrid_group(fallback="list")  # type: ignore[arg-type]  # bad d.py export
    @bot_has_permissions(manage_channels=True)
    @has_permissions(manage_channels=True)
    @default_permissions(manage_channels=True)
    @guild_only()
    @ac_guild_only()
    async def autosort(self, ctx: CustomContext) -> None:
        """
        Lists all categories registered for AutoSorting.
        Categories registered for AutoSorting have their channels moved to the top as soon as they have a message sent.
        """
        assert ctx.guild is not None  # guaranteed at runtime
        async with ctx.typing():
            menu: MenuPages[CustomBot, CustomContext, "CategoryList"] = MenuPages(
                CategoryList(
                    [
                        category
                        for category in [
                            ctx.guild.get_channel(category_id)
                            for category_id in ctx["guild_document"].get(
                                "autosort_categories", []
                            )
                        ]
                        if (
                            category is not None
                            and isinstance(category, CategoryChannel)
                        )
                    ]
                )
            )
            await menu.start(ctx)

    @autosort.command()  # type: ignore[arg-type]  # bad d.py export
    @bot_has_permissions(manage_channels=True)
    @has_permissions(manage_channels=True)
    @guild_only()
    @describe(category="The category in question.")
    async def add(self, ctx: CustomContext, category: CategoryChannel) -> None:
        """Adds a category to the list of categories with AutoSort."""
        async with ctx.typing(ephemeral=True):
            await ctx["guild_document"].update_db(
                {"$push": {"autosort_categories": category.id}}
            )
            await ctx.send(f"Added {category.mention}.", ephemeral=True)

    @autosort.command()  # type: ignore[arg-type]  # bad d.py export
    @bot_has_permissions(manage_channels=True)
    @has_permissions(manage_channels=True)
    @guild_only()
    @describe(category="The category in question.")
    async def remove(self, ctx: CustomContext, category: CategoryChannel) -> None:
        """Removes a category from the list of categories with AutoSort."""
        async with ctx.typing(ephemeral=True):
            await ctx["guild_document"].update_db(
                {"pull": {"autosort_categories": category.id}}
            )
            await ctx.send(f"Removed {category.mention}.", ephemeral=True)


async def setup(bot: CustomBot) -> None:
    await bot.add_cog(Categories(bot))
