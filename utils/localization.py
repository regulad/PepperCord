import json
from enum import Enum


class Message(Enum):
    """Represents a message that the bot may send, localized."""

    BOT_NAME = "bot_name"
    SELECT_LANGUAGE = "select_lang"
    CUSTOM_COMMAND_GET = "cc_get"
    PREFIX_GET = "prefix_get"
    THREAD_UNARCHIVED = "thread_unarchive"


class Locale(Enum):
    """An enumerator of locales."""

    catspeak = json.load(open("resources/locales/catspeak.json"))
    en_US = json.load(
        open("resources/locales/en_US.json")
    )  # Hmm.... This isn't perfect.

    def get_message(self, message: Message) -> str:
        """Get the locale's definition of a message. If it is not specified, get it from en_US."""

        return self.value.get(message.value) or self.__class__.en_US.value.get(
            message.value
        )
        # TODO: Perhaps some sort of automatic translation if a language does not have a message described?


__all__ = ["Locale", "Message"]
