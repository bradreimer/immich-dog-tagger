from immich_dog_tagger.immich import ImmichClient


class AlbumService:
    def __init__(
        self,
        client: ImmichClient,
    ):
        self.client = client

    def ensure_album(
        self,
        name: str,
    ) -> str:
        albums = self.client.list_albums()

        for album in albums:
            if album["albumName"] == name:
                return album["id"]

        return self.client.create_album(name)

    def sync_identity(
        self,
        identity: str,
        asset_ids: list[str],
    ) -> None:
        album_name = f"Dog - {identity}"

        album_id = self.ensure_album(
            album_name,
        )

        self.client.add_assets_to_album(
            album_id,
            asset_ids,
        )
