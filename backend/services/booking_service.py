"""Booking rules, including duplicate and capacity-safe reservations."""

from uuid import uuid4

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..database.models import Admin, Booking, Student
from ..repositories.booking_repository import BookingRepository
from ..repositories.event_repository import EventRepository
from .exceptions import ConflictError, ValidationError


class BookingService:
    def __init__(self, db: Session):
        self.db = db
        self.bookings = BookingRepository(db)
        self.events = EventRepository(db)

    def book(self, student: Student, event_id: int) -> Booking:
        event = self.events.get_public(event_id)
        if event is None:
            raise ConflictError("Event not found or registration is closed.")
        if event.registration_fee > 0:
            raise ValidationError("Payment is required before booking this event.")
        if self.bookings.get_for_student_event(student.id, event_id):
            raise ConflictError("You have already booked this event.")
        if not self.bookings.reserve_seat(event_id):
            self.db.rollback()
            raise ConflictError("This event has no available seats.")
        booking = Booking(
            booking_reference=f"CE-{uuid4().hex[:12].upper()}",
            student_id=student.id,
            event_id=event_id,
        )
        self.bookings.add(booking)
        try:
            self.db.commit()
        except IntegrityError as error:
            self.db.rollback()
            raise ConflictError("You have already booked this event.") from error
        result = self.bookings.get_with_event(booking.id)
        if result is None:
            raise RuntimeError("Booking was committed but could not be reloaded.")
        return result

    def list_for_student(self, student: Student) -> list[Booking]:
        return self.bookings.list_for_student(student.id)

    def participants(self, admin: Admin, event_id: int, offset: int, limit: int) -> tuple[object, list[Booking]]:
        event = self.events.get_owned(event_id, admin.college_id)
        if event is None:
            from .exceptions import NotFoundError
            raise NotFoundError("Event not found in your college.")
        return event, self.bookings.list_for_event(event.id, offset, limit)
