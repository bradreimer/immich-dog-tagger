from immich_dog_tagger.services.albums import AlbumService


class FakeImmich:
    def __init__(self):
        self.created = []
        self.added = []

    def list_albums(self):
        return []

    def create_album(self, name):
        self.created.append(name)
        return "album1"

    def add_assets_to_album(
        self,
        album_id,
        asset_ids,
    ):
        self.added.append(
            (
                album_id,
                asset_ids,
            )
        )


def test_album_service_creates_album():
    client = FakeImmich()

    service = AlbumService(client)

    service.sync_identity(
        "Hermann",
        ["asset1"],
    )

    assert client.created == ["Dog - Hermann"]

    assert client.added == [
        (
            "album1",
            ["asset1"],
        )
    ]
