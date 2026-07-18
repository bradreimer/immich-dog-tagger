"""
Immich API client.
"""

from dataclasses import dataclass

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
                f"Immich API error "
                f"{response.status_code}: "
                f"{response.text}"
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