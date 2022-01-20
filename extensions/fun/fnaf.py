import random
from enum import Enum, auto
from typing import Optional, ValuesView

from discord.ext import commands

from utils import bots


class DisplayTime(Enum):
    """Represents a time displayed to the player."""
    TWELVE_AM = auto()
    ONE_AM = auto()
    TWO_AM = auto()
    THREE_AM = auto()
    FOUR_AM = auto()
    FIVE_AM = auto()

    @property
    def offset(self) -> int:
        match self:
            case DisplayTime.TWELVE_AM:
                pass
            case DisplayTime.ONE_AM:
                return 0
            case DisplayTime.TWO_AM:
                pass
            case DisplayTime.THREE_AM:
                return 1
            case DisplayTime.FOUR_AM:
                pass
            case DisplayTime.FIVE_AM:
                return 2


class Animatronic(Enum):
    """Represents an animatronic."""
    FREDDY = auto()
    BONNIE = auto()
    CHICA = auto()
    FOXY = auto()

    @property
    def default_diff(self):
        return self.difficulty(4)

    def difficulty(self, night: int, time: DisplayTime = DisplayTime.TWELVE_AM) -> int:
        return 20  # fixme


class Room(Enum):
    """Represents a camera on the map."""
    CAM_1_A = auto()
    CAM_1_B = auto()
    CAM_1_C = auto()
    CAM_2_A = auto()
    CAM_2_B = auto()
    CAM_3 = auto()
    CAM_4_A = auto()
    CAM_4_B = auto()
    CAM_5 = auto()
    CAM_6 = auto()
    CAM_7 = auto()
    LEFT_DOOR = auto()
    RIGHT_DOOR = auto()
    OFFICE = auto()

    @classmethod
    def rooms(cls) -> ValuesView["Room"]:
        return dict(Room).values()

    @classmethod
    def possible_rooms(cls, animatronic: Animatronic) -> list["Room"]:
        return [room for room in cls.rooms() if room.possible(animatronic)]

    def possible(self, animatronic: Animatronic) -> bool:
        match self:
            case Room.CAM_1_A:
                pass
            case Room.CAM_1_B:
                return animatronic is not Animatronic.FOXY
            case Room.CAM_1_C:
                return animatronic is Animatronic.FOXY
            case Room.CAM_2_A:
                return animatronic is Animatronic.FOXY or animatronic is Animatronic.BONNIE

            case Room.CAM_4_A:
                pass
            case Room.CAM_4_B:
                pass
            case Room.CAM_6:
                pass
            case Room.CAM_7:
                return animatronic is Animatronic.FREDDY or animatronic is Animatronic.CHICA

            # Below has had logic implemented

            case Room.CAM_5:
                pass
            case Room.CAM_3:
                pass
            case Room.CAM_2_B:
                pass
            case Room.LEFT_DOOR:
                return animatronic is Animatronic.BONNIE

            case Room.RIGHT_DOOR:
                return animatronic is Animatronic.CHICA

            case Room.OFFICE:
                return True

    def is_immediately_accessible(self, other: "Room", animatronic: Animatronic) -> bool:
        if not self.possible(animatronic):
            raise RuntimeError("Bad room for this animatronic.")
        match other:
            case Room.OFFICE:
                match animatronic:
                    case Animatronic.FREDDY:
                        return self is Room.CAM_4_A or self is Room.CAM_4_B
                    case Animatronic.CHICA:
                        return self is Room.RIGHT_DOOR
                    case Animatronic.BONNIE:
                        return self is Room.LEFT_DOOR
                    case Animatronic.FOXY:
                        return self is Room.CAM_2_A
            case Room.RIGHT_DOOR:
                return self is Room.CAM_4_A or self is Room.CAM_4_B
            case Room.LEFT_DOOR:
                return self is Room.CAM_2_A or self is Room.CAM_2_B
            case Room.CAM_2_B:
                return self is Room.LEFT_DOOR or self is Room.CAM_2_A or self is Room.CAM_3
            case Room.CAM_3:
                return self is Room.CAM_5 or self is Room.CAM_2_A
            case Room.CAM_5:
                return self is Room.CAM_1_B or self is Room.CAM_3

    def get_room(self, animatronic: Animatronic) -> Optional["Room"]:
        all_rooms_copy: list[Room] = list(self.possible_rooms(animatronic))
        random.shuffle(all_rooms_copy)
        for room in all_rooms_copy:
            if self.is_immediately_accessible(room, animatronic):
                return room
        else:
            return None

    @property
    def has_camera(self) -> bool:
        match self:
            case Room.CAM_1_A:
                pass
            case Room.CAM_1_B:
                pass
            case Room.CAM_1_C:
                pass
            case Room.CAM_2_A:
                pass
            case Room.CAM_2_B:
                pass
            case Room.CAM_3:
                pass
            case Room.CAM_4_A:
                pass
            case Room.CAM_4_B:
                pass
            case Room.CAM_5:
                pass
            case Room.CAM_6:
                pass
            case Room.CAM_7:
                return True
            case _:
                return False

    @property
    def name(self) -> Optional[str]:
        match self:
            case Room.CAM_1_A:
                return "Show Stage"
            case Room.CAM_1_B:
                return "Dining Room"
            case Room.CAM_1_C:
                return "Pirate's Cove"
            case Room.CAM_2_A:
                return "West Hall"
            case Room.CAM_2_B:
                return "W. Hall Corner"
            case Room.CAM_3:
                return "Supply Closet"
            case Room.CAM_4_A:
                return "East Hall"
            case Room.CAM_4_B:
                return "E. Hall Corner"
            case Room.CAM_5:
                return "Backstage"
            case Room.CAM_6:
                return "Kitchen"
            case Room.CAM_7:
                return "Restrooms"
            case _:
                return None

    @property
    def emoji(self) -> str:
        match self:
            case Room.CAM_1_A:
                return "🎤"
            case Room.CAM_2_A:
                pass
            case Room.CAM_2_B:
                pass
            case Room.CAM_4_A:
                pass
            case Room.CAM_4_B:
                return "🚪"
            case Room.CAM_3:
                return "🧹"
            case Room.CAM_1_B:
                pass
            case Room.CAM_6:
                return "🍕"
            case Room.CAM_1_C:
                return "🪝"
            case Room.CAM_7:
                return "🚽"

    def __str__(self):
        return self.name


class FiveNightsAtFreddys(commands.Cog):
    """Play Five Night's At Freddys in discrod"""

    def __init__(self, bot: bots.BOT_TYPES) -> None:
        self.bot: bots.BOT_TYPES = bot

    @commands.command()
    async def fnaf(
            self,
            ctx: bots.CustomContext,
            freddy: Optional[int] = commands.Option(
                description="The difficulty for Freddy.",
                default=Animatronic.FREDDY.default_diff
            ),
            bonnie: Optional[int] = commands.Option(
                description="The difficulty for Bonnie.",
                default=Animatronic.BONNIE.default_diff
            ),
            chica: Optional[int] = commands.Option(
                description="The difficulty for Chica.",
                default=Animatronic.CHICA.default_diff
            ),
            foxy: Optional[int] = commands.Option(
                description="The difficulty for Foxy.",
                default=Animatronic.FOXY.default_diff
            ),
    ) -> None:
        pass


def setup(bot: bots.BOT_TYPES) -> None:
    bot.add_cog(FiveNightsAtFreddys(bot))
