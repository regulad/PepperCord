import os
import random
from enum import Enum, auto
from io import BytesIO
from pathlib import Path
from typing import Optional, Literal

from PIL import Image, ImageFont, ImageDraw
from PIL.Image import Image as ImageType
from PIL.ImageDraw import ImageDraw as ImageDrawType

from .abstract import *


class OfficeImage(Enum):
    OFFICE_CLEAN = auto()
    BONNIE_AT_DOOR = auto()
    CHICA_AT_DOOR = auto()
    LEFT_HALL_LIGHT = auto()
    RIGHT_HALL_LIGHT = auto()
    POWER_OUT = auto()
    FREDDY = auto()

    @classmethod
    def of(cls, game_state: GameState) -> Optional["OfficeImage"]:
        if game_state.power_left <= 0 and game_state.room_of(Animatronic.FREDDY) is Room.CAM_4_B:
            return cls.FREDDY
        elif game_state.power_left <= 0:
            return cls.POWER_OUT
        elif game_state.animatronics_in(Room.LEFT_DOOR) and game_state.light_state.left_light_on:
            return cls.BONNIE_AT_DOOR
        elif game_state.light_state.left_light_on:
            return cls.LEFT_HALL_LIGHT
        elif game_state.animatronics_in(Room.RIGHT_DOOR) and game_state.light_state.right_light_on:
            return cls.CHICA_AT_DOOR
        elif game_state.light_state.right_light_on:
            return cls.RIGHT_HALL_LIGHT
        else:
            return cls.OFFICE_CLEAN

    @property
    def offset(self) -> Literal[-1, 1, 0]:
        match self:
            case OfficeImage.BONNIE_AT_DOOR \
                 | OfficeImage.LEFT_HALL_LIGHT \
                 | OfficeImage.FREDDY:
                return -1
            case OfficeImage.RIGHT_HALL_LIGHT \
                 | OfficeImage.CHICA_AT_DOOR:
                return 1
            case _:
                return 0

    @property
    def title_name(self) -> str:
        return self.name.replace("_", " ").title().replace(" ", "")

    @property
    def filename(self) -> str:
        return f"resources/images/fnaf/office/{self.title_name}.png"


class CameraImage(Enum):
    # Multiple
    BACKSTAGE_BONNIE = auto()
    BACKSTAGE_NONE = auto()
    BATHROOM_CHICA = auto()
    DINING_BONNIE = auto()
    DINING_CHICA = auto()
    E_CORNER_CHICA = auto()
    E_CORNER_NONE = auto()
    E_HALL_CHICA = auto()
    STAGE_ALL = auto()
    STAGE_FREDDY = auto()
    W_CORNER_BONNIE = auto()
    W_CORNER_NONE = auto()
    W_HALL_FOXY = auto()
    W_HALL_NONE = auto()
    # Single
    BATHROOM_FREDDY = auto()
    BATHROOM_NONE = auto()
    DINING_FREDDY = auto()
    DINING_NONE = auto()
    E_CORNER_FREDDY = auto()
    E_HALL_FREDDY = auto()
    E_HALL_NONE = auto()
    FOXY_1 = auto()
    FOXY_2 = auto()
    FOXY_3 = auto()
    FOXY_NONE = auto()
    FOXY_OUT = auto()
    STAGE_BONNIE_FREDDY = auto()
    STAGE_CHICA_FREDDY = auto()
    STAGE_NONE = auto()
    SUPPLY_BONNIE = auto()
    SUPPLY_NONE = auto()
    W_HALL_BONNIE = auto()

    @classmethod
    def of(cls, game_state: GameState, room: Room) -> Optional["CameraImage"]:
        animatronics: list[Animatronic] = game_state.animatronics_in(room)
        match room:
            case Room.CAM_1_A:
                if Animatronic.FREDDY in animatronics \
                        and Animatronic.BONNIE in animatronics \
                        and Animatronic.CHICA in animatronics:
                    return cls.STAGE_ALL
                elif Animatronic.FREDDY in animatronics and Animatronic.CHICA in animatronics:
                    return cls.STAGE_CHICA_FREDDY
                elif Animatronic.FREDDY in animatronics and Animatronic.BONNIE in animatronics:
                    return cls.STAGE_BONNIE_FREDDY
                elif Animatronic.FREDDY in animatronics:
                    return cls.STAGE_FREDDY
                else:
                    return cls.STAGE_NONE
            case Room.CAM_1_B:
                if Animatronic.FREDDY in animatronics:
                    return cls.DINING_FREDDY
                elif Animatronic.BONNIE in animatronics:
                    return cls.DINING_BONNIE
                elif Animatronic.CHICA in animatronics:
                    return cls.DINING_CHICA
                else:
                    return cls.DINING_NONE
            case Room.CAM_1_C:
                match game_state.room_of(Animatronic.FOXY):
                    case Room.FOXY_1:
                        return cls.FOXY_1
                    case Room.FOXY_2:
                        return cls.FOXY_2
                    case Room.FOXY_3:
                        return cls.FOXY_3
                    case _:
                        return cls.FOXY_NONE
            case Room.CAM_2_A:
                if Animatronic.BONNIE in animatronics:
                    return cls.W_HALL_BONNIE
                elif Animatronic.FOXY in animatronics:
                    return cls.W_HALL_FOXY
                else:
                    return cls.W_HALL_NONE
            case Room.CAM_2_B:
                if Animatronic.BONNIE in animatronics:
                    return cls.W_CORNER_BONNIE
                else:
                    return cls.W_CORNER_NONE
            case Room.CAM_3:
                if Animatronic.BONNIE in animatronics:
                    return cls.SUPPLY_BONNIE
                else:
                    return cls.SUPPLY_NONE
            case Room.CAM_4_A:
                if Animatronic.FREDDY in animatronics:
                    return cls.E_HALL_FREDDY
                elif Animatronic.CHICA in animatronics:
                    return cls.E_HALL_CHICA
                else:
                    return cls.E_HALL_NONE
            case Room.CAM_4_B:
                if Animatronic.FREDDY in animatronics:
                    return cls.E_CORNER_FREDDY
                elif Animatronic.CHICA in animatronics:
                    return cls.E_CORNER_CHICA
                else:
                    return cls.E_CORNER_NONE
            case Room.CAM_5:
                if Animatronic.BONNIE in animatronics:
                    return cls.BACKSTAGE_BONNIE
                else:
                    return cls.BACKSTAGE_NONE
            case Room.CAM_7:
                if Animatronic.CHICA in animatronics:
                    return cls.BATHROOM_CHICA
                elif Animatronic.FREDDY in animatronics:
                    return cls.BATHROOM_FREDDY
                else:
                    return cls.BATHROOM_NONE
            case _:
                return None

    @property
    def filename(self) -> str:
        return self.name.lower()

    def get_png(self) -> Optional[str]:
        maybe_path: Path = Path(f"resources/images/fnaf/cam/{self.filename}")
        if not maybe_path.exists():
            return f"resources/images/fnaf/cam/{self.filename}.png"
        elif maybe_path.is_dir():
            files: list[str] = os.listdir(str(maybe_path))
            if len(files) > 0:
                return os.path.join(maybe_path, random.choice(files))
            else:
                return None
        else:
            return None


MAX_WIDTH: int = 960
MAX_HEIGHT: int = 720
OUTPUT_WIDTH: int = 1920
OUTPUT_HEIGHT: int = 1440


def canvas(color: float | tuple[float, float, float, float] | str = "grey") -> Image:
    return Image.new("RGBA", (MAX_WIDTH, MAX_HEIGHT), color)


def font(size: int = 72) -> ImageFont:
    return ImageFont.truetype(
        "resources/images/fnaf/five-nights-at-freddys.ttf", size
    )


def fits(image: ImageType) -> bool:
    return not (image.width < MAX_WIDTH or image.height < MAX_HEIGHT)


def quick_resize(image: ImageType) -> ImageType:
    return image.resize((image.width * 2, image.height * 2))


class AtomicImageReference:
    def __init__(self, image: ImageType) -> None:
        self.image: ImageType = image

    @property
    def fits(self) -> bool:
        return fits(self.image)


def resize_until(image: ImageType) -> ImageType:
    atomic_image_reference: AtomicImageReference = AtomicImageReference(image)
    while not atomic_image_reference.fits:
        atomic_image_reference.image = quick_resize(atomic_image_reference.image)
    return atomic_image_reference.image


def camera(game_state: GameState) -> Optional[ImageType]:
    camera_image: Optional[CameraImage] = CameraImage.of(game_state, game_state.camera_state.looking_at)
    maybe_file_name: Optional[str] = camera_image.get_png() if camera_image is not None else None
    if maybe_file_name is not None:
        image: ImageType = Image.open(maybe_file_name)
        if not fits(image):
            image = resize_until(image)
        width: int = image.width
        height: int = image.height
        width_buffer: int = int((width - MAX_WIDTH) / 2)
        height_buffer: int = int((height - MAX_HEIGHT) / 2)
        offset: int = random.randint(-300, 300)
        return image.crop((width_buffer + offset, height_buffer, width - width_buffer + offset, height - height_buffer))
    else:
        return None


def office(game_state: GameState) -> Optional[ImageType]:
    office_image: Optional[OfficeImage] = OfficeImage.of(game_state)
    maybe_file_name: Optional[str] = office_image.filename if office_image is not None else None
    if maybe_file_name is not None:
        image: ImageType = Image.open(maybe_file_name)
        if not fits(image):
            image = resize_until(image)
        width: int = image.width
        height: int = image.height
        width_buffer: int = int((width - MAX_WIDTH) / 2)
        height_buffer: int = int((height - MAX_HEIGHT) / 2)
        offset: int = int(office_image.offset * (width / 4))
        return image.crop((width_buffer + offset, height_buffer, width - width_buffer + offset, height - height_buffer))
    else:
        return None


def base_map(odd: bool = False) -> ImageType:
    return Image.open(f"resources/images/fnaf/map/{'Cam_Map' if odd else 'Cam_Map2'}.png")


def static() -> ImageType:
    opened_image: ImageType = Image.open("resources/images/fnaf/static2.png")
    left_offset: int = random.randint(0, 1000)
    top_offset: int = random.randint(0, 1000)
    return opened_image.crop((left_offset, top_offset, MAX_WIDTH + left_offset, MAX_HEIGHT + top_offset))


def camera_xy(room: Room) -> tuple[int, int, int, int]:
    assert room.has_camera
    match room:
        case Room.CAM_1_A:
            return 141, 2, 198, 37
        case Room.CAM_1_B:
            return 119, 63, 176, 99
        case Room.CAM_1_C:
            return 83, 149, 141, 184
        case Room.CAM_2_A:
            return 141, 277, 198, 311
        case Room.CAM_2_B:
            return 141, 321, 198, 355
        case Room.CAM_3:
            return 49, 257, 106, 292
        case Room.CAM_4_A:
            return 257, 277, 315, 311
        case Room.CAM_4_B:
            return 257, 321, 315, 355
        case Room.CAM_5:
            return 2, 93, 59, 128
        case Room.CAM_6:
            return 364, 238, 422, 273
        case Room.CAM_7:
            return 374, 94, 431, 129
        case _:
            return 0, 0, 30, 30


def render(game_state: GameState) -> ImageType:
    power_on: bool = game_state.power_left > 0
    even_frame: bool = game_state.game_time.millis % 2 == 0
    drawing_canvas: ImageType = canvas(color=(52, 52, 52, 255) if not power_on else (75, 75, 75, 255))
    image_draw: ImageDrawType = ImageDraw.Draw(drawing_canvas)
    # Background processing (static)
    can_draw_summary: bool = True
    if game_state.camera_state.camera_up:
        target_cam: Optional[Room] = game_state.camera_state.looking_at
        if target_cam is not None:
            # Camera Image
            camera_image: Optional[Image] = camera(game_state)
            if camera_image is not None:
                drawing_canvas.paste(camera_image)
                can_draw_summary = False
            # Map Dot
        # Static
        static_image: Image = static()
        drawing_canvas.paste(static_image, mask=static_image)
        # Map
        map_image: ImageType = base_map(not even_frame)
        map_image_draw: ImageDrawType = ImageDraw.Draw(map_image)
        if target_cam is not None:
            map_image_draw.rectangle(
                xy=camera_xy(target_cam),
                fill=(114, 191, 63, 137),
                # There is no way to mask this. We will have to settle with this.
            )
        left_offset: int = int((MAX_WIDTH / 3) * 2)
        down_offset: int = int((MAX_HEIGHT / 6) * 3.2)
        sub_width: int = int((MAX_WIDTH / 19) * 18.5) - left_offset
        sub_height: int = int((MAX_HEIGHT / 15) * 14.5) - down_offset
        resize_map: ImageType = map_image.resize((sub_width, sub_height))
        drawing_canvas.paste(
            resize_map,
            (
                left_offset,
                down_offset,
                left_offset + sub_width,
                down_offset + sub_height,
            ),
            resize_map,
        )
        if target_cam is not None:
            image_draw.text(
                xy=(
                    left_offset - 4,
                    down_offset - 7,
                ),
                text=target_cam.room_name,
                stroke_fill="#FFFFFF",
                font=font(78),
                anchor="ld",
            )
        # Outline
        image_draw.rectangle((7, 7, MAX_WIDTH - 8, MAX_HEIGHT - 8), outline="white", width=4)
        # Recording dot (random chance)
        if game_state.camera_state.camera_up and even_frame:
            image_draw.ellipse((MAX_WIDTH / 20, 50, (MAX_WIDTH / 20) + 70, 120), fill="red")
    else:
        office_image: Optional[Image] = office(game_state)
        if office_image is not None:
            drawing_canvas.paste(office_image)
            can_draw_summary = False
            if game_state.door_state.left_door_closed or game_state.door_state.right_door_closed:
                doors_closed: list[str] = [
                    door_name.title()
                    for door_name
                    in [
                        "Left" if game_state.door_state.left_door_closed else None,
                        "Right" if game_state.door_state.right_door_closed else None,
                    ]
                    if door_name is not None
                ]
                image_draw.text(
                    xy=(MAX_WIDTH / 2, MAX_HEIGHT / 5),
                    text=f"Doors closed: {', '.join(doors_closed)}",
                    stroke_fill="#FFFFFF",
                    font=font(90),
                    anchor="ma",
                    align="center"
                )
    # Start HUD (time and power)
    if power_on:
        if can_draw_summary:
            image_draw.text(
                xy=(MAX_WIDTH / 2, MAX_HEIGHT / 5),
                text=game_state.summary,
                stroke_fill="#FFFFFF",
                font=font(90),
                anchor="ma",
                align="center"
            )
        # Time
        image_draw.text(
            xy=(MAX_WIDTH - 15, 15),
            text=game_state.game_time.display_time.friendly_name,
            stroke_fill="#FFFFFF",
            font=font(98),
            anchor="ra",
            align="right"
        )
        # Night text
        image_draw.text(
            xy=(MAX_WIDTH - 15, 80),
            text=f"Night {game_state.difficulty.night}",
            stroke_fill="#FFFFFF",
            font=font(48),
            anchor="ra",
            align="right"
        )
        # Power left
        image_draw.text(
            xy=(15, MAX_HEIGHT - 60),
            text="Power left:",
            stroke_fill="#FFFFFF",
            font=font(60),
            anchor="ld",
        )
        image_draw.text(
            xy=(223, MAX_HEIGHT - 57),
            text=f"{game_state.power_left}%",
            stroke_fill="#FFFFFF",
            font=font(80),
            anchor="ls",
        )
        # Usage
        image_draw.text(
            xy=(15, MAX_HEIGHT - 15),
            text="Usage:",
            stroke_fill="#FFFFFF",
            font=font(60),
            anchor="ld",
        )
        for i in range(1, game_state.usage + 1):
            image_draw.rectangle(
                (105 + (i * 30), MAX_HEIGHT - 65, 105 + 25 + (i * 30), MAX_HEIGHT - 25),
                fill="green" if (i < 3) else ("yellow" if (i < 4) else "red"),
                width=3
            )
    return drawing_canvas.resize((OUTPUT_WIDTH, OUTPUT_HEIGHT))


def save_buffer(im: ImageType, image_format: str = "PNG") -> BytesIO:
    buffer: BytesIO = BytesIO()
    im.save(buffer, image_format)
    buffer.seek(0)
    return buffer


def load_bytes(im: ImageType, image_format: str = "PNG") -> bytes:
    with save_buffer(im, image_format) as buffer:
        return buffer


__all__: list[str] = [
    "render",
    "save_buffer",
    "load_bytes",
]
