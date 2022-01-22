from typing import Optional, cast

from discord.ext.commands import command, Cog, Option
from discord import Member, VoiceState, VoiceClient
from youtube_dl import YoutubeDL

from utils.sources import YTDLSource, YTDL_FORMAT_OPTIONS
from utils.bots import BOT_TYPES, CustomVoiceClient, CustomContext
from utils.checks import can_have_voice_client
from utils.validators import str_is_url


class Audio(Cog):
    """Controls for the audio features of the bot."""

    def __init__(self, bot: BOT_TYPES) -> None:
        self.bot: BOT_TYPES = bot
        self._file_downloader: YoutubeDL = YoutubeDL(YTDL_FORMAT_OPTIONS)

    @Cog.listener("on_voice_state_update")
    async def start_task(self, member: Member, before: VoiceState, after: VoiceState) -> None:
        if member == member.guild.me and before.channel is None and after.channel is not None:
            voice_client: Optional[VoiceClient] = member.guild.voice_client
            if voice_client is not None:
                cast(CustomVoiceClient, voice_client).create_task()

    @Cog.listener("on_voice_state_update")
    async def on_left_alone(self, member: Member, before: VoiceState, after: VoiceState) -> None:
        if member.guild.voice_client is not None and member.guild.voice_client.channel == before.channel:
            if len(before.channel.members) == 1:
                await member.guild.voice_client.disconnect(force=False)

    async def cog_check(self, ctx: CustomContext) -> bool:
        if await can_have_voice_client(ctx):
            return True
        else:
            raise

    @command()
    async def play(
            self,
            ctx: CustomContext,
            *,
            query: str = Option(description="The video to search on YouTube, or a url.")
    ) -> None:
        await ctx.defer()
        query: str = query if str_is_url(query) else f"ytsearch:{query}"
        for source in await YTDLSource.from_url(self._file_downloader, query, ctx.author, loop=ctx.voice_client.loop):
            await ctx.voice_client.queue.put(source)
        await ctx.send("Done")


def setup(bot: BOT_TYPES) -> None:
    bot.add_cog(Audio(bot))
