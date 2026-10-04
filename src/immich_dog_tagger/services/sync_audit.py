"""
Audit and repair of drift between state.db and what Immich actually holds (issue #407).

Sync trusts its own `SyncedAsset` bookkeeping and never reads Immich back, so a tag that was
rejected, deleted in Immich, or never written leaves a photo in an identity's album without the
matching tag, silently and permanently. `SyncAuditService` reads Immich's real album/tag
membership, compares it to what state.db says should be there (the same expectation Sync uses),
and can bring Immich back in line. state.db stays the source of truth (ADR-001); this never
changes classifications, reviews, or learned examples.
"""

import logging
from dataclasses import dataclass, field

from immich_dog_tagger.services.sync import SyncService

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class IdentityDrift:
    species: str
    identity: str
    expected: int
    missing_tag: list[str] = field(default_factory=list)
    missing_from_album: list[str] = field(default_factory=list)
    extra_in_tag: list[str] = field(default_factory=list)
    extra_in_album: list[str] = field(default_factory=list)

    @property
    def drifted(self) -> bool:
        return bool(
            self.missing_tag
            or self.missing_from_album
            or self.extra_in_tag
            or self.extra_in_album
        )


@dataclass(frozen=True)
class AuditFailure:
    species: str
    identity: str
    message: str
    permission_error: bool = False


@dataclass(frozen=True)
class AuditReport:
    checked: int
    drifts: list[IdentityDrift]
    failures: list[AuditFailure] = field(default_factory=list)

    @property
    def clean(self) -> bool:
        return not self.drifts and not self.failures

    @property
    def missing_tag(self) -> int:
        return sum(len(d.missing_tag) for d in self.drifts)

    @property
    def missing_from_album(self) -> int:
        return sum(len(d.missing_from_album) for d in self.drifts)

    @property
    def extras(self) -> int:
        return sum(len(d.extra_in_tag) + len(d.extra_in_album) for d in self.drifts)


@dataclass(frozen=True)
class RepairResult:
    report: AuditReport
    added_tags: int = 0
    added_to_albums: int = 0
    removed: int = 0
    failures: list[AuditFailure] = field(default_factory=list)


class SyncAuditService:
    def __init__(self, sync: SyncService):
        self.sync = sync

    def audit(self) -> AuditReport:
        expected = self.sync.expected_state().assets
        previous = self.sync.previously_synced_state()

        drifts: list[IdentityDrift] = []
        failures: list[AuditFailure] = []
        keys = sorted(set(expected) | set(previous))

        for species, identity in keys:
            wanted = expected.get((species, identity), set())

            try:
                drift = self._audit_identity(species, identity, wanted)
            except Exception as exc:
                logger.exception("Audit failed for %s identity %r", species, identity)
                failures.append(
                    AuditFailure(
                        species,
                        identity,
                        str(exc),
                        permission_error=getattr(exc, "permission_denied", False),
                    )
                )
                continue

            if drift.drifted:
                drifts.append(drift)

        return AuditReport(checked=len(keys), drifts=drifts, failures=failures)

    def _audit_identity(
        self, species: str, identity: str, wanted: set[str]
    ) -> IdentityDrift:
        missing_tag: set[str] = set()
        extra_in_tag: set[str] = set()
        missing_from_album: set[str] = set()
        extra_in_album: set[str] = set()

        if self.sync.tags is not None:
            tagged = self.sync.tags.member_ids(identity, species)

            if tagged is None:
                missing_tag = set(wanted)
            else:
                missing_tag = wanted - tagged
                extra_in_tag = tagged - wanted

        in_album = self.sync.albums.member_ids(identity, species)

        if in_album is not None:
            extra_in_album = in_album - wanted

        # An album is only expected for identities at or above the threshold (issue #405); one
        # that is below it is left alone, so its absence is not drift.
        if wanted and len(wanted) >= self.sync.policy.album_minimum_assets:
            missing_from_album = wanted - (in_album or set())

        return IdentityDrift(
            species=species,
            identity=identity,
            expected=len(wanted),
            missing_tag=sorted(missing_tag),
            missing_from_album=sorted(missing_from_album),
            extra_in_tag=sorted(extra_in_tag),
            extra_in_album=sorted(extra_in_album),
        )

    def repair(self, *, prune: bool = True) -> RepairResult:
        """Bring Immich in line with state.db. Missing tags/album members are added; with
        `prune`, photos state.db no longer assigns to the identity are removed. Idempotent, and
        each identity is isolated so one failure doesn't stop the rest -- re-running picks up
        whatever failed. Afterwards SyncedAsset is rebuilt from what is now confirmed in
        Immich, so the next regular sync's stale-removal starts from the truth."""
        report = self.audit()
        expected = self.sync.expected_state().assets
        previous = self.sync.previously_synced_state()

        failed: set[tuple[str, str]] = {
            (f.species, f.identity) for f in report.failures
        }
        failures: list[AuditFailure] = list(report.failures)
        added_tags = added_albums = removed = 0

        for drift in report.drifts:
            key = (drift.species, drift.identity)
            errors: list[Exception] = []

            if drift.missing_tag and self.sync.tags is not None:
                try:
                    self.sync.tags.sync_identity(
                        drift.identity, drift.missing_tag, species=drift.species
                    )
                    added_tags += len(drift.missing_tag)
                except Exception as exc:
                    logger.exception(
                        "Tag repair failed for %s identity %r",
                        drift.species,
                        drift.identity,
                    )
                    errors.append(exc)

            if drift.missing_from_album:
                try:
                    self.sync.albums.sync_identity(
                        drift.identity,
                        drift.missing_from_album,
                        species=drift.species,
                    )
                    added_albums += len(drift.missing_from_album)
                except Exception as exc:
                    logger.exception(
                        "Album repair failed for %s identity %r",
                        drift.species,
                        drift.identity,
                    )
                    errors.append(exc)

            if prune and drift.extra_in_tag and self.sync.tags is not None:
                try:
                    self.sync.tags.remove_from_identity(
                        drift.identity, drift.extra_in_tag, species=drift.species
                    )
                    removed += len(drift.extra_in_tag)
                except Exception as exc:
                    logger.exception(
                        "Tag prune failed for %s identity %r",
                        drift.species,
                        drift.identity,
                    )
                    errors.append(exc)

            if prune and drift.extra_in_album:
                try:
                    self.sync.albums.remove_from_identity(
                        drift.identity, drift.extra_in_album, species=drift.species
                    )
                    removed += len(drift.extra_in_album)
                except Exception as exc:
                    logger.exception(
                        "Album prune failed for %s identity %r",
                        drift.species,
                        drift.identity,
                    )
                    errors.append(exc)

            if errors:
                failed.add(key)
                failures.append(
                    AuditFailure(
                        drift.species,
                        drift.identity,
                        "; ".join(str(exc) for exc in errors),
                        permission_error=any(
                            getattr(exc, "permission_denied", False) for exc in errors
                        ),
                    )
                )

        self.sync.save_synced_state(expected, previous, failed)

        return RepairResult(
            report=report,
            added_tags=added_tags,
            added_to_albums=added_albums,
            removed=removed,
            failures=failures,
        )
