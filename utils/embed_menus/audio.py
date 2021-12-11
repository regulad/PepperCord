import discord
from discord.ext import menus

from utils import converters, sources


class QueueMenuSource(menus.ListPageSource):
    def __init__(self, entries: list, msg: str):
        self.msg = msg
        super().__init__(entries, per_page=10)

    async def format_page(self, menu, page_entries):
        offset = menu.current_page * self.per_page
        base_embed = discord.Embed(
            title=self.msg, description=f"{len(self.entries)} total tracks"
        )

        time_until = 0
        for track in self.entries[:offset]:
            if isinstance(track, sources.YTDLSource):
                duration = track.info["duration"]
                time_until += duration

        for iteration, value in enumerate(page_entries, start=offset):
            if isinstance(value, sources.YTDLSource):
                title = value.info["title"]
                duration = value.info["duration"]
                url = value.info["webpage_url"]
                invoker = value.invoker
                time_until += duration
                base_embed.add_field(
                    name=f"{iteration + 1}: {converters.duration_to_str(time_until)} left",
                    value=f"[{title}]({url})\n{converters.duration_to_str(duration)} long"
                    f"\nAdded by: {invoker.display_name}",
                    inline=False,
                )
            elif isinstance(value, sources.TTSSource):
                base_embed.add_field(
                    name=f"{iteration + 1}: {converters.duration_to_str(time_until)} left",
                    value=f'"{value.text}"\nAdded by: {value.invoker.display_name}',
                )
            else:
                base_embed.add_field(
                    name=f"{iteration + 1}: {converters.duration_to_str(time_until)} left",
                    value="Unknown",
                    inline=False,
                )
        return base_embed


class AudioSourceMenu(menus.ViewMenu):
    """An embed menu that makes displaying a source fancy."""

    def __init__(self, source: discord.AudioSource, **kwargs):
        self.source = source

        super().__init__(**kwargs)

    async def send_initial_message(self, ctx, channel):
        if self.source is None:
            await ctx.send("There is no source.")
        else:
            if isinstance(self.source, sources.YTDLSource):
                info = self.source.info
                embed = (
                    discord.Embed(title=info["title"], description=info["webpage_url"])
                    .add_field(
                        name="Duration:",
                        value=converters.duration_to_str(info["duration"]),
                    )
                    .add_field(name="Added by:", value=self.source.invoker.display_name)
                )

                thumbnail = info.get("thumbnail")
                if thumbnail is not None:
                    embed.set_thumbnail(url=thumbnail)

                uploader = info.get("uploader")
                uploader_url = info.get("uploader_url")
                if uploader is not None and uploader_url is not None:
                    embed.set_author(name=uploader, url=uploader_url)

                return await channel.send(embed=embed, **self._get_kwargs())
            elif isinstance(self.source, sources.TTSSource):
                embed = discord.Embed(
                    title="Text-To-Speech", description=f'"{self.source.text}"'
                ).add_field(name="Added by:", value=self.source.invoker.display_name)

                return await channel.send(embed=embed, **self._get_kwargs())
            else:
                return await ctx.send(
                    "Information cannot be displayed for the currently selected source.",
                    **self._get_kwargs(),
                )
