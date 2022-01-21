import random
from io import BytesIO

from PIL import Image, ImageFont, ImageDraw

from .abstract import *

MAX_WIDTH: int = 1700
MAX_HEIGHT: int = 1000


def canvas(color: float | tuple[float, float, float, float] | str = "grey") -> Image:
    return Image.new("RGBA", (MAX_WIDTH, MAX_HEIGHT), color)


def font(size: int = 72) -> ImageFont:
    return ImageFont.truetype(
        "resources/images/fnaf/five-nights-at-freddys.ttf", size
    )


def static() -> Image:
    opened_image: Image = Image.open("resources/images/fnaf/static2.png")
    left_offset: int = random.randint(0, 1000)
    top_offset: int = random.randint(0, 1000)
    return opened_image.crop((left_offset, top_offset, MAX_WIDTH + left_offset, MAX_HEIGHT + top_offset))


def render(game_state: GameState) -> Image:
    power_on: bool = game_state.power_left > 0
    drawing_canvas: Image = canvas(color=(52, 52, 52, 255) if not power_on else "grey")
    image_draw: ImageDraw = ImageDraw.Draw(drawing_canvas)
    if power_on:
        # Background processing (static)
        if game_state.camera_state.camera_up:
            static_image: Image = static()
            drawing_canvas.paste(static_image, mask=static_image)
        # Start pre-ui (like outlike and recording dot)
        if game_state.camera_state.camera_up:
            image_draw.rectangle((7, 7, MAX_WIDTH - 7, MAX_HEIGHT - 7), outline="white", width=3)
        if game_state.camera_state.camera_up and game_state.game_time.millis % 2 == 0:
            image_draw.ellipse((MAX_WIDTH / 20, 50, (MAX_WIDTH / 20) + 70, 120), fill="red")
        # Start HUD (time and power)
        image_draw.text(
            xy=(MAX_WIDTH / 2, MAX_HEIGHT / 2),
            text=game_state.summary,
            stroke_fill="#FFFFFF",
            font=font(90),
            anchor="mm",
            align="center"
        )
        # Time
        image_draw.text(
            xy=(MAX_WIDTH - 15, 15),
            text=f"{game_state.game_time.display_time.friendly_name}",
            stroke_fill="#FFFFFF",
            font=font(98),
            anchor="ra",
            align="right"
        )
        # Night text
        image_draw.text(
            xy=(MAX_WIDTH - 15, 80),
            text=f"Night 7"
                 f"\n{game_state.difficulty.freddy} "
                 f"{game_state.difficulty.bonnie} "
                 f"{game_state.difficulty.chica} "
                 f"{game_state.difficulty.foxy} ",
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
    return drawing_canvas


def save_buffer(im: Image, image_format: str = "PNG") -> BytesIO:
    buffer: BytesIO = BytesIO()
    im.save(buffer, image_format)
    buffer.seek(0)
    return buffer


def load_bytes(im: Image, image_format: str = "PNG") -> bytes:
    with save_buffer(im, image_format) as buffer:
        return buffer


__all__: list[str] = [
    "render",
    "save_buffer",
    "load_bytes",
]
