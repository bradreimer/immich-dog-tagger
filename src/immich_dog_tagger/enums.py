from enum import StrEnum


class AssetStatus(StrEnum):
    PENDING = "pending"
    DOWNLOADED = "downloaded"
    DETECTED = "detected"
    CLASSIFIED = "classified"
    TAGGED = "tagged"

    DOWNLOAD_FAILED = "download_failed"
    DETECTION_FAILED = "detection_failed"
    CLASSIFICATION_FAILED = "classification_failed"


class EmbeddingSources(StrEnum):
    BOOTSTRAP = "bootstrap"
    REVIEW = "review"
    IMPORT = "import"


class ClassificationSources(StrEnum):
    AUTO = "auto"
    REVIEW = "review"
    MANUAL = "manual"
