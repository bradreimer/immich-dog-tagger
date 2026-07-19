import httpx

from immich_dog_tagger.immich import ImmichClient


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


def test_client_creation():
    from immich_dog_tagger.immich import ImmichClient

    client = ImmichClient(
        "https://immich.example.com",
        "secret",
    )

    assert client.client is not None
