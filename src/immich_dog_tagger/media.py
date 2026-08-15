from pathlib import Path

SUPPORTED_IMAGE_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".heic",
}


def is_supported_extension(extension: str) -> bool:
    return extension.lower() in SUPPORTED_IMAGE_EXTENSIONS


def is_supported_image(path: Path) -> bool:
    return is_supported_extension(path.suffix)
