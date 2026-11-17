"""SQLAlchemy models and relationships for the database layer."""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .session import Base


class College(Base):
    __tablename__ = "colleges"

    id: Mapped[int] = mapped_column(primary_key=True)
    college_name: Mapped[str] = mapped_column(String(150), unique=True, index=True)
    college_location: Mapped[str] = mapped_column(String(150))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    admins: Mapped[list["Admin"]] = relationship(back_populates="college")
    events: Mapped[list["Event"]] = relationship(back_populates="college")


class Admin(Base):
    __tablename__ = "admins"

    id: Mapped[int] = mapped_column(primary_key=True)
    full_name: Mapped[str] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    college_id: Mapped[int] = mapped_column(ForeignKey("colleges.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    college: Mapped[College] = relationship(back_populates="admins")


class Student(Base):
    __tablename__ = "students"

    id: Mapped[int] = mapped_column(primary_key=True)
    full_name: Mapped[str] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    college_name: Mapped[str] = mapped_column(String(150))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    bookings: Mapped[list["Booking"]] = relationship(back_populates="student")


class Event(Base):
    __tablename__ = "events"
    __table_args__ = (
        Index("ix_events_college_date", "college_id", "event_date"),
        Index("ix_events_category", "category"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    college_id: Mapped[int] = mapped_column(ForeignKey("colleges.id"), index=True)
    event_name: Mapped[str] = mapped_column(String(150))
    description: Mapped[str] = mapped_column(Text, default="")
    event_date: Mapped[str] = mapped_column(String(10), index=True)
    event_time: Mapped[str] = mapped_column(String(30))
    duration: Mapped[str] = mapped_column(String(60), default="1 hour")
    venue: Mapped[str] = mapped_column(String(150))
    category: Mapped[str] = mapped_column(String(60))
    registration_fee: Mapped[float] = mapped_column(Float, default=0)
    maximum_seats: Mapped[int] = mapped_column(Integer)
    available_seats: Mapped[int] = mapped_column(Integer)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    college: Mapped[College] = relationship(back_populates="events")
    bookings: Mapped[list["Booking"]] = relationship(back_populates="event")


class Booking(Base):
    __tablename__ = "bookings"
    __table_args__ = (UniqueConstraint("student_id", "event_id", name="uq_student_event"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    booking_reference: Mapped[str] = mapped_column(String(30), unique=True, index=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), index=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id"), index=True)
    booking_status: Mapped[str] = mapped_column(String(20), default="confirmed")
    booked_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    reservation_expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    student: Mapped[Student] = relationship(back_populates="bookings")
    event: Mapped[Event] = relationship(back_populates="bookings")
    payments: Mapped[list["Payment"]] = relationship(back_populates="booking")


class Payment(Base):
    __tablename__ = "payments"
    __table_args__ = (UniqueConstraint("payment_reference", name="uq_payment_reference"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    booking_id: Mapped[int] = mapped_column(ForeignKey("bookings.id"), index=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), index=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id"), index=True)
    amount: Mapped[float] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String(3), default="INR")
    payment_reference: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    payment_method: Mapped[str] = mapped_column(String(40), default="Demo Payment")
    payment_status: Mapped[str] = mapped_column(String(20), default="Pending", index=True)
    transaction_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    booking: Mapped[Booking] = relationship(back_populates="payments")
    student: Mapped[Student] = relationship()
    event: Mapped[Event] = relationship()
