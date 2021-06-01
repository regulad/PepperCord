import discord
from discord.ext import menus

import utils.converters


class QueueMenuSource(menus.ListPageSource):
    def __init__(self, entries: list, msg: str):
        self.msg = msg
        super().__init__(entries, per_page=10)

    async def format_page(self, menu, page_entries):
        offset = menu.current_page * self.per_page
        base_embed = discord.Embed(title=self.msg, description=f"{len(self.entries)} total tracks")

        time_until = 0
        for track in self.entries[:offset]:
            duration = track.info["duration"]
            time_until += duration

        for iteration, value in enumerate(page_entries, start=offset):
            title = value.info["title"]
            duration = value.info["duration"]
            url = value.info["webpage_url"]
            invoker = value.invoker
            time_until += duration
            base_embed.add_field(
                name=f"{iteration + 1}: {utils.converters.duration_to_str(time_until)} left",
                value=f"[{title}]({url})\n{utils.converters.duration_to_str(duration)} long\nadded by {invoker.display_name}",
                inline=False,
            )
        return base_embed
