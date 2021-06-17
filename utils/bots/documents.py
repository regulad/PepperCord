from typing import Union, Any

from discord import Guild, Member, User
from utils.database import Document


class ModelDocument(Document):
    """Represents a document fetched via a model."""

    MODEL_TYPE = Any

    def __init__(self, *args, collection, query: dict, model: MODEL_TYPE, **kwargs):
        self._model = model

        super().__init__(*args, collection=collection, query=query, **kwargs)

    @classmethod
    async def get_from_model(cls, collection, model: MODEL_TYPE):
        return await cls.get_document(collection, {"_id": model.id}, model=model)

    @property
    def model(self) -> MODEL_TYPE:
        return self._model


class UserDocument(ModelDocument):
    """Represents the data collected on a user in their document."""

    MODEL_TYPE = Union[Member, User]


class GuildDocument(ModelDocument):
    """Represents the data collected on a guild in it's document."""

    MODEL_TYPE = Guild


__all__ = ["ModelDocument", "UserDocument", "GuildDocument"]
