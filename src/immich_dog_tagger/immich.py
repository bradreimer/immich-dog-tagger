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


class ImmichGetAssetError(Exception):
    pass


class ImmichAssetNotFoundError(ImmichGetAssetError):
    """Immich answered, and says it has no such asset (issue #370): a 404, or the 400 "Not found
    or no asset.read access" Immich returns for a deleted asset's ID. A subclass so existing
    ImmichGetAssetError handlers keep treating it as a failed fetch; AssetRepairService catches
    it first to mark the asset removed instead."""


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

    def __init__(
        self,
        message: str,
        failures: list[dict] | None = None,
        *,
        http_error: bool = False,
    ):
        super().__init__(message)
        self.failures = failures or []
        # True when at least one batch failed at the HTTP level, so `failures` alone doesn't
        # account for everything that went wrong.
        self.http_error = http_error

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

    def get_asset(
        self,
        asset_id: str,
    ) -> ImmichAsset:
        """
        Fetch current metadata for a single asset -- for a per-asset refresh
        (issue #326's Repair addendum) where paging the whole library through
        list_assets() just to pick up one row would be wasteful. Immich's
        AssetResponseDto carries the same originalFileName/checksum/
        fileCreatedAt/exifInfo/people/isFavorite fields list_assets() already
        parses via _parse_immich_asset(), so the same parser is reused here.
        """

        try:
            response = self.client.get(
                f"{self.url}/api/assets/{asset_id}",
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            message = f"Immich API error {response.status_code}: {response.text}"

            # Only "this asset doesn't exist" statuses -- never 401/403 (a credential or
            # permission problem) or 5xx (Immich itself failing), which say nothing about
            # whether the photo still exists (issue #370).
            if response.status_code in (400, 404):
                raise ImmichAssetNotFoundError(message) from exc

            raise ImmichGetAssetError(message) from exc
        except httpx.HTTPError as exc:
            # Anything short of a response -- a malformed/unreachable configured URL, DNS
            # failure, connection refused/timeout, TLS error -- so AssetRepairService's existing
            # ImmichGetAssetError handler turns it into a friendly repair-failed message instead
            # of an unhandled 500 (issue #350).
            raise ImmichGetAssetError(f"could not reach Immich: {exc}") from exc

        return _parse_immich_asset(response.json())

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

    def _bulk_membership_write(
        self,
        method: str,
        path: str,
        asset_ids: list[str],
        *,
        error_cls: type[ImmichBulkWriteError],
        benign: set[str],
        action: str,
        target_id: str,
    ) -> None:
        """Send a bulk album/tag membership write in batches (issue #407).

        A rejected batch -- an HTTP error, or per-item failures in a 200 body (issue #259) -- no
        longer stops the batches after it: every batch is attempted, then one `error_cls` carrying
        all the failures is raised, so one bad asset can't leave the rest of a large identity
        unwritten. Transport errors (timeouts, connection failures) still propagate immediately.
        """
        failures: list[dict] = []
        http_errors: list[str] = []
        attempted = 0

        # DELETE needs httpx.Client.request() -- .delete() doesn't accept a json= body.
        for batch in _batched(asset_ids, ASSET_BATCH_SIZE):
            attempted += len(batch)
            response = self.client.request(
                method,
                f"{self.url}{path}",
                json={
                    "ids": batch,
                },
            )

            try:
                response.raise_for_status()
            except httpx.HTTPStatusError:
                http_errors.append(
                    f"Immich API error {response.status_code}: {response.text}"
                )
                continue

            failures.extend(_bulk_failures(response.json(), benign=benign))

        if http_errors:
            raise error_cls(
                "; ".join(http_errors),
                failures=failures,
                http_error=True,
            )

        if failures:
            raise error_cls(
                f"Immich rejected {len(failures)}/{attempted} asset(s) "
                f"{action} {target_id}: {failures}",
                failures=failures,
            )

    def add_assets_to_album(
        self,
        album_id: str,
        asset_ids: list[str],
    ) -> None:
        self._bulk_membership_write(
            "PUT",
            f"/api/albums/{album_id}/assets",
            asset_ids,
            error_cls=ImmichAddAssetsToAlbumError,
            benign={"duplicate"},
            action="adding to album",
            target_id=album_id,
        )

    def remove_assets_from_album(
        self,
        album_id: str,
        asset_ids: list[str],
    ) -> None:
        self._bulk_membership_write(
            "DELETE",
            f"/api/albums/{album_id}/assets",
            asset_ids,
            error_cls=ImmichRemoveAssetsFromAlbumError,
            benign={"not_found"},
            action="removing from album",
            target_id=album_id,
        )

    def get_album_asset_ids(self, album_id: str) -> set[str]:
        """Ids of every asset currently in an album (issue #407 audit/repair)."""
        response = self.client.get(f"{self.url}/api/albums/{album_id}")

        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise ImmichListAlbumsError(
                f"Immich API error {response.status_code}: {response.text}"
            ) from exc

        return {asset["id"] for asset in response.json().get("assets", [])}

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
        self._bulk_membership_write(
            "PUT",
            f"/api/tags/{tag_id}/assets",
            asset_ids,
            error_cls=ImmichTagAssetsError,
            benign={"duplicate"},
            action="tagging with",
            target_id=tag_id,
        )

    def untag_assets(
        self,
        tag_id: str,
        asset_ids: list[str],
    ) -> None:
        self._bulk_membership_write(
            "DELETE",
            f"/api/tags/{tag_id}/assets",
            asset_ids,
            error_cls=ImmichUntagAssetsError,
            benign={"not_found"},
            action="untagging from",
            target_id=tag_id,
        )

    def get_tag_asset_ids(self, tag_id: str) -> set[str]:
        """Ids of every asset currently carrying a tag (issue #407 audit/repair), paged through
        Immich's metadata search since the tag endpoints themselves don't list members."""
        asset_ids: set[str] = set()
        page: int | None = 1

        while page is not None:
            response = self.client.post(
                f"{self.url}/api/search/metadata",
                json={
                    "tagIds": [tag_id],
                    "page": page,
                    "size": 1000,
                    "withDeleted": False,
                },
            )

            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                raise ImmichListTagsError(
                    f"Immich API error {response.status_code}: {response.text}"
                ) from exc

            assets = response.json().get("assets", {})
            asset_ids.update(item["id"] for item in assets.get("items", []))
            next_page = assets.get("nextPage")
            page = int(next_page) if next_page else None

        return asset_ids
