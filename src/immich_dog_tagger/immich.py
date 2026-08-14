"""
Immich API client.
"""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import httpx
import truststore

truststore.inject_into_ssl()


class ImmichDownloadError(Exception):
    pass


class ImmichListAssetsError(Exception):
    pass


class ImmichListAlbumsError(Exception):
    pass


class ImmichCreateAlbumError(Exception):
    pass


class ImmichAddAssetsToAlbumError(Exception):
    pass


class ImmichRemoveAssetsFromAlbumError(Exception):
    pass


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

    return datetime.fromisoformat(value)


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
        Retrieve all assets from Immich, following pagination until exhausted.
        """

        PAGE_SIZE = 1000

        assets: list[ImmichAsset] = []
        page: str | None = None

        while True:
            body: dict = {"size": PAGE_SIZE}

            if page is not None:
                body["page"] = page

            response = self.client.post(
                f"{self.url}/api/search/metadata",
                json=body,
            )

            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                raise ImmichListAssetsError(
                    f"Immich API error {response.status_code}: {response.text}"
                ) from exc

            result = response.json()["assets"]

            assets.extend(
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
                for item in result["items"]
            )

            page = result.get("nextPage")

            if not page:
                break

        return assets

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

        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise ImmichDownloadError(
                f"Immich API error {response.status_code}: {response.text}"
            ) from exc

        return response.content

    def list_albums(self) -> list[dict]:
        response = self.client.get(
            f"{self.url}/api/albums",
        )

        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise ImmichListAlbumsError(
                f"Immich API error {response.status_code}: {response.text}"
            ) from exc

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

        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise ImmichCreateAlbumError(
                f"Immich API error {response.status_code}: {response.text}"
            ) from exc

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

        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise ImmichAddAssetsToAlbumError(
                f"Immich API error {response.status_code}: {response.text}"
            ) from exc

    def remove_assets_from_album(
        self,
        album_id: str,
        asset_ids: list[str],
    ) -> None:
        # DELETE with a JSON body -- the same {"ids": [...]} shape as the
        # add endpoint above -- so httpx.Client.request() is used directly;
        # .delete() doesn't accept a json= body.
        response = self.client.request(
            "DELETE",
            f"{self.url}/api/albums/{album_id}/assets",
            json={
                "ids": asset_ids,
            },
        )

        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise ImmichRemoveAssetsFromAlbumError(
                f"Immich API error {response.status_code}: {response.text}"
            ) from exc
