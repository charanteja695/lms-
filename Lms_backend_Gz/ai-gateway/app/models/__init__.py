"""Import every model here so Base.metadata (and Alembic) sees all tables."""

from app.db.base import Base
from app.models.call_log import AiCallLog
from app.models.model_route import ModelRoute
from app.models.outbox_event import OutboxEvent
from app.models.processed_event import ProcessedEvent
from app.models.prompt import Prompt, PromptVersion
from app.models.quota import OrgQuota, OrgUsage
from app.models.refs import OrgStatusRef

__all__ = [
    "AiCallLog",
    "Base",
    "ModelRoute",
    "OrgQuota",
    "OrgStatusRef",
    "OrgUsage",
    "OutboxEvent",
    "ProcessedEvent",
    "Prompt",
    "PromptVersion",
]
