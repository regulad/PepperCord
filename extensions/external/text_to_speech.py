import os
from json import load
from typing import Optional

import discord
from aiohttp import ClientSession
from asyncgTTS import ServiceAccount, AsyncGTTSSession
from discord.ext import commands, menus

from utils import checks, bots
from utils.embed_menus import AudioSourceMenu
from utils.sources import TTSSource


class VoiceDoesNotExist(Exception):
    pass


class LanguageSource(menus.ListPageSource):
    async def format_page(self, menu, page_entries):
        offset = menu.current_page * self.per_page
        base_embed = discord.Embed(title="Available Languages")
        for iteration, value in enumerate(page_entries, start=offset):
            base_embed.add_field(
                name=f"{iteration + 1}: {value['name']}",
                value=f"Gender: {value['ssmlGender'].title()}"
                f"\nSample Rate: {round(value['naturalSampleRateHertz'] / 1000, 1)}kHz",
                inline=False,
            )
        return base_embed


class TextToSpeech(commands.Cog):
    """Sends Text-To-Speech in the voice chat."""

    def __init__(
        self, bot: bots.BOT_TYPES, async_gtts_client_session: AsyncGTTSSession
    ) -> None:
        self._async_gtts_session: AsyncGTTSSession = async_gtts_client_session
        self.bot: bots.BOT_TYPES = bot

    async def cog_check(self, ctx: bots.CustomContext) -> bool:
        return await checks.is_in_voice(ctx)

    async def cog_before_invoke(self, ctx: bots.CustomContext) -> None:
        if ctx.voice_client is None:
            await ctx.author.voice.channel.connect()

    def cog_unload(self) -> None:
        self.bot.loop.create_task(self._async_gtts_session.client_session.close())

    @commands.command()
    @commands.cooldown(10, 2, commands.BucketType.user)
    async def texttospeech(self, ctx: bots.CustomContext, *, text: str) -> None:
        """Have the bot talk for you in a voice channel."""
        await ctx.defer(ephemeral=True)

        source = await TTSSource.from_text(
            text,
            ctx["author_document"].get("voice", "en-US-Wavenet-D"),
            self._async_gtts_session,
            ctx.author,
        )

        if not len(list(ctx["audio_player"]().queue.deque)) > 0:
            ctx["audio_player"]().queue.put_nowait(source)
        else:
            ctx["audio_player"]().queue.deque.appendleft(source)  # Meh.

        await AudioSourceMenu(source).start(ctx, ephemeral=True)

    @commands.group()
    async def ttssettings(self, ctx: bots.CustomContext) -> None:
        pass

    @ttssettings.command()
    async def setvoice(
        self,
        ctx: bots.CustomContext,
        *,
        desiredvoice: Optional[str] = "en-US-Wavenet-D",
    ) -> None:
        """Allows you to select a voice that the bot will use to portray you in Text-To-Speech conversations."""
        await ctx.defer(ephemeral=True)

        voices: list = await self._async_gtts_session.get_voices("en-US")

        for voice in voices:
            if voice["name"] == desiredvoice:
                break
        else:
            raise VoiceDoesNotExist

        await ctx["author_document"].update_db({"$set": {"voice": desiredvoice}})

        await ctx.send("Updated.", ephemeral=True)

    @ttssettings.command()
    async def list_voices(self, ctx: bots.CustomContext) -> None:
        """Lists all voices that the bot can use."""
        await ctx.defer(ephemeral=True)
        voices: list = await self._async_gtts_session.get_voices("en-US")
        await menus.ViewMenuPages(source=LanguageSource(voices, per_page=6)).start(ctx, ephemeral=True)


def setup(bot: bots.BOT_TYPES):
    if os.path.exists("config/SERVICE_ACCOUNT.JSON"):
        with open("config/SERVICE_ACCOUNT.JSON") as service_account_fp:
            service_account = ServiceAccount.from_service_account_dict(
                load(service_account_fp)
            )

        bot.add_cog(
            TextToSpeech(
                bot,
                AsyncGTTSSession.from_service_account(
                    service_account, client_session=ClientSession()
                ),
            )
        )
