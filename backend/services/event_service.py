"""Event management and public event business rules."""

from sqlalchemy.orm import Session

from ..database.models import Admin, College, Event
from ..repositories.event_repository import EventRepository
from ..repositories.user_repository import UserRepository
from .exceptions import NotFoundError, ValidationError


class EventService:
    def __init__(self, db: Session):
        self.db = db
        self.events = EventRepository(db)
        self.users = UserRepository(db)

    def list_colleges(self, search: str | None, offset: int, limit: int) -> list[College]:
        return self.users.list_colleges(search, offset, limit)

    def list_public(self, search: str | None, category: str | None, event_date: str | None, college_id: int | None, offset: int, limit: int) -> list[Event]:
        if college_id is not None and self.users.get_college(college_id) is None:
            raise NotFoundError("College not found.")
        return self.events.list_public(search, category, event_date, college_id, offset, limit)

    def get_public(self, event_id: int) -> Event:
        event = self.events.get_public(event_id)
        if event is None:
            raise NotFoundError("Event not found.")
        return event

    def create(self, admin: Admin, values: dict) -> Event:
        event = Event(**values, college_id=admin.college_id, available_seats=values["maximum_seats"])
        self.events.add(event)
        self.db.commit()
        self.db.refresh(event)
        return event

    def list_owned(self, admin: Admin) -> list[Event]:
        return self.events.list_owned(admin.college_id)

    def get_owned(self, admin: Admin, event_id: int) -> Event:
        event = self.events.get_owned(event_id, admin.college_id)
        if event is None:
            raise NotFoundError("Event not found in your college.")
        return event

    def update(self, admin: Admin, event_id: int, values: dict) -> Event:
        event = self.get_owned(admin, event_id)
        booked = event.maximum_seats - event.available_seats
        if values["maximum_seats"] < booked:
            raise ValidationError("Maximum seats cannot be lower than existing bookings.")
        for key, value in values.items():
            setattr(event, key, value)
        event.available_seats = values["maximum_seats"] - booked
        self.db.commit()
        self.db.refresh(event)
        return event

    def delete(self, admin: Admin, event_id: int) -> None:
        event = self.get_owned(admin, event_id)
        event.is_deleted = True
        self.db.commit()
