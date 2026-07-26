from dataclasses import dataclass


@dataclass(frozen=True)
class SyncPolicy:
    minimum_confidence: float = 0.80
    include_unknown: bool = False
