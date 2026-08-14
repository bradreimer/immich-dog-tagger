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
