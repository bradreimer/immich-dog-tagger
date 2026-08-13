from immich_dog_tagger.immich import ImmichClient


class AlbumService:
    def __init__(
        self,
        client: ImmichClient,
    ):
        self.client = client

    def _find_album(
        self,
        name: str,
    ) -> str | None:
        albums = self.client.list_albums()

        for album in albums:
            if album["albumName"] == name:
                return album["id"]

        return None

    def ensure_album(
        self,
        name: str,
    ) -> str:
        album_id = self._find_album(name)

        if album_id is not None:
            return album_id

        return self.client.create_album(name)

    def sync_identity(
        self,
        identity: str,
        asset_ids: list[str],
        species: str = "dog",
    ) -> None:
        album_name = f"{species.capitalize()} - {identity}"

        album_id = self.ensure_album(
            album_name,
        )

        self.client.add_assets_to_album(
            album_id,
            asset_ids,
        )

    def remove_from_identity(
        self,
        identity: str,
        asset_ids: list[str],
        species: str = "dog",
    ) -> None:
        album_name = f"{species.capitalize()} - {identity}"

        album_id = self._find_album(album_name)

        if album_id is None:
            # Nothing to remove from -- the album doesn't exist (e.g. this
            # identity was never actually synced, or the album was deleted
            # directly in Immich). Removal never creates an album.
            return

        self.client.remove_assets_from_album(
            album_id,
            asset_ids,
        )
