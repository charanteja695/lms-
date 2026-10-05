from lms_common.envelopes import ResponseSchema, SuccessResponse

from app.schemas.types import PublicIdOut, Timestamp


class ItemProgressOut(ResponseSchema):
    topic_item_id: PublicIdOut
    completed_at: Timestamp


class ItemUnlockOut(ResponseSchema):
    topic_item_id: PublicIdOut
    title: str
    item_type: str
    position: int
    required: bool
    completed: bool


class TopicUnlockOut(ResponseSchema):
    topic_id: PublicIdOut
    title: str
    position: int
    unlocked: bool
    completed: bool
    completed_items: int
    required_items: int
    test_required: bool = False
    test_passed: bool = False
    items: list[ItemUnlockOut]


class ModuleUnlockOut(ResponseSchema):
    module_id: PublicIdOut
    title: str
    position: int
    unlocked: bool
    completed: bool
    test_required: bool = False
    test_passed: bool = False
    topics: list[TopicUnlockOut]


class UnlockStateOut(ResponseSchema):
    modules: list[ModuleUnlockOut]
    eligible_for_final: bool


class UnlockStateResponse(SuccessResponse):
    unlock_state: UnlockStateOut


class ItemProgressResponse(SuccessResponse):
    item_progress: ItemProgressOut
