"""Repository operations for payment records."""

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from ..database.models import Booking, Event, Payment


class PaymentRepository:
    def __init__(self, db: Session):
        self.db = db

    def add(self, payment: Payment) -> Payment:
        self.db.add(payment)
        return payment

    def get(self, payment_id: int) -> Payment | None:
        return self.db.scalar(
            select(Payment)
            .options(
                joinedload(Payment.booking).joinedload(Booking.student),
                joinedload(Payment.event).joinedload(Event.college),
            )
            .where(Payment.id == payment_id)
        )

    def get_pending(self, payment_id: int) -> Payment | None:
        return self.db.scalar(
            select(Payment)
            .options(
                joinedload(Payment.booking).joinedload(Booking.student),
                joinedload(Payment.event).joinedload(Event.college),
            )
            .where(Payment.id == payment_id)
        )

    def get_for_booking(self, booking_id: int) -> Payment | None:
        return self.db.scalar(select(Payment).where(Payment.booking_id == booking_id))

    def get_pending_for_booking(self, booking_id: int) -> Payment | None:
        return self.db.scalar(
            select(Payment)
            .where(Payment.booking_id == booking_id, Payment.payment_status == "Pending")
            .order_by(Payment.created_at.desc())
        )

    def list_for_student(self, student_id: int) -> list[Payment]:
        return list(
            self.db.scalars(
                select(Payment)
                .options(joinedload(Payment.event).joinedload(Event.college), joinedload(Payment.booking))
                .where(Payment.student_id == student_id)
                .order_by(Payment.created_at.desc())
            )
        )

    def list_for_event(self, event_id: int) -> list[Payment]:
        return list(
            self.db.scalars(
                select(Payment)
                .options(joinedload(Payment.student), joinedload(Payment.event).joinedload(Event.college))
                .where(Payment.event_id == event_id)
                .order_by(Payment.created_at.desc())
            )
        )
