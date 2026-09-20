from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from immich_dog_tagger.api.dependencies import get_config, get_session
from immich_dog_tagger.api.schemas import AccountResponse
from immich_dog_tagger.config import Config
from immich_dog_tagger.services.accounts import AccountService

router = APIRouter(
    prefix="/accounts",
)


@router.get(
    "",
    response_model=list[AccountResponse],
)
def list_accounts(
    session: Annotated[Session, Depends(get_session)],
    config: Annotated[Config, Depends(get_config)],
):
    """
    Every configured Immich account (issue #346) -- always exactly one
    ("default") for a legacy single-key deployment. Calls
    `sync_from_config()` itself (cheap: an upsert-by-name plus a
    WHERE-account_id-IS-NULL backfill, both no-ops once already applied)
    rather than assuming `api/app.py`'s startup call already ran, so this
    endpoint is self-sufficient in a context that skips the app lifespan
    (e.g. hitting it directly in a test). `Config` itself is cached for the
    process lifetime (`get_config()`), so a *newly edited* config file still
    needs a restart to be seen at all -- this only guarantees the DB stays
    in sync with whatever configuration this process already loaded.
    """

    accounts = AccountService(session).sync_from_config(config)
    return [AccountResponse.from_account(account) for account in accounts]
