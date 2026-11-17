"""Repository operations for events."""

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database.models import Event


class EventRepository:
    def __init__(self, db: Session):
        self.db = db

    def add(self, event: Event) -> Event:
        self.db.add(event)
        return event

    def get_public(self, event_id: int) -> Event | None:
        return self.db.scalar(self.public_query().where(Event.id == event_id))

    def get_owned(self, event_id: int, college_id: int) -> Event | None:
        return self.db.scalar(
            select(Event).where(Event.id == event_id, Event.college_id == college_id, ~Event.is_deleted)
        )

    def public_query(self):
        return select(Event).where(~Event.is_deleted, Event.event_date >= date.today().isoformat())

    def list_public(
        self, search: str | None, category: str | None, event_date: str | None, college_id: int | None, offset: int, limit: int
    ) -> list[Event]:
        statement = self.public_query()
        if college_id is not None:
            statement = statement.where(Event.college_id == college_id)
        if search:
            statement = statement.where(Event.event_name.ilike(f"%{search.strip()}%"))
        if category:
            statement = statement.where(Event.category == category)
        if event_date:
            statement = statement.where(Event.event_date == event_date)
        return list(self.db.scalars(statement.order_by(Event.event_date, Event.event_time).offset(offset).limit(limit)))

    def list_owned(self, college_id: int) -> list[Event]:
        return list(self.db.scalars(select(Event).where(Event.college_id == college_id, ~Event.is_deleted).order_by(Event.event_date)))
