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


def load_config(load_env_file: bool = True) -> Config:
    """
    Load application configuration from environment variables.
    """

    if load_env_file:
        load_dotenv()

    return Config(
        immich_url=os.environ.get(
            "IMMICH_URL",
            "",
        ),
        immich_api_key=os.environ.get(
            "IMMICH_API_KEY",
            "",
        ),
        data_dir=Path(
            os.environ.get(
                "DATA_DIR",
                "./data",
            )
        ),
    )
