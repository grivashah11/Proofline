from __future__ import annotations

import hashlib
import warnings
from io import BytesIO

from fastapi import HTTPException, status
from PIL import Image, ImageOps, UnidentifiedImageError

MAX_IMAGE_BYTES = 8 * 1024 * 1024
MAX_IMAGE_PIXELS = 20_000_000
MAX_IMAGE_DIMENSION = 8_000
ALLOWED_FORMATS = {
    "JPEG": ("image/jpeg", ".jpg"),
    "PNG": ("image/png", ".png"),
    "WEBP": ("image/webp", ".webp"),
}


class ProcessedImage(dict):
    """Typed-by-convention metadata dictionary used by image routes."""


def _dominant_colors(image: Image.Image, limit: int = 5) -> list[dict[str, str | float]]:
    quantized = image.quantize(colors=limit)
    colors = quantized.getcolors(maxcolors=limit) or []
    palette = quantized.getpalette() or []
    total = sum(count for count, _ in colors) or 1

    result: list[dict[str, str | float]] = []
    for count, palette_index in sorted(colors, reverse=True):
        offset = palette_index * 3
        if offset + 2 >= len(palette):
            continue
        red, green, blue = palette[offset : offset + 3]
        result.append(
            {
                "hex": f"#{red:02X}{green:02X}{blue:02X}",
                "percentage": round((count / total) * 100, 1),
            }
        )

    return result


def process_image(content: bytes, original_filename: str | None) -> ProcessedImage:
    if not content:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="The uploaded image is empty.",
        )

    if len(content) > MAX_IMAGE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=f"Image exceeds the {MAX_IMAGE_BYTES // (1024 * 1024)} MB upload limit.",
        )

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(content)) as opened:
                image_format = (opened.format or "").upper()
                if image_format not in ALLOWED_FORMATS:
                    raise HTTPException(
                        status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                        detail="Only JPEG, PNG, and WebP images are supported.",
                    )

                if getattr(opened, "n_frames", 1) != 1:
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                        detail="Animated images are not supported. Upload a single static image.",
                    )

                width, height = opened.size
                if (
                    width < 1
                    or height < 1
                    or width > MAX_IMAGE_DIMENSION
                    or height > MAX_IMAGE_DIMENSION
                    or width * height > MAX_IMAGE_PIXELS
                ):
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                        detail=(
                            "Image dimensions exceed the supported limits "
                            f"({MAX_IMAGE_DIMENSION}px per side and {MAX_IMAGE_PIXELS:,} total pixels)."
                        ),
                    )

                opened.verify()

            with Image.open(BytesIO(content)) as reopened:
                image = ImageOps.exif_transpose(reopened).convert("RGB")
                image.load()
                width, height = image.size
                dominant_colors = _dominant_colors(image)

    except HTTPException:
        raise
    except (
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
        UnidentifiedImageError,
        OSError,
        ValueError,
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="The uploaded file is not a valid supported image.",
        ) from None

    mime_type, extension = ALLOWED_FORMATS[image_format]
    digest = hashlib.sha256(content).hexdigest()
    safe_filename = _safe_filename(original_filename)

    return ProcessedImage(
        original_filename=safe_filename,
        mime_type=mime_type,
        file_size_bytes=len(content),
        sha256_hash=digest,
        image_format=image_format,
        extension=extension,
        width=width,
        height=height,
        dominant_colors=dominant_colors,
    )


def _safe_filename(filename: str | None) -> str:
    if not filename:
        return "uploaded-image"

    # Treat both Windows and POSIX separators as path separators.
    leaf = filename.replace("\\", "/").rsplit("/", 1)[-1]
    leaf = "".join(character for character in leaf if character.isprintable())
    leaf = leaf.strip().strip(".")
    if not leaf:
        return "uploaded-image"
    return leaf[:255]


async def read_upload(upload_file, *, max_bytes: int = MAX_IMAGE_BYTES) -> bytes:
    content = await upload_file.read(max_bytes + 1)
    if len(content) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=f"Image exceeds the {max_bytes // (1024 * 1024)} MB upload limit.",
        )
    return content
