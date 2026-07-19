"""
Application configuration.
"""

from dataclasses import dataclass
import os
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class Config:
    immich_url: str
    immich_api_key: str
    data_dir: Path
    cache_dir: Path
    yolo_model: Path
    crop_padding: float

    @property
    def crop_dir(self) -> Path:
        return self.data_dir / "cache" / "crops"


def load_config(load_env_file: bool = True) -> Config:
    """
    Load application configuration from environment variables.
    """
    
    if load_env_file:
        load_dotenv()

    data_dir = Path(
        os.environ.get("DATA_DIR", "./data")
    )

    return Config(
        immich_url=os.environ.get(
            "IMMICH_URL",
            "",
        ),
        immich_api_key=os.environ.get(
            "IMMICH_API_KEY",
            "",
        ),
        data_dir=data_dir,
        cache_dir=data_dir / "cache" / "assets",
        yolo_model=Path(
            os.environ.get(
                "YOLO_MODEL",
                "/models/yolo11n.pt",
            )
        ),
        crop_padding=float(
            os.environ.get(
                "CROP_PADDING",
                "0.15",
            )
        ),
    )
