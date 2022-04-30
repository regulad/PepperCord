import os
from json import load
from typing import Optional

import discord
from aiohttp import ClientSession
from asyncgTTS import (
    ServiceAccount,
    AsyncGTTSSession,
    SynthesisInput,
    VoiceSelectionParams,
    TextSynthesizeRequestBody,
)
from discord.app_commands import describe
from discord.ext.commands import (
    Context,
    hybrid_command,
    Cog,
    cooldown,
    BucketType,
    hybrid_group,
)
from discord.ext.menus import ListPageSource, ViewMenuPages

from utils import bots
from utils.checks import check_voice_client
from utils.fixes import FFmpegPCMAudioBytes as FFmpegPCMAudio
from utils.sources import EnhancedSourceWrapper


class VoiceDoesNotExist(Exception):
    pass


class TTSSource(EnhancedSourceWrapper):
    def __init__(
            self,
            source: FFmpegPCMAudio,
            volume=0.7,
            *,
            text: str,
            invoker: discord.abc.User,
    ):
        super().__init__(source, volume, invoker=invoker)

        self.text = text

    @property
    def name(self) -> str:
        return self.text

    @classmethod
    async def from_text(
            cls,
            text: str,
            voice: str,
            tts_session: AsyncGTTSSession,
            invoker: discord.abc.User,
    ):
        synthesis_input: SynthesisInput = SynthesisInput(text)
        voice_selection_params: VoiceSelectionParams = VoiceSelectionParams(
            "en-US", voice
        )
        text_synthesize_request_body: TextSynthesizeRequestBody = (
            TextSynthesizeRequestBody(
                synthesis_input, voice_input=voice_selection_params
            )
        )
        audio_bytes = await tts_session.synthesize(text_synthesize_request_body)
        source = FFmpegPCMAudio(audio_bytes, pipe=True)
        return cls(source, text=text, invoker=invoker)


class LanguageSource(ListPageSource):
    async def format_page(self, menu, page_entries):
        offset = menu.current_page * self.per_page
        base_embed = discord.Embed(title="Available Languages")
        base_embed.set_footer(
            text=f"Page {menu.current_page + 1}/{self.get_max_pages()}"
        )
        for iteration, value in enumerate(page_entries, start=offset):
            base_embed.add_field(
                name=f"{iteration + 1}: {value['name']}",
                value=f"Gender: {value['ssmlGender'].title()}"
                      f"\nSample Rate: {round(value['naturalSampleRateHertz'] / 1000, 1)}kHz",
                inline=False,
            )
        return base_embed


class TextToSpeech(Cog):
    """Sends Text-To-Speech in the voice chat."""

    def __init__(self, bot: bots.BOT_TYPES, service_account: ServiceAccount) -> None:
        self._async_gtts_session: AsyncGTTSSession | None = None
        self._service_account: ServiceAccount = service_account
        self.bot: bots.BOT_TYPES = bot

    async def cog_load(self) -> None:
        if self._async_gtts_session is None:
            self._async_gtts_session = AsyncGTTSSession.from_service_account(
                self._service_account, client_session=ClientSession()
            )

    async def cog_unload(self) -> None:
        if self._async_gtts_session is not None:
            await self._async_gtts_session.client_session.close()

    @hybrid_command(aliases=["tts"])
    @cooldown(10, 2, BucketType.user)
    @describe(text="The text that will be converted to speech.")
    @check_voice_client
    async def texttospeech(
            self,
            ctx: bots.CustomContext,
            *,
            text: str,
    ) -> None:
        """Have the bot talk for you in a voice channel."""
        await ctx.defer(ephemeral=True)

        source = await TTSSource.from_text(
            text,
            ctx["author_document"].get("voice", "en-US-Wavenet-D"),
            self._async_gtts_session,
            ctx.author,
        )

        if ctx.voice_client.queue.qsize() > 0:
            ctx.voice_client.queue.deque.appendleft(source)  # Meh.
        else:
            await ctx.voice_client.queue.put(source)

        await ctx.send("Added text.", ephemeral=True)

    @hybrid_group()
    async def ttssettings(self, ctx: bots.CustomContext) -> None:
        pass

    @ttssettings.command()
    @describe(
        desiredvoice="The voice that the bot will attempt to use when talking for you. See the command listvoices."
    )
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
    async def listvoices(self, ctx: bots.CustomContext) -> None:
        """Lists all voices that the bot can use."""
        await ctx.defer(ephemeral=True)
        voices: list = await self._async_gtts_session.get_voices("en-US")
        await ViewMenuPages(source=LanguageSource(voices, per_page=6)).start(
            ctx, ephemeral=True
        )


async def setup(bot: bots.BOT_TYPES) -> None:
    if os.path.exists("config/SERVICE_ACCOUNT.JSON"):
        with open("config/SERVICE_ACCOUNT.JSON") as service_account_fp:
            service_account: ServiceAccount = ServiceAccount.from_service_account_dict(
                load(service_account_fp)
            )

        await bot.add_cog(TextToSpeech(bot, service_account))
