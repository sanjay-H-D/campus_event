"""Business rules for the local simulated payment workflow."""

import secrets
from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy import update
from sqlalchemy.orm import Session

from ..database.models import Booking, Event, Payment, Student
from ..repositories.booking_repository import BookingRepository
from ..repositories.event_repository import EventRepository
from ..repositories.payment_repository import PaymentRepository
from .exceptions import ConflictError, NotFoundError, ValidationError

RESERVATION_MINUTES = 15


class PaymentService:
    def __init__(self, db: Session):
        self.db = db
        self.bookings = BookingRepository(db)
        self.events = EventRepository(db)
        self.payments = PaymentRepository(db)

    def _release_expired(self) -> None:
        expired = self.bookings.release_expired(datetime.utcnow())
        for booking in expired:
            payment = self.payments.get_pending_for_booking(booking.id)
            if payment is not None:
                payment.payment_status = "Failed"

    def release_expired(self) -> None:
        self._release_expired()
        self.db.commit()

    def create_demo_payment(self, student: Student, event_id: int) -> tuple[Payment, Event]:
        self._release_expired()
        event = self.events.get_public(event_id)
        if event is None:
            raise NotFoundError("Event not found or registration is closed.")
        if event.registration_fee <= 0:
            raise ValidationError("This event is free. Use the standard booking option.")

        existing = self.bookings.get_for_student_event_with_event(student.id, event_id)
        if existing is not None:
            if existing.booking_status == "confirmed":
                raise ConflictError("You have already booked this event.")
            if existing.booking_status == "pending_payment":
                payment = self.payments.get_pending_for_booking(existing.id)
                if payment is not None:
                    self.db.commit()
                    return payment, event

        if not self.bookings.reserve_seat(event.id):
            self.db.rollback()
            raise ConflictError("This event has no available seats.")

        if existing is None:
            booking = Booking(
                booking_reference=f"CE-{secrets.token_hex(6).upper()}",
                student_id=student.id,
                event_id=event.id,
            )
            self.bookings.add(booking)
        else:
            booking = existing
        booking.booking_status = "pending_payment"
        booking.reservation_expires_at = datetime.utcnow() + timedelta(minutes=RESERVATION_MINUTES)

        payment = Payment(
            booking=booking,
            student_id=student.id,
            event_id=event.id,
            amount=float(Decimal(str(event.registration_fee)).quantize(Decimal("0.01"))),
            currency="INR",
            payment_reference=f"DEMO-{secrets.token_hex(8).upper()}",
            payment_method="Demo Payment",
            payment_status="Pending",
        )
        self.payments.add(payment)
        self.db.commit()
        self.db.refresh(payment)
        return payment, event

    def simulate(self, student: Student, payment_id: int, outcome: str) -> Payment:
        self._release_expired()
        payment = self.payments.get(payment_id)
        if payment is None or payment.student_id != student.id:
            raise NotFoundError("Payment not found.")
        if payment.payment_status == "Successful":
            if outcome == "successful":
                return payment
            raise ConflictError("A successful payment cannot be failed.")
        if payment.payment_status != "Pending":
            raise ConflictError("This payment attempt is no longer active. Start a new payment.")

        if outcome == "failed":
            self._fail_and_release(payment)
            self.db.commit()
            self.db.refresh(payment)
            return payment

        booking = payment.booking
        if booking.booking_status != "pending_payment" or (
            booking.reservation_expires_at is not None and booking.reservation_expires_at <= datetime.utcnow()
        ):
            self._fail_and_release(payment)
            self.db.commit()
            raise ConflictError("The payment reservation has expired. Please start again.")
        payment.payment_status = "Successful"
        payment.transaction_date = datetime.utcnow()
        booking.booking_status = "confirmed"
        booking.reservation_expires_at = None
        self.db.commit()
        self.db.refresh(payment)
        return payment

    def _fail_and_release(self, payment: Payment) -> None:
        booking = payment.booking
        if booking.booking_status == "pending_payment":
            self.db.execute(
                update(Event).where(Event.id == booking.event_id).values(available_seats=Event.available_seats + 1)
            )
            booking.booking_status = "payment_failed"
            booking.reservation_expires_at = None
        payment.payment_status = "Failed"

    def list_for_student(self, student: Student) -> list[Payment]:
        self._release_expired()
        self.db.commit()
        return self.payments.list_for_student(student.id)

    def get_owned_payment(self, student: Student, payment_id: int) -> Payment:
        self._release_expired()
        self.db.commit()
        payment = self.payments.get(payment_id)
        if payment is None or payment.student_id != student.id:
            raise NotFoundError("Payment not found.")
        return payment

    def list_for_admin_event(self, admin_college_id: int, event_id: int) -> tuple[Event, list[Payment]]:
        event = self.events.get_owned(event_id, admin_college_id)
        if event is None:
            raise NotFoundError("Event not found in your college.")
        self._release_expired()
        self.db.commit()
        return event, self.payments.list_for_event(event_id)
