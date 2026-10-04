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
from pathlib import Path

from sqlalchemy import select

from immich_dog_tagger.immich import (
    ImmichAssetNotFoundError,
    ImmichBulkWriteError,
    ImmichClient,
    ImmichGetAssetError,
)
from immich_dog_tagger.models import Asset
from immich_dog_tagger.scanner import mark_asset_removed
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
    # Photos Immich no longer has, retired in state.db during this repair.
    retired: int = 0


class SyncAuditService:
    def __init__(
        self,
        sync: SyncService,
        client: ImmichClient | None = None,
        cache_dir: Path | None = None,
    ):
        self.sync = sync
        # Used only to tell a photo Immich deleted from one it won't let this key write to,
        # when a bulk write reports `no_permission` for it.
        self.client = client
        self.cache_dir = cache_dir

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
        retired_ids: set[str] = set()
        checked_ids: set[str] = set()

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

            errors = self._without_retired(errors, retired_ids, checked_ids)

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

        if retired_ids:
            # Retired photos are no longer expected anywhere, so don't record them as synced.
            expected = self.sync.expected_state().assets

        self.sync.save_synced_state(expected, previous, failed)

        return RepairResult(
            report=report,
            added_tags=added_tags,
            added_to_albums=added_albums,
            removed=removed,
            failures=failures,
            retired=len(retired_ids),
        )

    def _without_retired(
        self,
        errors: list[Exception],
        retired_ids: set[str],
        checked_ids: set[str],
    ) -> list[Exception]:
        """Drop the bulk-write errors whose only rejections are photos Immich no longer has.

        Immich reports a deleted photo as `no_permission` in a bulk write. A photo that really
        is gone is retired in state.db (same as scan reconciliation and Repair, issue #370), so
        it stops counting as drift. Anything else -- a photo that still exists, a non-
        `no_permission` rejection, an HTTP-level failure -- stays a failure."""
        if self.client is None:
            return errors

        remaining: list[Exception] = []

        for exc in errors:
            if not isinstance(exc, ImmichBulkWriteError) or exc.http_error:
                remaining.append(exc)
                continue

            rejected = [item.get("id") for item in exc.failures]

            if not rejected or any(
                item.get("error") != "no_permission" for item in exc.failures
            ):
                remaining.append(exc)
                continue

            for immich_id in rejected:
                if immich_id not in checked_ids:
                    checked_ids.add(immich_id)

                    if self._retire_if_gone(immich_id):
                        retired_ids.add(immich_id)

            if any(immich_id not in retired_ids for immich_id in rejected):
                remaining.append(exc)

        return remaining

    def _retire_if_gone(self, immich_asset_id: str) -> bool:
        asset = self.sync.session.scalar(
            select(Asset).where(Asset.immich_asset_id == immich_asset_id)
        )

        if asset is None:
            return False

        try:
            self.client.get_asset(immich_asset_id)
        except ImmichAssetNotFoundError:
            mark_asset_removed(self.sync.session, asset, self.cache_dir)
            self.sync.session.commit()
            logger.info(
                "Sync repair retired asset id=%d immich_asset_id=%s: no longer in Immich",
                asset.id,
                immich_asset_id,
            )
            return True
        except ImmichGetAssetError:
            return False

        return False
