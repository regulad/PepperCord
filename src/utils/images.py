from io import BytesIO
from tempfile import NamedTemporaryFile

from PIL import Image
from reportlab.graphics.renderPM import drawToFile
from svglib.svglib import svg2rlg


def svg2png(svg: bytes) -> bytes:
    with BytesIO() as png_file, NamedTemporaryFile(suffix=".svg") as svg_file:
        # The comment says that File-like objects are permitted for svg2rlg, but the types and code tell a different story.
        # A NamedTemporaryFile is used as a shim
        svg_file.write(svg)
        svg_file.flush()
        svg_file.seek(0)

        drawing = svg2rlg(svg_file.name)

        if drawing is None:
            raise RuntimeError("Failed to load SVG!")

        drawToFile(
            drawing, png_file, "png", bg=0x000000
        )  # Transparent background doesn't want to work with this library.
        png_file.seek(0)
        return png_file.read()


def vrt_concat_pngs(png1: bytes, png2: bytes) -> bytes:
    with BytesIO(png1) as png1_file, BytesIO(png2) as png2_file, BytesIO() as buffer:
        image1: Image.Image = Image.open(png1_file)
        image2: Image.Image = Image.open(png2_file)

        if image2.width != image1.width:
            image2_aspect_ratio: float = image2.height / image2.width
            image2 = image2.resize(
                (image1.width, int(image2_aspect_ratio * image1.width)),
                Image.Resampling.BILINEAR,
            )

        buffer_img: Image.Image = Image.new(
            "RGBA", (image1.width, image1.height + image2.height)
        )
        buffer_img.paste(image1, (0, 0))
        buffer_img.paste(image2, (0, image1.height))

        buffer_img.save(buffer, "PNG")
        buffer.seek(0)
        return buffer.read()


def hrz_concat_pngs(png1: bytes, png2: bytes) -> bytes:
    with BytesIO(png1) as png1_file, BytesIO(png2) as png2_file, BytesIO() as buffer:
        image1: Image.Image = Image.open(png1_file)
        image2: Image.Image = Image.open(png2_file)

        if image2.height != image1.height:
            image2_aspect_ratio: float = image2.width / image2.height
            image2 = image2.resize(
                (int(image1.height * image2_aspect_ratio), image1.height),
                Image.Resampling.BILINEAR,
            )

        buffer_img: Image.Image = Image.new(
            "RGBA", (image1.width + image2.width, image1.height)
        )
        buffer_img.paste(image1, (0, 0))
        buffer_img.paste(image2, (image1.width, 0))

        buffer_img.save(buffer, "PNG")
        buffer.seek(0)
        return buffer.read()


__all__ = ["svg2png", "vrt_concat_pngs", "hrz_concat_pngs"]
