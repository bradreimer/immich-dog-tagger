from dataclasses import dataclass


@dataclass(frozen=True)
class SyncPolicy:
    minimum_confidence: float = 0.80
    include_unknown: bool = False
    # An identity needs at least this many synced photos to get an Immich album
    # (issue #405). Every identity is still tagged. The code default of 0 keeps
    # the original "album for everyone" behavior; production call sites pass the
    # configured `ALBUM_MIN_PHOTOS` (default 50).
    album_minimum_assets: int = 0
