"""The skill profile: a student's own page, plus read access for their institution's staff and careers managers."""

from typing import Any

from fastapi import APIRouter, UploadFile

from app.api.deps import (
    AiRateLimit,
    CurrentAuth,
    DbSession,
    GatewayDep,
    ItemIdParam,
    RequireStudent,
    SettingsDep,
    UserIdParam,
    WriteRateLimit,
)
from app.api.responses import AUTHENTICATED, errors
from app.core.exceptions import NotFoundError, PayloadTooLargeError, PermissionDeniedError
from app.domain.enums import ItemKind
from app.importing.extract import extract_text
from app.importing.summary import item_label
from app.models.profile import Profile
from app.permissions.policy import can_view_student_profile
from app.schemas.resume import (
    BulkItemsCreate,
    ImportedItem,
    ImportedProfile,
    ImportResponse,
    ItemCreate,
    ItemOut,
    ItemReorder,
    ItemResponse,
    ItemsResponse,
    ItemUpdate,
    PersonalOut,
    ProfileOut,
    ProfileResponse,
    ProfileUpdate,
)
from app.services.ai_service import AiService
from app.services.profile_service import ItemView, ProfileService

router = APIRouter(prefix="/profile", tags=["Skill profile"])
students = APIRouter(prefix="/students", tags=["Skill profile (staff)"])


def present_item(view: ItemView) -> ItemOut:
    item = view.item
    return ItemOut(
        item_id=item.public_id, kind=item.kind, verified=item.verified, label=view.label, source=item.source, active=item.active, data=view.data,
        derived=view.derived, position=item.position, inactive_reason=item.inactive_reason,
    )


async def _profile_response(service: ProfileService, user_id: int, profile: Profile | None, *, message: str = "") -> ProfileResponse:
    ref = await service.user_ref(user_id)
    views = await service.views(user_id, include_inactive=True)
    name = " ".join(x for x in ((ref.first_name if ref else ""), (ref.last_name if ref else "")) if x) or "Student"
    fields: dict[str, Any] = {"headline": None, "summary": None, "phone": None, "location": None, "links": [], "target_roles": [], "revision": 0}
    if profile is not None:
        fields = {
            "headline": profile.headline, "summary": profile.summary, "phone": profile.phone, "location": profile.location, "links": list(profile.links or []),
            "target_roles": list(profile.target_roles or []), "revision": profile.revision,
        }
    return ProfileResponse(
        message=message, profile=ProfileOut.model_validate(fields), personal=PersonalOut(name=name, email=ref.email if ref else None), items=[present_item(v) for v in views]
    )


@router.get(
    "", response_model=ProfileResponse, summary="My skill profile",
    description="Personal details from user-management (verified), my own entries (self-declared) and the items the platform added — certificates, completed "
    "courses, assessment scores (verified, read-only). A revoked certificate stays listed with `active: false` and the reason, but never reaches a resume.",
    responses=errors(*AUTHENTICATED),
)
async def my_profile(auth: RequireStudent, db: DbSession, settings: SettingsDep) -> ProfileResponse:
    service = ProfileService(db, settings)
    return await _profile_response(service, auth.user_id, await service.get(auth.user_id))


@router.patch("", response_model=ProfileResponse, summary="Update headline, summary, contact details, links, target roles", responses=errors(*AUTHENTICATED), dependencies=[WriteRateLimit])
async def update_profile(body: ProfileUpdate, auth: RequireStudent, db: DbSession, settings: SettingsDep) -> ProfileResponse:
    service = ProfileService(db, settings)
    fields = body.model_dump(exclude_unset=True, mode="json")
    profile = await service.update_profile(auth.user_id, auth.organization_id, fields=fields)
    return await _profile_response(service, auth.user_id, profile, message="Profile updated.")


@router.post(
    "/items", response_model=ItemResponse, status_code=201, summary="Add an education, experience, project, skill or achievement",
    description="`data` depends on `kind` (see docs/API.md). Certificates, courses and assessment scores cannot be added by hand (`403 VERIFIED_KIND`).",
    responses=errors(*AUTHENTICATED, 409), dependencies=[WriteRateLimit],
)
async def add_item(body: ItemCreate, auth: RequireStudent, db: DbSession, settings: SettingsDep) -> ItemResponse:
    service = ProfileService(db, settings)
    item = await service.add_item(auth.user_id, auth.organization_id, body.kind, body.data)
    return ItemResponse(message="Added.", item=present_item(ItemView(item=item, data=dict(item.data))))


@router.post(
    "/import", response_model=ImportResponse, summary="Read an old resume or LinkedIn PDF into proposed entries",
    description="Upload a PDF, Word (.docx) or text file. The AI reads it into profile entries; each is checked (valid fields, no fact the file does not "
    "contain) and **nothing is saved** — send the ones the student keeps to `POST /profile/items/bulk`. The file itself is not stored.",
    responses=errors(*AUTHENTICATED, 413, 422, 503), dependencies=[AiRateLimit],
)
async def import_resume(file: UploadFile, auth: RequireStudent, db: DbSession, settings: SettingsDep, gateway: GatewayDep) -> ImportResponse:
    content = await file.read(settings.MAX_IMPORT_BYTES + 1)
    if len(content) > settings.MAX_IMPORT_BYTES:
        raise PayloadTooLargeError(f"The file is larger than {settings.MAX_IMPORT_BYTES // (1024 * 1024)} MB.", code="FILE_TOO_LARGE")
    text = extract_text(content)[: settings.MAX_IMPORT_TEXT_CHARS]
    await db.commit()  # no transaction is held open across the model call
    fields, items, skipped = await AiService(settings, gateway).read_resume(organization_id=auth.organization_id, user_id=auth.user_id, text=text)
    proposed = [ImportedItem(kind=i["kind"], data=i["data"], label=item_label(ItemKind(i["kind"]), i["data"])) for i in items]
    message = f"Found {len(proposed)} entries. Choose the ones to add." if proposed else "No entries could be read from this file."
    return ImportResponse(message=message, profile=ImportedProfile(**fields), items=proposed, skipped=skipped)


@router.post(
    "/items/bulk", response_model=ItemsResponse, status_code=201, summary="Add several entries at once (after an import)",
    description="All entries are validated first; either every one is added or none is.", responses=errors(*AUTHENTICATED, 409, 422), dependencies=[WriteRateLimit],
)
async def add_items(body: BulkItemsCreate, auth: RequireStudent, db: DbSession, settings: SettingsDep) -> ItemsResponse:
    service = ProfileService(db, settings)
    items = await service.add_items(auth.user_id, auth.organization_id, [(i.kind, i.data) for i in body.items])
    return ItemsResponse(message=f"Added {len(items)} entries.", items=[present_item(ItemView(item=i, data=dict(i.data))) for i in items])


@router.put("/items/order", response_model=ItemsResponse, summary="Reorder one kind of item", responses=errors(*AUTHENTICATED, 409), dependencies=[WriteRateLimit])
async def reorder(body: ItemReorder, auth: RequireStudent, db: DbSession, settings: SettingsDep) -> ItemsResponse:
    service = ProfileService(db, settings)
    await service.reorder(auth.user_id, body.kind, body.item_ids)
    return ItemsResponse(message="Reordered.", items=[present_item(v) for v in await service.views(auth.user_id, kinds=(body.kind,))])


@router.patch("/items/{item_id}", response_model=ItemResponse, summary="Edit one of my own entries", responses=errors(*AUTHENTICATED, 404), dependencies=[WriteRateLimit])
async def update_item(item_id: ItemIdParam, body: ItemUpdate, auth: RequireStudent, db: DbSession, settings: SettingsDep) -> ItemResponse:
    service = ProfileService(db, settings)
    item = await service.update_item(await service.get_item(auth.user_id, item_id), body.data)
    return ItemResponse(message="Saved.", item=present_item(ItemView(item=item, data=dict(item.data))))


@router.delete("/items/{item_id}", response_model=ItemsResponse, summary="Delete one of my own entries", responses=errors(*AUTHENTICATED, 404), dependencies=[WriteRateLimit])
async def delete_item(item_id: ItemIdParam, auth: RequireStudent, db: DbSession, settings: SettingsDep) -> ItemsResponse:
    service = ProfileService(db, settings)
    await service.delete_item(await service.get_item(auth.user_id, item_id))
    return ItemsResponse(message="Deleted.", items=[])


@students.get(
    "/{user_id}/profile", response_model=ProfileResponse, summary="A student's profile (institution staff for their own institution, careers managers)",
    description="Verified items and the student's self-declared entries, labelled. Read only.", responses=errors(*AUTHENTICATED, 404),
)
async def student_profile(user_id: UserIdParam, auth: CurrentAuth, db: DbSession, settings: SettingsDep) -> ProfileResponse:
    service = ProfileService(db, settings)
    ref = await service.user_ref(user_id)
    profile = await service.get(user_id)
    if ref is None and profile is None:
        raise NotFoundError("Student not found.", code="STUDENT_NOT_FOUND")
    organization_id = ref.organization_id if ref else profile.organization_id if profile else None
    if not can_view_student_profile(auth, student_user_id=user_id, student_organization_id=organization_id):
        raise PermissionDeniedError()
    return await _profile_response(service, user_id, profile)
