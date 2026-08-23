from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from immich_dog_tagger.api.dependencies import get_insights_service
from immich_dog_tagger.api.schemas import (
    InsightCardResponse,
    InsightsSummaryResponse,
    PersonCountResponse,
    PlaceCountResponse,
    TimelineEntryResponse,
    TopPhotoResponse,
)
from immich_dog_tagger.services.insights import IdentityNotFoundError, InsightsService

router = APIRouter(
    prefix="/dogs/{identity_id}/insights",
)


@router.get(
    "/summary",
    response_model=InsightsSummaryResponse,
)
def get_summary(
    identity_id: int,
    service: Annotated[InsightsService, Depends(get_insights_service)],
):
    try:
        return InsightsSummaryResponse.from_summary(service.summary(identity_id))
    except IdentityNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get(
    "/timeline",
    response_model=list[TimelineEntryResponse],
)
def get_timeline(
    identity_id: int,
    service: Annotated[InsightsService, Depends(get_insights_service)],
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    try:
        entries = service.timeline(identity_id, limit=limit, offset=offset)
    except IdentityNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return [TimelineEntryResponse.from_timeline_entry(entry) for entry in entries]


@router.get(
    "/top-photos",
    response_model=list[TopPhotoResponse],
)
def get_top_photos(
    identity_id: int,
    service: Annotated[InsightsService, Depends(get_insights_service)],
    limit: int = Query(10, ge=1, le=10),
):
    try:
        photos = service.top_photos(identity_id, limit=limit)
    except IdentityNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return [TopPhotoResponse.from_top_photo(photo) for photo in photos]


@router.get(
    "/places",
    response_model=list[PlaceCountResponse],
)
def get_places(
    identity_id: int,
    service: Annotated[InsightsService, Depends(get_insights_service)],
):
    try:
        places = service.places(identity_id)
    except IdentityNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return [PlaceCountResponse.from_place_count(place) for place in places]


@router.get(
    "/people",
    response_model=list[PersonCountResponse],
)
def get_people(
    identity_id: int,
    service: Annotated[InsightsService, Depends(get_insights_service)],
):
    try:
        people = service.people(identity_id)
    except IdentityNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return [PersonCountResponse.from_person_count(person) for person in people]


@router.get(
    "/cards",
    response_model=list[InsightCardResponse],
)
def get_cards(
    identity_id: int,
    service: Annotated[InsightsService, Depends(get_insights_service)],
):
    try:
        cards = service.cards(identity_id)
    except IdentityNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return [InsightCardResponse.from_card(card) for card in cards]
