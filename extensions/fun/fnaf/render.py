from io import BytesIO

from PIL import Image

from .abstract import *


def canvas() -> Image:
    return Image.new("RGB", (500, 500))


def overlay_canvas() -> Image:
    return Image.new("RGBA", (500, 500), (0, 0, 0, 0))


def render_overlay(game_state: GameState) -> Image:
    pass


def render_camera_underlay(game_state: GameState, camera: Room) -> Image:
    drawing_canvas: Image = canvas()


def composite(underlay: Image, overlay: Image) -> Image:
    underlay.paste(overlay)
    return underlay


def render(game_state: GameState) -> Image:
    pass


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
    "load_bytes"
]
