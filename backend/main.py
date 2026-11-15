"""FastAPI REST API for the Campus Event Ticketing Engine."""

from datetime import date, datetime
from pathlib import Path
from typing import Annotated
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import inspect, select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from .auth import create_access_token, get_current_identity, hash_password, require_admin, require_participant, verify_password
from .database import Base, engine, get_db
from .models import Admin, Booking, College, Event, Student
from .schemas import AdminRegister, BookingResponse, CollegeResponse, Credentials, EventCreate, EventResponse, LoginCredentials, ParticipantProfile, StudentRegister

app = FastAPI(title="Campus Event Ticketing Engine", version="3.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:8000", "http://localhost:8000"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)
app.mount(
    "/frontend",
    StaticFiles(directory=Path(__file__).resolve().parent.parent / "frontend", html=True),
    name="frontend",
)


@app.on_event("startup")
def startup() -> None:
    Base.metadata.create_all(bind=engine)
    if "duration" not in {column["name"] for column in inspect(engine).get_columns("events")}:
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE events ADD COLUMN duration VARCHAR(60) NOT NULL DEFAULT '1 hour'"))


def event_response(event: Event) -> EventResponse:
    return EventResponse.model_validate(event)


def booking_response(booking: Booking, include_student: bool = False) -> dict:
    result = {
        "id": booking.id,
        "booking_reference": booking.booking_reference,
        "booking_status": booking.booking_status,
        "booked_at": booking.booked_at.isoformat(),
        "event": event_response(booking.event),
        "college": CollegeResponse.model_validate(booking.event.college),
    }
    if include_student:
        result["student_name"] = booking.student.full_name
        result["student_email"] = booking.student.email
    return result


def owned_event_or_404(event_id: int, admin: Admin, db: Session) -> Event:
    event = db.scalar(select(Event).where(Event.id == event_id, Event.college_id == admin.college_id, ~Event.is_deleted))
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found in your college.")
    return event


def public_event_query() -> object:
    return select(Event).where(~Event.is_deleted, Event.event_date >= date.today().isoformat())


@app.get("/", include_in_schema=False)
def home() -> RedirectResponse:
    return RedirectResponse(url="/frontend/index.html")


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/admin/register", status_code=201)
def register_admin(payload: AdminRegister, db: Annotated[Session, Depends(get_db)]) -> dict:
    email = str(payload.email).lower()
    if db.scalar(select(Admin).where(Admin.email == email)):
        raise HTTPException(status_code=409, detail="An admin with this email already exists.")
    college = db.scalar(select(College).where(College.college_name.ilike(payload.college.college_name)))
    if college is None:
        college = College(**payload.college.model_dump())
        db.add(college)
        db.flush()
    admin = Admin(full_name=payload.full_name.strip(), email=email, password_hash=hash_password(payload.password), college_id=college.id)
    db.add(admin)
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(status_code=409, detail="Admin email or college already exists.") from error
    db.refresh(admin)
    return {"message": "Admin registration successful.", "admin_id": admin.id}


@app.post("/api/admin/login")
def login_admin(payload: LoginCredentials, db: Annotated[Session, Depends(get_db)]) -> dict:
    admin = db.scalar(select(Admin).where(Admin.email == str(payload.email).lower()))
    if admin is None or not verify_password(payload.password, admin.password_hash):
        raise HTTPException(status_code=401, detail="Invalid admin email or password.")
    return {"access_token": create_access_token(admin.id, "admin"), "token_type": "bearer", "role": "admin"}


@app.post("/api/participant/register", status_code=201)
def register_participant(payload: StudentRegister, db: Annotated[Session, Depends(get_db)]) -> dict:
    email = str(payload.email).lower()
    if db.scalar(select(Student).where(Student.email == email)):
        raise HTTPException(status_code=409, detail="A participant with this email already exists.")
    student = Student(full_name=payload.full_name.strip(), email=email, password_hash=hash_password(payload.password), college_name=payload.college_name.strip())
    db.add(student)
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(status_code=409, detail="Participant email already exists.") from error
    db.refresh(student)
    return {"message": "Participant registration successful.", "participant_id": student.id}


@app.post("/api/participant/login")
def login_participant(payload: LoginCredentials, db: Annotated[Session, Depends(get_db)]) -> dict:
    student = db.scalar(select(Student).where(Student.email == str(payload.email).lower()))
    if student is None or not verify_password(payload.password, student.password_hash):
        raise HTTPException(status_code=401, detail="Invalid participant email or password.")
    return {"access_token": create_access_token(student.id, "participant"), "token_type": "bearer", "role": "participant"}


@app.get("/api/admin/profile")
def admin_profile(admin: Annotated[Admin, Depends(require_admin)], db: Annotated[Session, Depends(get_db)]) -> dict:
    college = db.get(College, admin.college_id)
    return {"id": admin.id, "full_name": admin.full_name, "email": admin.email, "college": CollegeResponse.model_validate(college)}


@app.get("/api/participant/profile", response_model=ParticipantProfile)
def participant_profile(student: Annotated[Student, Depends(require_participant)]) -> Student:
    return student


@app.get("/api/auth/me")
def current_user(identity: Annotated[tuple[Admin | Student, str], Depends(get_current_identity)]) -> dict:
    user, role = identity
    if role == "admin":
        admin = user  # type: ignore[assignment]
        return {"role": role, "id": admin.id, "full_name": admin.full_name}
    student = user  # type: ignore[assignment]
    return {"role": role, "id": student.id, "full_name": student.full_name}


@app.get("/api/colleges", response_model=list[CollegeResponse])
def list_colleges(
    db: Annotated[Session, Depends(get_db)],
    search: str | None = Query(default=None, max_length=100),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
) -> list[College]:
    statement = select(College).order_by(College.college_name).offset(offset).limit(limit)
    if search:
        statement = statement.where(College.college_name.ilike(f"%{search.strip()}%"))
    return list(db.scalars(statement))


@app.get("/api/events", response_model=list[EventResponse])
def list_events(
    db: Annotated[Session, Depends(get_db)],
    search: str | None = Query(default=None, max_length=100),
    category: str | None = Query(default=None, max_length=60),
    event_date: str | None = Query(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$"),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
) -> list[Event]:
    statement = public_event_query()
    if search:
        statement = statement.where(Event.event_name.ilike(f"%{search.strip()}%"))
    if category:
        statement = statement.where(Event.category == category)
    if event_date:
        statement = statement.where(Event.event_date == event_date)
    return list(db.scalars(statement.order_by(Event.event_date, Event.event_time).offset(offset).limit(limit)))


@app.get("/api/colleges/{college_id}/events", response_model=list[EventResponse])
def college_events(
    college_id: int,
    db: Annotated[Session, Depends(get_db)],
    search: str | None = Query(default=None, max_length=100),
    category: str | None = Query(default=None, max_length=60),
    event_date: str | None = Query(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$"),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
) -> list[Event]:
    if db.get(College, college_id) is None:
        raise HTTPException(status_code=404, detail="College not found.")
    statement = public_event_query().where(Event.college_id == college_id)
    if search:
        statement = statement.where(Event.event_name.ilike(f"%{search.strip()}%"))
    if category:
        statement = statement.where(Event.category == category)
    if event_date:
        statement = statement.where(Event.event_date == event_date)
    return list(db.scalars(statement.order_by(Event.event_date, Event.event_time).offset(offset).limit(limit)))


@app.get("/api/events/{event_id}", response_model=EventResponse)
def get_event(event_id: int, db: Annotated[Session, Depends(get_db)]) -> Event:
    event = db.scalar(public_event_query().where(Event.id == event_id))
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found.")
    return event


@app.post("/api/admin/events", response_model=EventResponse, status_code=201)
def create_event(payload: EventCreate, admin: Annotated[Admin, Depends(require_admin)], db: Annotated[Session, Depends(get_db)]) -> Event:
    event = Event(**payload.model_dump(), college_id=admin.college_id, available_seats=payload.maximum_seats)
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


@app.get("/api/admin/events", response_model=list[EventResponse])
def admin_events(admin: Annotated[Admin, Depends(require_admin)], db: Annotated[Session, Depends(get_db)]) -> list[Event]:
    return list(db.scalars(select(Event).where(Event.college_id == admin.college_id, ~Event.is_deleted).order_by(Event.event_date)))


@app.get("/api/admin/events/{event_id}", response_model=EventResponse)
def admin_event(event_id: int, admin: Annotated[Admin, Depends(require_admin)], db: Annotated[Session, Depends(get_db)]) -> Event:
    return owned_event_or_404(event_id, admin, db)


@app.put("/api/admin/events/{event_id}", response_model=EventResponse)
def update_event(event_id: int, payload: EventCreate, admin: Annotated[Admin, Depends(require_admin)], db: Annotated[Session, Depends(get_db)]) -> Event:
    event = owned_event_or_404(event_id, admin, db)
    booked = event.maximum_seats - event.available_seats
    if payload.maximum_seats < booked:
        raise HTTPException(status_code=400, detail="Maximum seats cannot be lower than existing bookings.")
    for key, value in payload.model_dump().items():
        setattr(event, key, value)
    event.available_seats = payload.maximum_seats - booked
    db.commit()
    db.refresh(event)
    return event


@app.delete("/api/admin/events/{event_id}", status_code=204)
def delete_event(event_id: int, admin: Annotated[Admin, Depends(require_admin)], db: Annotated[Session, Depends(get_db)]) -> None:
    event = owned_event_or_404(event_id, admin, db)
    event.is_deleted = True
    db.commit()


@app.get("/api/admin/events/{event_id}/participants")
def event_participants(
    event_id: int,
    admin: Annotated[Admin, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
) -> dict:
    event = owned_event_or_404(event_id, admin, db)
    bookings = db.scalars(
        select(Booking).options(joinedload(Booking.student), joinedload(Booking.event).joinedload(Event.college))
        .where(Booking.event_id == event.id).order_by(Booking.booked_at.desc()).offset(offset).limit(limit)
    )
    return {
        "event": event_response(event),
        "total_bookings": event.maximum_seats - event.available_seats,
        "available_seats": event.available_seats,
        "participants": [booking_response(item, True) for item in bookings],
    }


@app.post("/api/events/{event_id}/book", response_model=BookingResponse, status_code=201)
def book_event(event_id: int, student: Annotated[Student, Depends(require_participant)], db: Annotated[Session, Depends(get_db)]) -> dict:
    event = db.scalar(public_event_query().where(Event.id == event_id))
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found or registration is closed.")
    if db.scalar(select(Booking).where(Booking.student_id == student.id, Booking.event_id == event_id)):
        raise HTTPException(status_code=409, detail="You have already booked this event.")
    reserved = db.execute(
        update(Event).where(Event.id == event_id, ~Event.is_deleted, Event.available_seats > 0).values(available_seats=Event.available_seats - 1)
    )
    if reserved.rowcount != 1:
        db.rollback()
        raise HTTPException(status_code=409, detail="This event has no available seats.")
    booking = Booking(booking_reference=f"CE-{uuid4().hex[:12].upper()}", student_id=student.id, event_id=event_id)
    db.add(booking)
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(status_code=409, detail="You have already booked this event.") from error
    db.refresh(booking)
    booking = db.scalar(select(Booking).options(joinedload(Booking.event).joinedload(Event.college)).where(Booking.id == booking.id))
    return booking_response(booking)


@app.get("/api/participant/bookings", response_model=list[BookingResponse])
def participant_bookings(student: Annotated[Student, Depends(require_participant)], db: Annotated[Session, Depends(get_db)]) -> list[dict]:
    bookings = db.scalars(
        select(Booking).options(joinedload(Booking.event).joinedload(Event.college))
        .where(Booking.student_id == student.id).order_by(Booking.booked_at.desc())
    )
    return [booking_response(item) for item in bookings]
