import json

import httpx
import pytest

from immich_dog_tagger.immich import ImmichClient, ImmichRemoveAssetsFromAlbumError


def test_list_assets():
    def handler(request):
        assert request.headers["x-api-key"] == "secret"

        return httpx.Response(
            200,
            json={
                "assets": {
                    "items": [
                        {
                            "id": "abc123",
                            "originalFileName": "dog.jpg",
                            "checksum": "xyz",
                        }
                    ]
                }
            },
        )

    transport = httpx.MockTransport(handler)

    client = ImmichClient(
        "http://immich.test",
        "secret",
    )

    client.client = httpx.Client(
        transport=transport,
        headers={
            "x-api-key": "secret",
        },
    )

    assets = client.list_assets()

    assert len(assets) == 1
    assert assets[0].id == "abc123"
    assert assets[0].filename == "dog.jpg"


def test_list_assets_follows_pagination():
    requests = []

    pages = {
        None: {
            "assets": {
                "items": [{"id": "1", "originalFileName": "a.jpg", "checksum": "a"}],
                "nextPage": "2",
            }
        },
        2: {
            "assets": {
                "items": [{"id": "2", "originalFileName": "b.jpg", "checksum": "b"}],
                "nextPage": None,
            }
        },
    }

    def handler(request):
        body = json.loads(request.content)
        requests.append(body)

        return httpx.Response(200, json=pages[body.get("page")])

    transport = httpx.MockTransport(handler)

    client = ImmichClient(
        "http://immich.test",
        "secret",
    )

    client.client = httpx.Client(
        transport=transport,
        headers={"x-api-key": "secret"},
    )

    assets = client.list_assets()

    assert [asset.id for asset in assets] == ["1", "2"]
    assert requests[0].get("page") is None
    assert requests[1]["page"] == 2
    assert isinstance(requests[1]["page"], int)


def test_list_assets_requests_exif_and_people():
    """
    Immich only includes `exifInfo`/`people` in a /api/search/metadata
    response when the request opts in. Without these flags every asset comes
    back without location or recognized-people data, so the Asset cache
    behind the insights place/person facts (issue #94) stays empty and the
    parsing above never sees anything to parse.
    """

    bodies = []

    def handler(request):
        bodies.append(json.loads(request.content))

        return httpx.Response(200, json={"assets": {"items": []}})

    transport = httpx.MockTransport(handler)

    client = ImmichClient("http://immich.test", "secret")
    client.client = httpx.Client(transport=transport, headers={"x-api-key": "secret"})

    client.list_assets()

    assert bodies[0]["withExif"] is True
    assert bodies[0]["withPeople"] is True


def test_list_assets_parses_location_people_and_favorite():
    def handler(request):
        return httpx.Response(
            200,
            json={
                "assets": {
                    "items": [
                        {
                            "id": "abc123",
                            "originalFileName": "dog.jpg",
                            "checksum": "xyz",
                            "isFavorite": True,
                            "exifInfo": {
                                "latitude": 47.6,
                                "longitude": -122.3,
                                "city": "Seattle",
                                "state": "Washington",
                                "country": "United States",
                            },
                            "people": [
                                {"id": "p1", "name": "Brad"},
                                {"id": "p2", "name": None},
                            ],
                        }
                    ]
                }
            },
        )

    transport = httpx.MockTransport(handler)

    client = ImmichClient("http://immich.test", "secret")
    client.client = httpx.Client(transport=transport, headers={"x-api-key": "secret"})

    assets = client.list_assets()

    assert len(assets) == 1
    asset = assets[0]
    assert asset.is_favorite is True
    assert asset.latitude == 47.6
    assert asset.longitude == -122.3
    assert asset.city == "Seattle"
    assert asset.state == "Washington"
    assert asset.country == "United States"
    assert [person.id for person in asset.people] == ["p1", "p2"]
    assert asset.people[0].name == "Brad"
    assert asset.people[1].name is None


def test_list_assets_defaults_missing_metadata():
    def handler(request):
        return httpx.Response(
            200,
            json={
                "assets": {
                    "items": [
                        {
                            "id": "abc123",
                            "originalFileName": "dog.jpg",
                            "checksum": "xyz",
                        }
                    ]
                }
            },
        )

    transport = httpx.MockTransport(handler)

    client = ImmichClient("http://immich.test", "secret")
    client.client = httpx.Client(transport=transport, headers={"x-api-key": "secret"})

    asset = client.list_assets()[0]

    assert asset.is_favorite is False
    assert asset.latitude is None
    assert asset.city is None
    assert asset.people == ()


def test_download_asset():
    def handler(request):
        return httpx.Response(
            200,
            content=b"image-data",
        )

    transport = httpx.MockTransport(handler)

    client = ImmichClient(
        "http://immich.test",
        "secret",
    )

    client.client = httpx.Client(
        transport=transport,
    )

    data = client.download_asset("abc123")

    assert data == b"image-data"


def test_download_asset_preview():
    captured = {}

    def handler(request):
        captured["url"] = str(request.url)

        return httpx.Response(
            200,
            content=b"preview-jpeg-data",
        )

    transport = httpx.MockTransport(handler)

    client = ImmichClient(
        "http://immich.test",
        "secret",
    )

    client.client = httpx.Client(
        transport=transport,
    )

    data = client.download_asset_preview("abc123")

    assert data == b"preview-jpeg-data"
    assert (
        captured["url"]
        == "http://immich.test/api/assets/abc123/thumbnail?isThumb=false"
    )


def test_remove_assets_from_album():
    captured = {}

    def handler(request):
        captured["method"] = request.method
        captured["url"] = str(request.url)
        captured["body"] = request.content

        return httpx.Response(200, json={"success": True})

    transport = httpx.MockTransport(handler)

    client = ImmichClient(
        "http://immich.test",
        "secret",
    )

    client.client = httpx.Client(
        transport=transport,
        headers={"x-api-key": "secret"},
    )

    client.remove_assets_from_album("album1", ["asset1", "asset2"])

    assert captured["method"] == "DELETE"
    assert captured["url"] == "http://immich.test/api/albums/album1/assets"
    assert json.loads(captured["body"]) == {"ids": ["asset1", "asset2"]}


def test_remove_assets_from_album_raises_on_error():
    def handler(request):
        return httpx.Response(500, text="boom")

    transport = httpx.MockTransport(handler)

    client = ImmichClient(
        "http://immich.test",
        "secret",
    )

    client.client = httpx.Client(transport=transport)

    with pytest.raises(ImmichRemoveAssetsFromAlbumError):
        client.remove_assets_from_album("album1", ["asset1"])


def test_client_creation():
    from immich_dog_tagger.immich import ImmichClient

    client = ImmichClient(
        "https://immich.example.com",
        "secret",
    )

    assert client.client is not None
