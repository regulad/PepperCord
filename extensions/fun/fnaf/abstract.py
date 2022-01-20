import random
from enum import Enum, auto
from typing import ValuesView, Optional, Mapping

from utils import misc

"""
Some notes on implementation:
1. Nothing is ever mutable.
2. Rendered images should be the same regardless of extraneous factors that would not effect the image in FNAF.
3. The game should be played as similar to FNAF as intricacies  of views allow.
"""


class DisplayTime(Enum):
    """Represents a time displayed to the player."""
    TWELVE_AM = auto()
    ONE_AM = auto()
    TWO_AM = auto()
    THREE_AM = auto()
    FOUR_AM = auto()
    FIVE_AM = auto()
    SIX_AM = auto()

    @property
    def offset(self) -> int:
        match self:
            case DisplayTime.TWO_AM:
                pass
            case DisplayTime.THREE_AM:
                return 1
            case DisplayTime.FOUR_AM:
                pass
            case DisplayTime.FIVE_AM:
                return 2
            case _:
                return 0


class DoorState:
    """Represents the state that doors are in."""

    def __init__(self, left_door: bool, right_door: bool) -> None:
        self._ld: bool = left_door
        self._rd: bool = right_door

    @classmethod
    def empty(cls) -> "DoorState":
        return cls(False, False)

    @property
    def left_door_closed(self) -> bool:
        return self._ld

    @property
    def right_door_closed(self) -> bool:
        return self._rd


class GameTime:
    """
    Time in this version of the game is expressed as a millisecond counter from 1-6000.
    Time scale can be changed by changing how fast this is ticked.
    """

    def __init__(self, time_millis: int) -> None:
        self._time_millis: int = time_millis

    @classmethod
    def start(cls) -> "GameTime":
        return cls(0)

    @property
    def millis(self) -> int:
        return self._time_millis

    @property
    def next(self) -> "GameTime":
        return self.__class__(self.millis + 1)

    @property
    def display_time(self) -> DisplayTime:
        if self.millis > 6000:
            return DisplayTime.SIX_AM
        elif self.millis > 5000:
            return DisplayTime.FIVE_AM
        elif self.millis > 4000:
            return DisplayTime.FOUR_AM
        elif self.millis > 3000:
            return DisplayTime.THREE_AM
        elif self.millis > 2000:
            return DisplayTime.TWO_AM
        elif self.millis > 1000:
            return DisplayTime.ONE_AM
        else:
            return DisplayTime.TWELVE_AM

    @property
    def game_win(self) -> bool:
        return self.display_time is DisplayTime.SIX_AM


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
    """Represents a camera on the map, or implicit place where an animatronic could be."""
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
    # The following represent the stages of foxy after CAM_1_C (which is curtains closed)
    FOXY_1 = auto()
    FOXY_2 = auto()
    FOXY_3 = auto()
    # After this, he will dash down the hall.
    FOXY_SAFE = auto()  # Represents where foxy is placed after he bangs on the office door

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

            case Room.FOXY_1:
                pass
            case Room.FOXY_2:
                pass
            case Room.FOXY_3:
                pass
            case Room.FOXY_SAFE:
                return animatronic is Animatronic.FOXY

    def can_move(self, other: "Room", animatronic: Animatronic, door_state: DoorState) -> bool:
        accessible: bool = self.is_immediately_accessible(other, animatronic)
        if not accessible:
            return False
        match animatronic:
            case Animatronic.FREDDY:
                pass
            case Animatronic.CHICA:
                return not door_state.right_door_closed if other is Room.OFFICE else True
            case Animatronic.BONNIE:
                return not door_state.left_door_closed if other is Room.OFFICE else True
            case Animatronic.FOXY:
                match other:
                    case Room.FOXY_SAFE:
                        return door_state.left_door_closed
                    case Room.OFFICE:
                        return not door_state.left_door_closed
                    case _:
                        return True
            case _:
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
            case Room.CAM_7:
                return self is Room.CAM_1_B
            case Room.CAM_6:
                return self is Room.CAM_7
            case Room.CAM_4_B:
                return self is Room.RIGHT_DOOR or self is Room.CAM_4_A
            case Room.CAM_4_A:
                return self is Room.RIGHT_DOOR or self is Room.CAM_6
            case Room.FOXY_3:
                return self is Room.FOXY_2
            case Room.FOXY_2:
                return self is Room.FOXY_1
            case Room.FOXY_1:
                return self is Room.CAM_1_C
            case Room.CAM_2_A:
                return self is Room.CAM_3 or self is Room.LEFT_DOOR or self is Room.FOXY_3
            case Room.CAM_1_C:
                return self is Room.FOXY_SAFE
            case Room.FOXY_SAFE:
                return self is Room.CAM_2_A
            case Room.CAM_1_B:
                return self is Room.CAM_1_A \
                       or self is Room.CAM_5 \
                       or self is Room.LEFT_DOOR \
                       or self is Room.RIGHT_DOOR \
                       or self is Room.CAM_6  # Maybe?
            case Room.CAM_1_A:
                return False  # Animatronics can only move from the stage, not to it.
            case _:
                return True

    def get_room(self, animatronic: Animatronic, door_state: Optional[DoorState] = None) -> Optional["Room"]:
        all_rooms_copy: list[Room] = list(self.possible_rooms(animatronic))
        random.shuffle(all_rooms_copy)
        for room in all_rooms_copy:
            if (self.can_move(room, animatronic, door_state)
            if door_state is not None
            else self.is_immediately_accessible(room, animatronic)):
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

    @classmethod
    def cameras(cls) -> list["Room"]:
        return [room for room in cls.rooms() if room.has_camera]

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


class CameraState:
    """Represents the current state of the cameras."""

    def __init__(self, camera: Optional[Room] = None, camera_up: bool = False) -> None:
        if camera is not None:
            assert camera.has_camera
        self._camera: Optional[Room] = camera
        self._camera_up: bool = camera_up

    @classmethod
    def empty(cls) -> "CameraState":
        return cls(None, False)

    @property
    def camera_up(self) -> bool:
        return self._camera_up

    @property
    def looking_at(self) -> Optional[Room]:
        return self._camera


class AnimatronicDifficulty:
    def __init__(
            self,
            diffs: Mapping[Animatronic, int] = misc.FrozenDict({
                Animatronic.FOXY: Animatronic.FOXY.default_diff,
                Animatronic.BONNIE: Animatronic.BONNIE.default_diff,
                Animatronic.FREDDY: Animatronic.FREDDY.default_diff,
                Animatronic.CHICA: Animatronic.CHICA.default_diff
            }),
    ) -> None:
        self._diffs: Mapping[Animatronic, int] = diffs

    @classmethod
    def empty(cls) -> "AnimatronicDifficulty":
        return cls()

    def __getitem__(self, item: Animatronic) -> int:
        return self._diffs[item]

    @property
    def foxy(self) -> int:
        return self[Animatronic.FOXY]

    @property
    def bonnie(self) -> int:
        return self[Animatronic.BONNIE]

    @property
    def freddy(self) -> int:
        return self[Animatronic.FREDDY]

    @property
    def chica(self) -> int:
        return self[Animatronic.CHICA]

    @staticmethod
    def roll(difficulty: int) -> bool:
        return difficulty > random.randint(1, 20)


class LightState:
    """Represents the state that lights are in."""

    def __init__(self, left_light: bool, right_light: bool) -> None:
        self._ll: bool = left_light
        self._rl: bool = right_light

    @classmethod
    def empty(cls) -> "LightState":
        return cls(False, False)

    @property
    def left_light_on(self) -> bool:
        return self._ll

    @property
    def right_light_on(self) -> bool:
        return self._rl


class GameState:
    def __init__(
            self,
            animatronic_positions: Mapping[Animatronic, Room] = misc.FrozenDict({
                Animatronic.FOXY: Room.CAM_1_C,
                Animatronic.BONNIE: Room.CAM_1_A,
                Animatronic.FREDDY: Room.CAM_1_A,
                Animatronic.CHICA: Room.CAM_1_A
            }),
            door_state: DoorState = DoorState.empty(),
            light_state: LightState = LightState.empty(),
            camera_state: CameraState = CameraState.empty(),
            difficulty: AnimatronicDifficulty = AnimatronicDifficulty.empty(),
            power_left: int = 100,
            game_time: GameTime = GameTime.start(),
    ) -> None:
        self._animatronic_positions: Mapping[Animatronic, Room] = animatronic_positions
        self._door_state: DoorState = door_state
        self._light_state: LightState = light_state
        self._camera_state: CameraState = camera_state
        self._difficulty: AnimatronicDifficulty = difficulty
        self._power_left: int = power_left
        self._game_time: GameTime = game_time

    @classmethod
    def empty(cls) -> "GameState":
        return cls()

    @property
    def game_time(self) -> GameTime:
        return self._game_time

    @property
    def won(self) -> bool:
        return self.game_time.game_win

    @property
    def lost(self) -> bool:
        # fixme: possible exploit, just never lower your camera! gotta fix foxy
        return (not self.camera_state.camera_up) and (Room.OFFICE in self.animatronic_positions.values())

    @classmethod
    def initialize(cls, difficulty: Optional[AnimatronicDifficulty] = None) -> "GameState":
        return cls(difficulty=difficulty) if difficulty is not None else cls.empty()

    @property
    def animatronic_positions(self) -> Mapping[Animatronic, Room]:
        return self._animatronic_positions

    @property
    def difficulty(self) -> AnimatronicDifficulty:
        return self._difficulty

    @property
    def usage(self) -> int:
        usage: int = 1
        if self._door_state.right_door_closed:
            usage += 1
        if self._door_state.left_door_closed:
            usage += 1
        if self._light_state.left_light_on:
            usage += 1
        if self._light_state.right_light_on:
            usage += 1
        if self._camera_state.camera_up:
            usage += 1
        return usage

    @property
    def door_state(self) -> DoorState:
        return self._door_state

    @property
    def power_left(self) -> int:
        return self._power_left

    @property
    def camera_state(self) -> CameraState:
        return self._camera_state

    @property
    def light_state(self) -> LightState:
        return self._light_state

    def tick_power(self) -> "GameState":
        return self.__class__(
            self.animatronic_positions,
            self.door_state,
            self.light_state,
            self.camera_state,
            self.difficulty,
            self.power_left - self.usage,
            self.game_time
        )

    def full_tick(self) -> "GameState":
        return (
            self
                .tick_power()
                .move_animatronics()
                .tick_time()
        )

    def process_input_changes(
            self,
            *,
            door_state: Optional[DoorState] = None,
            light_state: Optional[LightState] = None,
            camera_state: Optional[CameraState] = None,
    ) -> "GameState":
        return self.__class__(
            self.animatronic_positions,
            door_state or self.door_state,
            light_state or self.light_state,
            camera_state or self.camera_state,
            self.difficulty,
            self.power_left,
            self.game_time,
        )

    def tick_time(self) -> "GameState":
        return self.__class__(
            self.animatronic_positions,
            self.door_state,
            self.light_state,
            self.camera_state,
            self.difficulty,
            self.power_left,
            self.game_time.next,
        )

    def move_animatronics(self) -> "GameState":
        mutable_pos: dict[Animatronic, Room] = dict(self.animatronic_positions)

        for animatronic, room in self.animatronic_positions.items():
            if AnimatronicDifficulty.roll(self.difficulty[animatronic]):
                mutable_pos[animatronic] = room.get_room(animatronic, self.door_state)

        return self.__class__(
            misc.FrozenDict(mutable_pos),
            self.door_state,
            self.light_state,
            self.camera_state,
            self.difficulty,
            self.power_left,
            self.game_time
        )


__all__: list[str] = [
    "DisplayTime",
    "DoorState",
    "GameTime",
    "Animatronic",
    "Room",
    "CameraState",
    "AnimatronicDifficulty",
    "LightState",
    "GameState",
]
