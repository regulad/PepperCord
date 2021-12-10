from typing import List, Union, Optional

import discord
from discord.ext import menus, commands
from pretty_help import Paginator, PrettyMenu

from utils.bots import CustomContext


class PlainListPageSource(menus.ListPageSource):
    async def format_page(self, menu, page):
        return page


class BetterMenu(PrettyMenu):
    async def send_pages(
        self,
        ctx: CustomContext,
        destination: discord.abc.Messageable,
        pages: List[discord.Embed],
    ) -> None:
        (
            await menus.ViewMenuPages(
                PlainListPageSource(pages, per_page=1), delete_message_after=True
            ).start(ctx, channel=destination)
        )


class BetterPaginator(Paginator):
    def __init__(
        self,
        show_index: bool = True,
        color: Union[int, discord.Colour] = 0,
        *,
        ending_note: Optional[str] = None,
        char_limit: int = 6000,
        field_limit: int = 25,
        prefix: str = "```",
        suffix: str = "```",
    ) -> None:  # To be honest, I'm not sure why I did this. This library sucks big time.
        super().__init__(show_index, color)
        if ending_note is not None:
            self.ending_note = ending_note
        if char_limit != 6000:
            self.char_limit = char_limit
        if field_limit != 25:
            self.field_limit = field_limit
        if prefix != "```":
            self.prefix = prefix
        if suffix != "```":
            self.suffix = suffix

    def _add_command_fields(
        self, embed: discord.Embed, page_title: str, commands: List[commands.Command]
    ):
        """
        Adds command fields to Category/Cog and Command Group pages

        Args:
            embed (discord.Embed): The page to add command descriptions
            page_title (str): The title of the page
            commands (List[commands.Command]): The list of commands for the fields
        """
        for command in commands:
            if not self._check_embed(
                embed,
                self.ending_note,
                command.name,
                command.short_doc,
                self.prefix,
                self.suffix,
            ):
                self._add_page(embed)
                embed = self._new_page(page_title, embed.description)

            embed.add_field(
                name=command.name,
                value=f'{self.prefix}{short_desc(command) or "No Description"}{self.suffix}',
                inline=False,
            )
        self._add_page(embed)


def short_desc(command: commands.Command) -> str:
    """:class:`str`: Gets the "short" documentation of a command.

    By default, this is the :attr:`.brief` attribute.
    If that lookup leads to an empty string then the first line of the
    :attr:`.help` attribute is used instead.
    """

    if command.brief is not None:
        return command.brief
    elif command.description is not None:
        return command.description.split("\n", 1)[0]
    else:
        return ""


__all__ = ["BetterMenu", "BetterPaginator"]
