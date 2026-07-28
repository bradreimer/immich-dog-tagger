"""
Immich API client.
"""

from dataclasses import dataclass
from pathlib import Path
from datetime import datetime

import httpx
import truststore

truststore.inject_into_ssl()


@dataclass(frozen=True)
class ImmichAsset:
    """
    Minimal representation of an Immich asset.
    """

    id: str
    filename: str
    checksum: str | None
    captured_at: datetime | None = None

    @property
    def extension(self) -> str:
        return Path(self.filename).suffix.lower()


def parse_immich_datetime(value: str | None) -> datetime | None:
    if value is None:
        return None

    return datetime.fromisoformat(value.replace("Z", "+00:00"))


class ImmichClient:
    """
    Client for the Immich REST API.
    """

    def __init__(
        self,
        url: str,
        api_key: str,
    ):
        self.url = url.rstrip("/")
        self.client = httpx.Client(
            headers={
                "x-api-key": api_key,
            }
        )

    def list_assets(
        self,
    ) -> list[ImmichAsset]:
        """
        Retrieve assets from Immich.
        """

        # Default page size for asset listing
        DEFAULT_PAGE_SIZE = 1000

        response = self.client.post(
            f"{self.url}/api/search/metadata",
            json={
                "size": DEFAULT_PAGE_SIZE,
            },
        )

        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise RuntimeError(
                f"Immich API error {response.status_code}: {response.text}"
            ) from exc

        data = response.json()

        items = data["assets"]["items"]

        return [
            ImmichAsset(
                id=item["id"],
                filename=item.get(
                    "originalFileName",
                    "",
                ),
                checksum=item.get(
                    "checksum",
                ),
                captured_at=parse_immich_datetime(item.get("fileCreatedAt")),
            )
            for item in items
        ]

    def download_asset(
        self,
        asset_id: str,
    ) -> bytes:
        """
        Download original asset bytes.
        """

        response = self.client.get(
            f"{self.url}/api/assets/{asset_id}/original",
        )

        response.raise_for_status()

        return response.content

    def list_albums(self) -> list[dict]:
        response = self.client.get(
            f"{self.url}/api/albums",
        )

        response.raise_for_status()

        return response.json()

    def create_album(
        self,
        name: str,
    ) -> str:
        response = self.client.post(
            f"{self.url}/api/albums",
            json={
                "albumName": name,
            },
        )

        response.raise_for_status()

        return response.json()["id"]

    def add_assets_to_album(
        self,
        album_id: str,
        asset_ids: list[str],
    ) -> None:
        response = self.client.put(
            f"{self.url}/api/albums/{album_id}/assets",
            json={
                "ids": asset_ids,
            },
        )

        response.raise_for_status()
