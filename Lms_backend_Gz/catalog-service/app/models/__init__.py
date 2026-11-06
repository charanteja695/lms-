"""Import every model here so Base.metadata (and Alembic) sees all tables."""

from app.db.base import Base
from app.models.course import Course
from app.models.course_rule import CourseRule
from app.models.course_version import CourseVersion
from app.models.learning_path import LearningPath
from app.models.learning_path_item import LearningPathItem
from app.models.module import Module
from app.models.outbox_event import OutboxEvent
from app.models.review import CourseReview
from app.models.topic import Topic
from app.models.topic_item import TopicItem

__all__ = [
    "Base",
    "Course",
    "CourseRule",
    "CourseReview",
    "CourseVersion",
    "LearningPath",
    "LearningPathItem",
    "Module",
    "OutboxEvent",
    "Topic",
    "TopicItem",
]
