from lms_common.envelopes import RequestSchema, ResponseSchema, SuccessResponse
from pydantic import Field

from app.schemas.types import text

ReservationKey = text(100, min_length=1, examples=["enrolment-1755000000004123"])


class SeatReserveRequest(RequestSchema):
    reservation_key: ReservationKey = Field(description="Caller-supplied idempotency key, e.g. the enrolment id")  # type: ignore[valid-type]


class SeatReleaseRequest(RequestSchema):
    reservation_key: ReservationKey  # type: ignore[valid-type]


class SeatStatusOut(ResponseSchema):
    seats_total: int
    seats_used: int
    seats_available: int


class SeatStatusResponse(SuccessResponse):
    seats: SeatStatusOut
