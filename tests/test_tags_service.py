from immich_dog_tagger.services.tags import TagService


class FakeImmich:
    def __init__(self, existing_tags=None):
        self.created = []
        self.tagged = []
        self.untagged = []
        self._tags = list(existing_tags or [])

    def list_tags(self):
        return self._tags

    def create_tag(self, name):
        self.created.append(name)
        tag = {"id": "tag1", "name": name}
        self._tags.append(tag)
        return tag["id"]

    def tag_assets(
        self,
        tag_id,
        asset_ids,
    ):
        self.tagged.append(
            (
                tag_id,
                asset_ids,
            )
        )

    def untag_assets(
        self,
        tag_id,
        asset_ids,
    ):
        self.untagged.append(
            (
                tag_id,
                asset_ids,
            )
        )


def test_tag_service_creates_tag():
    client = FakeImmich()

    service = TagService(client)

    service.sync_identity(
        "Hermann",
        ["asset1"],
    )

    assert client.created == ["Dog - Hermann"]

    assert client.tagged == [
        (
            "tag1",
            ["asset1"],
        )
    ]


def test_tag_service_names_cat_tags_by_species():
    client = FakeImmich()

    service = TagService(client)

    service.sync_identity(
        "Whiskers",
        ["asset1"],
        species="cat",
    )

    assert client.created == ["Cat - Whiskers"]


def test_tag_service_reuses_existing_tag():
    client = FakeImmich(existing_tags=[{"id": "tag1", "name": "Dog - Fibs"}])

    service = TagService(client)

    service.sync_identity(
        "Fibs",
        ["asset1"],
    )

    assert client.created == []
    assert client.tagged == [("tag1", ["asset1"])]


def test_tag_service_removes_from_existing_tag():
    client = FakeImmich(existing_tags=[{"id": "tag1", "name": "Dog - Fibs"}])

    service = TagService(client)

    service.remove_from_identity(
        "Fibs",
        ["asset1"],
    )

    assert client.untagged == [("tag1", ["asset1"])]
    assert client.created == []


def test_tag_service_remove_from_identity_is_noop_when_tag_missing():
    client = FakeImmich()

    service = TagService(client)

    service.remove_from_identity(
        "Fibs",
        ["asset1"],
    )

    assert client.untagged == []
    assert client.created == []


def test_tag_service_remove_from_identity_names_cat_tags_by_species():
    client = FakeImmich(existing_tags=[{"id": "tag1", "name": "Cat - Whiskers"}])

    service = TagService(client)

    service.remove_from_identity(
        "Whiskers",
        ["asset1"],
        species="cat",
    )

    assert client.untagged == [("tag1", ["asset1"])]
