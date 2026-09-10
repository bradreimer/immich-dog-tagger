import time

from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.orm import Session

from immich_dog_tagger.enums import EmbeddingSources
from immich_dog_tagger.models import (
    EmbeddingExample,
    Identity,
)


class _RecordFirstResponseBody:
    """
    Wraps an ASGI app to record when it sends the first `http.response.body`
    message -- i.e. when the client actually starts receiving file bytes,
    as opposed to when the endpoint function returns. Used below to check
    that a DB connection is released *before* streaming starts, not after
    it finishes.
    """

    def __init__(self, asgi_app, events):
        self.asgi_app = asgi_app
        self.events = events

    async def __call__(self, scope, receive, send):
        seen = False

        async def wrapped_send(message):
            nonlocal seen
            if not seen and message.get("type") == "http.response.body":
                seen = True
                self.events.append(("body", time.perf_counter()))
            await send(message)

        await self.asgi_app(scope, receive, wrapped_send)


def test_embedding_example_image(
    api_client,
    engine,
    tmp_path,
):
    image = tmp_path / "example.jpg"
    image.write_bytes(b"fake-image")

    with Session(engine) as session:
        identity = Identity(
            name="Hermann",
        )

        example = EmbeddingExample(
            identity=identity,
            crop_path=str(image),
            embedding=b"fake",
            source=EmbeddingSources.REVIEW,
        )

        session.add(example)
        session.commit()

        example_id = example.id

    response = api_client.get(
        f"/embedding-examples/{example_id}/image",
    )

    assert response.status_code == 200
    assert response.content == b"fake-image"


def test_embedding_example_image_releases_its_db_connection_before_streaming_the_file(
    api_client, engine, tmp_path
):
    # Issue #277: same root cause and fix as crops.py's `crop` route --
    # FastAPI only runs a `Depends(yield)` dependency's cleanup *after* the
    # full response has been sent, so a request-scoped session stayed
    # checked out of the pool for as long as the image took to stream, not
    # just for the DB lookup. Pin the fix: the connection is released
    # before the file starts streaming, not after it finishes.
    image = tmp_path / "example.jpg"
    image.write_bytes(b"x" * (1024 * 1024))

    with Session(engine) as session:
        identity = Identity(name="Hermann")
        example = EmbeddingExample(
            identity=identity,
            crop_path=str(image),
            embedding=b"fake",
            source=EmbeddingSources.REVIEW,
        )
        session.add(example)
        session.commit()
        example_id = example.id

    events = []

    def on_checkin(dbapi_connection, connection_record):
        events.append(("checkin", time.perf_counter()))

    event.listen(engine, "checkin", on_checkin)
    try:
        wrapped_client = TestClient(_RecordFirstResponseBody(api_client.app, events))
        response = wrapped_client.get(f"/embedding-examples/{example_id}/image")
    finally:
        event.remove(engine, "checkin", on_checkin)

    assert response.status_code == 200

    checkin_times = [t for name, t in events if name == "checkin"]
    body_times = [t for name, t in events if name == "body"]

    assert checkin_times, "expected the lookup to check its connection back in"
    assert body_times, "expected the response body to be sent"
    assert checkin_times[-1] <= body_times[0], (
        "the DB connection used to look up the example must be released "
        "before the file starts streaming to the client, not held open "
        "for the whole transfer"
    )
