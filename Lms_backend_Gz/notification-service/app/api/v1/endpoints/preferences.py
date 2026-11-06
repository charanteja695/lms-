from fastapi import APIRouter

from app.api.deps import CurrentAuth, DbSession, WriteRateLimit
from app.api.responses import errors
from app.schemas.preference import PreferenceOut, PreferencesResponse, PreferencesUpdate
from app.services.preference_service import PreferenceService

router = APIRouter(prefix="/notification-preferences", tags=["Preferences"])


@router.get("", response_model=PreferencesResponse, summary="Get my notification preferences", responses=errors(401, 429))
async def get_preferences(auth: CurrentAuth, db: DbSession) -> PreferencesResponse:
    views = await PreferenceService(db).list_for_user(auth.user_id)
    return PreferencesResponse(
        message="Preferences retrieved successfully.", preferences=[PreferenceOut.model_validate(view) for view in views]
    )


@router.put(
    "",
    response_model=PreferencesResponse,
    summary="Choose which categories are also emailed to me",
    responses=errors(401, 422, 429),
    dependencies=[WriteRateLimit],
)
async def update_preferences(data: PreferencesUpdate, auth: CurrentAuth, db: DbSession) -> PreferencesResponse:
    changes = {change.category: change.email_enabled for change in data.preferences}
    views = await PreferenceService(db).update(auth.user_id, changes)
    return PreferencesResponse(
        message="Preferences updated successfully.", preferences=[PreferenceOut.model_validate(view) for view in views]
    )
