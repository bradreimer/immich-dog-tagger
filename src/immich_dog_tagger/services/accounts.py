"""
Configured Immich accounts (issue #346).

`Config.accounts` (issue #348) is the source of truth for *which* accounts
exist and their credentials; this module keeps a lightweight, credential-free
`ImmichAccount` row per account in `state.db` so `Asset`/`SyncedAsset`/
`PipelineJob`/`PipelineSchedule` can carry a stable `account_id` foreign key,
and resolves that row back to a real `ImmichClient` at the point of use.
"""

import logging
from dataclasses import dataclass

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from immich_dog_tagger.config import Config
from immich_dog_tagger.immich import ImmichClient
from immich_dog_tagger.models import Asset, ImmichAccount

logger = logging.getLogger(__name__)

# The name config.py's legacy env-var path always synthesizes for a
# deployment with no CONFIG_FILE (see config.py's _immich_settings_from_env).
# Used here as the backfill target for every Asset row scanned before this
# feature existed -- every one of them was necessarily scanned under that
# single implicit account, whatever config shape the deployment uses today.
DEFAULT_ACCOUNT_NAME = "default"


class AccountResolutionError(Exception):
    """Raised when an account_id/name cannot be resolved to a usable account."""


class AccountService:
    def __init__(self, session: Session):
        self.session = session

    def sync_from_config(self, config: Config) -> list[ImmichAccount]:
        """
        Upsert an `ImmichAccount` row by exact name match for every account
        `Config.accounts` currently declares, plus one always named
        `DEFAULT_ACCOUNT_NAME` (creating it if it doesn't already exist as
        one of the configured accounts) so pre-existing `Asset` rows from
        before this feature existed have somewhere to backfill onto.

        Never deletes a row whose name has disappeared from `Config.accounts`
        (a rename or removal) -- it is left in place, orphaned, per
        docs/specs/multi-immich-account-sync.md's open question on that
        topic. Safe to call on every startup: existing rows are left alone,
        and the backfill only ever touches rows that still have no account.
        """

        existing_by_name = {
            account.name: account
            for account in self.session.scalars(select(ImmichAccount)).all()
        }

        configured_names = {account.name for account in config.accounts} | {
            DEFAULT_ACCOUNT_NAME
        }

        for name in configured_names:
            if name not in existing_by_name:
                account = ImmichAccount(name=name)
                self.session.add(account)
                self.session.flush()
                existing_by_name[name] = account
                logger.info("Registered Immich account %r", name)

        self.session.commit()

        default_account = existing_by_name[DEFAULT_ACCOUNT_NAME]
        self._backfill_legacy_assets(default_account)

        return list(existing_by_name.values())

    def _backfill_legacy_assets(self, default_account: ImmichAccount) -> None:
        result = self.session.execute(
            update(Asset)
            .where(Asset.account_id.is_(None))
            .values(account_id=default_account.id)
        )
        self.session.commit()

        if result.rowcount:
            logger.info(
                "Backfilled %d pre-existing asset(s) onto the %r account",
                result.rowcount,
                default_account.name,
            )

    def list_accounts(self) -> list[ImmichAccount]:
        return list(
            self.session.scalars(select(ImmichAccount).order_by(ImmichAccount.id)).all()
        )

    def get(self, account_id: int) -> ImmichAccount | None:
        return self.session.get(ImmichAccount, account_id)

    def get_by_name(self, name: str) -> ImmichAccount | None:
        return self.session.scalar(
            select(ImmichAccount).where(ImmichAccount.name == name)
        )


@dataclass(frozen=True)
class ResolvedAccount:
    """
    An account to run an Immich-touching operation against: the API key to
    use, plus its `ImmichAccount` DB row id to tag new `Asset` rows with --
    `None` when no such row exists yet (see `resolve_account`'s fallback
    path), which callers already treat as "unscoped", the exact pre-#346
    behavior.
    """

    id: int | None
    name: str
    api_key: str


def resolve_account(
    session: Session,
    config: Config,
    account_id: int | None,
) -> ResolvedAccount:
    """
    Resolve an account_id (from a PipelineJob/PipelineSchedule, or a CLI/API
    request) to a usable account -- its DB id/name plus the API key
    `Config` has for it right now.

    `account_id=None` resolves to the *default* account: the first entry in
    `Config.accounts` when any are configured, or -- when `Config.accounts`
    is empty -- a synthetic account built directly from
    `Config.immich_api_key`. That fallback matters beyond legacy env-var
    deployments: it's also what makes this function work against a `Config`
    built directly (`Config(immich_api_key=..., ...)`, `accounts` left at
    its empty-tuple default) rather than through `load_config()` -- the
    common pattern throughout this project's tests -- without every one of
    them needing to learn about `accounts`.

    Callers that mean "every configured account" (the CLI's `scan`/`sync`/
    `pipeline` with no `--account`) loop over
    `AccountService.list_accounts()`/`Config.accounts` themselves and call
    this once per account instead of relying on this fallback.

    Raises `AccountResolutionError` only when an *explicit* account_id names
    a row that no longer matches anything in `Config.accounts` (renamed or
    removed there -- see the multi-account spec's open question on this).
    The default (`account_id=None`) path never raises, even when nothing is
    configured at all -- it resolves to an empty API key instead, the exact
    pre-#346 behavior of building a client from `Config.immich_api_key`
    unconditionally and letting a genuinely missing credential fail where
    it's actually used (a real Immich call), not preemptively here. Several
    existing tests deliberately run a pipeline stage against a faked-out
    Immich client with no credentials configured at all; raising here would
    break that pattern for no benefit, since nothing downstream would have
    made a real network call anyway.
    """

    if account_id is not None:
        db_account = AccountService(session).get(account_id)

        if db_account is None:
            raise AccountResolutionError(f"No account with id={account_id}")

        configured = {a.name: a for a in config.accounts}.get(db_account.name)

        if configured is None:
            raise AccountResolutionError(
                f"Account {db_account.name!r} is not present in the current "
                "configuration (it may have been renamed or removed)"
            )

        return ResolvedAccount(
            id=db_account.id,
            name=configured.name,
            api_key=configured.api_key,
        )

    if config.accounts:
        default_name = config.accounts[0].name
        default_api_key = config.accounts[0].api_key
    else:
        # Empty even when config.immich_api_key is also empty -- that's the
        # pre-#346 status quo (an unconfigured deployment building a client
        # with an empty key, which only fails once something actually tries
        # to use it), not a new error condition this function should
        # introduce.
        default_name = DEFAULT_ACCOUNT_NAME
        default_api_key = config.immich_api_key

    db_account = AccountService(session).get_by_name(default_name)

    return ResolvedAccount(
        id=db_account.id if db_account is not None else None,
        name=default_name,
        api_key=default_api_key,
    )


def build_immich_client(config: Config, account: ResolvedAccount) -> ImmichClient:
    return ImmichClient(
        config.immich_url,
        account.api_key,
        timeout=config.immich_timeout_seconds,
    )
