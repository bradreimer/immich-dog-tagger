"""
Image decoding.

Every image decode in the pipeline goes through this module. Detection,
cropping, and embedding all have to agree on one pixel coordinate space,
and they only do so if they decode identically -- see `open_upright`.
"""

import logging
from pathlib import Path

from PIL import Image, ImageOps

logger = logging.getLogger(__name__)

# EXIF tag 274 is Orientation.
_ORIENTATION_TAG = 274

_heif_registered = False


def _register_heif() -> None:
    # `.heic` is in SUPPORTED_IMAGE_EXTENSIONS, so Pillow needs the pi-heif
    # opener registered to decode one at all. Done lazily (and once) rather
    # than at import time so a broken/missing pi-heif can't take down every
    # code path that merely imports this module.
    global _heif_registered

    if _heif_registered:
        return

    try:
        from pi_heif import register_heif_opener

        register_heif_opener()
    except Exception:
        logger.warning(
            "Failed to register the HEIF opener; .heic assets will fail to decode",
            exc_info=True,
        )

    # Set even on failure: retrying per-image would just repeat the same
    # import failure once per asset.
    _heif_registered = True


def open_upright(
    image_path: Path | str,
) -> Image.Image:
    """
    Decode an image with its EXIF orientation applied.

    Pillow returns the raw stored pixels and leaves the EXIF Orientation tag
    (274) for the caller to honour, while OpenCV -- which ultralytics uses to
    decode for YOLO -- applies it during decoding. Left alone, that means the
    detector and the cropper see the same photo in two different coordinate
    spaces, and every crop of an orientation-tagged photo is cut from the
    wrong region and comes out rotated (issue #137, and the root cause of the
    out-of-bounds detection boxes in issue #88).

    `exif_transpose` covers all eight orientation values, including the
    mirrored ones (2/4/5/7), and drops the tag from the result, so applying
    it is idempotent and a no-op for images that are already upright.

    HEIC/HEIF needs one extra step first: pi-heif's Pillow plugin resets the
    Orientation tag to 1 in its own decoded `info["exif"]` as soon as it
    opens the file -- verified against a real device-shaped HEIC fixture, it
    does this unconditionally, without rotating the pixel data to match. The
    real value survives only in the non-standard `info["original_orientation"]`
    key it stashes instead. Left alone, `image.getexif()` -- what
    `exif_transpose` reads -- always reports 1 for a HEIC file, so every
    orientation-tagged HEIC (most iPhone photos not shot in landscape) skips
    correction entirely and comes out rotated exactly like the pre-#137 bug,
    just via a different mechanism. Copying it back into the Exif tag
    `exif_transpose` reads makes HEIC agree with every other format again.
    """
    _register_heif()

    # exif_transpose() returns a new image either way (a transposed one, or a
    # copy when there's nothing to do), so the source can be closed here
    # rather than left to the garbage collector -- this runs once per asset
    # across a whole library.
    with Image.open(image_path) as image:
        original_orientation = image.info.get("original_orientation")

        if original_orientation and original_orientation != 1:
            image.getexif()[_ORIENTATION_TAG] = original_orientation

        return ImageOps.exif_transpose(image)
