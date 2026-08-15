from pathlib import Path

from immich_dog_tagger.media import is_supported_extension, is_supported_image


def test_supported_image_extensions():
    assert is_supported_image(Path("photo.jpg"))
    assert is_supported_image(Path("photo.jpeg"))
    assert is_supported_image(Path("photo.png"))
    assert is_supported_image(Path("photo.heic"))


def test_unsupported_media_extensions():
    assert not is_supported_image(Path("video.mov"))
    assert not is_supported_image(Path("video.mp4"))
    assert not is_supported_image(Path("photo.cr2"))


def test_is_supported_extension_matches_is_supported_image():
    assert is_supported_extension(".jpg")
    assert is_supported_extension(".HEIC")
    assert not is_supported_extension(".mov")
    assert not is_supported_extension(".cr2")
