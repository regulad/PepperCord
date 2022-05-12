import logging
from collections import deque
from typing import Union, Type, MutableMapping

import discord
from discord import Member
from discord.ext import commands
from discord.user import BaseUser
from motor.motor_asyncio import AsyncIOMotorDatabase

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

        self._context_cache: deque[tuple[discord.Message, commands.Context]] = deque(
            maxlen=10
        )
        self._user_doc_cache: deque[tuple[BaseUser | Member, Document]] = deque(
            maxlen=30
        )
        self._guild_doc_cache: deque[tuple[discord.Guild, Document]] = deque(maxlen=30)

        super().__init__(
            command_prefix,
            help_command=help_command,
            description=description,
            **options,
        )

    @property
    def database(self) -> AsyncIOMotorDatabase:
        return self._database

    @property
    def config(self) -> CONFIGURATION_PROVIDERS:
        return self._config

    async def get_command_document(self, command: commands.Command):
        """Gets a command's document from the database."""

        return await Document.get_document(
            self._database["commands"],
            {
                "name": command.name,
                "cog": command.cog_name
                if (hasattr(command, "cog_name") and command.cog_name is not None)
                else None,
            },
        )

    async def get_guild_document(self, model: discord.Guild) -> Document:
        """Gets a guild's document from the database."""

        for other, document in self._guild_doc_cache:
            if other == model:
                return document
        else:
            document: Document = await Document.get_document(
                self._database["guild"], {"_id": model.id}
            )
            self._guild_doc_cache.appendleft((model, document))
            return document

    async def get_user_document(self, model: Member | BaseUser) -> Document:
        """Gets a user's document from the database."""

        for other, document in self._user_doc_cache:
            if other == model:
                return document
        else:
            document: Document = await Document.get_document(
                self._database["user"], {"_id": model.id}
            )
            self._user_doc_cache.appendleft((model, document))
            return document

    async def get_context(
            self, message: discord.Message, *, cls: Type[commands.Context] = CustomContext
    ):
        for other, context in self._context_cache:
            if isinstance(context, cls) and other == message:
                return context
        else:
            result: cls = await super().get_context(message, cls=cls)
            await self.wait_for_dispatch("context_creation", result)
            self._context_cache.appendleft((message, result))
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


class CustomBot(CustomBotBase, CustomClientBase, discord.Client):
    pass


BOT_TYPES = CustomBot

__all__ = ["CustomBot", "BOT_TYPES", "CONFIGURATION_PROVIDERS"]
