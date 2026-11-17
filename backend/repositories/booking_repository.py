"""Repository operations for bookings and capacity-safe reservations."""

from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.orm import Session, joinedload

from ..database.models import Booking, Event


class BookingRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_for_student_event(self, student_id: int, event_id: int) -> Booking | None:
        return self.db.scalar(select(Booking).where(Booking.student_id == student_id, Booking.event_id == event_id))

    def get_for_student_event_with_event(self, student_id: int, event_id: int) -> Booking | None:
        return self.db.scalar(
            select(Booking)
            .options(joinedload(Booking.event).joinedload(Event.college))
            .where(Booking.student_id == student_id, Booking.event_id == event_id)
        )

    def reserve_seat(self, event_id: int) -> bool:
        result = self.db.execute(
            update(Event)
            .where(Event.id == event_id, ~Event.is_deleted, Event.available_seats > 0)
            .values(available_seats=Event.available_seats - 1)
        )
        return result.rowcount == 1

    def add(self, booking: Booking) -> Booking:
        self.db.add(booking)
        return booking

    def release_expired(self, now: datetime) -> list[Booking]:
        bookings = list(
            self.db.scalars(
                select(Booking)
                .where(Booking.booking_status == "pending_payment", Booking.reservation_expires_at <= now)
            )
        )
        for booking in bookings:
            self.db.execute(
                update(Event).where(Event.id == booking.event_id).values(available_seats=Event.available_seats + 1)
            )
            booking.booking_status = "expired"
            booking.reservation_expires_at = None
        return bookings

    def get_with_event(self, booking_id: int) -> Booking | None:
        return self.db.scalar(
            select(Booking)
            .options(joinedload(Booking.event).joinedload(Event.college))
            .where(Booking.id == booking_id)
        )

    def list_for_student(self, student_id: int) -> list[Booking]:
        return list(
            self.db.scalars(
                select(Booking)
                .options(joinedload(Booking.event).joinedload(Event.college))
                .where(Booking.student_id == student_id)
                .order_by(Booking.booked_at.desc())
            )
        )

    def list_for_event(self, event_id: int, offset: int, limit: int) -> list[Booking]:
        return list(
            self.db.scalars(
                select(Booking)
                .options(joinedload(Booking.student), joinedload(Booking.event).joinedload(Event.college))
                .where(Booking.event_id == event_id)
                .order_by(Booking.booked_at.desc())
                .offset(offset)
                .limit(limit)
            )
        )
