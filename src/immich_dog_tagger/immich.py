"""
Immich API client.
"""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import httpx
import truststore

truststore.inject_into_ssl()

# Immich's bulk album/tag membership endpoints take an unbounded "ids" array, but a single
# request carrying an entire large identity's asset list can take Immich longer to process than
# any timeout is worth granting (issue #243, following #237's fix of the request timeout itself).
# Splitting into fixed-size batches keeps each request's processing time bounded regardless of
# how many assets an identity has.
ASSET_BATCH_SIZE = 200


def _batched(ids: list[str], size: int) -> list[list[str]]:
    return [ids[i : i + size] for i in range(0, len(ids), size)]


def _bulk_failures(results: list[dict], *, benign: set[str]) -> list[dict]:
    """Immich's bulk album/tag membership endpoints return HTTP 200 with a per-asset
    ``[{id, success, error}]`` body (``BulkIdResponseDto``) even when every asset was rejected --
    e.g. ``no_permission`` when the asset isn't owned by the API key's Immich user (issue #259).
    ``benign`` names the error code(s) that mean "already in the desired state, nothing to do"
    for this call -- ``duplicate`` (already a member) for the add-side calls, ``not_found``
    (already not a member) for the remove-side calls (issue #278); anything else is a real
    failure."""
    return [
        item
        for item in results
        if not item.get("success", True) and item.get("error") not in benign
    ]


class ImmichDownloadError(Exception):
    pass


class ImmichListAssetsError(Exception):
    pass


class ImmichListAlbumsError(Exception):
    pass


class ImmichCreateAlbumError(Exception):
    pass


class ImmichBulkWriteError(Exception):
    """Raised for a bulk album/tag membership write Immich rejected -- either at the HTTP level,
    or (issue #259) via a 200 response whose per-asset body reported failures. `failures` carries
    the rejected `{id, success, error}` items when known, so callers (e.g. SyncService) can tell
    a permission problem (`no_permission`, most often a missing `tag.asset`/`albumAsset.*` grant
    on the Immich API key -- tags in particular are per-owner, not shareable like albums) apart
    from a transient one, without parsing this exception's message text."""

    def __init__(self, message: str, failures: list[dict] | None = None):
        super().__init__(message)
        self.failures = failures or []

    @property
    def permission_denied(self) -> bool:
        return any(failure.get("error") == "no_permission" for failure in self.failures)


class ImmichAddAssetsToAlbumError(ImmichBulkWriteError):
    pass


class ImmichRemoveAssetsFromAlbumError(ImmichBulkWriteError):
    pass


class ImmichListTagsError(Exception):
    pass


class ImmichCreateTagError(Exception):
    pass


class ImmichTagAssetsError(ImmichBulkWriteError):
    pass


class ImmichUntagAssetsError(ImmichBulkWriteError):
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

    # Raw (pre-rotation) dimensions and EXIF orientation tag (1-8), also from
    # exifInfo -- added for the stale-detection auto-repair spec
    # (docs/specs/stale-detection-auto-repair.md). None when Immich has no
    # EXIF data for the asset, same as the other exifInfo-sourced fields.
    exif_width: int | None = None
    exif_height: int | None = None
    exif_orientation: int | None = None

    @property
    def extension(self) -> str:
        return Path(self.filename).suffix.lower()


def _parse_int(value) -> int | None:
    if value is None:
        return None

    try:
        return int(value)
    except (
        TypeError,
        ValueError,
    ):
        return None


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
        exif_width=_parse_int(exif.get("exifImageWidth")),
        exif_height=_parse_int(exif.get("exifImageHeight")),
        exif_orientation=_parse_int(exif.get("orientation")),
    )


class ImmichClient:
    """
    Client for the Immich REST API.
    """

    def __init__(
        self,
        url: str,
        api_key: str,
        timeout: float = 60.0,
    ):
        self.url = url.rstrip("/")
        self.client = httpx.Client(
            headers={
                "x-api-key": api_key,
            },
            # httpx's 5s default is too short for bulk album/tag membership writes, which scale
            # with the number of assets in an identity and can legitimately take Immich longer to
            # process (issue #237).
            timeout=timeout,
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
        for batch in _batched(asset_ids, ASSET_BATCH_SIZE):
            response = self.client.put(
                f"{self.url}/api/albums/{album_id}/assets",
                json={
                    "ids": batch,
                },
            )

            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                raise ImmichAddAssetsToAlbumError(
                    f"Immich API error {response.status_code}: {response.text}"
                ) from exc

            failures = _bulk_failures(response.json(), benign={"duplicate"})

            if failures:
                raise ImmichAddAssetsToAlbumError(
                    f"Immich rejected {len(failures)}/{len(batch)} asset(s) "
                    f"adding to album {album_id}: {failures}",
                    failures=failures,
                )

    def remove_assets_from_album(
        self,
        album_id: str,
        asset_ids: list[str],
    ) -> None:
        # DELETE with a JSON body -- the same {"ids": [...]} shape as the
        # add endpoint above -- so httpx.Client.request() is used directly;
        # .delete() doesn't accept a json= body.
        for batch in _batched(asset_ids, ASSET_BATCH_SIZE):
            response = self.client.request(
                "DELETE",
                f"{self.url}/api/albums/{album_id}/assets",
                json={
                    "ids": batch,
                },
            )

            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                raise ImmichRemoveAssetsFromAlbumError(
                    f"Immich API error {response.status_code}: {response.text}"
                ) from exc

            failures = _bulk_failures(response.json(), benign={"not_found"})

            if failures:
                raise ImmichRemoveAssetsFromAlbumError(
                    f"Immich rejected {len(failures)}/{len(batch)} asset(s) "
                    f"removing from album {album_id}: {failures}",
                    failures=failures,
                )

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
        for batch in _batched(asset_ids, ASSET_BATCH_SIZE):
            response = self.client.put(
                f"{self.url}/api/tags/{tag_id}/assets",
                json={
                    "ids": batch,
                },
            )

            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                raise ImmichTagAssetsError(
                    f"Immich API error {response.status_code}: {response.text}"
                ) from exc

            failures = _bulk_failures(response.json(), benign={"duplicate"})

            if failures:
                raise ImmichTagAssetsError(
                    f"Immich rejected {len(failures)}/{len(batch)} asset(s) "
                    f"tagging with {tag_id}: {failures}",
                    failures=failures,
                )

    def untag_assets(
        self,
        tag_id: str,
        asset_ids: list[str],
    ) -> None:
        # DELETE with a JSON body, same as remove_assets_from_album -- httpx.Client.request()
        # is needed directly since .delete() doesn't accept a json= body.
        for batch in _batched(asset_ids, ASSET_BATCH_SIZE):
            response = self.client.request(
                "DELETE",
                f"{self.url}/api/tags/{tag_id}/assets",
                json={
                    "ids": batch,
                },
            )

            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                raise ImmichUntagAssetsError(
                    f"Immich API error {response.status_code}: {response.text}"
                ) from exc

            failures = _bulk_failures(response.json(), benign={"not_found"})

            if failures:
                raise ImmichUntagAssetsError(
                    f"Immich rejected {len(failures)}/{len(batch)} asset(s) "
                    f"untagging from {tag_id}: {failures}",
                    failures=failures,
                )
