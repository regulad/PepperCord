from __future__ import annotations

import datetime
from typing import TYPE_CHECKING, Any, Optional, Union, cast

from discord import ButtonStyle, Embed, Guild
from discord.ext.commands import Cog, guild_only, CheckFailure, command
from discord.ext.menus import ListPageSource, Menu, MenuPages

from utils.bots.bot import CustomBot
from utils.bots.context import CustomContext


if TYPE_CHECKING:
    from _typeshed import SupportsRichComparison

# Because ListPageSource comes from legacy untyped code and is being patched over with a stub, we need to do this to make sure it never gets subscripted at runtime.
if TYPE_CHECKING:
    _GuildsMenuList_Base = ListPageSource[
        Guild, "MenuPages[CustomBot, CustomContext, GuildsMenuList]"
    ]
else:
    _GuildsMenuList_Base = ListPageSource


class GuildsMenuList(_GuildsMenuList_Base):
    async def format_page(
        self,
        menu: "MenuPages[CustomBot, CustomContext, GuildsMenuList]",
        page_entries: Union[Guild, list[Guild]],
    ) -> Embed:
        assert not isinstance(
            page_entries, Guild
        )  # guaranteed at runtime since per_page with this class is never initialized to 1
        offset = menu.current_page * self.per_page
        base_embed = Embed(title="Guilds")
        base_embed.set_footer(
            text=f"Page {menu.current_page + 1}/{self.get_max_pages()}"
        )
        for iteration, value in enumerate(page_entries, start=offset):
            base_embed.add_field(
                name=f"{iteration + 1}: {value.name} ({value.id})",
                value=f"{value.member_count} members",
                inline=False,
            )
        return base_embed


class OwnerUtils(Cog):
    """Tools to be used by the bots developer to operate the bots."""

    def __init__(self, bot: CustomBot) -> None:
        self.bot = bot

    async def cog_check(self, ctx: CustomContext) -> bool:  # type: ignore[override]  # compatible
        if not await ctx.bot.is_owner(ctx.author):
            raise CheckFailure("You do not own this bot.")
        return True

    @command()
    @guild_only()
    async def nick(
        self,
        ctx: CustomContext,
        *,
        nickname: Optional[str],
    ) -> None:
        """Sets the bots nickname in this guild to a desired string."""
        await cast(Guild, ctx.guild).me.edit(nick=nickname)  # cast: enforced by check
        await ctx.send("Changed nickname", ephemeral=True)

    @command()
    async def guilds(self, ctx: CustomContext) -> None:
        """List all the guilds the bot is in."""

        def guild_comp_key(g: Guild) -> SupportsRichComparison:
            if g.me.joined_at is not None:
                return g.me.joined_at
            else:
                # This is weird...
                raise RuntimeError(
                    f"Got a None joined_at in guild {g}, but we aren't a guest!"
                )

        menu: "MenuPages[CustomBot, CustomContext, GuildsMenuList]" = MenuPages(
            GuildsMenuList(sorted(ctx.bot.guilds, key=guild_comp_key), per_page=10)
        )

        # We have to do this because the legacy menu doesn't respond to the Interaction
        await ctx.send("Bringing up your menu...", ephemeral=True)
        await menu.start(ctx)


async def setup(bot: CustomBot) -> None:
    await bot.add_cog(OwnerUtils(bot))
