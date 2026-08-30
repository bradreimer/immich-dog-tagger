from pathlib import Path

import pytest
from PIL import Image

from immich_dog_tagger.images import open_upright

# EXIF tag 274 is Orientation.
_ORIENTATION_TAG = 274


def _write(
    path: Path,
    image: Image.Image,
    orientation: int | None,
) -> Path:
    exif = image.getexif()

    if orientation is not None:
        exif[_ORIENTATION_TAG] = orientation

    image.save(path, exif=exif)

    return path


def _landscape() -> Image.Image:
    """
    A 200x100 image whose top-left quadrant is red, so a transform that
    rotates or mirrors it is detectable from pixel positions alone.
    """
    image = Image.new("RGB", (200, 100), "white")
    image.paste(Image.new("RGB", (100, 50), "red"), (0, 0))

    return image


def test_open_upright_swaps_dimensions_for_rotated_orientations(tmp_path: Path):
    # 5-8 are the quarter-turn orientations: the stored pixels are landscape
    # but the photo is meant to be displayed portrait, so honouring the tag
    # has to swap width and height.
    for orientation in (5, 6, 7, 8):
        path = _write(
            tmp_path / f"o{orientation}.jpg",
            _landscape(),
            orientation,
        )

        assert Image.open(path).size == (200, 100)
        assert open_upright(path).size == (100, 200), orientation


def test_open_upright_leaves_unrotated_orientations_landscape(tmp_path: Path):
    # 2/3/4 are the mirror/180 orientations -- the pixels move, but the
    # frame's dimensions don't.
    for orientation in (2, 3, 4):
        path = _write(
            tmp_path / f"o{orientation}.jpg",
            _landscape(),
            orientation,
        )

        assert open_upright(path).size == (200, 100), orientation


@pytest.mark.parametrize(
    "orientation, expected_red_corner",
    [
        # Where the originally-top-left red quadrant ends up once the tag is
        # honoured, pinning down the actual transform rather than just the
        # resulting dimensions. Covers the mirrored orientations (2/4/5/7),
        # which a naive rotate-only implementation gets wrong.
        (1, "top-left"),
        (2, "top-right"),
        (3, "bottom-right"),
        (4, "bottom-left"),
        (5, "top-left"),
        (6, "top-right"),
        (7, "bottom-right"),
        (8, "bottom-left"),
    ],
)
def test_open_upright_applies_the_full_transform(
    tmp_path: Path,
    orientation: int,
    expected_red_corner: str,
):
    path = _write(
        tmp_path / f"o{orientation}.jpg",
        _landscape(),
        orientation,
    )

    image = open_upright(path)

    width, height = image.size

    inset = 5

    corners = {
        "top-left": (inset, inset),
        "top-right": (width - inset, inset),
        "bottom-left": (inset, height - inset),
        "bottom-right": (width - inset, height - inset),
    }

    for name, point in corners.items():
        red, green, blue = image.convert("RGB").getpixel(point)

        is_red = red > 200 and green < 80 and blue < 80

        assert is_red == (name == expected_red_corner), (
            f"orientation {orientation}: corner {name} "
            f"{'should' if name == expected_red_corner else 'should not'} be red"
        )


def test_open_upright_is_a_no_op_without_an_orientation_tag(tmp_path: Path):
    path = _write(
        tmp_path / "untagged.jpg",
        _landscape(),
        None,
    )

    assert open_upright(path).size == (200, 100)
    assert open_upright(path).tobytes() == Image.open(path).tobytes()


def test_open_upright_strips_the_orientation_tag(tmp_path: Path):
    # Without this, anything that re-read the result would apply the rotation
    # a second time.
    path = _write(
        tmp_path / "o6.jpg",
        _landscape(),
        6,
    )

    image = open_upright(path)

    assert image.getexif().get(_ORIENTATION_TAG) in (None, 1)

    round_tripped = tmp_path / "round-tripped.jpg"
    image.save(round_tripped)

    assert open_upright(round_tripped).size == image.size


def test_open_upright_accepts_a_string_path(tmp_path: Path):
    path = _write(
        tmp_path / "o6.jpg",
        _landscape(),
        6,
    )

    assert open_upright(str(path)).size == (100, 200)


def test_open_upright_registers_the_heif_opener(tmp_path: Path):
    """
    `.heic` is a supported extension, but Pillow can't decode one until the
    pi-heif opener is registered. Before this module existed nothing in
    `src/` registered it -- HEIC decoding worked only because ultralytics
    monkeypatches `PIL.Image.open` globally.
    """
    path = _write(
        tmp_path / "plain.jpg",
        _landscape(),
        None,
    )

    open_upright(path)

    assert ".heic" in Image.registered_extensions()


_HEIC_FIXTURES_DIR = Path(__file__).parent / "fixtures"

# Real device-shaped HEIC files, one per orientation plus one with no
# Orientation tag at all -- generated once from the same red-quadrant
# landscape frame `_landscape()` builds for the JPEG tests above, so the
# expected geometry below matches `test_open_upright_applies_the_full_transform`
# exactly. A synthetic in-memory HEIC can't stand in for these: pi-heif's
# Pillow plugin only exhibits this bug when it has actually decoded a HEIC
# container (see the comment on the `original_orientation` handling in
# `images.open_upright`).
_HEIC_EXPECTED = {
    "untagged": ((200, 100), "top-left"),
    "o1": ((200, 100), "top-left"),
    "o2": ((200, 100), "top-right"),
    "o3": ((200, 100), "bottom-right"),
    "o4": ((200, 100), "bottom-left"),
    "o5": ((100, 200), "top-left"),
    "o6": ((100, 200), "top-right"),
    "o7": ((100, 200), "bottom-right"),
    "o8": ((100, 200), "bottom-left"),
}


@pytest.mark.parametrize(
    "fixture_name, expected_size, expected_red_corner",
    [(name, size, corner) for name, (size, corner) in _HEIC_EXPECTED.items()],
)
def test_open_upright_applies_the_full_transform_for_heic(
    fixture_name: str,
    expected_size: tuple[int, int],
    expected_red_corner: str,
):
    """
    Regression test for a HEIC-specific bug distinct from #137: pi-heif's
    Pillow plugin resets the Orientation tag to 1 in its own decoded
    `info["exif"]` as soon as it opens a HEIC file, without rotating the
    pixel data to match -- verified against these fixtures, it does this
    unconditionally. The real value survives only in the non-standard
    `info["original_orientation"]` key. Left unhandled, `image.getexif()`
    (what `ImageOps.exif_transpose` reads) always reports 1 for a HEIC file,
    so every orientation-tagged HEIC -- most iPhone photos not shot in
    landscape -- skipped correction entirely and came out rotated, even
    after #137 fixed the equivalent JPEG case.
    """
    path = _HEIC_FIXTURES_DIR / f"heic_{fixture_name}.heic"

    image = open_upright(path).convert("RGB")

    assert image.size == expected_size, fixture_name

    width, height = image.size
    inset = 5

    corners = {
        "top-left": (inset, inset),
        "top-right": (width - inset, inset),
        "bottom-left": (inset, height - inset),
        "bottom-right": (width - inset, height - inset),
    }

    for name, point in corners.items():
        red, green, blue = image.getpixel(point)

        is_red = red > 200 and green < 80 and blue < 80

        assert is_red == (name == expected_red_corner), (
            f"{fixture_name}: corner {name} "
            f"{'should' if name == expected_red_corner else 'should not'} be red"
        )
