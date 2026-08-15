from enum import Enum, StrEnum


class Species(StrEnum):
    """
    Hardcoded to exactly these two values (DT-1110) -- not a general-purpose,
    configurable species list.
    """

    DOG = "dog"
    CAT = "cat"


class AssetStatus(StrEnum):
    PENDING = "pending"
    DOWNLOADED = "downloaded"
    DETECTED = "detected"
    CLASSIFIED = "classified"
    TAGGED = "tagged"

    DOWNLOAD_FAILED = "download_failed"
    DETECTION_FAILED = "detection_failed"
    CLASSIFICATION_FAILED = "classification_failed"

    # Terminal: detect can never process this file type (see is_supported_image),
    # so download skips it rather than fetching bytes nothing will use.
    UNSUPPORTED = "unsupported"


class EmbeddingSources(StrEnum):
    BOOTSTRAP = "bootstrap"
    REVIEW = "review"
    IMPORT = "import"


class ClassificationMode(str, Enum):
    PENDING = "pending"
    LOW_CONFIDENCE = "low_confidence"
    ALL = "all"


class ClassificationSources(StrEnum):
    AUTO = "auto"
    REVIEW = "review"
    MANUAL = "manual"


class ReviewActions(StrEnum):
    SKIP = "skip"
    CORRECT = "correct"


class PipelineOperation(StrEnum):
    SCAN = "scan"
    DETECT = "detect"
    EMBED = "embed"
    CLASSIFY = "classify"
    RECLASSIFY = "reclassify"
    LEARN = "learn"
    SYNC = "sync"
    FULL_PIPELINE = "full_pipeline"


class PipelineJobStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELED = "canceled"


class ClassificationPassStatus(StrEnum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
