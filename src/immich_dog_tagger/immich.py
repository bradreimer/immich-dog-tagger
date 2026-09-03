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


class ImmichListTagsError(Exception):
    pass


class ImmichCreateTagError(Exception):
    pass


class ImmichTagAssetsError(Exception):
    pass


class ImmichUntagAssetsError(Exception):
    pass


@dataclass(frozen=True)
class ImmichPerson:
    """
    A person Immich recognized in an asset (issue #94) -- a read-only
    reference to Immich's own recognition, never Dog Tagger's own.
    """

    id: str
    name: str | None


@dataclass(frozen=True)
class ImmichAsset:
    """
    Minimal representation of an Immich asset.
    """

    id: str
    filename: str
    checksum: str | None
    captured_at: datetime | None = None

    # Cached from exifInfo/people/isFavorite in the same /api/search/metadata
    # response (issue #94) -- no extra Immich API call. None/[] when Immich
    # has no location/people data for this asset, not "not yet known".
    latitude: float | None = None
    longitude: float | None = None
    country: str | None = None
    state: str | None = None
    city: str | None = None
    is_favorite: bool = False
    people: tuple[ImmichPerson, ...] = ()

    @property
    def extension(self) -> str:
        return Path(self.filename).suffix.lower()


def parse_immich_datetime(value: str | None) -> datetime | None:
    if value is None:
        return None

    return datetime.fromisoformat(value)


def _parse_immich_asset(item: dict) -> ImmichAsset:
    """
    Build an ImmichAsset from one /api/search/metadata result item,
    including the exifInfo/people/isFavorite fields issue #94 needs for
    insights. Every field is read with .get() -- an Immich response that
    omits exifInfo or people (e.g. an older server version, or a photo with
    no EXIF) yields None/[]/False rather than a parse error, matching how
    checksum/originalFileName are already read defensively above.
    """

    exif = item.get("exifInfo") or {}

    people = tuple(
        ImmichPerson(
            id=person["id"],
            name=person.get("name") or None,
        )
        for person in item.get("people") or []
        if person.get("id")
    )

    return ImmichAsset(
        id=item["id"],
        filename=item.get(
            "originalFileName",
            "",
        ),
        checksum=item.get(
            "checksum",
        ),
        captured_at=parse_immich_datetime(item.get("fileCreatedAt")),
        latitude=exif.get("latitude"),
        longitude=exif.get("longitude"),
        country=exif.get("country"),
        state=exif.get("state"),
        city=exif.get("city"),
        is_favorite=bool(item.get("isFavorite", False)),
        people=people,
    )


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
        page: int | None = None

        while True:
            # withExif/withPeople are opt-in on /api/search/metadata: without
            # them Immich omits `exifInfo` and `people` from every item, so
            # the location/people fields cached on Asset for insights (issue
            # #94) silently stay NULL/[] -- which is what left "Most
            # photographed place" and "Most often photographed with" blank
            # while `isFavorite` (a top-level, ungated field) worked.
            body: dict = {
                "size": PAGE_SIZE,
                "withExif": True,
                "withPeople": True,
            }

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

            assets.extend(_parse_immich_asset(item) for item in result["items"])

            next_page = result.get("nextPage")
            page = int(next_page) if next_page else None

            if page is None:
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

    def list_tags(self) -> list[dict]:
        response = self.client.get(
            f"{self.url}/api/tags",
        )

        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise ImmichListTagsError(
                f"Immich API error {response.status_code}: {response.text}"
            ) from exc

        return response.json()

    def create_tag(
        self,
        name: str,
    ) -> str:
        response = self.client.post(
            f"{self.url}/api/tags",
            json={
                "name": name,
            },
        )

        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise ImmichCreateTagError(
                f"Immich API error {response.status_code}: {response.text}"
            ) from exc

        return response.json()["id"]

    def tag_assets(
        self,
        tag_id: str,
        asset_ids: list[str],
    ) -> None:
        response = self.client.put(
            f"{self.url}/api/tags/{tag_id}/assets",
            json={
                "ids": asset_ids,
            },
        )

        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise ImmichTagAssetsError(
                f"Immich API error {response.status_code}: {response.text}"
            ) from exc

    def untag_assets(
        self,
        tag_id: str,
        asset_ids: list[str],
    ) -> None:
        # DELETE with a JSON body, same as remove_assets_from_album -- httpx.Client.request()
        # is needed directly since .delete() doesn't accept a json= body.
        response = self.client.request(
            "DELETE",
            f"{self.url}/api/tags/{tag_id}/assets",
            json={
                "ids": asset_ids,
            },
        )

        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise ImmichUntagAssetsError(
                f"Immich API error {response.status_code}: {response.text}"
            ) from exc
