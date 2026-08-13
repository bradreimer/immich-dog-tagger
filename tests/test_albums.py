from immich_dog_tagger.services.albums import AlbumService


class FakeImmich:
    def __init__(self, existing_albums=None):
        self.created = []
        self.added = []
        self.removed = []
        self._albums = list(existing_albums or [])

    def list_albums(self):
        return self._albums

    def create_album(self, name):
        self.created.append(name)
        album = {"id": "album1", "albumName": name}
        self._albums.append(album)
        return album["id"]

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

    def remove_assets_from_album(
        self,
        album_id,
        asset_ids,
    ):
        self.removed.append(
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


def test_album_service_names_cat_albums_by_species():
    client = FakeImmich()

    service = AlbumService(client)

    service.sync_identity(
        "Whiskers",
        ["asset1"],
        species="cat",
    )

    assert client.created == ["Cat - Whiskers"]


def test_album_service_removes_from_existing_album():
    client = FakeImmich(existing_albums=[{"id": "album1", "albumName": "Dog - Fibs"}])

    service = AlbumService(client)

    service.remove_from_identity(
        "Fibs",
        ["asset1"],
    )

    assert client.removed == [("album1", ["asset1"])]
    assert client.created == []


def test_album_service_remove_from_identity_is_noop_when_album_missing():
    """DT-1113: removal never creates an album -- if the identity was never
    synced (or its album was deleted directly in Immich), there's nothing
    to remove from."""
    client = FakeImmich()

    service = AlbumService(client)

    service.remove_from_identity(
        "Fibs",
        ["asset1"],
    )

    assert client.removed == []
    assert client.created == []


def test_album_service_remove_from_identity_names_cat_albums_by_species():
    client = FakeImmich(
        existing_albums=[{"id": "album1", "albumName": "Cat - Whiskers"}]
    )

    service = AlbumService(client)

    service.remove_from_identity(
        "Whiskers",
        ["asset1"],
        species="cat",
    )

    assert client.removed == [("album1", ["asset1"])]
