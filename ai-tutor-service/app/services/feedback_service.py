"""Thumbs up/down on tutor answers (docs/PRODUCT.md §5.5 "Quality"), and what course authors see of it."""

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.core.time import utcnow
from app.domain.enums import MessageRole, Rating
from app.models.conversation import Conversation, Feedback, Message
from app.models.faq import FaqEntry
from app.services.outbox import write_event


class FeedbackService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def rate(self, *, user_id: int, message_public_id: int, rating: Rating, comment: str | None) -> tuple[Feedback, Message]:
        row = (
            await self.db.execute(
                select(Message, Conversation)
                .join(Conversation, Conversation.id == Message.conversation_id)
                .where(Message.public_id == message_public_id, Conversation.user_id == user_id, Conversation.deleted_at.is_(None), Message.role == MessageRole.ASSISTANT)
            )
        ).one_or_none()
        if row is None:
            raise NotFoundError("Message not found.", code="MESSAGE_NOT_FOUND")
        message, conversation = row
        feedback = (await self.db.execute(select(Feedback).where(Feedback.message_id == message.id, Feedback.user_id == user_id))).scalar_one_or_none()
        previous = feedback.rating if feedback else None
        if feedback is None:
            feedback = Feedback(message_id=message.id, user_id=user_id, course_id=conversation.course_id, rating=rating, comment=comment)
            self.db.add(feedback)
        else:
            feedback.rating, feedback.comment = rating, comment
        await self._helpful(message, previous, rating)
        await self.db.flush()
        write_event(
            self.db, event_type="tutor.feedback", aggregate_type="message", aggregate_id=message.id,
            payload={
                "message_id": str(message.public_id), "conversation_id": str(conversation.public_id), "student_user_id": str(user_id),
                "organization_id": str(conversation.organization_id) if conversation.organization_id else None,
                "course_id": str(conversation.course_id) if conversation.course_id else None, "rating": rating.value, "message_kind": message.kind,
                "occurred_at": utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
            },
        )
        await self.db.commit()
        return feedback, message

    async def _helpful(self, message: Message, previous: str | None, current: Rating) -> None:
        """A thumbs up on an answer that came from a FAQ entry is what ranks that entry for other students."""
        delta = (1 if current == Rating.UP else 0) - (1 if previous == Rating.UP else 0)
        if not delta:
            return
        for citation in message.citations or []:
            if citation.get("type") == "faq":
                entry = (await self.db.execute(select(FaqEntry).where(FaqEntry.public_id == int(citation["faq_id"])))).scalar_one_or_none()
                if entry is not None:
                    entry.helpful_count = max(entry.helpful_count + delta, 0)

    async def summary(self, course_id: int) -> dict[str, Any]:
        rows = (await self.db.execute(select(Feedback.rating, func.count()).where(Feedback.course_id == course_id).group_by(Feedback.rating))).all()
        counts = {rating: int(n) for rating, n in rows}
        up, down = counts.get(Rating.UP, 0), counts.get(Rating.DOWN, 0)
        return {"course_id": course_id, "up": up, "down": down, "down_rate": round(down / (up + down), 3) if up + down else None}

    async def downvoted(self, course_id: int, limit: int) -> list[dict[str, Any]]:
        """The questions and answers students marked unhelpful, without who asked: what an author reads to fix a lesson."""
        rows = (
            await self.db.execute(
                select(Feedback, Message)
                .join(Message, Message.id == Feedback.message_id)
                .where(Feedback.course_id == course_id, Feedback.rating == Rating.DOWN)
                .order_by(Feedback.created_at.desc())
                .limit(limit)
            )
        ).all()
        out = []
        for feedback, message in rows:
            question = (
                await self.db.execute(select(Message.content).where(Message.conversation_id == message.conversation_id, Message.seq == message.seq - 1))
            ).scalar_one_or_none()
            out.append({"message_id": str(message.public_id), "question": question, "answer": message.content, "kind": message.kind, "comment": feedback.comment, "at": feedback.created_at})
        return out
