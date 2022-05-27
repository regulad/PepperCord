from discord import CategoryChannel, Embed, Message
from discord.app_commands import default_permissions, guild_only as ac_guild_only, describe
from discord.ext.commands import Cog, hybrid_group, bot_has_permissions, has_permissions, guild_only
from discord.ext.menus import ListPageSource, ViewMenuPages

from utils.bots import BOT_TYPES, CustomContext


class CategoryList(ListPageSource):
    def __init__(self, entries: list[CategoryChannel], *, per_page=15):
        super().__init__(entries, per_page=per_page)

    async def format_page(self, menu, entries):
        offset = menu.current_page * self.per_page

        embed: Embed = Embed(title=f"All campaigns", color=0xBBFAFA)
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

    def __init__(self, bot: BOT_TYPES) -> None:
        self.bot: BOT_TYPES = bot

    @Cog.listener()
    async def on_message(self, message: Message) -> None:
        ctx: CustomContext = await self.bot.get_context(message)
        if ctx.channel.category is not None \
                and (ctx.channel.category.id in ctx["guild_document"].get("autosort_categories", [])):
            await ctx.channel.edit(position=ctx.channel.category.position)

    @hybrid_group(fallback="list")
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
        async with ctx.typing(ephemeral=True):
            await ViewMenuPages(
                CategoryList(
                    [
                        category
                        for category
                        in [
                        ctx.guild.get_channel(category_id)
                        for category_id
                        in ctx["guild_document"].get("autosort_categories", [])
                    ]
                        if (category is not None and isinstance(category, CategoryChannel))
                    ]
                )
            ).start(ctx, ephemeral=True)

    @autosort.command()
    @bot_has_permissions(manage_channels=True)
    @has_permissions(manage_channels=True)
    @guild_only()
    @describe(category="The category in question.")
    async def add(self, ctx: CustomContext, category: CategoryChannel) -> None:
        """Adds a category to the list of categories with AutoSort."""
        async with ctx.typing(ephemeral=True):
            await ctx["guild_document"].update_db({"$push": {"autosort_categories": category.id}})
            await ctx.send(f"Added {category.mention}.", ephemeral=True)

    @autosort.command()
    @bot_has_permissions(manage_channels=True)
    @has_permissions(manage_channels=True)
    @guild_only()
    @describe(category="The category in question.")
    async def remove(self, ctx: CustomContext, category: CategoryChannel) -> None:
        """Removes a category from the list of categories with AutoSort."""
        async with ctx.typing(ephemeral=True):
            await ctx["guild_document"].update_db({"pull": {"autosort_categories": category.id}})
            await ctx.send(f"Removed {category.mention}.", ephemeral=True)


async def setup(bot: BOT_TYPES) -> None:
    await bot.add_cog(Categories(bot))
