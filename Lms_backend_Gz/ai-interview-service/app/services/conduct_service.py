"""Conducting an interview: one candidate answer in, one interviewer reply out; and the coding round's code runs.

A turn is two short transactions around one slow call. The candidate's answer is saved and the interview marked "awaiting a reply" (so a second answer
cannot interleave), the transaction is committed, the model is asked for a follow-up, and then the director — not the model — decides what is asked next
(app/conduct/director.py). If the model cannot answer, the interview does not stop: the next core question is asked and the turn is marked degraded.
"""

import base64
import json
from datetime import timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.codeexec import CodeExecutionClient
from app.clients.errors import Rejected, Unavailable
from app.clients.gateway import GatewayClient, GatewayError, SpeechUnavailable
from app.conduct import director
from app.core.config import Settings
from app.core.exceptions import ConflictError, UpstreamUnavailableError, ValidationFailedError
from app.core.time import utcnow
from app.domain.enums import InterviewStatus, RoundType, Speaker, TurnKind
from app.models.interview import Interview, InterviewTurn
from app.services.interview_service import InterviewService

STALE_REPLY_SECONDS = 90
_MAX_RESULT_CHARS = 2_000


def _parse_follow_up(text: str) -> str | None:
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        value = json.loads(text[start : end + 1]).get("follow_up")
    except (ValueError, AttributeError):
        return None
    return value.strip()[:600] if isinstance(value, str) and value.strip() else None


class ConductService:
    def __init__(self, db: AsyncSession, settings: Settings, gateway: GatewayClient | None, codeexec: CodeExecutionClient | None = None) -> None:
        self.db = db
        self.settings = settings
        self.gateway = gateway
        self.codeexec = codeexec
        self.interviews = InterviewService(db, settings)

    def _billing_org(self, interview: Interview) -> int:
        return interview.employer_org_id or interview.organization_id or self.settings.PLATFORM_ORGANIZATION_ID

    async def _reply_after(self, interview: Interview, seq: int) -> InterviewTurn | None:
        return (
            await self.db.execute(
                select(InterviewTurn).where(InterviewTurn.interview_id == interview.id, InterviewTurn.seq > seq, InterviewTurn.speaker == Speaker.INTERVIEWER).order_by(InterviewTurn.seq).limit(1)
            )
        ).scalar_one_or_none()

    async def _expired(self, interview: Interview) -> bool:
        """True (and the interview is ended) when the server's clock says the time is up."""
        if interview.ends_at and utcnow() > interview.ends_at + timedelta(seconds=self.settings.OVERRUN_GRACE_SECONDS):
            if interview.turn_count:
                self.interviews.add_turn(interview, speaker=Speaker.SYSTEM, kind=TurnKind.NOTE, text="The interview's time ran out.", round_key=self.interviews.current_round(interview)["key"])
            await self.interviews.complete(interview, "time_up")
            await self.db.commit()
            return True
        return False

    # ------------------------------------------------------------------ an answer
    async def answer(
        self, interview: Interview, *, text: str | None, audio: bytes | None, audio_type: str | None, key: str | None, want_audio: bool
    ) -> tuple[InterviewTurn, InterviewTurn | None, Interview, dict[str, Any]]:
        """Take the candidate's answer (typed, or audio transcribed by ai-gateway) and return ``(their turn, the interviewer's reply, the interview, extras)``."""
        via = "text"
        if audio is not None:
            if not self.settings.SPEECH_ENABLED or self.gateway is None:
                raise UpstreamUnavailableError("Speech is switched off: type your answer.", code="SPEECH_UNAVAILABLE")
            try:
                text = await self.gateway.transcribe(audio, content_type=audio_type or "audio/webm", organization_id=self._billing_org(interview), user_id=interview.user_id)
            except SpeechUnavailable as exc:
                raise UpstreamUnavailableError("Speech recognition is not available right now: type your answer instead.", code="SPEECH_UNAVAILABLE") from exc
            via = "audio"
        text = (text or "").strip()
        if not text:
            raise ValidationFailedError(details=[{"field": "text", "code": "REQUIRED", "message": "Say or type your answer"}])
        if len(text) > self.settings.MAX_TURN_CHARS:
            raise ValidationFailedError(details=[{"field": "text", "code": "TOO_LONG", "message": f"Keep an answer under {self.settings.MAX_TURN_CHARS} characters"}])

        interview = await self.interviews.locked(interview)
        if interview.status != InterviewStatus.IN_PROGRESS:
            raise ConflictError(f"This interview is {interview.status}.", code="INVALID_STATE")
        if key:
            previous = (await self.db.execute(select(InterviewTurn).where(InterviewTurn.interview_id == interview.id, InterviewTurn.idempotency_key == key))).scalar_one_or_none()
            if previous is not None:  # a retry of an answer already taken: return what was said, or finish the reply that was never made
                reply = await self._reply_after(interview, previous.seq)
                if reply is not None or self._awaiting(interview):
                    if reply is None:
                        raise ConflictError("Your last answer is still being handled.", code="TURN_IN_PROGRESS")
                    return previous, reply, interview, {"replayed": True}
                return await self._reply(interview, previous, want_audio)
        if await self._expired(interview):
            raise ConflictError("The interview's time is up.", code="INTERVIEW_ENDED")
        if self._awaiting(interview):
            raise ConflictError("Wait for the interviewer's reply before answering again.", code="TURN_IN_PROGRESS")
        if interview.turn_count >= self.settings.MAX_TURNS_PER_INTERVIEW:
            await self.interviews.complete(interview, "finished")
            await self.db.commit()
            raise ConflictError("This interview has reached its length limit.", code="INTERVIEW_ENDED")
        turn = self.interviews.add_turn(interview, speaker=Speaker.CANDIDATE, kind=TurnKind.ANSWER, text=text, round_key=self.interviews.current_round(interview)["key"], key=key, via=via)
        interview.awaiting_reply_since = utcnow()
        await self.db.commit()
        return await self._reply(interview, turn, want_audio)

    def _awaiting(self, interview: Interview) -> bool:
        since = interview.awaiting_reply_since
        return since is not None and (utcnow() - since).total_seconds() < STALE_REPLY_SECONDS

    async def _context(self, interview: Interview, answer: InterviewTurn) -> str:
        """What the model reads: the question that was asked, the answer, and (coding round) the latest code and its output."""
        turns = await self.interviews.turns(interview)
        question = next((t for t in reversed(turns) if t.speaker == Speaker.INTERVIEWER and t.seq < answer.seq), None)
        parts = [f"QUESTION:\n{question.text if question else ''}", f"ANSWER:\n{answer.text}"]
        code = next((t for t in reversed(turns) if t.kind == TurnKind.CODE and t.round_key == answer.round_key), None)
        if code is not None:
            result = next((t for t in turns if t.kind == TurnKind.CODE_RESULT and t.seq > code.seq), None)
            parts.append(f"CODE ({(code.meta or {}).get('language', '')}):\n{code.text}")
            if result is not None:
                parts.append(f"RUN OUTPUT:\n{result.text}")
        return "\n\n".join(parts)

    async def _propose(self, interview: Interview, answer: InterviewTurn) -> tuple[str | None, bool]:
        """The model's follow-up, or ``(None, degraded)`` when it has none (degraded: True when it could not be asked)."""
        if self.gateway is None:
            return None, True
        round_ = self.interviews.current_round(interview)
        round_left, _ = self.interviews.seconds_left(interview)
        content = await self._context(interview, answer)
        plan = interview.plan_snapshot
        billing = self._billing_org(interview)
        await self.db.commit()  # nothing is held open across the model call
        try:
            done = await self.gateway.complete(
                organization_id=billing, user_id=interview.user_id, prompt_key="interview.conduct",
                variables={"role": plan["role"][:120], "difficulty": plan["difficulty"], "round_type": round_["type"], "minutes_left": str(max(int(round_left // 60), 0))},
                messages=[{"role": "user", "content": content}],
            )
        except GatewayError:
            return None, True
        if done.status != "ok":
            return None, True
        return _parse_follow_up(done.content), False

    async def _reply(self, interview: Interview, answer: InterviewTurn, want_audio: bool) -> tuple[InterviewTurn, InterviewTurn | None, Interview, dict[str, Any]]:
        follow_up, degraded = await self._propose(interview, answer)
        interview = await self.interviews.locked(interview)
        if interview.status != InterviewStatus.IN_PROGRESS:  # ended (time up, or the candidate ended it) while the model thought
            return answer, None, interview, {"ended": True}
        if await self._expired(interview):
            return answer, None, interview, {"ended": True}
        round_left, total_left = self.interviews.seconds_left(interview)
        plan = interview.plan_snapshot
        step = director.next_step(
            plan, director.State(interview.round_index, interview.question_index, interview.follow_ups, round_left, total_left), proposed_follow_up=follow_up,
            max_follow_ups=self.settings.MAX_FOLLOW_UPS_PER_QUESTION,
        )
        interview.awaiting_reply_since = None
        reply: InterviewTurn | None = None
        if step.action == director.Action.WRAP_UP:
            reply = self.interviews.add_turn(interview, speaker=Speaker.INTERVIEWER, kind=TurnKind.NOTE, text=director.wrap_up_text(plan), round_key=plan["rounds"][-1]["key"] if step.reason == "finished" else self.interviews.current_round(interview)["key"])
            await self.interviews.complete(interview, "time_up" if step.reason == "time_up" else "finished")
        else:
            if step.action == director.Action.NEXT_ROUND:
                interview.round_index, interview.round_started_at, interview.question_index, interview.follow_ups = step.round_index, utcnow(), 0, 0
                new_round = plan["rounds"][step.round_index]
                self.interviews.add_turn(interview, speaker=Speaker.SYSTEM, kind=TurnKind.NOTE, text=f"Next round: {new_round['type'].replace('_', ' ')}.", round_key=new_round["key"])
            elif step.action == director.Action.NEXT_QUESTION:
                interview.question_index, interview.follow_ups = step.question_index, 0
            else:
                interview.follow_ups += 1
            kind = TurnKind.FOLLOW_UP if step.action == director.Action.FOLLOW_UP else TurnKind.QUESTION
            reply = self.interviews.add_turn(
                interview, speaker=Speaker.INTERVIEWER, kind=kind, text=step.text or "", round_key=plan["rounds"][interview.round_index]["key"], meta={"degraded": True} if degraded else {"reason": step.reason}
            )
        await self.db.commit()
        extras: dict[str, Any] = {"degraded": degraded, "finished": interview.status != InterviewStatus.IN_PROGRESS}
        if want_audio and reply is not None:
            extras.update(await self._speak(interview, reply.text))
        return answer, reply, interview, extras

    async def _speak(self, interview: Interview, text: str) -> dict[str, Any]:
        """The interviewer's line as audio, best effort: the text is always returned, so a missing voice never stops an interview."""
        if not self.settings.SPEECH_ENABLED or self.gateway is None:
            return {"audio": None, "audio_error": "SPEECH_DISABLED"}
        try:
            audio, content_type = await self.gateway.synthesize(text, organization_id=self._billing_org(interview), user_id=interview.user_id)
        except SpeechUnavailable:
            return {"audio": None, "audio_error": "SPEECH_UNAVAILABLE"}
        return {"audio": base64.b64encode(audio).decode(), "audio_type": content_type}

    # ------------------------------------------------------------------ the coding round
    async def run_code(self, interview: Interview, *, language: str, source: str, stdin: str) -> tuple[InterviewTurn, InterviewTurn, dict[str, Any]]:
        """Run the candidate's code with code-execution-service and put both the code and what it printed in the transcript, so the interviewer (and the
        evaluation) can see what was actually run."""
        if self.codeexec is None:
            raise UpstreamUnavailableError("The compiler is not available.", code="COMPILER_UNAVAILABLE")
        interview = await self.interviews.locked(interview)
        if interview.status != InterviewStatus.IN_PROGRESS:
            raise ConflictError(f"This interview is {interview.status}.", code="INVALID_STATE")
        if await self._expired(interview):
            raise ConflictError("The interview's time is up.", code="INTERVIEW_ENDED")
        round_ = self.interviews.current_round(interview)
        if round_["type"] != RoundType.CODING:
            raise ConflictError("The compiler opens in the coding round.", code="NOT_CODING_ROUND")
        language = language.strip().lower()
        if language not in round_["languages"]:
            raise ValidationFailedError(details=[{"field": "language", "code": "LANGUAGE_NOT_ALLOWED", "message": f"This round allows: {', '.join(round_['languages'])}"}])
        if len(source) > self.settings.MAX_CODE_CHARS:
            raise ValidationFailedError(details=[{"field": "source", "code": "TOO_LONG", "message": f"Keep the code under {self.settings.MAX_CODE_CHARS} characters"}])
        if interview.code_runs >= self.settings.CODE_RUN_LIMIT_PER_INTERVIEW:
            raise ConflictError("You have used all your runs for this interview.", code="RUN_LIMIT")
        interview.code_runs += 1
        code_turn = self.interviews.add_turn(interview, speaker=Speaker.CANDIDATE, kind=TurnKind.CODE, text=source, round_key=round_["key"], meta={"language": language})
        user_id, org, key = interview.user_id, interview.organization_id, round_["key"]
        await self.db.commit()  # nothing is held open while the code runs
        try:
            result = await self.codeexec.run(user_id=user_id, organization_id=org, language=language, source=source, stdin=stdin, wait_seconds=self.settings.CODE_RUN_WAIT_SECONDS)
        except (Unavailable, Rejected) as exc:
            interview = await self.interviews.locked(interview)
            self.interviews.add_turn(interview, speaker=Speaker.SYSTEM, kind=TurnKind.CODE_RESULT, text="The compiler was not available: the code was not run.", round_key=key, meta={"outcome": "unavailable"})
            await self.db.commit()
            raise UpstreamUnavailableError("The compiler is not available right now: your code was saved but not run.", code="COMPILER_UNAVAILABLE") from exc
        shown = "\n".join(part for part in (f"outcome: {result.outcome or result.status}", f"stdout:\n{result.stdout}" if result.stdout else "", f"stderr:\n{result.stderr}" if result.stderr else "", result.compile_output) if part)[:_MAX_RESULT_CHARS]
        interview = await self.interviews.locked(interview)
        result_turn = self.interviews.add_turn(
            interview, speaker=Speaker.SYSTEM, kind=TurnKind.CODE_RESULT, text=shown, round_key=key, meta={"run_id": str(result.run_id), "outcome": result.outcome or result.status, "time_ms": result.time_ms}
        )
        await self.db.commit()
        return code_turn, result_turn, {"run_id": str(result.run_id), "status": result.status, "outcome": result.outcome, "stdout": result.stdout, "stderr": result.stderr, "compile_output": result.compile_output, "time_ms": result.time_ms}

