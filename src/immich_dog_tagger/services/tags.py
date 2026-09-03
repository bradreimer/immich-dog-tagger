from immich_dog_tagger.immich import ImmichClient


class TagService:
    def __init__(
        self,
        client: ImmichClient,
    ):
        self.client = client

    def _find_tag(
        self,
        name: str,
    ) -> str | None:
        tags = self.client.list_tags()

        for tag in tags:
            if tag["name"] == name:
                return tag["id"]

        return None

    def ensure_tag(
        self,
        name: str,
    ) -> str:
        tag_id = self._find_tag(name)

        if tag_id is not None:
            return tag_id

        return self.client.create_tag(name)

    def sync_identity(
        self,
        identity: str,
        asset_ids: list[str],
        species: str = "dog",
    ) -> None:
        tag_name = f"{species.capitalize()} - {identity}"

        tag_id = self.ensure_tag(
            tag_name,
        )

        self.client.tag_assets(
            tag_id,
            asset_ids,
        )

    def remove_from_identity(
        self,
        identity: str,
        asset_ids: list[str],
        species: str = "dog",
    ) -> None:
        tag_name = f"{species.capitalize()} - {identity}"

        tag_id = self._find_tag(tag_name)

        if tag_id is None:
            # Nothing to remove from -- the tag doesn't exist (e.g. this
            # identity was never actually synced, or the tag was deleted
            # directly in Immich). Removal never creates a tag, mirroring
            # AlbumService.remove_from_identity (DT-1113).
            return

        self.client.untag_assets(
            tag_id,
            asset_ids,
        )
