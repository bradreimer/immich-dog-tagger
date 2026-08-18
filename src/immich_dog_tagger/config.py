"""
Application configuration.
"""

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class Config:
    immich_url: str
    immich_api_key: str
    state_dir: Path
    cache_dir: Path
    yolo_model: Path
    crop_padding: float

    #: Browser-facing Immich base URL, for links a human clicks. Deployments where the
    #: container reaches Immich at a different address than the reviewer's browser (a
    #: Docker-internal hostname, say) set this; everyone else leaves it empty and gets
    #: ``immich_url``. Read through :attr:`immich_link_base_url`, never directly.
    immich_external_url: str = ""

    @property
    def crop_dir(self) -> Path:
        return self.cache_dir / "crops"

    @property
    def immich_link_base_url(self) -> str:
        """
        Base URL for Immich deep links handed to the browser.
        """

        return self.immich_external_url or self.immich_url


def load_config(load_env_file: bool = True) -> Config:
    """
    Load application configuration from environment variables.
    """

    if load_env_file:
        load_dotenv()

    state_dir = Path(
        os.environ.get(
            "STATE_DIR",
            "./state",
        )
    )

    cache_dir = Path(
        os.environ.get(
            "CACHE_DIR",
            "./cache",
        )
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
        immich_external_url=os.environ.get(
            "IMMICH_EXTERNAL_URL",
            "",
        ).strip(),
        state_dir=state_dir,
        cache_dir=cache_dir,
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
