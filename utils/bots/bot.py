import logging
from typing import Union, List, Type, Optional, MutableMapping

import discord
from discord.ext import commands

from utils.audio import AudioPlayer
from utils.database import Document
from .context import CustomContext

CONFIGURATION_PROVIDERS = Union[dict, MutableMapping]


class CustomBotBase(commands.bot.BotBase):
    def __init__(
            self,
            command_prefix,
            help_command=commands.HelpCommand(),
            description=None,
            *,
            database,
            config: CONFIGURATION_PROVIDERS,
            **options,
    ):
        self._database = database
        self._config: CONFIGURATION_PROVIDERS = config

        self._audio_players: List[AudioPlayer] = []
        # TODO: Having audio players stored here prevents them from being garbage collected, causing a memory leak.
        # Ideally, they should be deleted once the VoiceClient ceases to exist.
        # A subclass of VoiceClient may be a good idea, but that isn't very well documented.
        # There doesn't seem to be an event dispatched when a VoiceClient is destroyed. Perhaps implement that?

        super().__init__(
            command_prefix,
            help_command=help_command,
            description=description,
            **options,
        )

    @property
    def config(self) -> CONFIGURATION_PROVIDERS:
        return self._config

    @property
    def home_guild(self) -> discord.Guild:
        return super().get_guild(int(self.config.get("PEPPERCORD_HOME_GUILD", "730908012851757078")))

    @property
    def scratch_channel(self) -> discord.TextChannel:
        return self.home_guild.get_channel(int(self.config.get("PEPPERCORD_SCRATCH_CHANNEL", "933823355231031386")))

    def get_audio_player(
            self, voice_client: Optional[discord.VoiceClient]
    ) -> AudioPlayer:
        """Gets or creates audio player from VoiceClient."""

        for player in self._audio_players:
            if player.voice_client == voice_client:
                return player
        else:
            if voice_client is not None:
                music_player = AudioPlayer(voice_client)
                self._audio_players.append(music_player)
                return music_player
            else:
                return None

    async def get_command_document(self, command: commands.Command):
        """Gets a command's document from the database."""

        return await Document.get_document(
            self._database["commands"],
            {
                "name": command.name,
                "cog": command.cog_name,
            },
        )

    async def get_guild_document(self, model: discord.Guild) -> Document:
        """Gets a guild's document from the database."""

        return await Document.get_document(self._database["guild"], {"_id": model.id})

    async def get_user_document(
            self, model: Union[discord.Member, discord.User]
    ) -> Document:
        """Gets a user's document from the database."""

        return await Document.get_document(self._database["user"], {"_id": model.id})

    async def get_context(
            self, message, *, cls: Type[commands.Context] = CustomContext
    ):
        result: cls = await super().get_context(message, cls=cls)
        await self.wait_for_dispatch("context_creation", result)
        # Possiblily could safely be made asynchronous?
        # We don't need to wait for one to complete to start the other,
        # just for all to complete before the context is sent.
        return result

    async def on_context_creation(
            self, ctx: commands.Context
    ) -> None:  # Placeholder method
        pass

    async def wait_for_dispatch(self, event_name, *args, **kwargs):
        await super().wait_for_dispatch(event_name, *args, **kwargs)
        ev = "on_" + event_name
        for event in self.extra_events.get(ev, []):
            await super()._schedule_event(event, ev, *args, **kwargs)


class CustomClientBase:
    async def wait_for_dispatch(self, event: str, *args, **kwargs):
        logging.debug("Dispatching event %s", event)
        method = "on_" + event

        listeners = self._listeners.get(event)
        if listeners:
            removed = []
            for i, (future, condition) in enumerate(listeners):
                if future.cancelled():
                    removed.append(i)
                    continue

                try:
                    result = condition(*args)
                except Exception as exc:
                    future.set_exception(exc)
                    removed.append(i)
                else:
                    if result:
                        if len(args) == 0:
                            future.set_result(None)
                        elif len(args) == 1:
                            future.set_result(args[0])
                        else:
                            future.set_result(args)
                        removed.append(i)

            if len(removed) == len(listeners):
                self._listeners.pop(event)
            else:
                for idx in reversed(removed):
                    del listeners[idx]

        try:
            coro = getattr(self, method)
        except AttributeError:
            pass
        else:
            await self._schedule_event(coro, method, *args, **kwargs)


class CustomAutoShardedBot(CustomBotBase, CustomClientBase, discord.AutoShardedClient):
    pass


class CustomBot(CustomBotBase, CustomClientBase, discord.Client):
    pass


BOT_TYPES = Union[CustomBot, CustomAutoShardedBot]

__all__ = ["CustomBot", "CustomAutoShardedBot", "BOT_TYPES", "CONFIGURATION_PROVIDERS"]
